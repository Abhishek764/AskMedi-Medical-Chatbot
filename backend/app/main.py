"""FastAPI application factory."""

from __future__ import annotations

import hmac
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, request_id_var
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS, render
from app.core.observability import init_sentry


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_sentry(settings)
    if settings.env != "test":
        configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from app.core.container import Container

        container = Container(settings)
        await container.startup()
        app.state.container = container
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "prod" else None,
        redoc_url=None,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        t = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            request_id_var.reset(token)
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")  # template, e.g. /x/{id}: low cardinality
            prefix = settings.api_prefix
            if request.url.path.startswith(prefix + "/") and not path.startswith(prefix + "/"):
                path = prefix + path  # routes under the mounted /v1 app report a local path
            if path != "/metrics":
                HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
                HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - t)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics(request: Request) -> Response:
        expected = settings.metrics_token
        if settings.env not in ("dev", "test"):
            got = request.headers.get("Authorization", "")
            if not expected or not hmac.compare_digest(got, f"Bearer {expected}"):
                return Response(status_code=404)
        body, content_type = render()
        return Response(body, media_type=content_type)

    install_error_handlers(app)
    app.include_router(api_router)
    return app
