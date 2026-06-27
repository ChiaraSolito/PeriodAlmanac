from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.model import ts_model
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    LogRequest,
    LogResponse,
    PredictRequest,
    PredictResponse,
    TrainResponse,
)

router = APIRouter()


@router.post("/train", response_model=TrainResponse)
def train() -> TrainResponse:
    try:
        rmse = ts_model.train()
        return TrainResponse(
            success=True,
            samples=len(ts_model.data),
            window=ts_model.window,
            rmse=rmse,
            message="Model trained successfully.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    try:
        predictions = ts_model.predict(request.recent_data, request.horizon)
        return PredictResponse(success=True, predictions=predictions, message="Forecast complete.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    

@router.post("/log", response_model=LogResponse)
def log(request: LogRequest) -> LogResponse:
    try:
        result = ts_model.analyze(request.data)
        return LogResponse(success=True, message="Analysis complete.", **result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = ts_model.analyze(request.data)
        return AnalyzeResponse(success=True, message="Analysis complete.", **result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})