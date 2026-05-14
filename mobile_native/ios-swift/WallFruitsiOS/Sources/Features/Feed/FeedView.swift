import SwiftUI

struct FeedView: View {
    let userName: String
    let offersTotal: Int
    let ordersTotal: Int
    let aiSignals: Int
    let onRefresh: () -> Void
    let onLogout: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                premiumHero
                metricsRow
                actionRow
                feedCard(title: "Sessao", body: "JWT ativo para \(userName)", accent: Color(red: 0.17, green: 0.42, blue: 0.26))
                feedCard(title: "Feed", body: "/api/offers: \(offersTotal)", accent: Color(red: 0.14, green: 0.46, blue: 0.31))
                feedCard(title: "Marketplace", body: "/api/store/orders/my: \(ordersTotal)", accent: Color(red: 0.54, green: 0.42, blue: 0.18))
                feedCard(title: "AI", body: "/api/ai/agenda/market-intelligence: \(aiSignals)", accent: Color(red: 0.12, green: 0.44, blue: 0.39))
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 98)
        }
        .background(
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
        )
    }

    private var premiumHero: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Inicio")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
            Text("WallFruits")
                .font(.largeTitle.weight(.bold))
            Text("Scroll nativo, premium e rapido, com leitura limpa e menos ruido visual.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .shadow(color: Color.black.opacity(0.06), radius: 18, x: 0, y: 10)
        )
    }

    private var metricsRow: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Resumo rapido").font(.headline)
            HStack(spacing: 10) {
                metricPill(title: "Feed", value: offersTotal, color: Color(red: 0.17, green: 0.42, blue: 0.26))
                metricPill(title: "Market", value: ordersTotal, color: Color(red: 0.54, green: 0.42, blue: 0.18))
            }
            HStack(spacing: 10) {
                metricPill(title: "IA", value: aiSignals, color: Color(red: 0.12, green: 0.44, blue: 0.39))
                metricPill(title: "Sessao", value: 1, color: Color(red: 0.34, green: 0.47, blue: 0.39))
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(Color(red: 0.85, green: 0.9, blue: 0.86), lineWidth: 1)
                )
        )
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

    private func metricPill(title: String, value: Int, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(color)
            Text("\(value)")
                .font(.title3.weight(.bold))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(color.opacity(0.08))
        )
    }

    private func feedCard(title: String, body: String, accent: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
                .foregroundStyle(accent)
            Text(body)
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
