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
    @EnvironmentObject var auth: AuthViewModel
    @State private var isFollowing = false
    @State private var actionMessage: String?

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

                    HStack(spacing: 12) {
                        if auth.currentUser?.id == profile["id"] as? Int {
                            Button("Editar Perfil") {
                                actionMessage = "Abra o editor de perfil (a implementar)."
                            }
                        } else {
                            Button(isFollowing ? "Seguindo" : "Seguir") {
                                Task { await toggleFollow() }
                            }

                            Button("Mensagem") {
                                Task { await sendMessage() }
                            }
                        }
                    }
                    .padding(.top, 8)

                    if let m = actionMessage {
                        Text(m).foregroundColor(.green).font(WFTypography.caption)
                    }
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
            // initialize following state from server payload if provided
            if let following = profile["is_following"] as? Bool {
                isFollowing = following
            }
        } catch {
            profile = [:]
        }
        loading = false
    }

    func toggleFollow() async {
        guard let uid = userId else { return }
        do {
            _ = try await APIClient.shared.post(path: "social/users/\(uid)/follow", body: Data())
            isFollowing.toggle()
            let currentCount = profile["followers_count"] as? Int ?? 0
            profile["followers_count"] = isFollowing ? currentCount + 1 : max(0, currentCount - 1)
            actionMessage = isFollowing ? "Você seguiu o usuário." : "Você deixou de seguir o usuário."
        } catch {
            actionMessage = "Falha na operação."
        }
        // clear after short delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            actionMessage = nil
        }
    }

    func sendMessage() async {
        guard let uid = userId else { return }
        let payload: [String: Any] = [
            "to_user_id": uid,
            "body": "Olá, tenho interesse nos seus produtos."
        ]
        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            _ = try await APIClient.shared.post(path: "api/messages", body: body)
            actionMessage = "Mensagem enviada."
        } catch {
            actionMessage = "Falha ao enviar mensagem."
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            actionMessage = nil
        }
    }
}

struct ProfileView_Previews: PreviewProvider {
    static var previews: some View {
        ProfileView(userId: nil)
    }
}
