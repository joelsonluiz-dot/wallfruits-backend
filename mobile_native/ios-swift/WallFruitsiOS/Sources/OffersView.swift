import SwiftUI

struct Offer: Decodable, Identifiable {
    let id: Int
    let product_name: String?
    let price: Double?
}

struct OffersResponse: Decodable {
    let total: Int
    let offers: [Offer]
}

struct OffersView: View {
    @State private var offers: [Offer] = []
    @State private var loading = false

    var body: some View {
        NavigationView {
            List {
                if offers.isEmpty && !loading {
                    Text("Nenhuma oferta encontrada.")
                        .foregroundColor(.secondary)
                } else {
                    ForEach(offers) { offer in
                        VStack(alignment: .leading) {
                            Text(offer.product_name ?? "Produto")
                                .font(.headline)
                            if let price = offer.price {
                                Text(String(format: "R$ %.2f", price))
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Ofertas")
            .task {
                await loadOffers()
            }
        }
    }

    func loadOffers() async {
        loading = true
        do {
            let data = try await APIClient.shared.request(path: "api/offers?skip=0&limit=12")
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let resp = try decoder.decode(OffersResponse.self, from: data)
            offers = resp.offers
        } catch {
            offers = []
        }
        loading = false
    }
}

struct OffersView_Previews: PreviewProvider {
    static var previews: some View {
        OffersView()
    }
}
