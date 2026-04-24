import Foundation

final class AuthAPI {
    static let shared = AuthAPI()

    private let baseURL = URL(string: "https://wallfruits-api.onrender.com")!

    private func authorizedRequest(path: String, token: String) -> URLRequest {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        return request
    }

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
        let request = authorizedRequest(path: "api/auth/me", token: token)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(ApiUser.self, from: data)
    }

    func dashboardSnapshot(token: String) async throws -> DashboardSnapshot {
        async let offersCount = fetchOffersTotal(token: token)
        async let ordersCount = fetchOrdersTotal(token: token)
        async let aiCount = fetchAISignalsTotal(token: token)

        return try await DashboardSnapshot(
            offersTotal: offersCount,
            ordersTotal: ordersCount,
            aiSignals: aiCount
        )
    }

    private func fetchOffersTotal(token: String) async throws -> Int {
        var request = authorizedRequest(path: "api/offers?skip=0&limit=5", token: token)
        request.httpMethod = "GET"

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(OffersResponse.self, from: data).total
    }

    private func fetchOrdersTotal(token: String) async throws -> Int {
        let request = authorizedRequest(path: "api/store/orders/my", token: token)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(StoreOrdersResponse.self, from: data).total
    }

    private func fetchAISignalsTotal(token: String) async throws -> Int {
        let request = authorizedRequest(path: "api/ai/agenda/market-intelligence", token: token)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }

        let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        let alerts = (payload["alerts"] as? [Any])?.count ?? 0
        let opportunities = (payload["opportunities"] as? [Any])?.count ?? 0
        let recommendations = (payload["recommendations"] as? [Any])?.count ?? 0
        return alerts + opportunities + recommendations
    }
}
