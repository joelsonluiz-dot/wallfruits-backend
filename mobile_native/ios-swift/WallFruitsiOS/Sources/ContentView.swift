import SwiftUI

struct ContentView: View {
    @StateObject private var authViewModel = AuthViewModel()
    @State private var selectedTab: Int = 0

    var body: some View {
        Group {
            if authViewModel.isAuthenticated {
                TabView(selection: $selectedTab) {
                    // Home / Feed
                    FeedView()
                        .tabItem {
                            Label("Home", systemImage: "house")
                        }
                        .tag(0)

                    // Offers
                    OffersView()
                        .tabItem {
                            Label("Ofertas", systemImage: "tag")
                        }
                        .tag(1)

                    // Services
                    ServicesView()
                        .tabItem {
                            Label("Serviços", systemImage: "wrench")
                        }
                        .tag(2)

                    // Community
                    CommunityView()
                        .tabItem {
                            Label("Comunidade", systemImage: "person.3")
                        }
                        .tag(3)

                    // Profile
                    ProfileView(userId: authViewModel.currentUser?.id)
                        .tabItem {
                            Label("Perfil", systemImage: "person")
                        }
                        .tag(4)
                }
            } else {
                LoginView(viewModel: authViewModel)
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
