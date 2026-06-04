import SwiftUI

struct CreateOfferViewV2: View {
    @State private var productName: String = ""
    @State private var description: String = ""
    @State private var price: String = ""
    @State private var unit: String = "kg"
    @State private var location: String = ""
    @State private var quantity: String = ""
    @State private var isLoading = false
    @StateObject private var toastHost = ToastHostModel()

    let units = ["kg", "ton", "unidade", "lote", "caixa"]

    var body: some View {
        Form {
            Section("Produto") {
                TextField("Nome do Produto", text: $productName)
                TextField("Descrição", text: $description)
                    .lineLimit(3...5)
            }

            Section("Preço e Unidade") {
                HStack {
                    TextField("Preço", text: $price)
                        .keyboardType(.decimalPad)
                    Picker("Unidade", selection: $unit) {
                        ForEach(units, id: \.self) { u in
                            Text(u).tag(u)
                        }
                    }
                }
            }

            Section("Quantidade e Localização") {
                TextField("Quantidade", text: $quantity)
                    .keyboardType(.numberPad)
                TextField("Localização", text: $location)
            }

            Section {
                Button(action: submitOffer) {
                    if isLoading {
                        ProgressView()
                    } else {
                        Text("Criar Oferta")
                    }
                }
                .disabled(isLoading || productName.isEmpty || price.isEmpty)
            }
        }
        .navigationTitle("Criar Oferta")
        .overlay(alignment: .top) {
            ToastContainerView(toastHost: toastHost)
        }
    }

    func submitOffer() {
        guard !productName.isEmpty && !price.isEmpty else {
            toastHost.show("Preencha todos os campos", type: .warning)
            return
        }

        isLoading = true
        let payload: [String: Any] = [
            "product_name": productName,
            "description": description,
            "price": Double(price) ?? 0.0,
            "unit": unit,
            "location": location,
            "quantity": quantity
        ]

        Task {
            do {
                let body = try JSONSerialization.data(withJSONObject: payload)
                // TODO: call API to create offer (e.g., /api/offers/create)
                toastHost.show("Oferta criada com sucesso!", type: .success)
                // Reset form
                productName = ""
                description = ""
                price = ""
                unit = "kg"
                location = ""
                quantity = ""
                isLoading = false
            } catch {
                toastHost.show("Erro ao criar oferta", type: .error)
                isLoading = false
            }
        }
    }
}

struct CreateOfferViewV2_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            CreateOfferViewV2()
        }
    }
}
