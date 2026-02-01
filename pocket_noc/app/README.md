# Pocket NOC – Mobile App

Flutter mobile application for **O-RAN Fronthaul Network Optimization**. A digital twin dashboard that visualizes topology, capacity, traffic patterns, and supports What-If simulations—aligned with the Nokia hackathon problem statement.

---

## Features

| Feature | Description |
|--------|-------------|
| **Topology view** | Cell-to-link mapping with confidence scores |
| **Correlation heatmap** | Pairwise loss correlation matrix |
| **Traffic sparklines** | Per-link demand over time |
| **Loss correlation over time** | Temporal loss patterns per cell |
| **Link capacity chart** | No-buffer vs buffer-aware capacity, bandwidth savings % |
| **Congestion risk** | Risk scores and levels per link |
| **Root cause attribution** | Congestion events with contributors |
| **Congestion fingerprint** | Link characterization |
| **Action recommendations** | Capacity and topology recommendations |
| **What-If simulator** | Adjust traffic multipliers per cell, see updated capacity and risk |

---

## Requirements

- **Flutter SDK** 3.0+
- **Dart** 3.0+
- **Backend API** (local or hosted on Render)

---

## Quick Start

### 1. Install dependencies

```bash
cd pocket_noc/app
flutter pub get
```

### 2. Run the app

```bash
# Default device (connected phone, emulator, or browser)
flutter run

# Web
flutter run -d chrome

# Android emulator
flutter run -d android

# iOS simulator (macOS only)
flutter run -d ios
```

### 3. Configure API URL

The app uses `https://o-ran-fronthaul.onrender.com` by default (cloud backend).

- **Local backend:** Start the FastAPI server, then build with:
  ```bash
  flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
  ```
- **Android emulator:** Use `http://10.0.2.2:8000` instead of `127.0.0.1`
- **Physical device:** Use your machine's LAN IP, e.g. `http://192.168.1.5:8000`

---

## Build

### Web

```bash
flutter build web
# Optional: use custom API URL
flutter build web --dart-define=API_BASE_URL=https://your-api.onrender.com
```

Output: `build/web/` — deploy to any static host (Vercel, Netlify, GitHub Pages).

### Android APK

```bash
flutter build apk --release
```

**If the app shows "Demo" mode**, your Render URL may differ. Get the exact URL from the Render dashboard, then:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://YOUR-ACTUAL-URL.onrender.com
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

### Android App Bundle (Play Store)

```bash
flutter build appbundle --release
```

### iOS (macOS only)

```bash
flutter build ios --release
```

---

## Project structure

```
app/
├── lib/
│   ├── main.dart              # App entry, MaterialApp setup
│   ├── models/
│   │   └── fronthaul_data.dart # Data models (topology, capacity, risk, etc.)
│   ├── screens/
│   │   ├── dashboard_screen.dart  # Main dashboard with all visualizations
│   │   └── whatif_screen.dart     # What-If traffic simulator
│   ├── services/
│   │   └── api_service.dart       # HTTP client for /results and /simulate
│   ├── theme/
│   │   └── app_theme.dart         # Nokia-style dark theme, colors
│   └── widgets/
│       ├── section_card.dart      # Reusable section container
│       ├── skeleton_loader.dart   # Loading placeholder
│       └── explainer_tooltip.dart # Help tooltips
├── assets/
│   └── results_fallback.json  # Bundled fallback when API unreachable
├── pubspec.yaml
└── README.md
```

---

## API integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/results` | GET | Baseline topology, capacity, traffic, risk, recommendations |
| `/simulate` | POST | What-If: `{"traffic_multipliers": {"7": 1.4}}` → scaled capacity |

**Fallback:** If the API is unreachable (e.g. cold start, offline), the app loads `assets/results_fallback.json` and shows a "Demo" badge. Pull-to-refresh or tap refresh to retry.

**Timeouts:** 60 seconds to allow for Render free-tier cold starts.

---

## What-If simulator

1. Open What-If from the dashboard app bar (tune icon).
2. Set traffic multipliers per cell (e.g. Cell 7: 1.4 = +40%).
3. Use presets: "Cell 7 +40%", "All +20%", "Peak hour".
4. Tap **Simulate** to run the scenario.
5. Compare baseline vs simulated capacity and risk.

The backend supports approximate What-If without raw `.dat` files: capacity is scaled from multipliers using the topology (equal per-cell contribution assumption).

---

## Dependencies

| Package | Use |
|---------|-----|
| `http` | API calls |
| `share_plus` | Share report / simulation result |

---

## Theme

- **Primary:** Nokia cyan `#00A9E0`
- **Background:** Dark `#0A0E14`
- **Success / warning / danger:** Green, amber, red for risk levels

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Demo" badge always shown** | Backend may be cold. Wait 30–60s and pull-to-refresh. |
| **Web: CORS errors** | Ensure backend CORS allows your origin (`*` is fine for development). |
| **Android: Cleartext HTTP blocked** | Use `https://` or add `android:usesCleartextTraffic="true"` in `AndroidManifest.xml` for local dev. |
| **Simulate returns null** | Check backend is reachable; 400 means JSON-only mode with no simulation support (now fixed). |

---

## License

Part of the O-RAN Fronthaul Optimization project.
