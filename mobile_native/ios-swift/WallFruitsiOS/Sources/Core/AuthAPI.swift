import Foundation

final class AuthAPI {
    static let shared = AuthAPI()

    private let baseURL = URL(string: "https://wallfruits-api.onrender.com")!

    func login(email: String, password: String) async throws -> LoginResponse {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/auth/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(LoginRequest(email: email, password: password))

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(LoginResponse.self, from: data)
    }

    func me(token: String) async throws -> ApiUser {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/auth/me"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(ApiUser.self, from: data)
    }
}
