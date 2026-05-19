#!/usr/bin/env python3
"""Export design tokens to platform artifacts: CSS, Android colors.xml, iOS Swift file."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "design" / "tokens.json"

def load_tokens():
    with open(TOKENS, "r", encoding="utf-8") as f:
        return json.load(f)

def write_css(tokens):
    out = ROOT / "desktop-web" / "src" / "styles"
    out.mkdir(parents=True, exist_ok=True)
    css = [":root {\n"]
    for k,v in tokens.get("colors", {}).items():
        css.append(f"  --color-{k}: {v};\n")
    css.append(f"  --font-family: {tokens['typography']['fontFamily']};\n")
    for k,v in tokens.get("spacing", {}).items():
        css.append(f"  --space-{k}: {v}px;\n")
    for k,v in tokens.get("radius", {}).items():
        css.append(f"  --radius-{k}: {v}px;\n")
    css.append("}\n")
    (out / "tokens.css").write_text(''.join(css), encoding='utf-8')

def write_android(tokens):
    out = ROOT / "mobile_native" / "android-kotlin" / "WallFruitsAndroid" / "app" / "src" / "main" / "res" / "values"
    out.mkdir(parents=True, exist_ok=True)
    parts = ["<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<resources>\n"]
    for k,v in tokens.get("colors", {}).items():
        parts.append(f"  <color name=\"color_{k}\">{v}</color>\n")
    parts.append("</resources>\n")
    (out / "colors_tokens.xml").write_text(''.join(parts), encoding='utf-8')

def write_ios(tokens):
    out = ROOT / "mobile_native" / "ios-swift" / "WallFruitsiOS" / "Sources" / "Design"
    out.mkdir(parents=True, exist_ok=True)
    sw = ["import SwiftUI\n\n"]
    sw.append("extension Color {\n")
    sw.append("    init(hex: String) {\n")
    sw.append("        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)\n")
    sw.append("        var int: UInt64 = 0\n")
    sw.append("        Scanner(string: hex).scanHexInt64(&int)\n")
    sw.append("        let r, g, b, a: UInt64\n")
    sw.append("        switch hex.count {\n")
    sw.append("        case 3: (r, g, b, a) = ((int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17, 255)\n")
    sw.append("        case 6: (r, g, b, a) = (int >> 16, int >> 8 & 0xFF, int & 0xFF, 255)\n")
    sw.append("        case 8: (r, g, b, a) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)\n")
    sw.append("        default: (r, g, b, a) = (0,0,0,255)\n")
    sw.append("        }\n")
    sw.append("        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, opacity: Double(a) / 255)\n")
    sw.append("    }\n\n")
    for k,v in tokens.get("colors", {}).items():
        hex = v.lstrip('#')
        sw.append(f"    static let {k} = Color(hex: \"{hex}\")\n")
    sw.append("}\n")
    (out / "Colors.swift").write_text(''.join(sw), encoding='utf-8')

def main():
    tokens = load_tokens()
    write_css(tokens)
    write_android(tokens)
    write_ios(tokens)
    print("Export complete: CSS, Android colors, iOS Colors.swift")

if __name__ == '__main__':
    main()
