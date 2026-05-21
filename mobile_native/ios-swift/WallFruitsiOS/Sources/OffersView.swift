import SwiftUI

struct OffersView: View {
    var body: some View {
        NavigationView {
            List {
                Section(header: Text("Ofertas em destaque")) {
                    ForEach(0..<6) { i in
                        VStack(alignment: .leading) {
                            Text("Oferta \(i + 1)")
                                .font(.headline)
                            Text("Resumo da oferta - preço, unidade e localização")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Ofertas")
        }
    }
}

struct OffersView_Previews: PreviewProvider {
    static var previews: some View {
        OffersView()
    }
}
