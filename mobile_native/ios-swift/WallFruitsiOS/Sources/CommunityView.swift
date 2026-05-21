import SwiftUI

struct CommunityView: View {
    var body: some View {
        NavigationView {
            List(0..<8) { i in
                VStack(alignment: .leading) {
                    Text("Post de comunidade \(i + 1)")
                        .font(.headline)
                    Text("Resumo do post e interação")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.vertical, 8)
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Comunidade")
        }
    }
}

struct CommunityView_Previews: PreviewProvider {
    static var previews: some View {
        CommunityView()
    }
}
