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

private struct DirectRealtimeSession: Decodable {
    let url: URL
    let clientSecret: String

    enum CodingKeys: String, CodingKey {
        case url
        case clientSecret = "client_secret"
    }
}

private struct RealtimeToolResponse: Decodable {
    let output: String
}

private enum RealtimeConnectionMode {
    case proxy
    case direct
}

actor RealtimeBackendClient {
    typealias EventHandler = @Sendable (RealtimeBackendEvent) -> Void

    private let proxyURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    private var socket: URLSessionWebSocketTask?
    private var receiveTask: Task<Void, Never>?
    private var eventHandler: EventHandler?
    private var mode: RealtimeConnectionMode?
    private var spokenStarted = false
    private var audioByteCount = 0

    init(
        url: URL = AppConfiguration.realtimeWebSocketURL,
        session: URLSession = .shared
    ) {
        proxyURL = url
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

        if let directSession = try? await requestDirectSession() {
            do {
                try await openDirectConnection(directSession)
                eventHandler(.ready)
                return
            } catch {
                dropConnection()
            }
        }

        try await openProxyConnection()
        eventHandler(.ready)
    }

    func startTurn() async throws {
        audioByteCount = 0
        switch mode {
        case .direct:
            try await send(["type": "input_audio_buffer.clear"])
        case .proxy:
            try await send(["type": "start"])
        case nil:
            throw RealtimeBackendError.notConnected
        }
    }

    func sendAudio(_ data: Data) async throws {
        audioByteCount += data.count
        guard audioByteCount <= 10 * 1024 * 1024 else {
            throw RealtimeBackendError.server("The realtime audio turn is too large.")
        }

        let audio = data.base64EncodedString()
        switch mode {
        case .direct:
            try await send([
                "type": "input_audio_buffer.append",
                "audio": audio,
            ])
        case .proxy:
            try await send([
                "type": "audio",
                "audio": audio,
            ])
        case nil:
            throw RealtimeBackendError.notConnected
        }
    }

    func commitTurn() async throws {
        guard audioByteCount >= 4_800 else {
            throw RealtimeBackendError.server(
                "Please speak for at least a tenth of a second."
            )
        }
        audioByteCount = 0

        switch mode {
        case .direct:
            try await send(["type": "input_audio_buffer.commit"])
            try await send(["type": "response.create"])
        case .proxy:
            try await send(["type": "commit"])
        case nil:
            throw RealtimeBackendError.notConnected
        }
    }

    func cancelTurn() async throws {
        audioByteCount = 0
        switch mode {
        case .direct:
            try await send(["type": "response.cancel"])
            try await send(["type": "input_audio_buffer.clear"])
        case .proxy:
            try await send(["type": "cancel"])
        case nil:
            throw RealtimeBackendError.notConnected
        }
    }

    func close() async {
        if mode == .proxy, socket != nil {
            try? await send(["type": "close"])
        }
        dropConnection()
    }

    private func requestDirectSession() async throws -> DirectRealtimeSession {
        var request = URLRequest(url: AppConfiguration.directRealtimeSessionURL)
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        AppConfiguration.authorize(&request)

        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse,
              response.statusCode == 200
        else {
            throw RealtimeBackendError.server(
                "Direct realtime is unavailable on this server."
            )
        }
        return try decoder.decode(DirectRealtimeSession.self, from: data)
    }

    private func openDirectConnection(_ directSession: DirectRealtimeSession) async throws {
        var request = URLRequest(url: directSession.url)
        request.timeoutInterval = 20
        request.networkServiceType = .avStreaming
        request.setValue(
            "Bearer \(directSession.clientSecret)",
            forHTTPHeaderField: "Authorization"
        )

        let socket = session.webSocketTask(with: request)
        self.socket = socket
        mode = .direct
        socket.resume()

        do {
            let event = try decodeObject(try await socket.receive())
            if event["type"] as? String == "error" {
                throw RealtimeBackendError.server(
                    errorMessage(from: event)
                        ?? "OpenAI rejected the realtime connection."
                )
            }
            guard event["type"] as? String == "session.created" else {
                throw RealtimeBackendError.invalidMessage
            }
            receiveTask = Task { [weak self] in
                await self?.receiveMessages(from: socket, mode: .direct)
            }
        } catch {
            socket.cancel(with: .goingAway, reason: nil)
            self.socket = nil
            mode = nil
            throw error
        }
    }

    private func openProxyConnection() async throws {
        var request = URLRequest(url: proxyURL)
        request.timeoutInterval = 20
        request.networkServiceType = .avStreaming
        AppConfiguration.authorize(&request)

        let socket = session.webSocketTask(with: request)
        self.socket = socket
        mode = .proxy
        socket.resume()

        do {
            let event = try decodeObject(try await socket.receive())
            if event["type"] as? String == "error" {
                throw RealtimeBackendError.server(
                    event["message"] as? String
                        ?? "The realtime server rejected the connection."
                )
            }
            guard event["type"] as? String == "ready" else {
                throw RealtimeBackendError.invalidMessage
            }
            receiveTask = Task { [weak self] in
                await self?.receiveMessages(from: socket, mode: .proxy)
            }
        } catch {
            socket.cancel(with: .goingAway, reason: nil)
            self.socket = nil
            mode = nil
            throw error
        }
    }

    private var isConnectionLive: Bool {
        guard let socket, receiveTask != nil else {
            return false
        }
        return socket.state == .running
    }

    private func dropConnection() {
        let socket = self.socket
        receiveTask?.cancel()
        receiveTask = nil
        self.socket = nil
        mode = nil
        spokenStarted = false
        audioByteCount = 0
        socket?.cancel(with: .goingAway, reason: nil)
    }

    private func send(_ object: [String: Any]) async throws {
        guard let socket else {
            throw RealtimeBackendError.notConnected
        }
        let data = try JSONSerialization.data(withJSONObject: object)
        guard let text = String(data: data, encoding: .utf8) else {
            throw RealtimeBackendError.invalidMessage
        }
        try await socket.send(.string(text))
    }

    private func receiveMessages(
        from socket: URLSessionWebSocketTask,
        mode: RealtimeConnectionMode
    ) async {
        do {
            while !Task.isCancelled {
                let event = try decodeObject(try await socket.receive())
                switch mode {
                case .proxy:
                    try handleProxyEvent(event)
                case .direct:
                    try await handleDirectEvent(event)
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
            self.mode = nil
            eventHandler?(.error("The realtime connection was lost."))
        }
    }

    private func handleProxyEvent(_ event: [String: Any]) throws {
        switch event["type"] as? String {
        case "response_started":
            eventHandler?(.responseStarted)
        case "audio_delta":
            guard let encoded = event["audio"] as? String,
                  let audio = Data(base64Encoded: encoded)
            else {
                throw RealtimeBackendError.invalidMessage
            }
            eventHandler?(.audio(audio))
        case "transcript_delta":
            eventHandler?(.transcriptDelta(event["text"] as? String ?? ""))
        case "response_done":
            eventHandler?(.responseDone)
        case "response_cancelled":
            eventHandler?(.responseCancelled)
        case "error":
            let message = event["message"] as? String
                ?? "The realtime voice session failed."
            eventHandler?(
                Self.isBenignCancel(message) ? .responseCancelled : .error(message)
            )
        default:
            break
        }
    }

    private func handleDirectEvent(_ event: [String: Any]) async throws {
        switch event["type"] as? String {
        case "response.created":
            spokenStarted = false
        case "response.output_audio.delta", "response.audio.delta":
            markResponseStarted()
            guard let encoded = event["delta"] as? String,
                  let audio = Data(base64Encoded: encoded)
            else {
                throw RealtimeBackendError.invalidMessage
            }
            eventHandler?(.audio(audio))
        case "response.output_audio_transcript.delta", "response.audio_transcript.delta":
            markResponseStarted()
            eventHandler?(.transcriptDelta(event["delta"] as? String ?? ""))
        case "response.done":
            guard let response = event["response"] as? [String: Any] else {
                throw RealtimeBackendError.invalidMessage
            }
            let status = response["status"] as? String
            let calls = functionCalls(from: response)
            if !calls.isEmpty, status != "cancelled" {
                try await fulfillFunctionCalls(calls)
            } else if status == "cancelled" {
                eventHandler?(.responseCancelled)
            } else if status == "failed" || status == "incomplete" {
                eventHandler?(.error("OpenAI could not complete the response."))
            } else {
                eventHandler?(.responseDone)
            }
        case "error":
            let message = errorMessage(from: event)
                ?? "The OpenAI realtime session failed."
            if !Self.isBenignCancel(message) {
                eventHandler?(.error(message))
            }
        default:
            break
        }
    }

    private func markResponseStarted() {
        if !spokenStarted {
            spokenStarted = true
            eventHandler?(.responseStarted)
        }
    }

    private func functionCalls(from response: [String: Any]) -> [[String: Any]] {
        guard let output = response["output"] as? [[String: Any]] else {
            return []
        }
        return output.filter { $0["type"] as? String == "function_call" }
    }

    private func fulfillFunctionCalls(_ calls: [[String: Any]]) async throws {
        for call in calls {
            guard let name = call["name"] as? String,
                  let callID = call["call_id"] as? String,
                  !name.isEmpty,
                  !callID.isEmpty
            else {
                continue
            }
            let arguments = toolArguments(from: call["arguments"])
            let output = await executeTool(name: name, arguments: arguments)
            try await send([
                "type": "conversation.item.create",
                "item": [
                    "type": "function_call_output",
                    "call_id": callID,
                    "output": output,
                ],
            ])
        }
        try await send(["type": "response.create"])
    }

    private func executeTool(name: String, arguments: [String: Any]) async -> String {
        var request = URLRequest(url: AppConfiguration.realtimeToolURL(named: name))
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        AppConfiguration.authorize(&request)

        do {
            request.httpBody = try JSONSerialization.data(
                withJSONObject: ["arguments": arguments]
            )
            let (data, response) = try await session.data(for: request)
            guard let response = response as? HTTPURLResponse,
                  response.statusCode == 200
            else {
                return #"{"error":"The Kuma tool request failed."}"#
            }
            return try decoder.decode(RealtimeToolResponse.self, from: data).output
        } catch {
            return #"{"error":"The Kuma tool request failed."}"#
        }
    }

    private func toolArguments(from raw: Any?) -> [String: Any] {
        if let arguments = raw as? [String: Any] {
            return arguments
        }
        guard let text = raw as? String,
              let data = text.data(using: .utf8),
              let arguments = try? JSONSerialization.jsonObject(with: data)
                    as? [String: Any]
        else {
            return [:]
        }
        return arguments
    }

    private func errorMessage(from event: [String: Any]) -> String? {
        if let message = event["message"] as? String {
            return message
        }
        guard let error = event["error"] as? [String: Any] else {
            return nil
        }
        return error["message"] as? String
    }

    private func decodeObject(
        _ message: URLSessionWebSocketTask.Message
    ) throws -> [String: Any] {
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
        guard let object = try JSONSerialization.jsonObject(with: data)
                as? [String: Any]
        else {
            throw RealtimeBackendError.invalidMessage
        }
        return object
    }

    private static func isBenignCancel(_ message: String) -> Bool {
        let lowered = message.lowercased()
        return lowered.contains("cancelled")
            || lowered.contains("canceled")
            || lowered.contains("cancellation failed")
    }
}
