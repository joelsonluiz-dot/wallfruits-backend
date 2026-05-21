import SwiftUI

struct ServicesView: View {
    var body: some View {
        NavigationView {
            VStack(alignment: .leading) {
                Text("Serviços (skeleton)")
                    .font(.title2)
                    .bold()
                Text("Lista de serviços oferecidos pelo perfil ou mercado")
                    .foregroundColor(.secondary)
                Spacer()
            }
            .padding()
            .navigationTitle("Serviços")
        }
    }
}

struct ServicesView_Previews: PreviewProvider {
    static var previews: some View {
        ServicesView()
    }
}
