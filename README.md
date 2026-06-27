# poc_cycle

A FastAPI backend for training and serving a time series forecasting model with lag features. Designed for predicting menstrual cycle durations using historical cycle data.

## Project Structure

```
poc_cycle/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization & startup events
│   ├── model.py             # TimeSeriesModel with lag feature engineering
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── api/
│   │   └── v1/
│   │       └── endpoints.py # API endpoints (train, predict, analyze, log, health)
├── data/
│   ├── cycles_with_durations.csv    # Training data
│   └── ...
├── notebooks/
│   └── data_analysis.ipynb
├── requirements.txt
└── README.md
```

## Features

- **Lag Feature Engineering**: Automatically creates `lag_1`, `lag_2`, ..., `lag_window` features from time series data
- **Linear Regression Model**: Trains on lagged features to forecast future values
- **Recursive Forecasting**: Makes multi-step predictions by feeding predictions back into the model
- **Statistical Analysis**: Computes mean, std, trend, and seasonality estimates
- **Model Persistence**: Saves/loads trained models using joblib
- **REST API**: All functionality exposed via FastAPI endpoints

## Setup

1. Create and activate a Python environment:

   ```powershell
   cd c:...\poc_cycle
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Start the API server:

   ```powershell
   uvicorn app.main:app --reload
   ```

   The server will start at `http://127.0.0.1:8000`

3. View interactive API docs:

   - **Swagger UI**: http://127.0.0.1:8000/docs
   - **ReDoc**: http://127.0.0.1:8000/redoc

## API Endpoints

### `GET /health`
Check service status.

**Response:**
```json
{
  "status": "ok"
}
```

### `POST /train`
Train the time series model on loaded data using specified window size for lag features.

**Request:**
```json
{}
```

**Response:**
```json
{
  "success": true,
  "samples": 150,
  "window": 5,
  "rmse": 2.34,
  "message": "Model trained successfully."
}
```

### `POST /predict`
Make recursive forecasts from recent data.

**Request:**
```json
{
  "recent_data": [28, 30, 27, 29, 31],
  "horizon": 3
}
```

**Response:**
```json
{
  "success": true,
  "predictions": [29.2, 28.8, 29.5],
  "message": "Forecast complete."
}
```

### `POST /analyze`
Compute statistical analysis of time series data (mean, std, trend, seasonality).

**Request:**
```json
{
  "data": [28, 30, 27, 29, 31, 32, 28, 29]
}
```

**Response:**
```json
{
  "success": true,
  "mean": 29.25,
  "std": 1.58,
  "trend": "increasing",
  "seasonality": "moderate",
  "message": "Analysis complete."
}
```

### `POST /log`
Log and analyze cycle data (alias for `/analyze` with different schema).

**Request:**
```json
{
  "data": [28, 30, 27, 29, 31]
}
```

**Response:**
```json
{
  "success": true,
  "mean": 29.0,
  "std": 1.41,
  "trend": "flat",
  "seasonality": "weak",
  "message": "Analysis complete."
}
```

## Example Usage

```python
import requests

BASE_URL = "http://127.0.0.1:8000"

# Train model
train_response = requests.post(f"{BASE_URL}/train")
print(train_response.json())

# Make predictions
pred_response = requests.post(
    f"{BASE_URL}/predict",
    json={"recent_data": [28, 30, 27, 29, 31], "horizon": 3}
)
print(pred_response.json())

# Analyze data
analyze_response = requests.post(
    f"{BASE_URL}/analyze",
    json={"data": [28, 30, 27, 29, 31]}
)
print(analyze_response.json())
```

## Dependencies

See `requirements.txt` for all dependencies

## Data Files

- `data/cycles_with_durations.csv`: Main training dataset with columns:
  - `cycle_id`: Unique cycle identifier
  - `year`, `month`, `day`: Date components
  - `cycle_duration`: Duration in days (target variable)
