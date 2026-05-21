import SwiftUI

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r, g, b, a: UInt64
        switch hex.count {
        case 3: (r, g, b, a) = ((int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17, 255)
        case 6: (r, g, b, a) = (int >> 16, int >> 8 & 0xFF, int & 0xFF, 255)
        case 8: (r, g, b, a) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (r, g, b, a) = (0,0,0,255)
        }
        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, opacity: Double(a) / 255)
    }

    static let wfPrimary = Color(hex: "6C63FF")
    static let wfPrimaryVariant = Color(hex: "8B5CF6")
    static let wfSecondary = Color(hex: "00D4FF")
    static let wfBackground = Color(hex: "0B0F1A")
    static let wfSurface = Color(hex: "121826")
    static let wfText = Color(hex: "FFFFFF")
    static let wfMuted = Color(hex: "B8C1D9")
    static let wfSuccess = Color(hex: "16A34A")
    static let wfError = Color(hex: "DC2626")
    static let wfWarning = Color(hex: "F59E0B")
    static let wfDarkBackground = Color(hex: "0B0F1A")
    static let wfDeepSurface = Color(hex: "0F1624")
    static let wfMutedText = Color(hex: "B8C1D9")
    static let wfSoftNeon = Color(hex: "D9D6FF")
    static let wfCyan = Color(hex: "00D4FF")
    static let wfInput = Color(hex: "1A2235")
}
