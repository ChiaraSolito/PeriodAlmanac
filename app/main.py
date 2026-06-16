# main structure copied from elsewhere
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, date
import pickle
import os

# Define the input data schema using Pydantic
class LogInput(BaseModel):
    start_date: date

# Initialize FastAPI app
app = FastAPI(title="Period Almanac! Log your periods and predict next date")

# Load the model during startup
model_path = os.path.join("model", "linear_regression_model.pkl")
with open(model_path, 'rb') as f:
    model = pickle.load(f)

@app.post(
    "/predict_next",
    #response_model=tobe,
    responses={
        200: {
            "description": "Request was successful."
        },
        400: {"description": "Bad Request"},
        500: {
            "description": "Internal Server Error: processing or services error"
        },
        504: {"description": "Gateway Timeout Error"},
    },
    summary="Start the fetch_data pipeline for the list of clients.",
)
def predict():
    try:
      prediction = model.predict(input_features)
      return {"predicted_date": prediction[0]}
    except Exception:
      return {"Error while predicting."}

@app.post(
    "/log_cycle",
    #response_model=tobe,
    responses={
        200: {
            "description": "Request was successful."
        },
        {"description": "Unprocessable Entity. Payload not correct"},
        400: {"description": "Bad Request"},
        500: {
            "description": "Internal Server Error: processing or services error"
        },
        504: {"description": "Gateway Timeout Error"},
    },
    summary="Start the fetch_data pipeline for the list of clients.",
)
def log_cycle(data: LogInput):
    try:
      # log input 
      return {"Correctly logged data."}
    except Exception:
      return {"error while logging"}
      
