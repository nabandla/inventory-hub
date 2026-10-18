from fastapi import FastAPI
from fastapi.responses import JSONResponse

from db import check_db

app = FastAPI(title="Inventory Hub")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    if check_db():
        return {"status": "ok", "database": "ok"}
    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "database": "unreachable"},
    )
