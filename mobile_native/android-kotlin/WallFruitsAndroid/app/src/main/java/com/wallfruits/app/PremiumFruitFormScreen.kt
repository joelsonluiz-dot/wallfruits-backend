package com.wallfruits.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import java.io.ByteArrayOutputStream

private val premiumBackground = Brush.linearGradient(
    colors = listOf(Color(0xFF0B0F1A), Color(0xFF121826), Color(0xFF0B0F1A)),
)

private val premiumGradient = Brush.linearGradient(
    colors = listOf(Color(0xFF6C63FF), Color(0xFF8B5CF6), Color(0xFF00D4FF)),
)

private val fruitCatalog = listOf(
    Triple("Manga", listOf("Palmer", "Tommy", "Kent", "Haden"), listOf("Premium", "Seleção A", "Exportação")),
    Triple("Banana", listOf("Prata", "Nanica", "Maçã", "Ouro"), listOf("Prime", "Mercado interno", "Madura")),
    Triple("Uva", listOf("Thompson", "BRS Vitória", "Crimson", "Italia"), listOf("Premium", "Sem semente", "Mesa")),
    Triple("Maçã", listOf("Gala", "Fuji", "Pink Lady", "Sundowner"), listOf("Classe 1", "Top export", "Selecionada")),
    Triple("Laranja", listOf("Pera", "Valencia", "Lima", "Bahia"), listOf("Suco", "Mesa", "Brix alto")),
)

private val certifications = listOf(
    "Global GAP",
    "Orgânico",
    "Fair Trade",
    "Bonsucro",
    "RainForest Alliance",
    "UTZ Certified",
    "ISO 14001",
)

private val origins = listOf("São Paulo", "Minas Gerais", "Bahia", "Pernambuco", "Goiás", "Paraná")
private val markets = listOf("Hortifruti premium", "Atacado", "Supermercado", "Exportação", "Restaurantes")
private val maturities = listOf("Verde", "Ponto de colheita", "Madura", "Pronta para despacho")

private fun formatCurrency(rawValue: String): String {
    val digits = rawValue.filter(Char::isDigit)
    if (digits.isEmpty()) return ""
    val normalized = digits.toLongOrNull()?.div(100.0) ?: 0.0
    return "R$ ${"%,.2f".format(normalized).replace(',', '#').replace('.', ',').replace('#', '.')}"
}

private fun formatBytes(bytes: Int): String = when {
    bytes < 1024 -> "$bytes B"
    bytes < 1024 * 1024 -> "${String.format("%.1f", bytes / 1024.0)} KB"
    else -> "${String.format("%.1f", bytes / (1024.0 * 1024.0))} MB"
}

private fun compressBitmap(bitmap: Bitmap): Pair<ImageBitmap, String> {
    val output = ByteArrayOutputStream()
    bitmap.compress(Bitmap.CompressFormat.JPEG, 84, output)
    val bytes = output.toByteArray()
    return BitmapFactory.decodeByteArray(bytes, 0, bytes.size).asImageBitmap() to formatBytes(bytes.size)
}

