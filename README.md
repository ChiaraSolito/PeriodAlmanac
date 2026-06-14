# poc_cycle

A minimal Python backend for training and serving a simple time series model using FastAPI.

## Features

- `POST /train`: train a linear regression time series model using lag features
- `POST /predict`: make recursive forecasts from recent values
- `POST /analyze`: compute basic statistics and trend/seasonality hints
- `GET /health`: check service status

## Setup

1. Create a Python environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

## Example requests

### Train

```bash
curl -X POST http://127.0.0.1:8000/train \
  -H "Content-Type: application/json" \
  -d '{"data": [10, 11, 13, 12, 14, 15, 16], "window": 3}'
```

### Predict

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"recent_data": [12, 14, 15], "horizon": 3}'
```

### Analyze

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"data": [10, 11, 13, 12, 14, 15, 16]}'
```
