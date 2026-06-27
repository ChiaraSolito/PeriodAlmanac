from typing import List, Optional
from pydantic import BaseModel, Field

class PredictRequest(BaseModel):
    recent_data: List[float] = Field(..., description="Most recent time series values")
    horizon: int = Field(1, gt=0, description="Number of future steps to predict")


class AnalyzeRequest(BaseModel):
    data: List[float] = Field(..., description="Time series values to analyze")


class TrainResponse(BaseModel):
    success: bool
    samples: int
    window: int
    rmse: float
    message: Optional[str]


class PredictResponse(BaseModel):
    success: bool
    predictions: List[float]
    message: Optional[str]


class AnalyzeResponse(BaseModel):
    success: bool
    mean: float
    std: float
    trend: str
    seasonality: str
    message: Optional[str]

class LogRequest(BaseModel):
    data: List[float] = Field(..., description="Time series values to log")

class LogResponse(BaseModel):
    success: bool
    message: Optional[str]