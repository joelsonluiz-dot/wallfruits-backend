import SwiftUI

struct ProfileView: View {
    var userId: Int?

    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Perfil (skeleton)")
                    .font(.title2)
                    .bold()
                Text("Identidade pública, Sobre, Serviços e Ofertas - placeholder")
                    .foregroundColor(.secondary)
                Spacer()
            }
            .padding()
            .navigationTitle("Perfil")
        }
    }
}

struct ProfileView_Previews: PreviewProvider {
    static var previews: some View {
        ProfileView(userId: nil)
    }
}
