import SwiftUI
import Foundation

private let statusError = "Nao foi possivel carregar os dados."

@MainActor
final class AuthViewModel: ObservableObject {
    @Published var email: String = ""
    @Published var password: String = ""
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var currentUser: ApiUser?
    @Published var offersTotal: Int = 0
    @Published var ordersTotal: Int = 0
    @Published var aiSignals: Int = 0

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
                await refreshDashboard()
            } catch {
                errorMessage = statusError
                isLoading = false
            }
        }
    }

    func loadCurrentUser(token: String) async {
        do {
            currentUser = try await api.me(token: token)
            await refreshDashboard()
        } catch {
            sessionStore.clear()
        }
    }

    func refreshDashboard() async {
        guard let token = sessionStore.load() else { return }
        do {
            let snapshot = try await api.dashboardSnapshot(token: token)
            offersTotal = snapshot.offersTotal
            ordersTotal = snapshot.ordersTotal
            aiSignals = snapshot.aiSignals
        } catch {
            // Mantem UI funcional mesmo se alguma secao ainda nao retornar dados.
        }
    }

    func logout() {
        sessionStore.clear()
        currentUser = nil
        email = ""
        password = ""
        offersTotal = 0
        ordersTotal = 0
        aiSignals = 0
    }
}
