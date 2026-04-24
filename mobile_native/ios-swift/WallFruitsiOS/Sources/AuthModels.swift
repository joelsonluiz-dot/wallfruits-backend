import Foundation

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct ApiUser: Codable {
    let id: Int
    let name: String
    let email: String
    let role: String
    let platformRole: String?
    let accountRole: String?
    let accountScopeId: String?
    let profileImage: String?

    enum CodingKeys: String, CodingKey {
        case id, name, email, role
        case platformRole = "platform_role"
        case accountRole = "account_role"
        case accountScopeId = "account_scope_id"
        case profileImage = "profile_image"
    }
}

struct LoginResponse: Codable {
    let accessToken: String
    let tokenType: String
    let user: ApiUser

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case user
    }
}

struct OffersResponse: Codable {
    let total: Int
}

struct StoreOrdersResponse: Codable {
    let total: Int
}

struct DashboardSnapshot {
    let offersTotal: Int
    let ordersTotal: Int
    let aiSignals: Int
}
