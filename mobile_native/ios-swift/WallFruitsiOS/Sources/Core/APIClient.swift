import Foundation

final class APIClient {
    static let shared = APIClient()

    let baseURL = URL(string: "https://wallfruits-api.onrender.com")!

    func request(path: String) async throws -> Data {
        let url = baseURL.appendingPathComponent(path)
        let (data, _) = try await URLSession.shared.data(from: url)
        return data
    }
}
