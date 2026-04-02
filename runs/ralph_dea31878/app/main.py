"""FastAPI application entry point for the Todo API."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routers import todos


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the database on startup."""
    init_db()
    yield


app = FastAPI(title="Todo API", lifespan=lifespan)

# Include the todos router
app.include_router(todos.router, prefix="/api")


@app.get("/")
async def health_check() -> dict:
    """Return health check status."""
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions and return 500 JSON response."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
