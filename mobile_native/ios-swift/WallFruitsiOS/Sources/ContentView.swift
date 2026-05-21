import SwiftUI

struct ContentView: View {
    @State private var selectedTab: AppTab = .feed

    var body: some View {
        Group {
                PremiumFruitFormView(
                    onLogout: authViewModel.logout,
                    onRefresh: {
                        Task { await authViewModel.refreshDashboard() }
                    }
                )
                }
            } else {
                LoginView(viewModel: authViewModel)
            }
        }
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(accent.opacity(0.14), lineWidth: 1)
                )
        )
    }
}
