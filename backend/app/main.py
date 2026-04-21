from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.limiter import limiter
from app.api.v1 import auth, users, sites, excel, logs, contractors, regions, sync, projects, reports

app = FastAPI(
    title="RTKS Tracker",
    description="Система трекинга строительства мобильной сети",
    version="1.0.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Роутеры
app.include_router(auth.router,        prefix="/api/v1/auth",        tags=["auth"])
app.include_router(projects.router,    prefix="/api/v1/projects",    tags=["projects"])
app.include_router(users.router,       prefix="/api/v1/users",       tags=["users"])
app.include_router(sites.router,       prefix="/api/v1/sites",       tags=["sites"])
app.include_router(excel.router,       prefix="/api/v1/excel",       tags=["excel"])
app.include_router(reports.router,     prefix="/api/v1/reports",     tags=["reports"])
app.include_router(logs.router,        prefix="/api/v1/logs",        tags=["logs"])
app.include_router(contractors.router, prefix="/api/v1/contractors", tags=["contractors"])
app.include_router(regions.router,     prefix="/api/v1/regions",     tags=["regions"])
app.include_router(sync.router,        prefix="/api/v1/sync",        tags=["sync"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
