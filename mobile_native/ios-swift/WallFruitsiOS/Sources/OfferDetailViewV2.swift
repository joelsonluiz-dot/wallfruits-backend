import SwiftUI

struct OfferDetailViewV2: View {
    let offerId: Int
    @StateObject private var toastHost = ToastHostModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Detalhe da Oferta #\(offerId)")
                    .font(.title2)
                    .bold()
                Text("Galeria, descrição, preço e ações (skeleton)")
                    .foregroundColor(.secondary)

                HStack(spacing: 12) {
                    Button(action: { Task { await favorite() } }) {
                        Label("Curtir", systemImage: "heart")
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.bordered)

                    Button(action: { Task { await bookmark() } }) {
                        Label("Salvar", systemImage: "bookmark")
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.bordered)

                    Button(action: { Task { await reserve() } }) {
                        Label("Reservar", systemImage: "cart")
                            .font(.system(size: 14))
                    }
                    .buttonStyle(.bordered)
                }
                .padding(.top, 8)
                Spacer()
            }
            .padding()
        }
        .navigationTitle("Oferta")
        .overlay(alignment: .top) {
            ToastContainerView(toastHost: toastHost)
        }
    }

    func favorite() async {
        do {
            _ = try await APIClient.shared.post(path: "api/offers/\(offerId)/favorite", body: Data())
            toastHost.show("Oferta curtida!", type: .success)
        } catch {
            toastHost.show("Erro ao curtir", type: .error)
        }
    }

    func bookmark() async {
        do {
            _ = try await APIClient.shared.post(path: "api/offers/\(offerId)/bookmark", body: Data())
            toastHost.show("Oferta salva!", type: .success)
        } catch {
            toastHost.show("Erro ao salvar", type: .error)
        }
    }

    func reserve() async {
        let payload: [String: Any] = ["boxes": 1, "price_per_box": 0.0]
        do {
            let data = try JSONSerialization.data(withJSONObject: payload)
            _ = try await APIClient.shared.post(path: "api/offers/\(offerId)/reserve", body: data)
            toastHost.show("Reserva confirmada!", type: .success)
        } catch {
            toastHost.show("Erro ao reservar", type: .error)
        }
    }
}

struct OfferDetailViewV2_Previews: PreviewProvider {
    static var previews: some View {
        OfferDetailViewV2(offerId: 123)
    }
}
