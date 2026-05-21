import PhotosUI
import SwiftUI
import UIKit

struct PremiumFruitFormView: View {
    let onLogout: () -> Void
    let onRefresh: () -> Void

    @State private var photosPickerItem: PhotosPickerItem?
    @State private var stepIndex = 0
    @State private var fruitName = "Manga"
    @State private var variety = "Palmer"
    @State private var quality = "Premium"
    @State private var origin = "Bahia"
    @State private var market = "Exportação"
    @State private var maturity = "Ponto de colheita"
    @State private var farmName = ""
    @State private var farmAddress = ""
    @State private var descriptionText = ""
    @State private var harvestDate = ""
    @State private var reserveStart = ""
    @State private var reserveEnd = ""
    @State private var validityDate = ""
    @State private var minPrice = "R$ 18,00"
    @State private var avgPrice = "R$ 22,00"
    @State private var maxPrice = "R$ 29,00"
    @State private var pricePerKg = "R$ 4,20"
    @State private var pricePerBox = "R$ 42,00"
    @State private var weightBox = "18"
    @State private var availableQuantity = "420"
    @State private var minBoxes = 12
    @State private var minFruitUnits = 48
    @State private var selectedCertifications: Set<String> = ["Global GAP", "Orgânico"]
    @State private var selectedImage: UIImage?
    @State private var selectedImageSize = "0 B"
    @State private var imageName = "Imagem principal ainda não enviada"
    @State private var isUploading = false
    @State private var publishState: PublishState = .idle
    @State private var showImagePicker = false
    @State private var imageSource: UIImagePickerController.SourceType = .photoLibrary
    @State private var showConfetti = false

    private let certifications = [
        "Global GAP",
        "Orgânico",
        "Fair Trade",
        "Bonsucro",
        "RainForest Alliance",
        "UTZ Certified",
        "ISO 14001",
    ]

    private let fruits: [(name: String, varieties: [String], qualities: [String])] = [
        ("Manga", ["Palmer", "Tommy", "Kent", "Haden"], ["Premium", "Seleção A", "Exportação"]),
        ("Banana", ["Prata", "Nanica", "Maçã", "Ouro"], ["Prime", "Mercado interno", "Madura"]),
        ("Uva", ["Thompson", "BRS Vitória", "Crimson", "Italia"], ["Premium", "Sem semente", "Mesa"]),
        ("Maçã", ["Gala", "Fuji", "Pink Lady", "Sundowner"], ["Classe 1", "Top export", "Selecionada"]),
        ("Laranja", ["Pera", "Valencia", "Lima", "Bahia"], ["Suco", "Mesa", "Brix alto"]),
    ]

    private let origins = ["São Paulo", "Minas Gerais", "Bahia", "Pernambuco", "Goiás", "Paraná"]
    private let markets = ["Hortifruti premium", "Atacado", "Supermercado", "Exportação", "Restaurantes"]
    private let maturities = ["Verde", "Ponto de colheita", "Madura", "Pronta para despacho"]

    private var availableVarieties: [String] {
        fruits.first(where: { $0.name == fruitName })?.varieties ?? fruits[0].varieties
    }

    private var availableQualities: [String] {
        fruits.first(where: { $0.name == fruitName })?.qualities ?? fruits[0].qualities
    }

    private var completion: Double { Double(stepIndex + 1) / 9.0 }

