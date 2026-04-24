import SwiftUI

struct ContentView: View {
    @StateObject private var authViewModel = AuthViewModel()

    var body: some View {
        Group {
            if authViewModel.isAuthenticated {
                TabView {
                    FeedView(viewModel: FeedViewModel())
                        .tabItem {
                            Label("Feed", systemImage: "play.rectangle.fill")
                        }

                    Text("Marketplace")
                        .tabItem {
                            Label("Market", systemImage: "bag.fill")
                        }

                    Text("AI Lab")
                        .tabItem {
                            Label("AI", systemImage: "sparkles")
                        }
                }
            } else {
                LoginView(viewModel: authViewModel)
            }
        }
    }
}
