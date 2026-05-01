"""HR Service — Employees, Attendance, Leave, Shifts."""
import logging
import sys
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.config import ServiceSettings
from common.database import get_database
from common.models.base import Base
from common.exceptions import ReceiptBuddyException, as_json_response

from services.hr.app.routers import router

settings = ServiceSettings()

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("hr-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db = get_database()
        db.create_all(Base)
        logger.info("✅ HR Service: database tables verified")
    except Exception as e:
        logger.error(f"Startup error: {e}")
    yield
    logger.info("👋 HR Service shutting down")


app = FastAPI(
    title="ReceiptBuddy HR Service",
    version=settings.VERSION,
    description="Employee management, attendance, leave, shift scheduling",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.exception_handler(ReceiptBuddyException)
async def app_exception_handler(request: Request, exc: ReceiptBuddyException):
    return JSONResponse(
        status_code=exc.status_code,
        content=as_json_response(exc),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/health")
def health():
    return {"status": "healthy", "service": "hr", "version": settings.VERSION}