    private var summaryPriceSpread: String {
        let min = currencyValue(minPrice)
        let max = currencyValue(maxPrice)
        guard min > 0, max > 0 else { return "Defina a faixa de preço." }
        let spread = max - min
        return spread > 0 ? "Amplitude de \(spread.formattedCurrency)." : "Faixa coerente e estável."
    }

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color.wfDarkBackground, Color.wfDeepSurface, Color.wfDarkBackground],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    heroCard
                    progressCard
                    stepChips
                    sectionUpload
                    sectionPrices
                    sectionProduct
                    sectionCertifications
                    sectionLogistics
                    sectionDates
                    sectionProperty
                    sectionQuantity
                    sectionFinalize
                }
                .padding(16)
                .padding(.bottom, 28)
            }
            .overlay(alignment: .topTrailing) {
                if showConfetti {
                    ConfettiOverlay()
                        .allowsHitTesting(false)
                        .transition(.opacity)
                }
            }
        }
    }

    private var heroCard: some View {
        premiumCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("WallFruits Studio")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Color.wfSoftNeon)
                    .textCase(.uppercase)
                Text("Cadastro premium de frutas e produtos agrícolas")
                    .font(.system(size: 30, weight: .black, design: .rounded))
                    .foregroundStyle(.white)
                Text("Experiência nativa com aparência cinematográfica, validação instantânea e foco em conversão.")
                    .foregroundStyle(Color.wfMutedText)
                HStack(spacing: 8) {
                    premiumBadge("GPU first")
                    premiumBadge("Glass blur")
                    premiumBadge("60 FPS")
                    premiumBadge("Auto validate")
                }
            }
        }
    }

    private var progressCard: some View {
        premiumCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Progresso")
                        .foregroundStyle(.white)
                        .font(.headline)
                    Spacer()
                    Text("\(Int(completion * 100))%")
                        .foregroundStyle(Color.wfSoftNeon)
                        .font(.headline.weight(.bold))
                }
                GeometryReader { proxy in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 999, style: .continuous)
                            .fill(Color.white.opacity(0.08))
                            .frame(height: 10)
                        RoundedRectangle(cornerRadius: 999, style: .continuous)
                            .fill(
                                LinearGradient(
                                    colors: [Color.wfPrimary, Color.wfSecondary, Color.wfCyan],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(width: proxy.size.width * completion, height: 10)
                    }
                }
                .frame(height: 10)
            }
        }
    }

    private var stepChips: some View {
        let steps = ["Imagem", "Preços", "Produto", "Certificações", "Logística", "Datas", "Propriedade", "Quantidade", "Final"]
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                    ForEach(Array(steps.enumerated()), id: \.offset) { index, title in
                    Button {
                        stepIndex = index
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(index + 1)")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(.white)
                            Text(title)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white)
                        }
                        .padding(.vertical, 12)
                        .padding(.horizontal, 14)
                        .background(stepIndex == index ? Color.wfPrimary.opacity(0.24) : Color.white.opacity(0.04))
                        .overlay(
                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                .stroke(stepIndex == index ? Color.wfPrimary.opacity(0.6) : Color.white.opacity(0.08), lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var sectionUpload: some View {
        premiumSection(title: "Upload de imagem", subtitle: "Upload, câmera, preview e compressão automática") {
            HStack(spacing: 10) {
                Button("Selecionar imagem") {
                    imageSource = .photoLibrary
                    showImagePicker = true
                }
                .buttonStyle(.borderedProminent)

                Button("Abrir câmera") {
                    imageSource = .camera
                    showImagePicker = true
                }
                .buttonStyle(.bordered)
                .disabled(!UIImagePickerController.isSourceTypeAvailable(.camera))
            }

            if isUploading {
                HStack(spacing: 12) {
                    ProgressView()
                        .tint(Color.wfPrimary)
                    Text("Otimizando imagem...")
                        .foregroundStyle(Color.wfMutedText)
                }
            } else if let image = selectedImage {
                VStack(alignment: .leading, spacing: 8) {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .frame(maxWidth: .infinity)
                        .frame(height: 220)
                        .clipped()
                        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                    Text(imageName)
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text("Imagem otimizada · \(selectedImageSize)")
                        .foregroundStyle(Color.wfMutedText)
                }
            } else {
                Text("Toque para abrir a câmera ou escolher do dispositivo.")
                    .foregroundStyle(Color.wfMutedText)
            }

            PhotosPicker(selection: $photosPickerItem, matching: .images) {
                Text("Importar da galeria")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .sheet(isPresented: $showImagePicker) {
            UIKitImagePicker(sourceType: imageSource) { image in
                processPickedImage(image)
            }
        }
        .onChange(of: photosPickerItem) { _, newValue in
            guard let newValue else { return }
            Task {
                isUploading = true
                if let data = try? await newValue.loadTransferable(type: Data.self), let uiImage = UIImage(data: data) {
                    processPickedImage(uiImage)
                }
                isUploading = false
            }
        }
    }

    private var sectionPrices: some View {
        premiumSection(title: "Preços", subtitle: "Máscara monetária e validação em tempo real") {
            premiumCurrencyField("Preço mínimo", text: $minPrice)
            premiumCurrencyField("Preço médio", text: $avgPrice)
            premiumCurrencyField("Preço máximo", text: $maxPrice)
            premiumCurrencyField("Preço por kg", text: $pricePerKg)
            premiumCurrencyField("Preço por caixa", text: $pricePerBox)
            Text(summaryPriceSpread)
                .foregroundStyle(Color.wfSoftNeon)
                .font(.caption.weight(.semibold))
        }
    }

    private var sectionProduct: some View {
        premiumSection(title: "Produto", subtitle: "Nome, variedade e qualidade") {
            premiumMenu(label: "Nome da fruta", selection: $fruitName, options: fruits.map(\.name))
            premiumMenu(label: "Variedade", selection: $variety, options: availableVarieties)
            premiumMenu(label: "Qualidade", selection: $quality, options: availableQualities)
            HStack(spacing: 8) {
                premiumPill(fruitName)
                premiumPill(variety)
                premiumPill(quality)
            }
        }
    }

    private var sectionCertifications: some View {
        premiumSection(title: "Certificações", subtitle: "Multi select premium") {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 130), spacing: 8)], spacing: 8) {
                ForEach(certifications, id: \.self) { certification in
                    let active = selectedCertifications.contains(certification)
                    Button {
                        if active { selectedCertifications.remove(certification) } else { selectedCertifications.insert(certification) }
                    } label: {
                        Text(certification)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(active ? .white : Color.wfMutedText)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 12)
                            .frame(maxWidth: .infinity)
                            .background(active ? Color.wfPrimary.opacity(0.25) : Color.white.opacity(0.04))
                            .overlay(
                                RoundedRectangle(cornerRadius: 16, style: .continuous)
                                    .stroke(active ? Color.wfPrimary.opacity(0.55) : Color.white.opacity(0.08), lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var sectionLogistics: some View {
        premiumSection(title: "Logística", subtitle: "Origem, mercado, maturação e estoque") {
            premiumMenu(label: "Origem", selection: $origin, options: origins)
            premiumMenu(label: "Mercado de venda", selection: $market, options: markets)
            premiumMenu(label: "Grau de maturação", selection: $maturity, options: maturities)
            premiumField("Peso da caixa", text: $weightBox)
            premiumField("Quantidade disponível", text: $availableQuantity)
        }
    }

    private var sectionDates: some View {
        premiumSection(title: "Datas", subtitle: "Seleção inteligente e transições suaves") {
            premiumField("Data da colheita", text: $harvestDate)
            premiumField("Data inicial reserva", text: $reserveStart)
            premiumField("Data final reserva", text: $reserveEnd)
            premiumField("Validade", text: $validityDate)
        }
    }

    private var sectionProperty: some View {
        premiumSection(title: "Propriedade", subtitle: "Multiline inteligente e auto spacing") {
            premiumField("Nome da propriedade", text: $farmName)
            premiumField("Endereço da propriedade", text: $farmAddress)
            TextEditor(text: $descriptionText)
                .frame(minHeight: 120)
                .padding(12)
                .background(Color.wfInput)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(Color.white.opacity(0.08), lineWidth: 1)
                )
        }
    }

    private var sectionQuantity: some View {
        premiumSection(title: "Quantidade", subtitle: "Counter premium e hold increment") {
            HStack(spacing: 10) {
                quantityCounter(title: "Caixas", value: $minBoxes)
                quantityCounter(title: "Fruta", value: $minFruitUnits)
            }
        }
    }

    private var sectionFinalize: some View {
        premiumSection(title: "Finalização", subtitle: "Publicar com loading, sucesso e revisão") {
            VStack(alignment: .leading, spacing: 12) {
                summaryTile(title: "Produto", value: "\(fruitName) · \(variety)", subtitle: quality)
                summaryTile(title: "Precificação", value: "\(minPrice) - \(maxPrice)", subtitle: summaryPriceSpread)
                summaryTile(title: "Certificações", value: "\(selectedCertifications.count)", subtitle: "Selecionadas com chips animados")
                summaryTile(title: "Status", value: publishState.title, subtitle: publishState.subtitle)
            }

            HStack(spacing: 10) {
                Button("Voltar") { stepIndex = max(0, stepIndex - 1) }
                    .buttonStyle(.bordered)
                    .frame(maxWidth: .infinity)
                Button("Próximo") { stepIndex = min(8, stepIndex + 1) }
                    .buttonStyle(.bordered)
                    .frame(maxWidth: .infinity)
                Button(publishState == .loading ? "Publicando..." : "Publicar anúncio") {
                    publish()
                }
                .buttonStyle(.borderedProminent)
                .frame(maxWidth: .infinity)
            }

            Button("Atualizar métricas") {
                onRefresh()
            }
            .buttonStyle(.bordered)
            .frame(maxWidth: .infinity)

            Button(role: .destructive, action: onLogout) {
                Text("Sair")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .overlay(alignment: .topTrailing) {
            if showConfetti {
                ConfettiOverlay()
                    .allowsHitTesting(false)
            }
        }
    }

    @ViewBuilder
    private func premiumSection(title: String, subtitle: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline.weight(.bold))
                    .foregroundStyle(.white)
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(Color.wfMutedText)
            }
            content()
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.wfSurface.opacity(0.86))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .shadow(color: Color.black.opacity(0.32), radius: 24, x: 0, y: 12)
    }

    private func premiumCard(@ViewBuilder content: () -> some View) -> some View {
        content()
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.wfSurface.opacity(0.86))
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
            .shadow(color: Color.black.opacity(0.32), radius: 24, x: 0, y: 12)
    }

    private func premiumBadge(_ label: String) -> some View {
        Text(label)
            .font(.caption2.weight(.bold))
            .foregroundStyle(Color.wfSoftNeon)
            .padding(.vertical, 8)
            .padding(.horizontal, 12)
            .background(Color.wfPrimary.opacity(0.12))
            .overlay(
                RoundedRectangle(cornerRadius: 999, style: .continuous)
                    .stroke(Color.wfPrimary.opacity(0.2), lineWidth: 1)
            )
            .clipShape(Capsule())
    }

    private func premiumPill(_ label: String) -> some View {
        Text(label)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.vertical, 8)
            .padding(.horizontal, 12)
            .background(Color.wfPrimary.opacity(0.16))
            .clipShape(Capsule())
    }

    private func premiumField(_ label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white)
            TextField(label, text: text)
                .textInputAutocapitalization(.never)
                .padding(.vertical, 14)
                .padding(.horizontal, 16)
                .background(Color.wfInput)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(Color.white.opacity(0.08), lineWidth: 1)
                )
        }
    }

    private func premiumCurrencyField(_ label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white)
            TextField(label, text: Binding(
                get: { text.wrappedValue },
                set: { text.wrappedValue = formatCurrency($0) }
            ))
            .keyboardType(.decimalPad)
            .textInputAutocapitalization(.never)
            .padding(.vertical, 14)
            .padding(.horizontal, 16)
            .background(Color.wfInput)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            )
        }
    }

    private func premiumMenu(label: String, selection: Binding<String>, options: [String]) -> some View {
        Menu {
            ForEach(options, id: \.self) { option in
                Button(option) {
                    selection.wrappedValue = option
                }
            }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(label)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white)
                    Text(selection.wrappedValue)
                        .foregroundStyle(.white)
                }
                Spacer()
                Image(systemName: "chevron.down")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(Color.wfMutedText)
            }
            .padding(.vertical, 14)
            .padding(.horizontal, 16)
            .background(Color.wfInput)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            )
        }
    }

    private func quantityCounter(title: String, value: Binding<Int>) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white)
            Stepper(value: value, in: 0...9999) {
                Text("\(value.wrappedValue)")
                    .font(.title2.weight(.black))
                    .foregroundStyle(.white)
            }
            .tint(.wfPrimary)
        }
        .padding(14)
        .frame(maxWidth: .infinity)
        .background(Color.wfInput)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }

    private func summaryTile(title: String, value: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption2.weight(.bold))
                .foregroundStyle(Color.wfMutedText)
            Text(value)
                .font(.headline.weight(.bold))
                .foregroundStyle(.white)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(Color.wfMutedText)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func publish() {
        publishState = .loading
        showConfetti = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            publishState = .success
            onRefresh()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                publishState = .idle
                showConfetti = false
            }
        }
    }

    private func processPickedImage(_ image: UIImage) {
        isUploading = true
        DispatchQueue.global(qos: .userInitiated).async {
            let compressed = image.jpegData(compressionQuality: 0.84)
            let data = compressed ?? image.pngData() ?? Data()
            DispatchQueue.main.async {
                if let finalImage = UIImage(data: data) {
                    selectedImage = finalImage
                }
                selectedImageSize = formatBytes(data.count)
                imageName = "Imagem principal"
                isUploading = false
            }
        }
    }

    private func currencyValue(_ value: String) -> Double {
        let normalized = value
            .replacingOccurrences(of: "R$", with: "")
            .trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: ".", with: "")
            .replacingOccurrences(of: ",", with: ".")
        return Double(normalized) ?? 0
    }
}

