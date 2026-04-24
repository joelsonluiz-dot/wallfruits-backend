import SwiftUI

struct ContentView: View {
    @StateObject private var authViewModel = AuthViewModel()

    var body: some View {
        Group {
            if authViewModel.isAuthenticated {
                TabView {
                    FeedView(
                        userName: authViewModel.currentUser?.name ?? "usuario",
                        offersTotal: authViewModel.offersTotal,
                        ordersTotal: authViewModel.ordersTotal,
                        aiSignals: authViewModel.aiSignals,
                        onRefresh: {
                            Task {
                                await authViewModel.refreshDashboard()
                            }
                        },
                        onLogout: authViewModel.logout
                    )
                        .tabItem {
                            Label("Feed", systemImage: "play.rectangle.fill")
                        }

                    VStack(spacing: 12) {
                        Text("Marketplace")
                            .font(.title2.weight(.bold))
                        Text("Pedidos do usuario: \(authViewModel.ordersTotal)")
                    }
                        .tabItem {
                            Label("Market", systemImage: "bag.fill")
                        }

                    VStack(spacing: 12) {
                        Text("AI Lab")
                            .font(.title2.weight(.bold))
                        Text("Sinais de IA: \(authViewModel.aiSignals)")
                    }
                        .tabItem {
                            Label("AI", systemImage: "sparkles")
                        }
                }
            } else {
                LoginView(viewModel: authViewModel)
            }
        }
    }
}
