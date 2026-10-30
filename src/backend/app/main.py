"""FastAPI application: lifespan (migrations, seed, scheduler, model warm-up), middleware, routes,
WebSocket, health endpoints and the built web UI.

    uvicorn src.backend.app.main:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__, errors
from .api.routes import router
from .config import get_settings
from .db import get_engine
from .deps import current_device, principal_from_token
from .errors import AppError
from .jobs import Scheduler, default_jobs, lease_status
from .migrate import upgrade
from .models import Device
from .observability import METRICS, RequestContextMiddleware, configure_logging
from .realtime import HUB
from .seed import seed
from .services import telemetry
from .services.weather import WEATHER

logger = logging.getLogger('trident.app')


def _warm_weather() -> None:
    try:
        WEATHER.refresh()
    except Exception:
        logger.warning('weather warm-up failed; requests will retry', exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    upgrade()
    seed()
    HUB.bind(asyncio.get_running_loop())
    # warm the ML runtime off the event loop so the first device frame does not pay for it
    threading.Thread(target=telemetry.RUNTIMES.load, name='ml-warmup', daemon=True).start()
    # the forecast cache is per process: warm it here, independent of the cluster-wide job schedule
    if s.weather_enabled:
        threading.Thread(target=_warm_weather, name='weather-warmup', daemon=True).start()
    scheduler = Scheduler(default_jobs()) if s.run_scheduler else None
    if scheduler:
        scheduler.start()
    logger.info('TRIDENT API %s started (%s, %s)', __version__, s.env,
                'sqlite' if s.is_sqlite else 'postgresql')
    try:
        yield
    finally:
        if scheduler:
            await scheduler.stop()


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(json_logs=s.is_production)
    expose_docs = not s.is_production or os.environ.get('TRIDENT_EXPOSE_DOCS', '').lower() in ('1', 'true')
    app = FastAPI(title='TRIDENT Command API', version=__version__, lifespan=lifespan,
                  docs_url='/api/docs' if expose_docs else None, redoc_url=None,
                  openapi_url='/api/openapi.json' if expose_docs else None)
    errors.install(app)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'PATCH', 'DELETE'],
                       allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key', 'X-Device-Key',
                                      'X-Request-ID'], expose_headers=['X-Request-ID', 'Retry-After'])
    app.include_router(router)

    @app.post('/api/telemetry/wearable', tags=['telemetry'], include_in_schema=False)
    def legacy_ingest(body: dict = Body(...), device: Device = Depends(current_device)):
        """v1 firmware path: schema 1 payloads are mapped onto schema 2 by the parser. v1 sends no
        sequence number, so the receive time in ms stands in for it (one frame per 1.5 s)."""
        return telemetry.ingest(device, {**body, 'seq': body.get('seq') or int(time.time() * 1000),
                                         'boot_id': body.get('boot_id') or 'v1'})

    @app.websocket('/ws')
    async def ws(websocket: WebSocket, token: str = Query(default='')):
        origin = websocket.headers.get('origin')
        host = websocket.headers.get('host', '')
        if origin and origin not in s.cors_origins and origin.split('://', 1)[-1] != host:
            await websocket.accept()
            await websocket.close(code=4403)            # cross-site pages may not open staff sockets
            return
        try:
            user = await asyncio.to_thread(principal_from_token, token)
        except AppError:
            await websocket.accept()                    # accept first so the client sees 4401, not a bare 403
            await websocket.close(code=4401)
            return
        await websocket.accept()

        def still_valid() -> bool:
            from .db import read_session
            from .models import User
            with read_session() as db:
                u = db.get(User, user.id)
                return bool(u and u.is_active and u.role == user.role)
        await HUB.serve(websocket, user.username, still_valid)

    @app.get('/healthz', include_in_schema=False)
    def healthz():
        return {'status': 'ok', 'version': __version__}

    @app.get('/readyz', include_in_schema=False)
    def readyz():
        checks = {}
        try:
            with get_engine().connect() as c:
                c.execute(text('SELECT 1'))
            checks['database'] = {'ok': True, 'writable': _write_probe()}
            if not checks['database']['writable']:
                checks['database'].update(ok=False, error='database is locked or read-only')
        except Exception as e:
            checks['database'] = {'ok': False, 'error': str(e)}
        checks['wearable_ml'] = {'ok': telemetry.RUNTIMES.models is not None, **telemetry.RUNTIMES.status()}
        checks['weather'] = {'ok': WEATHER.forecast is not None, **WEATHER.status()}
        checks['jobs'] = lease_status()
        ready = checks['database']['ok']         # ML/weather degrade gracefully; only the DB is required
        if s.is_production:                      # no hostnames, PIDs or error text to anonymous callers
            checks = {k: {'ok': v['ok']} for k, v in checks.items() if isinstance(v, dict)}
        return JSONResponse({'ready': ready, 'checks': checks}, status_code=200 if ready else 503)

    @app.get('/metrics', include_in_schema=False)
    def metrics():
        return PlainTextResponse(METRICS.render(), media_type='text/plain; version=0.0.4')

    _mount_web(app, s.web_dist)
    return app


def _write_probe() -> bool:
    """Can we take the write lock right now? (SQLite: BEGIN IMMEDIATE with a short timeout; PostgreSQL:
    the session must not be read-only.) A database that answers SELECT 1 but refuses writes is not ready."""
    s = get_settings()
    if s.is_sqlite:
        import sqlite3
        path = s.database_url.split('sqlite:///', 1)[-1]
        try:
            con = sqlite3.connect(f'file:{path}?mode=rw', uri=True, timeout=0.5, isolation_level=None)
            try:
                con.execute('BEGIN IMMEDIATE')
                con.execute('ROLLBACK')
            finally:
                con.close()
            return True
        except sqlite3.Error:
            return False
    with get_engine().connect() as c:
        return c.exec_driver_sql('SHOW transaction_read_only').scalar() == 'off'


def _mount_web(app: FastAPI, dist) -> None:
    """Serve the built React app; unknown non-API paths fall back to index.html (client routing)."""
    index = dist / 'index.html'
    if not index.exists():
        logger.warning('web UI not built (%s missing): run `npm run build` in src/frontend/web', index)
        return
    if (dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def spa(path: str):
        if path.startswith(('api/', 'ws', 'healthz', 'readyz', 'metrics')):
            return JSONResponse({'error': {'code': 'not_found', 'message': 'Not found'}}, status_code=404)
        f = (dist / path).resolve()
        if path and f.is_file() and dist.resolve() in f.parents:
            if path == 'sw.js':           # browsers must always re-check the service worker itself
                return FileResponse(f, media_type='text/javascript',
                                    headers={'Cache-Control': 'no-cache', 'Service-Worker-Allowed': '/'})
            if path.endswith('.webmanifest'):
                return FileResponse(f, media_type='application/manifest+json')
            return FileResponse(f)
        return FileResponse(index, headers={'Cache-Control': 'no-cache'})


app = create_app()
