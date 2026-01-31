# Pocket NOC - Fronthaul Digital Twin + Decision Engine

Mobile app that acts as a live digital twin of the fronthaul network and proactively recommends capacity and topology actions.

## Architecture

```
net12/                    # Python pipeline (topology, capacity)
pocket_noc/
  backend/                # FastAPI - what-if simulations
  app/                    # Flutter app - dashboard + what-if UI
```

## Quick Start

### 1. Start the backend

```bash
cd net12
pip install -r requirements.txt
pip install fastapi uvicorn

cd pocket_noc/backend
# Ensure net12/config.py DATA_DIR points to your data
python api.py
# API runs at http://localhost:8000
```

### 2. Run the Flutter app

```bash
cd pocket_noc/app

# If Flutter project not initialized:
flutter create . --project-name pocket_noc

flutter pub get
flutter run
# For web: flutter run -d chrome
# For Android emulator: flutter run -d android
```

### 3. API base URL

- **Web:** Use `http://localhost:8000` (edit `lib/services/api_service.dart`)
- **Android emulator:** `http://10.0.2.2:8000` (default)
- **Physical device:** Use your machine's IP, e.g. `http://192.168.1.x:8000`

## Features

- **Dashboard:** Topology, capacity, risk scores, action recommendations
- **What-If Simulator:** Adjust traffic multipliers per cell (e.g. Cell 7 +40%) and see updated capacity, risk, and recommendations

## API Endpoints

- `GET /results` - Baseline topology, capacity, risk, recommendations
- `POST /simulate` - Body: `{"traffic_multipliers": {"7": 1.4}}` - Run what-if
