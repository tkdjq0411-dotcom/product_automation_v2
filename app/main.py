import os
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.admin_items import router as admin_items_router
from app.api.admin_stats import router as admin_stats_router
from app.api.admin_settings import router as admin_settings_router
from app.api.admin_decisions import router as admin_decisions_router
from app.api.admin_watch import router as admin_watch_router
from app.api.admin_analytics import router as admin_analytics_router

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-secret"),
    same_site="lax",
    https_only=False,
)

app.include_router(auth_router)
app.include_router(admin_items_router)
app.include_router(admin_stats_router)
app.include_router(admin_settings_router)
app.include_router(admin_decisions_router)
app.include_router(admin_watch_router)
app.include_router(admin_analytics_router)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/code.html")

from app.api.admin_extra import router as admin_extra_router
app.include_router(admin_extra_router)

