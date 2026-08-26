import Combine
import Foundation

enum VoiceUIState: Equatable {
    case ready
    case connecting
    case listening
    case sending
    case speaking
    case failed(String)
}

struct ChatMessage: Identifiable, Equatable {
    enum Role: Equatable {
        case user
        case assistant
    }

    let id: UUID
    let role: Role
    var text: String

    init(id: UUID = UUID(), role: Role, text: String) {
        self.id = id
        self.role = role
        self.text = text
    }
}

@MainActor
final class VoiceConversationViewModel: ObservableObject {
    @Published private(set) var state: VoiceUIState = .ready
    @Published private(set) var messages: [ChatMessage] = []
    @Published private(set) var inputLevel: Float = 0

    private let audio = RealtimeAudioController()
    private let backend = RealtimeBackendClient()
    private var audioContinuation: AsyncStream<Data>.Continuation?
    private var audioUploadTask: Task<Void, Error>?
    private var assistantMessageID: UUID?
    private var responsePlaybackPrepared = false
    private var acceptingAssistantOutput = false
    private var actionID = 0

    init() {
        audio.didFinishPlayback = { [weak self] in
            Task { @MainActor in
                guard self?.state == .speaking else { return }
                self?.state = .ready
            }
        }
        audio.onInputLevel = { [weak self] level in
            Task { @MainActor in
                self?.inputLevel = level
            }
        }
    }

    var isBusy: Bool {
        state == .connecting || state == .sending || state == .speaking
    }

    /// Changes as the latest bubble grows so the chat can stay pinned to the end.
    var latestScrollToken: String {
        "\(messages.count):\(messages.last?.text.count ?? 0)"
    }

    var buttonAccessibilityLabel: String {
        switch state {
        case .listening:
            return "Stop recording and send"
        case .ready, .failed:
            return "Start speaking"
        case .connecting:
            return "Connecting"
        case .sending, .speaking:
            return "Stop speaking and start a new message"
        }
    }

    func buttonTapped() {
        switch state {
        case .ready, .failed:
            actionID += 1
            state = .connecting
            Task { await startRecording() }
        case .listening:
            actionID += 1
            state = .sending
            Task { await stopAndSend() }
        case .sending, .speaking:
            actionID += 1
            acceptingAssistantOutput = false
            assistantMessageID = nil
            responsePlaybackPrepared = false
            state = .connecting
            Task { await interruptAndRecord() }
        case .connecting:
            break
        }
    }

    private func startRecording() async {
        let action = actionID
        state = .connecting
        inputLevel = 0
        do {
            let (stream, streamContinuation) = AsyncStream<Data>.makeStream(
                // Preserve the complete utterance. Dropping packets while the
                // Watch network is briefly slow can fall below Realtime's
                // minimum committed audio duration.
                bufferingPolicy: .unbounded
            )
            audioContinuation = streamContinuation
            try await audio.startStreaming { chunk in
                streamContinuation.yield(chunk)
            }
            guard action == actionID else {
                audio.stopRecording()
                return
            }

            try await backend.connect { [weak self] event in
                Task { @MainActor in
                    self?.handle(event)
                }
            }
            guard action == actionID else {
                audio.stopRecording()
                return
            }
            do {
                try await backend.startTurn()
            } catch {
                guard isNotConnected(error) else { throw error }
                try await backend.connect(
                    eventHandler: { [weak self] event in
                        Task { @MainActor in
                            self?.handle(event)
                        }
                    },
                    forceReconnect: true
                )
                try await backend.startTurn()
            }
            guard action == actionID else {
                audio.stopRecording()
                return
            }

            audioUploadTask = Task { [backend] in
                for await chunk in stream {
                    try Task.checkCancellation()
                    try await backend.sendAudio(chunk)
                }
            }
            state = .listening
        } catch {
            guard action == actionID else { return }
            finishAudioUpload()
            audio.stopAll()
            inputLevel = 0
            recover(from: error)
        }
    }

