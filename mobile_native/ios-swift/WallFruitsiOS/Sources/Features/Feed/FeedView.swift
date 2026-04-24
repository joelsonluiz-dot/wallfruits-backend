import SwiftUI

struct FeedView: View {
    let userName: String
    let offersTotal: Int
    let ordersTotal: Int
    let aiSignals: Int
    let onRefresh: () -> Void
    let onLogout: () -> Void

    var body: some View {
        NavigationStack {
            List {
                Section("Sessao") {
                    Text("JWT ativo para \(userName)")
                }
                Section("Integracoes") {
                    Text("Feed /api/offers: \(offersTotal)")
                    Text("Marketplace /api/store/orders/my: \(ordersTotal)")
                    Text("IA /api/ai/agenda/market-intelligence: \(aiSignals)")
                }
            }
            .navigationTitle("WallFruits")
            .toolbar {
                Button("Refresh") {
                    onRefresh()
                }
                Button("Sair") {
                    onLogout()
                }
            }
        }
    }
}
