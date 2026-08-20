import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.exceptions import integrity_error_handler, generic_error_handler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    if settings.POLLER_ENABLED:
        from app.services.poller import poller_loop
        tasks.append(asyncio.create_task(poller_loop()))
    from app.services.cleanup_service import cleanup_loop
    tasks.append(asyncio.create_task(cleanup_loop()))
    from app.services.job_worker import job_worker_loop
    tasks.append(asyncio.create_task(job_worker_loop()))
    yield
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    docs_url = "/api/docs" if settings.EXPOSE_OPENAPI_DOCS else None
    openapi_url = "/api/openapi.json" if settings.EXPOSE_OPENAPI_DOCS else None

    app = FastAPI(title="MongoDB Dashboard API", version="0.2.0", docs_url=docs_url, openapi_url=openapi_url, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    from app.api.auth_router import router as auth_router
    app.include_router(auth_router)

    from app.api.user_router import router as user_router
    app.include_router(user_router)

    from app.api.secret_router import router as secret_router
    app.include_router(secret_router)

    from app.api.cluster_router import router as cluster_router
    app.include_router(cluster_router)

    from app.api.cluster_host_router import router as cluster_host_router
    app.include_router(cluster_host_router)

    from app.api.audit_router import router as audit_router
    app.include_router(audit_router)

    from app.api.metrics_router import router as metrics_router
    app.include_router(metrics_router)

    from app.api.alert_router import router as alert_router
    app.include_router(alert_router)

    from app.api.job_router import router as job_router
    app.include_router(job_router)

    from app.api.log_stream_router import router as log_stream_router
    app.include_router(log_stream_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
