# Running Pocket NOC on Web (Chrome)

## Fix for 10.0.2.2 / ERR_CONNECTION_TIMED_OUT

The app uses `http://127.0.0.1:8000` for the API. If you still see requests to `10.0.2.2`, clear the cache:

```powershell
cd pocket_noc/app
flutter clean
flutter pub get
flutter run -d chrome
```

## Backend must be running

In a **separate terminal**:

```powershell
cd c:\Users\induj\Downloads\net12
python pocket_noc\backend\api.py
```

Wait for "Uvicorn running on http://0.0.0.0:8000", then run the Flutter app.

## Order

1. Start backend first
2. Then run `flutter run -d chrome`
