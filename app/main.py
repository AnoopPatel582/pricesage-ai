import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.products import router as product_router
from app.database.session import Base, engine
from app.models import Product, PriceHistory, TrackedProduct, User  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.scheduler.task_runner import start_scheduler, stop_scheduler
from app.scrapers.exceptions import ScraperException, UnsupportedSiteException
from app.utils.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
logger = logging.getLogger("pricesage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler(check_interval_seconds=60)
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Agentic product price tracking, history, and alerts.",
    lifespan=lifespan,
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.exception_handler(UnsupportedSiteException)
async def unsupported_site_handler(request: Request, exc: UnsupportedSiteException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Unsupported Domain", "detail": str(exc)},
    )


@app.exception_handler(ScraperException)
async def scraper_exception_handler(request: Request, exc: ScraperException):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Scraping Failure", "detail": str(exc)},
    )


app.include_router(auth_router)
app.include_router(product_router)
app.include_router(agent_router)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", tags=["General"])
def serve_dashboard():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"project": settings.PROJECT_NAME, "status": "online", "docs_url": "/docs"}


@app.get("/health", tags=["General"])
def health_check():
    return {"status": "healthy"}
