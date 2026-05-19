import SwiftUI

struct FeedView: View {
    let userName: String
    let offersTotal: Int
    let ordersTotal: Int
    let aiSignals: Int
    let onRefresh: () -> Void
    let onLogout: () -> Void

    private let statusEmpty = "Nenhum item encontrado."

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                premiumHero
                metricsRow
                actionRow
                feedCard(title: "Sessao", body: "JWT ativo para \(userName)", accent: .wfPrimaryVariant)
                if offersTotal == 0 && ordersTotal == 0 && aiSignals == 0 {
                    feedCard(title: "Vazio", body: statusEmpty, accent: .wfMuted)
                }
                feedCard(title: "Feed", body: "/api/offers: \(offersTotal)", accent: .wfPrimary)
                feedCard(title: "Marketplace", body: "/api/store/orders/my: \(ordersTotal)", accent: .wfSecondary)
                feedCard(title: "AI", body: "/api/ai/agenda/market-intelligence: \(aiSignals)", accent: .wfWarning)
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 98)
        }
        .background(
            LinearGradient(
                colors: [
                    Color(red: 0.96, green: 0.98, blue: 1.0),
                    .white,
                    Color(red: 0.98, green: 0.96, blue: 0.95)
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
            Text("Mesma base visual em iOS, Android e Web: hero, metricas, acoes e cards com a mesma linguagem.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(Color.wfPrimary.opacity(0.10), lineWidth: 1)
                )
                .shadow(color: Color.black.opacity(0.05), radius: 16, x: 0, y: 8)
        )
    }

    private var metricsRow: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Resumo rapido").font(.headline)
            HStack(spacing: 10) {
                metricPill(title: "Feed", value: offersTotal, color: .wfPrimary)
                metricPill(title: "Market", value: ordersTotal, color: .wfSecondary)
            }
            HStack(spacing: 10) {
                metricPill(title: "IA", value: aiSignals, color: .wfWarning)
                metricPill(title: "Sessao", value: 1, color: .wfPrimaryVariant)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(Color.wfPrimary.opacity(0.10), lineWidth: 1)
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
            HStack(spacing: 10) {
                Circle()
                    .fill(accent)
                    .frame(width: 10, height: 10)
                Text(title)
                    .font(.headline)
                    .foregroundStyle(.primary)
            }
            Text(body)
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
}
