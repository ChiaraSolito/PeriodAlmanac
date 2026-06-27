from fastapi import FastAPI
from app.api.v1.endpoints import router as v1_router
from app.model import ts_model

app = FastAPI(
    title="Poc Cycle API",
    description="Home made menstruation days prediction.",
    version="0.1.0",
)

app.include_router(v1_router)


@app.on_event("startup")
def startup_event() -> None:
    ts_model.load()

