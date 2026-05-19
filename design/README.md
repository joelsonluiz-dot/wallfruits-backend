Design tokens and usage

How to use
- `design/tokens.json` is the canonical source of truth for colors, spacing, typography and radii.
- Use `scripts/export_tokens.py` to generate platform artifacts:
  - `desktop-web/src/styles/tokens.css`
  - `mobile_native/android-kotlin/.../res/values/colors_tokens.xml`
  - `mobile_native/ios-swift/WallFruitsiOS/Sources/Design/Colors.swift`

Run:

```bash
python scripts/export_tokens.py
```

Then import the generated tokens in each platform's theme.
