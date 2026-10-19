import logging

import pyodbc
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cors import configure_cors
from db import check_db
from routers import items

logger = logging.getLogger(__name__)

app = FastAPI(title="Inventory Hub")
configure_cors(app)
app.include_router(items.router)


@app.exception_handler(pyodbc.Error)
async def database_error_handler(request: Request, exc: pyodbc.Error):
    # Full detail goes to the server log only, never to the caller
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


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
