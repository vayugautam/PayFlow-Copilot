from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import logging
import logging.config

from app.api.routes.auth import router as auth_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.chat import router as chat_router
from app.api.routes.disputes import router as disputes_router
from app.api.routes.audit import router as audit_router
from app.api.routes.payments import router as payments_router
from app.core.config import get_settings
from app.core.observability import RequestContextFilter
from app.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)
app_logger = logging.getLogger("payflow")
cors_origins = list(
    dict.fromkeys(
        [
            *settings.CORS_ORIGINS,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
)

app = FastAPI(
    title="PayFlow Copilot API",
    description="AI-powered payment support and dispute assistant",
    version="1.0.0"
)
app.state.settings = settings
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestContextFilter())

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
async def database_unavailable(_, exc: OperationalError) -> JSONResponse:
    """Return a recoverable response when PostgreSQL cannot be reached."""
    logger.exception("Database connection failed", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is unavailable. Start PostgreSQL and retry."},
    )


@app.exception_handler(SQLAlchemyError)
async def database_request_failed(_, exc: SQLAlchemyError) -> JSONResponse:
    """Avoid exposing database traces to the browser while retaining server logs."""
    logger.exception("Database request failed", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database request failed. Apply the latest migrations and retry."},
    )


@app.exception_handler(Exception)
async def unexpected_request_failure(request, exc: Exception) -> JSONResponse:
    """Log diagnostic details server-side while returning a safe response."""
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("Unhandled request failure", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred.", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )

app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(
    transactions_router,
    prefix="/api/v1/transactions",
    tags=["transactions"],
)
app.include_router(
    knowledge_router,
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
)
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(disputes_router, prefix="/api/v1/disputes", tags=["disputes"])
app.include_router(audit_router, prefix="/api/v1", tags=["audit"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])


@app.get("/")
def root():
    return {
        "message": "Welcome to PayFlow Copilot",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "PayFlow Copilot"
    }