    private func stopAndSend() async {
        let action = actionID
        audioContinuation?.finish()
        audioContinuation = nil
        state = .sending
        inputLevel = 0

        do {
            if let audioUploadTask {
                try await audioUploadTask.value
            }
            guard action == actionID else { return }
            self.audioUploadTask = nil
            assistantMessageID = nil
            responsePlaybackPrepared = false
            acceptingAssistantOutput = true
            messages.append(ChatMessage(role: .user, text: "Voice message"))
            try await audio.prepareForResponsePlayback()
            guard action == actionID else { return }
            responsePlaybackPrepared = true
            try await backend.commitTurn()
        } catch {
            guard action == actionID else { return }
            finishAudioUpload()
            audio.stopAll()
            recover(from: error)
        }
    }

    private func interruptAndRecord() async {
        let action = actionID
        acceptingAssistantOutput = false
        assistantMessageID = nil
        responsePlaybackPrepared = false
        audio.interruptPlayback()
        do {
            try await backend.cancelTurn()
        } catch {
            print("Kuma Voice cancel skipped: \(error.localizedDescription)")
        }
        guard action == actionID else { return }
        await startRecording()
    }

    private func handle(_ event: RealtimeBackendEvent) {
        switch event {
        case .ready:
            break
        case .responseStarted:
            guard acceptingAssistantOutput else { return }
            beginAssistantMessage()
            state = .speaking
        case let .audio(data):
            guard acceptingAssistantOutput else { return }
            do {
                prepareResponsePlaybackIfNeeded()
                try audio.enqueuePlayback(data)
                state = .speaking
            } catch {
                audio.stopAll()
                recover(from: error)
            }
        case let .transcriptDelta(text):
            guard acceptingAssistantOutput else { return }
            appendAssistantTranscript(text)
        case .responseDone:
            guard acceptingAssistantOutput else { return }
            prepareResponsePlaybackIfNeeded()
            audio.markResponseComplete()
        case .responseCancelled:
            break
        case let .error(message):
            if isBenignCancel(message) {
                return
            }
            if state == .connecting || state == .listening,
               !isTransientConnectionLoss(message) {
                print("Kuma Voice session error: \(message)")
                return
            }
            finishAudioUpload()
            audio.stopAll()
            inputLevel = 0
            if isTransientConnectionLoss(message) {
                state = .ready
            } else {
                // Keep failures silent in the chrome; log for debugging.
                print("Kuma Voice session error: \(message)")
                state = .ready
            }
        }
    }

    private func beginAssistantMessage() {
        if assistantMessageID == nil {
            let message = ChatMessage(role: .assistant, text: "")
            assistantMessageID = message.id
            messages.append(message)
        }
    }

    private func appendAssistantTranscript(_ text: String) {
        beginAssistantMessage()
        guard let assistantMessageID,
              let index = messages.firstIndex(where: { $0.id == assistantMessageID })
        else {
            return
        }
        messages[index].text += text
    }

    private func finishAudioUpload() {
        audioContinuation?.finish()
        audioContinuation = nil
        audioUploadTask?.cancel()
        audioUploadTask = nil
    }

    private func prepareResponsePlaybackIfNeeded() {
        guard !responsePlaybackPrepared else {
            return
        }
        audio.stopRecording()
        audio.beginResponse()
        responsePlaybackPrepared = true
    }

    private func recover(from error: Error) {
        let nsError = error as NSError
        print(
            "Kuma Voice error domain=\(nsError.domain) "
                + "code=\(nsError.code): \(nsError.localizedDescription)"
        )
        state = .ready
    }

    private func isTransientConnectionLoss(_ message: String) -> Bool {
        let lowered = message.lowercased()
        return lowered.contains("connection was lost")
            || lowered.contains("not connected")
            || lowered.contains("realtime connection")
    }

    private func isBenignCancel(_ message: String) -> Bool {
        let lowered = message.lowercased()
        return lowered.contains("cancelled")
            || lowered.contains("canceled")
            || lowered.contains("cancellation failed")
    }

    private func isNotConnected(_ error: Error) -> Bool {
        if let backendError = error as? RealtimeBackendError {
            if case .notConnected = backendError {
                return true
            }
        }
        return (error as NSError).domain == "Kuma_Voice.RealtimeBackendError"
            && (error as NSError).code == 1
    }

    func resetConversation() {
        actionID += 1
        acceptingAssistantOutput = false
        assistantMessageID = nil
        responsePlaybackPrepared = false
        finishAudioUpload()
        audio.stopAll()
        inputLevel = 0
        messages = []
        state = .ready
        Task { await backend.close() }
    }
}
