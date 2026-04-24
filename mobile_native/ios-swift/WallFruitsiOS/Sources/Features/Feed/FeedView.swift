import SwiftUI

final class FeedViewModel: ObservableObject {
    @Published var posts: [String] = ["WallFruits ready", "Native iOS starter"]

    func refresh() {
        posts = ["Refreshing feed...", "Connected to API client scaffold"]
    }
}

struct FeedView: View {
    @ObservedObject var viewModel: FeedViewModel

    var body: some View {
        NavigationStack {
            List(viewModel.posts, id: \.self) { post in
                Text(post)
            }
            .navigationTitle("WallFruits")
            .toolbar {
                Button("Refresh") {
                    viewModel.refresh()
                }
            }
        }
    }
}
