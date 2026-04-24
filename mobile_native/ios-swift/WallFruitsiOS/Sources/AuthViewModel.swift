import SwiftUI
import Foundation

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var email: String = ""
    @Published var password: String = ""
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var currentUser: ApiUser?

    private let api = AuthAPI.shared
    private let sessionStore = SessionStore.shared

    init() {
        if let token = sessionStore.load() {
            Task {
                await loadCurrentUser(token: token)
            }
        }
    }

    var isAuthenticated: Bool {
        currentUser != nil
    }

    func login() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let response = try await api.login(email: email, password: password)
                sessionStore.save(token: response.accessToken)
                currentUser = response.user
                isLoading = false
            } catch {
                errorMessage = error.localizedDescription
                isLoading = false
            }
        }
    }

    func loadCurrentUser(token: String) async {
        do {
            currentUser = try await api.me(token: token)
        } catch {
            sessionStore.clear()
        }
    }

    func logout() {
        sessionStore.clear()
        currentUser = nil
        email = ""
        password = ""
    }
}
