from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ai.provider import get_provider
from .api.deps import RateLimiter
from .api.routes import router
from .assets.image_service import get_image_provider
from .assets.storage import AssetStorage
from .config import Settings
from .db.session import init_db
from .service import GameService, ServiceError


def create_app(settings: Settings | None = None, provider=None, image_provider=None) -> FastAPI:
    settings = settings or Settings()
    engine, sessions = init_db(settings)
    app = FastAPI(title="Interactive AI RPG Worldbuilder & Game Master", version="1.0.0")
    app.state.service = GameService(settings, sessions, provider or get_provider(settings),
                                    image_provider or get_image_provider(settings), AssetStorage(settings.asset_dir))
    app.state.limiter = RateLimiter()
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, e: ServiceError):
        return JSONResponse({"detail": {"code": e.code, "message": e.message}}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, e: RequestValidationError):
        return JSONResponse({"detail": {"code": "VALIDATION_ERROR", "message": "Invalid request.",
                                        "errors": [{"loc": list(x["loc"]), "msg": x["msg"]} for x in e.errors()]}}, status_code=422)

    app.include_router(router)
    return app

