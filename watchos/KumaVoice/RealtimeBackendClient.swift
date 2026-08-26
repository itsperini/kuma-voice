import Foundation

enum RealtimeBackendEvent {
    case ready
    case responseStarted
    case audio(Data)
    case transcriptDelta(String)
    case responseDone
    case responseCancelled
    case error(String)
}

enum RealtimeBackendError: LocalizedError {
    case notConnected
    case invalidMessage
    case server(String)

    var errorDescription: String? {
        switch self {
        case .notConnected:
            return "Kuma Voice is not connected to the server."
        case .invalidMessage:
            return "Kuma Voice received an invalid realtime message."
        case let .server(message):
            return message
        }
    }
}

private struct RealtimeMessage: Decodable {
    let type: String
    let audio: String?
    let text: String?
    let message: String?
}

actor RealtimeBackendClient {
    typealias EventHandler = @Sendable (RealtimeBackendEvent) -> Void

    private let url: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    private var socket: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var eventHandler: EventHandler?

    init(
        url: URL = AppConfiguration.realtimeWebSocketURL,
        session: URLSession = .shared
    ) {
        self.url = url
        self.session = session
    }

    func connect(
        eventHandler: @escaping EventHandler,
        forceReconnect: Bool = false
    ) async throws {
        self.eventHandler = eventHandler
        if !forceReconnect, isConnectionLive {
            return
        }

        dropConnection()

        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        request.networkServiceType = .avStreaming
        AppConfiguration.authorize(&request)
        let socket = session.webSocketTask(with: request)
        self.socket = socket
        socket.resume()

        do {
            let firstMessage = try await socket.receive()
            let event = try decode(firstMessage)
            if event.type == "error" {
                throw RealtimeBackendError.server(
                    event.message ?? "The realtime server rejected the connection."
                )
            }
            guard event.type == "ready" else {
                throw RealtimeBackendError.invalidMessage
            }

            eventHandler(.ready)
            receiveTask = Task { [weak self] in
                await self?.receiveMessages(from: socket)
            }
        } catch {
            socket.cancel(with: .goingAway, reason: nil)
            self.socket = nil
            throw error
        }
    }

    func startTurn() async throws {
        try await send(["type": "start"])
    }

    func sendAudio(_ data: Data) async throws {
        try await send(
            [
                "type": "audio",
                "audio": data.base64EncodedString(),
            ]
        )
    }

    func commitTurn() async throws {
        try await send(["type": "commit"])
    }

    func cancelTurn() async throws {
        try await send(["type": "cancel"])
    }

    func close() async {
        if socket != nil {
            try? await send(["type": "close"])
        }
        dropConnection()
    }

    private var isConnectionLive: Bool {
        guard let socket, receiveTask != nil else {
            return false
        }
        switch socket.state {
        case .running:
            return true
        default:
            return false
        }
    }

    private func dropConnection() {
        let socket = self.socket
        receiveTask?.cancel()
        receiveTask = nil
        self.socket = nil
        socket?.cancel(with: .goingAway, reason: nil)
    }

    private func send(_ object: [String: String]) async throws {
        guard let socket else {
            throw RealtimeBackendError.notConnected
        }
        let data = try JSONSerialization.data(withJSONObject: object)
        guard let text = String(data: data, encoding: .utf8) else {
            throw RealtimeBackendError.invalidMessage
        }
        try await socket.send(.string(text))
    }

    private func receiveMessages(from socket: URLSessionWebSocketTask) async {
        do {
            while !Task.isCancelled {
                let message = try await socket.receive()
                let event = try decode(message)
                switch event.type {
                case "response_started":
                    eventHandler?(.responseStarted)
                case "audio_delta":
                    guard
                        let encoded = event.audio,
                        let audio = Data(base64Encoded: encoded)
                    else {
                        throw RealtimeBackendError.invalidMessage
                    }
                    eventHandler?(.audio(audio))
                case "transcript_delta":
                    eventHandler?(.transcriptDelta(event.text ?? ""))
                case "response_done":
                    eventHandler?(.responseDone)
                case "response_cancelled":
                    eventHandler?(.responseCancelled)
                case "error":
                    let message = event.message ?? "The realtime voice session failed."
                    if Self.isBenignCancel(message) {
                        eventHandler?(.responseCancelled)
                        continue
                    }
                    // Keep the socket open. Cancelling a spoken reply used to
                    // arrive as an error and tear down the session, so the
                    // next startTurn failed with notConnected.
                    eventHandler?(.error(message))
                case "pong", "ready":
                    break
                default:
                    break
                }
            }
        } catch is CancellationError {
            return
        } catch {
            guard self.socket === socket else {
                return
            }
            self.socket = nil
            receiveTask = nil
            eventHandler?(.error("The realtime connection was lost."))
        }
    }

    private func decode(_ message: URLSessionWebSocketTask.Message) throws -> RealtimeMessage {
        let data: Data
        switch message {
        case let .string(text):
            guard let stringData = text.data(using: .utf8) else {
                throw RealtimeBackendError.invalidMessage
            }
            data = stringData
        case let .data(binary):
            data = binary
        @unknown default:
            throw RealtimeBackendError.invalidMessage
        }
        return try decoder.decode(RealtimeMessage.self, from: data)
    }

    private static func isBenignCancel(_ message: String) -> Bool {
        let lowered = message.lowercased()
        return lowered.contains("cancelled")
            || lowered.contains("canceled")
            || lowered.contains("cancellation failed")
    }
}
