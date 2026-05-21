import SwiftUI

struct ProfileView: View {
    var userId: Int?

    var body: some View {
        NavigationView {
            ProfileContent(userId: userId)
        }
    }
}

struct ProfileContent: View {
    let userId: Int?
    @State private var loading = false
    @State private var profile: [String: Any] = [:]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if loading {
                    Text("Carregando perfil...")
                        .foregroundColor(.secondary)
                } else if profile.isEmpty {
                    Text("Perfil não encontrado.")
                        .foregroundColor(.secondary)
                } else {
                    Text(profile["display_name"] as? String ?? profile["name"] as? String ?? "Perfil")
                        .font(WFTypography.h2)
                        .bold()
                    Text(profile["bio"] as? String ?? "")
                        .foregroundColor(.secondary)

                    HStack(spacing: 12) {
                        Text("Ofertas: \(profile["total_offers"] as? Int ?? 0)")
                        Text("Serviços: \((profile["services"] as? [Any])?.count ?? 0)")
                        Text("Seguidores: \(profile["followers_count"] as? Int ?? 0)")
                    }
                    .font(WFTypography.body)
                }
                Spacer()
            }
            .padding()
            .task {
                await loadProfile()
            }
        }
        .navigationTitle("Perfil")
    }

    func loadProfile() async {
        guard let uid = userId else { return }
        loading = true
        do {
            let data = try await APIClient.shared.request(path: "social/users/\(uid)")
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
            profile = json
        } catch {
            profile = [:]
        }
        loading = false
    }
}

struct ProfileView_Previews: PreviewProvider {
    static var previews: some View {
        ProfileView(userId: nil)
    }
}
