"""One error envelope for every failure: {"error": {"code", "message", "details"}, "request_id"}."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger('trident.errors')


class AppError(Exception):
    status = 400
    code = 'bad_request'

    def __init__(self, message: str, details: Optional[dict] = None, *, status: int | None = None,
                 code: str | None = None, headers: Optional[dict] = None):
        super().__init__(message)
        self.message, self.details, self.headers = message, details, headers
        if status:
            self.status = status
        if code:
            self.code = code


class NotFound(AppError):
    status, code = 404, 'not_found'


class Conflict(AppError):
    status, code = 409, 'conflict'


class Unauthorized(AppError):
    status, code = 401, 'unauthorized'


class Forbidden(AppError):
    status, code = 403, 'forbidden'


class RateLimited(AppError):
    status, code = 429, 'rate_limited'


class Unavailable(AppError):
    status, code = 503, 'unavailable'


def _body(request: Request, code: str, message: str, details: Any = None) -> dict:
    err = {'code': code, 'message': message}
    if details is not None:
        err['details'] = details
    return {'error': err, 'request_id': getattr(request.state, 'request_id', None)}


_HTTP_CODES = {400: 'bad_request', 401: 'unauthorized', 403: 'forbidden', 404: 'not_found',
               405: 'method_not_allowed', 409: 'conflict', 413: 'too_large', 429: 'rate_limited'}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status,
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = [{'loc': list(e.get('loc', ())), 'msg': e.get('msg')} for e in exc.errors()]
        return JSONResponse(_body(request, 'validation_error', 'Request validation failed', details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(request, _HTTP_CODES.get(exc.status_code, 'error'), str(exc.detail)),
                            status_code=exc.status_code, headers=getattr(exc, 'headers', None))

    from sqlalchemy.exc import OperationalError

    @app.exception_handler(OperationalError)
    async def _db_unavailable(request: Request, exc: OperationalError):
        # locked (writer contention past busy_timeout), read-only or unreachable database: nothing was
        # committed, so the client may safely retry - say so, instead of a generic 500
        logger.warning('database unavailable on %s %s: %s', request.method, request.url.path, exc.orig)
        return JSONResponse(_body(request, 'unavailable', 'Database busy or unavailable, retry shortly'),
                            status_code=503, headers={'Retry-After': '2'})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception('unhandled error on %s %s', request.method, request.url.path)
        return JSONResponse(_body(request, 'internal_error', 'Internal server error'), status_code=500)
