import SwiftUI

struct ToastMessage {
    let id = UUID()
    let text: String
    let type: ToastType
}

enum ToastType {
    case success
    case error
    case info
    case warning

    var color: Color {
        switch self {
        case .success: return Color.green
        case .error: return Color.red
        case .warning: return Color.orange
        case .info: return Color.blue
        }
    }
}

struct ToastView: View {
    let message: ToastMessage

    var body: some View {
        HStack {
            Image(systemName: iconName)
                .foregroundColor(.white)
            Text(message.text)
                .foregroundColor(.white)
                .font(.system(size: 14, weight: .medium))
            Spacer()
        }
        .padding(12)
        .background(message.type.color)
        .cornerRadius(8)
        .padding(.horizontal, 16)
    }

    var iconName: String {
        switch message.type {
        case .success: return "checkmark.circle.fill"
        case .error: return "xmark.circle.fill"
        case .warning: return "exclamationmark.circle.fill"
        case .info: return "info.circle.fill"
        }
    }
}

class ToastHostModel: ObservableObject {
    @Published var messages: [ToastMessage] = []

    func show(_ text: String, type: ToastType = .info) {
        let msg = ToastMessage(text: text, type: type)
        messages.append(msg)

        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
            self.messages.removeAll { $0.id == msg.id }
        }
    }

    func remove(id: UUID) {
        messages.removeAll { $0.id == id }
    }
}

struct ToastContainerView: View {
    @ObservedObject var toastHost: ToastHostModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(toastHost.messages, id: \.id) { message in
                ToastView(message: message)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .pointerInteractionEnabled(false)
    }
}
