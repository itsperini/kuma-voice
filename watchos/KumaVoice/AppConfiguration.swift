import Foundation

enum AppConfiguration {
    static var backendBaseURL: URL {
        let configured = Bundle.main.object(forInfoDictionaryKey: "KUMA_BACKEND_URL") as? String
        return URL(string: configured ?? "http://127.0.0.1:8000")!
    }

    static var realtimeWebSocketURL: URL {
        let endpoint = backendBaseURL.appendingPathComponent("api/v1/realtime")
        var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)!
        components.scheme = components.scheme == "https" ? "wss" : "ws"
        return components.url!
    }

    static var apiToken: String {
        let configured = Bundle.main.object(forInfoDictionaryKey: "KUMA_API_TOKEN") as? String
        return configured?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    static func authorize(_ request: inout URLRequest) {
        guard !apiToken.isEmpty else { return }
        request.setValue("Bearer \(apiToken)", forHTTPHeaderField: "Authorization")
    }
}
