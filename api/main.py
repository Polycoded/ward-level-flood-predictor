from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import structlog
from datetime import datetime

from api.routes.main import router as api_router
from api.schemas import ErrorResponse


structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = structlog.get_logger()
    logger.info("Starting Flood Predictor API")
    yield
    logger.info("Shutting down Flood Predictor API")


app = FastAPI(
    title="Chennai Ward-Level Flood Predictor",
    description="API for ward-level flood risk prediction and alerting",
    version="0.1.0",
    lifespan=lifespan,
)

# The API uses no cookies or auth headers, so credentials are never allowed; with
# allow_credentials=True and "*" Starlette reflects any Origin with credentials enabled.
# Set CORS_ORIGINS (comma-separated) in production to the Vercel URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
# /wards is ~2.9 MB of GeoJSON; gzip takes it to a few hundred KB.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    # Don't echo the rejected input back: it may be huge, and values like 1e999/Infinity
    # can't be encoded as JSON, which turned a 422 into a 500.
    errors = [{"loc": list(e.get("loc", ())), "msg": str(e.get("msg", "")), "type": str(e.get("type", ""))}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger = structlog.get_logger()
    # full detail goes to the server log only; clients get a generic message
    logger.error("Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=None,
            timestamp=datetime.now()
        ).model_dump(mode="json")
    )


@app.get("/")
async def root():
    return {
        "name": "Chennai Ward-Level Flood Predictor",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/healthz",
        "ready": "/api/v1/readyz"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)