private extension String {
    var formattedCurrency: String {
        let normalized = self.replacingOccurrences(of: "R$", with: "")
            .trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: ".", with: "")
            .replacingOccurrences(of: ",", with: ".")
        let value = Double(normalized) ?? 0
        return "R$ \(value, specifier: "%.2f")".replacingOccurrences(of: ".", with: ",")
    }
}

private enum PublishState {
    case idle
    case loading
    case success

    var title: String {
        switch self {
        case .idle: return "Pronto"
        case .loading: return "Publicando..."
        case .success: return "Publicado"
        }
    }

    var subtitle: String {
        switch self {
        case .idle: return "Revisão final antes do envio"
        case .loading: return "Concluindo publicação premium"
        case .success: return "Concluído com animação premium"
        }
    }
}

private struct UIKitImagePicker: UIViewControllerRepresentable {
    let sourceType: UIImagePickerController.SourceType
    let onPick: (UIImage) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = sourceType
        picker.delegate = context.coordinator
        picker.allowsEditing = false
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onPick: onPick) }

    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let onPick: (UIImage) -> Void

        init(onPick: @escaping (UIImage) -> Void) {
            self.onPick = onPick
        }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            if let image = info[.originalImage] as? UIImage {
                onPick(image)
            }
            picker.dismiss(animated: true)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true)
        }
    }
}

private struct ConfettiOverlay: View {
    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let time = timeline.date.timeIntervalSinceReferenceDate
                for index in 0..<18 {
                    let x = CGFloat((index * 37) % Int(size.width))
                    let progress = CGFloat((time * Double(0.3 + Double(index) * 0.03)).truncatingRemainder(dividingBy: 1))
                    let y = -20 + (size.height + 60) * progress
                    let rect = CGRect(x: x, y: y, width: 8, height: 16)
                    context.fill(Path(roundedRect: rect, cornerRadius: 6), with: .color([.wfPrimary, .wfSecondary, .wfCyan, .wfWarning].randomElement() ?? .wfPrimary))
                }
            }
        }
        .ignoresSafeArea()
    }
}