import Foundation
import Security

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

    static var configuredAPIToken: String {
        let configured = Bundle.main.object(forInfoDictionaryKey: "KUMA_API_TOKEN") as? String
        return configured?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    static var apiToken: String {
        DeviceCredentialStore.load() ?? configuredAPIToken
    }

    static var hasAuthorization: Bool {
        !apiToken.isEmpty
    }

    static func authorize(_ request: inout URLRequest) {
        guard !apiToken.isEmpty else { return }
        request.setValue("Bearer \(apiToken)", forHTTPHeaderField: "Authorization")
    }
}

enum DeviceCredentialError: LocalizedError {
    case keychain(OSStatus)

    var errorDescription: String? {
        "Kuma could not securely save this Watch."
    }
}

enum DeviceCredentialStore {
    private static let service = "com.kumavoice.device"
    private static let account = "managed-access-token"

    static func load() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8),
              !value.isEmpty
        else {
            return nil
        }
        return value
    }

    static func save(_ value: String) throws {
        let lookup: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attributes: [String: Any] = [
            kSecValueData as String: Data(value.utf8),
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let updated = SecItemUpdate(lookup as CFDictionary, attributes as CFDictionary)
        if updated == errSecSuccess {
            return
        }
        guard updated == errSecItemNotFound else {
            throw DeviceCredentialError.keychain(updated)
        }

        var insert = lookup
        attributes.forEach { insert[$0.key] = $0.value }
        let inserted = SecItemAdd(insert as CFDictionary, nil)
        guard inserted == errSecSuccess else {
            throw DeviceCredentialError.keychain(inserted)
        }
    }
}

struct DeviceAuthorizationResponse: Decodable {
    let deviceCode: String
    let userCode: String
    let verificationURI: String
    let expiresIn: Int
    let interval: Int

    enum CodingKeys: String, CodingKey {
        case deviceCode = "device_code"
        case userCode = "user_code"
        case verificationURI = "verification_uri"
        case expiresIn = "expires_in"
        case interval
    }
}

private struct DeviceTokenResponse: Decodable {
    let accessToken: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
    }
}

enum DevicePairingError: LocalizedError {
    case invalidResponse
    case server(String)
    case expired

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Kuma received an invalid pairing response."
        case let .server(message):
            return message
        case .expired:
            return "The pairing code expired. Create a new one."
        }
    }
}

actor DevicePairingClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()

    init(
        baseURL: URL = AppConfiguration.backendBaseURL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    func createAuthorization() async throws -> DeviceAuthorizationResponse {
        let endpoint = baseURL.appendingPathComponent("device/v1/authorizations")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(
            withJSONObject: ["device_name": "Apple Watch"]
        )
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data, expected: 201)
        return try decoder.decode(DeviceAuthorizationResponse.self, from: data)
    }

    func waitForApproval(_ authorization: DeviceAuthorizationResponse) async throws -> String {
        let endpoint = baseURL.appendingPathComponent("device/v1/token")
        let deadline = Date().addingTimeInterval(TimeInterval(authorization.expiresIn))
        while Date() < deadline {
            try await Task.sleep(
                nanoseconds: UInt64(max(authorization.interval, 1)) * 1_000_000_000
            )
            try Task.checkCancellation()

            var request = URLRequest(url: endpoint)
            request.httpMethod = "POST"
            request.timeoutInterval = 20
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(
                withJSONObject: ["device_code": authorization.deviceCode]
            )
            let (data, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw DevicePairingError.invalidResponse
            }
            if httpResponse.statusCode == 202 {
                continue
            }
            if httpResponse.statusCode == 410 {
                throw DevicePairingError.expired
            }
            try validate(response: response, data: data, expected: 200)
            return try decoder.decode(DeviceTokenResponse.self, from: data).accessToken
        }
        throw DevicePairingError.expired
    }

    private func validate(response: URLResponse, data: Data, expected: Int) throws {
        guard let response = response as? HTTPURLResponse else {
            throw DevicePairingError.invalidResponse
        }
        guard response.statusCode == expected else {
            let message = serverMessage(from: data) ?? "Pairing failed on the Kuma server."
            throw DevicePairingError.server(message)
        }
    }

    private func serverMessage(from data: Data) -> String? {
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let detail = object["detail"] as? String
        else {
            return nil
        }
        return detail
    }
}
