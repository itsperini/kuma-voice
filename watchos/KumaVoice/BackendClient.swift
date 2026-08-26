import Foundation

struct ConversationCreated: Decodable {
    let conversationID: String

    enum CodingKeys: String, CodingKey {
        case conversationID = "conversation_id"
    }
}

struct VoiceTurn: Decodable {
    let conversationID: String
    let userText: String
    let assistantText: String
    let audioBase64: String
    let audioMimeType: String

    enum CodingKeys: String, CodingKey {
        case conversationID = "conversation_id"
        case userText = "user_text"
        case assistantText = "assistant_text"
        case audioBase64 = "audio_base64"
        case audioMimeType = "audio_mime_type"
    }
}

enum BackendError: LocalizedError {
    case invalidResponse
    case server(statusCode: Int, message: String)
    case invalidAudio

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Kuma Voice received an invalid server response."
        case let .server(_, message):
            return message
        case .invalidAudio:
            return "Kuma Voice received invalid reply audio."
        }
    }
}

actor BackendClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    private var conversationID: String?

    init(baseURL: URL = AppConfiguration.backendBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func sendTurn(audioURL: URL) async throws -> VoiceTurn {
        let conversationID = try await ensureConversation()
        let boundary = "Boundary-\(UUID().uuidString)"
        let endpoint = baseURL
            .appendingPathComponent("api/v1/conversations")
            .appendingPathComponent(conversationID)
            .appendingPathComponent("turns")

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = try multipartBody(audioURL: audioURL, boundary: boundary)

        let data = try await send(request)
        let turn = try decoder.decode(VoiceTurn.self, from: data)
        guard Data(base64Encoded: turn.audioBase64) != nil else {
            throw BackendError.invalidAudio
        }
        return turn
    }

    private func ensureConversation() async throws -> String {
        if let conversationID {
            return conversationID
        }

        let endpoint = baseURL.appendingPathComponent("api/v1/conversations")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let data = try await send(request)
        let created = try decoder.decode(ConversationCreated.self, from: data)
        conversationID = created.conversationID
        return created.conversationID
    }

    private func send(_ request: URLRequest) async throws -> Data {
        var authorizedRequest = request
        AppConfiguration.authorize(&authorizedRequest)
        let (data, response) = try await session.data(for: authorizedRequest)
        guard let response = response as? HTTPURLResponse else {
            throw BackendError.invalidResponse
        }
        guard (200..<300).contains(response.statusCode) else {
            let message = serverMessage(from: data) ?? "Server error \(response.statusCode)."
            throw BackendError.server(statusCode: response.statusCode, message: message)
        }
        return data
    }

    private func serverMessage(from data: Data) -> String? {
        guard
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let detail = object["detail"] as? String
        else {
            return nil
        }
        return detail
    }

    private func multipartBody(audioURL: URL, boundary: String) throws -> Data {
        let audio = try Data(contentsOf: audioURL)
        var body = Data()
        body.appendUTF8("--\(boundary)\r\n")
        body.appendUTF8("Content-Disposition: form-data; name=\"audio\"; filename=\"voice.m4a\"\r\n")
        body.appendUTF8("Content-Type: audio/mp4\r\n\r\n")
        body.append(audio)
        body.appendUTF8("\r\n--\(boundary)--\r\n")
        return body
    }
}

private extension Data {
    mutating func appendUTF8(_ string: String) {
        append(string.data(using: .utf8)!)
    }
}
