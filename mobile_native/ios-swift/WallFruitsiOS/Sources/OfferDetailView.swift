import SwiftUI

struct OfferDetailView: View {
    let offerId: Int

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Detalhe da Oferta #\(offerId)")
                    .font(.title2)
                    .bold()
                Text("Galeria, descrição, preço e ações (skeleton)")
                    .foregroundColor(.secondary)
                HStack(spacing: 16) {
                    Button(action: { Task { await favorite() } }) {
                        Label("Curtir", systemImage: "heart")
                    }
                    Button(action: { Task { await bookmark() } }) {
                        Label("Salvar", systemImage: "bookmark")
                    }
                    Button(action: { Task { await reserve() } }) {
                        Label("Reservar", systemImage: "cart")
                    }
                }
                .padding(.top, 8)
                Spacer()
            }
            .padding()
        }
        .navigationTitle("Oferta")
    }

    func favorite() async {
        do {
            _ = try await APIClient.shared.post(path: "api/offers/\(offerId)/favorite", body: Data())
        } catch {
            // ignore for now
        }
    }

    func bookmark() async {
        do {
            _ = try await APIClient.shared.post(path: "api/offers/\(offerId)/bookmark", body: Data())
        } catch {
        }
    }

    func reserve() async {
        let payload: [String: Any] = ["boxes": 1, "price_per_box": 0.0]
        do {
            let data = try JSONSerialization.data(withJSONObject: payload)
            _ = try await APIClient.shared.post(path: "api/offers/\(offerId)/reserve", body: data)
        } catch {
        }
    }
}

struct OfferDetailView_Previews: PreviewProvider {
    static var previews: some View {
        OfferDetailView(offerId: 123)
    }
}
