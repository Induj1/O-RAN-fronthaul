# Deploy Pocket NOC Backend on Render

## Quick Deploy (static mode – no raw data)

1. **Push your repo to GitHub** (ensure `output/results.json` is committed).

2. **Create a new Web Service on Render:**
   - Go to [render.com](https://render.com) → Dashboard → New → Web Service
   - Connect your GitHub repo
   - **Root Directory:** leave empty if `net12` is the repo root; otherwise set to `net12`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements-render.txt`
   - **Start Command:** `uvicorn pocket_noc.backend.api:app --host 0.0.0.0 --port $PORT`

3. **Deploy.** The API will serve precomputed `output/results.json`. What-If simulations are disabled.

---

## Full Deploy (with raw data for simulations)

1. Copy hackathon data into `data/`:
   ```
   net12/data/
   ├── throughput-cell-1.dat
   ├── throughput-cell-2.dat
   ├── ... (all 24 cells)
   ├── pkt-stats-cell-1.dat
   ├── pkt-stats-cell-2.dat
   └── ... (all 24 cells)
   ```

2. In Render Dashboard → Environment, add:
   - `DATA_DIR` = `/opt/render/project/src/data` (or leave unset; defaults to `./data`)

3. Commit and push. Render will build and run with full analysis + simulations.

---

## AI Chat (optional)

To enable the in-app AI assistant, add in Render Dashboard → Environment:

- `OPENAI_API_KEY` = your OpenAI API key (from platform.openai.com)

Without it, the `/chat` endpoint returns 503. The app shows a fallback message.

---

## Connect Flutter App

**Option A – Build with API URL:**
```bash
flutter build web --dart-define=API_BASE_URL=https://YOUR-SERVICE.onrender.com
```

**Option B – Edit** `pocket_noc/app/lib/services/api_service.dart` and change `defaultValue` to your Render URL.

---

## Endpoints

- `GET /` – Redirect to docs
- `GET /health` – Health check
- `GET /results` – Fronthaul results (topology, capacity, risk, etc.)
- `POST /simulate` – What-If simulation (approximate, no .dat required)
- `POST /chat` – AI assistant (requires `OPENAI_API_KEY`)
- `GET /docs` – Swagger UI
