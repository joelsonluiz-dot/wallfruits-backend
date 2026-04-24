import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = FeedViewModel()

    var body: some View {
        TabView {
            FeedView(viewModel: viewModel)
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
    }
}
