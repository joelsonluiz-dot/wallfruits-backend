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
                Spacer()
            }
            .padding()
        }
        .navigationTitle("Oferta")
    }
}

struct OfferDetailView_Previews: PreviewProvider {
    static var previews: some View {
        OfferDetailView(offerId: 123)
    }
}
