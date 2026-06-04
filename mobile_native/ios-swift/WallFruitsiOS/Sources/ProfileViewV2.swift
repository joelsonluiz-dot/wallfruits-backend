import SwiftUI

struct ProfileViewV2: View {
    var userId: Int?
    @StateObject private var toastHost = ToastHostModel()

    var body: some View {
        NavigationView {
            ProfileContentV2(userId: userId, toastHost: toastHost)
                .overlay(alignment: .top) {
                    ToastContainerView(toastHost: toastHost)
                }
        }
    }
}

struct ProfileContentV2: View {
    let userId: Int?
    let toastHost: ToastHostModel
    @State private var loading = false
    @State private var profile: [String: Any] = [:]
    @EnvironmentObject var auth: AuthViewModel
    @State private var isFollowing = false
    @State private var isMessageingLoading = false

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
                            Button(action: {
                                toastHost.show("Editor de perfil em desenvolvimento", type: .info)
                            }) {
                                Label("Editar", systemImage: "pencil")
                                    .font(.system(size: 14))
                            }
                            .buttonStyle(.bordered)
                        } else {
                            Button(action: {
                                Task { await toggleFollow() }
                            }) {
                                Label(isFollowing ? "Seguindo" : "Seguir", systemImage: "person.badge.plus")
                                    .font(.system(size: 14))
                            }
                            .buttonStyle(.bordered)

                            Button(action: {
                                Task { await sendMessage() }
                            }) {
                                Label("Mensagem", systemImage: isMessageingLoading ? "hourglass" : "message")
                                    .font(.system(size: 14))
                            }
                            .buttonStyle(.bordered)
                            .disabled(isMessageingLoading)
                        }
                    }
                    .padding(.top, 8)
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
            if let following = profile["is_following"] as? Bool {
                isFollowing = following
            }
        } catch {
            profile = [:]
            toastHost.show("Erro ao carregar perfil", type: .error)
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
            toastHost.show(
                isFollowing ? "Você seguiu o usuário!" : "Você deixou de seguir.",
                type: .success
            )
        } catch {
            toastHost.show("Erro ao seguir usuário", type: .error)
        }
    }

    func sendMessage() async {
        guard let uid = userId else { return }
        isMessageingLoading = true
        let payload: [String: Any] = [
            "to_user_id": uid,
            "body": "Olá, tenho interesse nos seus produtos."
        ]
        do {
            let body = try JSONSerialization.data(withJSONObject: payload)
            _ = try await APIClient.shared.post(path: "api/messages", body: body)
            toastHost.show("Mensagem enviada!", type: .success)
        } catch {
            toastHost.show("Erro ao enviar mensagem", type: .error)
        }
        isMessageingLoading = false
    }
}

struct ProfileViewV2_Previews: PreviewProvider {
    static var previews: some View {
        ProfileViewV2(userId: nil)
    }
}
