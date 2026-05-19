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
                accent: .wfSecondary,
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
        case .ai:
            PlaceholderModuleView(
                title: "AI Lab",
                subtitle: "Sinais de IA: \(authViewModel.aiSignals)",
                accent: .wfWarning,
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
                Color(red: 0.96, green: 0.98, blue: 1.0),
                Color.white,
                Color(red: 0.98, green: 0.96, blue: 0.95)
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
                    .foregroundStyle(selectedTab == tab ? Color.white : Color.wfMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .fill(selectedTab == tab ? Color.wfPrimary : Color.white.opacity(0.92))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(selectedTab == tab ? Color.clear : Color.wfPrimary.opacity(0.10), lineWidth: 1)
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
    let offersTotal: Int
    let ordersTotal: Int
    let aiSignals: Int
    let onRefresh: () -> Void
    let onLogout: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                premiumHeader
                metricsRow
                actionRow
                premiumStatCard
                feedCard(title: "Feed", subtitle: "/api/offers", value: "\(offersTotal)", accent: .wfPrimary)
                feedCard(title: "Marketplace", subtitle: "/api/store/orders/my", value: "\(marketValue)", accent: .wfSecondary)
                feedCard(title: "AI", subtitle: "/api/ai/agenda/market-intelligence", value: "\(aiValue)", accent: .wfWarning)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 98)
        }
    }

    private var marketValue: String { "\(ordersTotal)" }

    private var aiValue: String { "\(aiSignals)" }

    private var premiumHeader: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Inicio")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(title)
                .font(.largeTitle.weight(.bold))
            Text("Mesma base visual em iOS, Android e Web: hero, metricas, acoes e cards com a mesma linguagem.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(accent.opacity(0.10), lineWidth: 1)
                )
                .shadow(color: Color.black.opacity(0.05), radius: 16, x: 0, y: 8)
        )
    }

    private var premiumStatCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(subtitle)
                .font(.headline)
                .foregroundStyle(.primary)
            Text("A interface segue uma linha nativa e minimalista, com acoes concentradas em um unico fluxo visual.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(accent.opacity(0.14), lineWidth: 1)
                )
        )
    }

    private var metricsRow: some View {
        HStack(spacing: 10) {
            metricPill(title: "Feed", value: "\(offersTotal)", color: .wfPrimary)
            metricPill(title: "Market", value: marketValue, color: .wfSecondary)
        }
    }

    private var actionRow: some View {
        HStack(spacing: 10) {
            Button(action: onRefresh) {
                Text("Atualizar")
                    .frame(maxWidth: .infinity)
            }
                .buttonStyle(.borderedProminent)

            Button(role: .destructive, action: onLogout) {
                Text("Sair")
                    .frame(maxWidth: .infinity)
            }
                .buttonStyle(.bordered)
        }
    }

    private func metricPill(title: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(color)
            Text(value)
                .font(.title3.weight(.bold))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(color.opacity(0.08))
        )
    }

    private func feedCard(title: String, subtitle: String, value: String, accent: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Circle()
                    .fill(accent)
                    .frame(width: 10, height: 10)
                Text(title)
                    .font(.headline)
            }
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.weight(.bold))
                .foregroundStyle(.primary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(accent.opacity(0.14), lineWidth: 1)
                )
        )
    }
}
