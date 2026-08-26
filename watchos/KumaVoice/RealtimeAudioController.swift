import AVFoundation
import Foundation

enum RealtimeAudioError: LocalizedError {
    case permissionDenied
    case invalidAudioFormat
    case couldNotStart
    case simulatorUnavailable

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Microphone permission is required."
        case .invalidAudioFormat:
            return "The Watch could not prepare realtime audio."
        case .couldNotStart:
            return "The Watch could not start realtime audio."
        case .simulatorUnavailable:
            return "Realtime audio needs a physical Apple Watch."
        }
    }
}

final class RealtimeAudioController {
    static let sampleRate: Double = 24_000

    var didFinishPlayback: (() -> Void)?
    /// 0...1 approximate input loudness while recording.
    var onInputLevel: ((Float) -> Void)?

    private let recordingEngine = AVAudioEngine()
    private let playbackEngine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private let wireFormat: AVAudioFormat
    private let playbackFormat: AVAudioFormat
    private var inputConverter: AVAudioConverter?
    private var isRecording = false
    private var pendingPlaybackBuffers = 0
    private var responseIsComplete = false
    private var playbackGeneration = 0

    init() {
        wireFormat = AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: Self.sampleRate,
            channels: 1,
            interleaved: false
        )!
        // Mixer nodes use floating-point PCM. Keep the OpenAI wire format
        // separate so A2DP/HFP hardware changes do not make the graph invalid.
        playbackFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: Self.sampleRate,
            channels: 1,
            interleaved: false
        )!
        playbackEngine.attach(player)
        playbackEngine.connect(
            player,
            to: playbackEngine.mainMixerNode,
            format: playbackFormat
        )
        playbackEngine.mainMixerNode.outputVolume = 1
        player.volume = 1
    }

    func startStreaming(
        onChunk: @escaping @Sendable (Data) -> Void
    ) async throws {
        #if targetEnvironment(simulator)
        throw RealtimeAudioError.simulatorUnavailable
        #endif

        guard await requestPermission() else {
            throw RealtimeAudioError.permissionDenied
        }

        // Release the I/O unit from playback before claiming it for the mic.
        // Switching to .playback / longFormAudio after the first turn caused
        // SessionCore '!res' (resource not available) on the next record.
        let playbackWasRunning = playbackEngine.isRunning
        stopRecording()
        interruptPlayback()
        if playbackWasRunning {
            try await Task.sleep(for: .milliseconds(40))
        }

        try await activateVoiceSession()

        let session = AVAudioSession.sharedInstance()
        logCurrentOutput(for: session)

        let input = recordingEngine.inputNode
        let inputFormat = input.outputFormat(forBus: 0)
        guard inputFormat.sampleRate > 0, inputFormat.channelCount > 0 else {
            throw RealtimeAudioError.invalidAudioFormat
        }

        inputConverter = nil
        input.installTap(
            onBus: 0,
            bufferSize: 1_024,
            // Let AVAudioEngine choose the active route's native format. Giving
            // it the pre-route-change format can raise an Objective-C exception.
            format: nil
        ) { [weak self] buffer, _ in
            guard let self else { return }
            if let level = self.inputLevel(from: buffer) {
                DispatchQueue.main.async {
                    self.onInputLevel?(level)
                }
            }
            guard let data = self.convertToPCM16(buffer), !data.isEmpty else {
                return
            }
            onChunk(data)
        }

        recordingEngine.prepare()
        do {
            if !recordingEngine.isRunning {
                try recordingEngine.start()
            }
        } catch {
            input.removeTap(onBus: 0)
            inputConverter = nil
            recordingEngine.stop()
            recordingEngine.reset()
            throw RealtimeAudioError.couldNotStart
        }
        isRecording = true
    }

    func stopRecording() {
        guard isRecording else {
            return
        }
        recordingEngine.inputNode.removeTap(onBus: 0)
        inputConverter = nil
        isRecording = false
        recordingEngine.stop()
        recordingEngine.reset()
        DispatchQueue.main.async { [weak self] in
            self?.onInputLevel?(0)
        }
    }

    func prepareForResponsePlayback() async throws {
        #if targetEnvironment(simulator)
        beginResponse()
        return
        #endif

        stopRecording()
        beginResponse()
        try await activateVoiceSession()
        logCurrentOutput(for: AVAudioSession.sharedInstance())
    }

    func beginResponse() {
        playbackGeneration += 1
        player.stop()
        pendingPlaybackBuffers = 0
        responseIsComplete = false
    }

    func interruptPlayback() {
        playbackGeneration += 1
        pendingPlaybackBuffers = 0
        responseIsComplete = false
        stopPlaybackEngine()
    }

    func enqueuePlayback(_ data: Data) throws {
        #if targetEnvironment(simulator)
        return
        #endif

        guard !data.isEmpty, data.count.isMultiple(of: 2) else {
            throw RealtimeAudioError.invalidAudioFormat
        }

        if !playbackEngine.isRunning {
            playbackEngine.mainMixerNode.outputVolume = 1
            player.volume = 1
            playbackEngine.prepare()
            try playbackEngine.start()
        }

        let frameCount = AVAudioFrameCount(data.count / MemoryLayout<Int16>.size)
        guard
            let buffer = AVAudioPCMBuffer(
                pcmFormat: playbackFormat,
                frameCapacity: frameCount
            ),
            let samples = buffer.floatChannelData?.pointee
        else {
            throw RealtimeAudioError.invalidAudioFormat
        }

        buffer.frameLength = frameCount
        data.withUnsafeBytes { bytes in
            let source = bytes.bindMemory(to: Int16.self)
            for index in 0..<min(source.count, Int(frameCount)) {
                samples[index] = Float(source[index]) / 32_768
            }
        }

        let generation = playbackGeneration
        pendingPlaybackBuffers += 1
        player.scheduleBuffer(
            buffer,
            completionCallbackType: .dataPlayedBack
        ) { [weak self] _ in
            DispatchQueue.main.async {
                self?.playbackBufferFinished(generation: generation)
            }
        }
        if !player.isPlaying {
            player.play()
        }
    }

    func markResponseComplete() {
        responseIsComplete = true
        finishPlaybackIfPossible()
    }

    func stopAll() {
        stopRecording()
        recordingEngine.stop()
        interruptPlayback()
        DispatchQueue.main.async { [weak self] in
            self?.onInputLevel?(0)
        }
    }

    private func inputLevel(from buffer: AVAudioPCMBuffer) -> Float? {
        let frameLength = Int(buffer.frameLength)
        guard frameLength > 0 else { return 0 }

        var sum: Float = 0
        if let channel = buffer.floatChannelData?.pointee {
            for index in 0..<frameLength {
                let sample = channel[index]
                sum += sample * sample
            }
        } else if let channel = buffer.int16ChannelData?.pointee {
            for index in 0..<frameLength {
                let sample = Float(channel[index]) / 32_768
                sum += sample * sample
            }
        } else {
            return nil
        }

        let rms = sqrt(sum / Float(frameLength))
        // Soft knee so quiet speech still moves the bars a little.
        return min(1, pow(rms * 3.2, 0.65))
    }

    private func convertToPCM16(_ input: AVAudioPCMBuffer) -> Data? {
        if inputConverter == nil
            || inputConverter?.inputFormat.isEqual(input.format) == false {
            inputConverter = AVAudioConverter(
                from: input.format,
                to: wireFormat
            )
        }

        guard let converter = inputConverter else {
            return nil
        }

        let ratio = wireFormat.sampleRate / input.format.sampleRate
        let capacity = AVAudioFrameCount(ceil(Double(input.frameLength) * ratio)) + 1
        guard let output = AVAudioPCMBuffer(
            pcmFormat: wireFormat,
            frameCapacity: capacity
        ) else {
            return nil
        }

        var suppliedInput = false
        var conversionError: NSError?
        let status = converter.convert(to: output, error: &conversionError) {
            _, inputStatus in
            if suppliedInput {
                inputStatus.pointee = .noDataNow
                return nil
            }
            suppliedInput = true
            inputStatus.pointee = .haveData
            return input
        }

        guard
            status != .error,
            conversionError == nil,
            output.frameLength > 0,
            let samples = output.int16ChannelData?.pointee
        else {
            return nil
        }

        return Data(
            bytes: samples,
            count: Int(output.frameLength) * MemoryLayout<Int16>.size
        )
    }

    private func playbackBufferFinished(generation: Int) {
        guard generation == playbackGeneration else {
            return
        }
        pendingPlaybackBuffers = max(0, pendingPlaybackBuffers - 1)
        finishPlaybackIfPossible()
    }

    private func finishPlaybackIfPossible() {
        guard responseIsComplete, pendingPlaybackBuffers == 0 else {
            return
        }
        responseIsComplete = false
        stopPlaybackEngine()
        didFinishPlayback?()
    }

    private func activateVoiceSession() async throws {
        let session = AVAudioSession.sharedInstance()
        // Keep playAndRecord so the next tap can reuse the mic.
        // voiceChat routes through the call path (HFP): quiet speaker and
        // crackly AirPods. spokenAudio uses the media path and A2DP.
        try session.setCategory(
            .playAndRecord,
            mode: .spokenAudio,
            options: [.allowBluetoothA2DP]
        )
        try await session.activate()
    }

    private func stopPlaybackEngine() {
        player.stop()
        if playbackEngine.isRunning {
            playbackEngine.stop()
        }
        playbackEngine.reset()
        if player.engine == nil {
            playbackEngine.attach(player)
        }
        playbackEngine.connect(
            player,
            to: playbackEngine.mainMixerNode,
            format: playbackFormat
        )
        playbackEngine.mainMixerNode.outputVolume = 1
        player.volume = 1
    }

    private func requestPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioApplication.requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    private func logCurrentOutput(for session: AVAudioSession) {
        let route = session.currentRoute.outputs
            .map { "\($0.portName) [\($0.portType.rawValue)]" }
            .joined(separator: ", ")
        print("Kuma Voice audio output: \(route)")
    }
}
