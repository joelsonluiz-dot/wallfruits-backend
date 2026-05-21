import SwiftUI

struct ServiceItem: Decodable, Identifiable {
    let id: Int
    let title: String?
}

struct ServicesResponse: Decodable {
    let total: Int
    let services: [ServiceItem]
}

struct ServicesView: View {
    @State private var services: [ServiceItem] = []
    @State private var loading = false

    var body: some View {
        NavigationView {
            List {
                if services.isEmpty && !loading {
                    Text("Nenhum serviço encontrado.")
                        .foregroundColor(.secondary)
                } else {
                    ForEach(services) { svc in
                        VStack(alignment: .leading) {
                            Text(svc.title ?? "Serviço")
                                .font(.headline)
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Serviços")
            .task {
                await loadServices()
            }
        }
    }

    func loadServices() async {
        loading = true
        do {
            let data = try await APIClient.shared.request(path: "api/services?skip=0&limit=20")
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let resp = try decoder.decode(ServicesResponse.self, from: data)
            services = resp.services
        } catch {
            services = []
        }
        loading = false
    }
}

struct ServicesView_Previews: PreviewProvider {
    static var previews: some View {
        ServicesView()
    }
}
