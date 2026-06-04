import SwiftUI

struct EditProfileViewV2: View {
    @State private var name: String = ""
    @State private var bio: String = ""
    @State private var location: String = ""
    @State private var isLoading = false
    @StateObject private var toastHost = ToastHostModel()
    @EnvironmentObject var auth: AuthViewModel

    var body: some View {
        Form {
            Section("Informações Pessoais") {
                TextField("Nome", text: $name)
                TextField("Bio", text: $bio)
                TextField("Localização", text: $location)
            }

            Section {
                Button(action: submitProfile) {
                    if isLoading {
                        ProgressView()
                    } else {
                        Text("Salvar Perfil")
                    }
                }
                .disabled(isLoading || name.isEmpty)
            }
        }
        .navigationTitle("Editar Perfil")
        .onAppear {
            if let user = auth.currentUser {
                name = user.name
                // bio e location viriam do profile completo (a implementar)
            }
        }
        .overlay(alignment: .top) {
            ToastContainerView(toastHost: toastHost)
        }
    }

    func submitProfile() {
        guard !name.isEmpty else {
            toastHost.show("Nome é obrigatório", type: .warning)
            return
        }

        isLoading = true
        let payload: [String: Any] = [
            "name": name,
            "bio": bio,
            "location": location
        ]

        Task {
            do {
                let body = try JSONSerialization.data(withJSONObject: payload)
                // TODO: call API to update profile (e.g., /api/profile/update)
                toastHost.show("Perfil atualizado!", type: .success)
                isLoading = false
            } catch {
                toastHost.show("Erro ao salvar perfil", type: .error)
                isLoading = false
            }
        }
    }
}

struct EditProfileViewV2_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            EditProfileViewV2()
                .environmentObject(AuthViewModel())
        }
    }
}
