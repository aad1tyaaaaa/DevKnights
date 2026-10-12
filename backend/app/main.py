import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import get_scan_service, router
from app.core.config import settings
from app.core.security import API_KEY_HEADER, api_key_rejection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background tasks are not durable: scans a restart interrupted are picked up again here.
    service = app.dependency_overrides.get(get_scan_service, get_scan_service)()
    recovery = asyncio.create_task(service.recover_interrupted())
    yield
    recovery.cancel()


app = FastAPI(title="Provenyx API", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def prevent_authenticated_response_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/github", "/api/scans")):
        response.headers["Cache-Control"] = "private, no-store"
        vary = {value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()}
        response.headers["Vary"] = ", ".join(sorted(vary | {"Authorization", "Cookie"}))
    return response


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    # A middleware rather than per-route dependencies, so routes added later are protected by default.
    return api_key_rejection(request) or await call_next(request)


# Added last so it is the outermost layer: preflights and 401s still carry CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", API_KEY_HEADER],
)

app.include_router(router)
