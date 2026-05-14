import SwiftUI

struct ContentView: View {
    @StateObject private var authViewModel = AuthViewModel()
    @State private var selectedTab: AppTab = .feed

    var body: some View {
        Group {
            if authViewModel.isAuthenticated {
                ZStack(alignment: .bottom) {
                    PremiumShellBackground()

                    VStack(spacing: 0) {
                        shellContent
                        PremiumBottomTabBar(selectedTab: $selectedTab)
                    }
                }
                .onAppear {
                    selectedTab = .feed
                }
            } else {
                LoginView(viewModel: authViewModel)
            }
        }
    }

    @ViewBuilder
    private var shellContent: some View {
        switch selectedTab {
        case .feed:
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
        case .market:
            PlaceholderModuleView(
                title: "Marketplace",
                subtitle: "Pedidos do usuario: \(authViewModel.ordersTotal)",
                accent: Color(red: 0.17, green: 0.45, blue: 0.28)
            )
        case .ai:
            PlaceholderModuleView(
                title: "AI Lab",
                subtitle: "Sinais de IA: \(authViewModel.aiSignals)",
                accent: Color(red: 0.12, green: 0.44, blue: 0.39)
            )
        }
    }
}

private enum AppTab: String, CaseIterable {
    case feed
    case market
    case ai

    var title: String {
        switch self {
        case .feed: return "Feed"
        case .market: return "Market"
        case .ai: return "AI"
        }
    }

    var systemImage: String {
        switch self {
        case .feed: return "house.fill"
        case .market: return "bag.fill"
        case .ai: return "sparkles"
        }
    }
}

private struct PremiumShellBackground: View {
    var body: some View {
        LinearGradient(
            colors: [
                Color(red: 0.96, green: 0.98, blue: 0.96),
                Color.white,
                Color(red: 0.95, green: 0.97, blue: 0.95)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .ignoresSafeArea()
    }
}

private struct PremiumBottomTabBar: View {
    @Binding var selectedTab: AppTab

    var body: some View {
        HStack(spacing: 10) {
            ForEach(AppTab.allCases, id: \.self) { tab in
                Button {
                    selectedTab = tab
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.systemImage)
                            .font(.system(size: 17, weight: .semibold))
                        Text(tab.title)
                            .font(.caption2.weight(.semibold))
                    }
                    .foregroundStyle(selectedTab == tab ? Color.white : Color(red: 0.26, green: 0.35, blue: 0.29))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .fill(selectedTab == tab ? Color(red: 0.15, green: 0.47, blue: 0.29) : Color.white.opacity(0.92))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(selectedTab == tab ? Color.clear : Color(red: 0.84, green: 0.89, blue: 0.85), lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 14)
        .padding(.top, 6)
        .padding(.bottom, 12)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) {
            Divider().opacity(0.2)
        }
    }
}

private struct PlaceholderModuleView: View {
    let title: String
    let subtitle: String
    let accent: Color

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                premiumHeader
                premiumStatCard
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 98)
        }
    }

    private var premiumHeader: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Inicio")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(title)
                .font(.largeTitle.weight(.bold))
            Text("Scroll nativo, barra compacta e leitura rapida.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .shadow(color: accent.opacity(0.08), radius: 18, x: 0, y: 10)
        )
    }

    private var premiumStatCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(subtitle)
                .font(.headline)
                .foregroundStyle(accent)
            Text("A interface segue uma linha nativa e minimalista, com acoes concentradas em um unico fluxo visual.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(accent.opacity(0.12), lineWidth: 1)
                )
        )
    }
}