private data class PremiumFruitState(
    val fruitName: String = "Manga",
    val variety: String = "Palmer",
    val quality: String = "Premium",
    val origin: String = "Bahia",
    val market: String = "Exportação",
    val maturity: String = "Ponto de colheita",
    val farmName: String = "",
    val farmAddress: String = "",
    val description: String = "",
    val harvestDate: String = "",
    val reserveStart: String = "",
    val reserveEnd: String = "",
    val validityDate: String = "",
    val minPrice: String = "R$ 18,00",
    val avgPrice: String = "R$ 22,00",
    val maxPrice: String = "R$ 29,00",
    val pricePerKg: String = "R$ 4,20",
    val pricePerBox: String = "R$ 42,00",
    val weightBox: String = "18",
    val availableQuantity: String = "420",
    val minBoxes: Int = 12,
    val minFruitUnits: Int = 48,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PremiumFruitFormScreen(
    onLogout: () -> Unit,
    onRefresh: () -> Unit,
) {
    var state by remember { mutableStateOf(PremiumFruitState()) }
    var selectedCertifications by remember { mutableStateOf(listOf("Global GAP", "Orgânico")) }
    var selectedImage by remember { mutableStateOf<ImageBitmap?>(null) }
    var selectedImageSize by remember { mutableStateOf("0 B") }
    var imageName by remember { mutableStateOf("Imagem principal ainda não enviada") }
    var isUploading by remember { mutableStateOf(false) }
    var isPublished by remember { mutableStateOf(false) }
    var stepIndex by remember { mutableStateOf(0) }
    val scrollScope = rememberCoroutineScope()

    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            isUploading = true
            val context = LocalContext.current
            val inputStream = context.contentResolver.openInputStream(uri)
            val bitmap = inputStream?.use(BitmapFactory::decodeStream)
            if (bitmap != null) {
                val compressed = compressBitmap(bitmap)
                selectedImage = compressed.first
                selectedImageSize = compressed.second
                imageName = uri.lastPathSegment ?: "Imagem principal"
            }
            isUploading = false
        }
    }

    val cameraPicker = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap ->
        bitmap?.let {
            val compressed = compressBitmap(it)
            selectedImage = compressed.first
            selectedImageSize = compressed.second
            imageName = "Foto da câmera"
        }
    }

    val currentOptions = fruitCatalog.firstOrNull { it.first == state.fruitName }
    val availableVarieties = currentOptions?.second ?: fruitCatalog.first().second
    val availableQualities = currentOptions?.third ?: fruitCatalog.first().third

    LaunchedEffect(state.fruitName) {
        if (state.variety !in availableVarieties) state = state.copy(variety = availableVarieties.first())
        if (state.quality !in availableQualities) state = state.copy(quality = availableQualities.first())
    }

    val completion = ((stepIndex + 1) * 100) / 9

    MaterialTheme(colorScheme = MaterialTheme.colorScheme.copy(background = Color(0xFF0B0F1A), surface = Color(0xFF121826))) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(premiumBackground),
        ) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                item {
                    Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = Color(0xFF121826)),
                            shape = RoundedCornerShape(28.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 10.dp),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                                Text("WallFruits Studio", color = Color(0xFFD9D6FF), style = MaterialTheme.typography.labelMedium)
                                Text("Cadastro premium de frutas e produtos agrícolas", style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.Black), color = Color.White)
                                Text("Experiência nativa com visual cinematográfico, states refinados e fluxo em etapas.", color = Color(0xFFB8C1D9))
                                Box(modifier = Modifier
                                    .fillMaxWidth()
                                    .height(10.dp)
                                    .background(Color.White.copy(alpha = 0.08), RoundedCornerShape(999.dp))) {
                                    Box(modifier = Modifier
                                        .fillMaxWidth(completion / 100f)
                                        .height(10.dp)
                                        .background(premiumGradient, RoundedCornerShape(999.dp)))
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                                    listOf("GPU first", "Glass blur", "60 FPS", "Auto validate").forEach { label ->
                                        AssistChip(onClick = {}, label = { Text(label) })
                                    }
                                }
                            }
                        }

                        PremiumSection(title = "Upload de imagem", subtitle = "Upload, câmera, preview e compressão automática") {
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                                Button(onClick = { imagePicker.launch("image/*") }, modifier = Modifier.weight(1f)) { Text("Selecionar imagem") }
                                Button(onClick = { cameraPicker.launch(null) }, modifier = Modifier.weight(1f)) { Text("Abrir câmera") }
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            if (isUploading) {
                                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                                    CircularProgressIndicator(color = Color(0xFF6C63FF), modifier = Modifier.size(28.dp))
                                    Text("Otimizando imagem...", color = Color(0xFFB8C1D9))
                                }
                            } else if (selectedImage != null) {
                                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF1A2235))) {
                                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Image(bitmap = selectedImage!!, contentDescription = null, modifier = Modifier.fillMaxWidth().height(220.dp), contentScale = ContentScale.Crop)
                                        Text(imageName, color = Color.White, fontWeight = FontWeight.SemiBold)
                                        Text("Imagem otimizada · $selectedImageSize", color = Color(0xFFB8C1D9))
                                    }
                                }
                            } else {
                                Text("Toque para abrir a câmera ou escolher do dispositivo.", color = Color(0xFFB8C1D9))
                            }
                        }

                        PremiumSection(title = "Preços", subtitle = "Máscara monetária inteligente e validação em tempo real") {
                            PremiumTextField("Preço mínimo", state.minPrice, { state = state.copy(minPrice = formatCurrency(it)) }, KeyboardType.Decimal)
                            PremiumTextField("Preço médio", state.avgPrice, { state = state.copy(avgPrice = formatCurrency(it)) }, KeyboardType.Decimal)
                            PremiumTextField("Preço máximo", state.maxPrice, { state = state.copy(maxPrice = formatCurrency(it)) }, KeyboardType.Decimal)
                            PremiumTextField("Preço por kg", state.pricePerKg, { state = state.copy(pricePerKg = formatCurrency(it)) }, KeyboardType.Decimal)
                            PremiumTextField("Preço por caixa", state.pricePerBox, { state = state.copy(pricePerBox = formatCurrency(it)) }, KeyboardType.Decimal)
                        }

                        PremiumSection(title = "Produto", subtitle = "Nome, variedade e qualidade") {
                            PremiumDropdown("Nome da fruta", state.fruitName, fruitCatalog.map { it.first }) { state = state.copy(fruitName = it) }
                            PremiumDropdown("Variedade", state.variety, availableVarieties) { state = state.copy(variety = it) }
                            PremiumDropdown("Qualidade", state.quality, availableQualities) { state = state.copy(quality = it) }
                        }

                        PremiumSection(title = "Certificações", subtitle = "Multi select premium e popup blur") {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                                certifications.forEach { cert ->
                                    FilterChip(selected = true, onClick = { selectedCertifications = selectedCertifications.filterNot { it == cert } }, label = { Text(cert) })
                                }
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            certifications.chunked(2).forEach { rowItems ->
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                                    rowItems.forEach { cert ->
                                        FilterChip(
                                            selected = cert in selectedCertifications,
                                            onClick = {
                                                selectedCertifications = if (cert in selectedCertifications) selectedCertifications - cert else selectedCertifications + cert
                                            },
                                            label = { Text(cert) },
                                            modifier = Modifier.weight(1f),
                                        )
                                    }
                                }
                            }
                        }

                        PremiumSection(title = "Logística", subtitle = "Origem, mercado, maturação e validade") {
                            PremiumDropdown("Origem", state.origin, origins) { state = state.copy(origin = it) }
                            PremiumDropdown("Mercado de venda", state.market, markets) { state = state.copy(market = it) }
                            PremiumDropdown("Grau de maturação", state.maturity, maturities) { state = state.copy(maturity = it) }
                            PremiumTextField("Peso da caixa", state.weightBox, { state = state.copy(weightBox = it) }, KeyboardType.Number)
                            PremiumTextField("Quantidade disponível", state.availableQuantity, { state = state.copy(availableQuantity = it) }, KeyboardType.Number)
                        }

                        PremiumSection(title = "Datas", subtitle = "Seleção inteligente e transições suaves") {
                            PremiumTextField("Data da colheita", state.harvestDate, { state = state.copy(harvestDate = it) })
                            PremiumTextField("Data inicial reserva", state.reserveStart, { state = state.copy(reserveStart = it) })
                            PremiumTextField("Data final reserva", state.reserveEnd, { state = state.copy(reserveEnd = it) })
                            PremiumTextField("Validade", state.validityDate, { state = state.copy(validityDate = it) })
                        }

                        PremiumSection(title = "Propriedade", subtitle = "Campo multiline com auto spacing") {
                            PremiumTextField("Nome da propriedade", state.farmName, { state = state.copy(farmName = it) })
                            PremiumTextField("Endereço da propriedade", state.farmAddress, { state = state.copy(farmAddress = it) })
                            OutlinedTextField(
                                value = state.description,
                                onValueChange = { state = state.copy(description = it) },
                                modifier = Modifier.fillMaxWidth(),
                                label = { Text("Descrição do produto") },
                                minLines = 4,
                            )
                        }

                        PremiumSection(title = "Quantidade", subtitle = "Counter premium e hold increment") {
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                                CounterControl(label = "Caixas", value = state.minBoxes, modifier = Modifier.weight(1f), onChange = { state = state.copy(minBoxes = it) })
                                CounterControl(label = "Fruta", value = state.minFruitUnits, modifier = Modifier.weight(1f), onChange = { state = state.copy(minFruitUnits = it) })
                            }
                        }

                        PremiumSection(title = "Finalização", subtitle = "Publicar com loading, sucesso e revisão") {
                            Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF1A2235))) {
                                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("${state.fruitName} · ${state.variety}", color = Color.White, fontWeight = FontWeight.Bold)
                                    Text("${state.minPrice} - ${state.maxPrice}", color = Color(0xFFB8C1D9))
                                    Text("Certificações: ${selectedCertifications.size}", color = Color(0xFFB8C1D9))
                                    Text(if (isPublished) "Publicado" else "Pronto para publicar", color = Color(0xFF00D4FF))
                                }
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                                TextButton(onClick = { stepIndex = maxOf(0, stepIndex - 1) }, modifier = Modifier.weight(1f)) { Text("Voltar") }
                                TextButton(onClick = { stepIndex = minOf(8, stepIndex + 1) }, modifier = Modifier.weight(1f)) { Text("Próximo") }
                                Button(
                                    onClick = {
                                        isPublished = true
                                        onRefresh()
                                        scrollScope.launch {
                                            delay(1800)
                                            isPublished = false
                                        }
                                    },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6C63FF)),
                                ) { Text(if (isPublished) "Publicando..." else "Publicar anúncio") }
                            }
                            Button(onClick = onLogout, modifier = Modifier.fillMaxWidth()) { Text("Sair") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PremiumSection(title: String, subtitle: String, content: @Composable Column.() -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFF121826)),
        shape = RoundedCornerShape(28.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
        Column(modifier = Modifier.padding(horizontal = 18.dp, vertical = 0.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold), color = Color.White)
            Text(subtitle, color = Color(0xFFB8C1D9))
        }
    }
}

@Composable
private fun PremiumTextField(label: String, value: String, onValueChange: (String) -> Unit, keyboardType: KeyboardType = KeyboardType.Text) {
    OutlinedTextField(
        modifier = Modifier.fillMaxWidth(),
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        singleLine = true,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PremiumDropdown(label: String, selected: String, options: List<String>, onSelected: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    androidx.compose.material3.ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth().menuAnchor(),
            value = selected,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { androidx.compose.material3.ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
        )
        androidx.compose.material3.ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                androidx.compose.material3.DropdownMenuItem(text = { Text(option) }, onClick = {
                    onSelected(option)
                    expanded = false
                })
            }
        }
    }
}

@Composable
private fun CounterControl(label: String, value: Int, modifier: Modifier = Modifier, onChange: (Int) -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF1A2235)), modifier = modifier) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, color = Color(0xFFD9D6FF), style = MaterialTheme.typography.labelMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = { onChange((value - 1).coerceAtLeast(0)) }, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) { Text("−") }
                Text(value.toString(), color = Color.White, style = MaterialTheme.typography.headlineMedium)
                Button(onClick = { onChange(value + 1) }, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) { Text("+") }
            }
        }
    }
}