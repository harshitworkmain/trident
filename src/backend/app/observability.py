"""JSON logs with request ids, security headers, and Prometheus-style metrics."""

from __future__ import annotations

import json
import logging
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request



class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(record.created)) + f'.{int(record.msecs):03d}Z',
               'level': record.levelname, 'logger': record.name, 'msg': record.getMessage()}
        rid = getattr(record, 'request_id', None)
        if rid:
            out['request_id'] = rid
        if record.exc_info:
            out['exc'] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


class RedactSecrets(logging.Filter):
    """uvicorn logs WebSocket and stream URLs verbatim; strip ?token= / ?ticket= values from every record."""
    PATTERN = re.compile(r'((?:token|ticket)=)[^&\s"\']+')

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if 'token=' in msg or 'ticket=' in msg:
            record.msg, record.args = self.PATTERN.sub(r'\1***', msg), ()
        return True


def configure_logging(json_logs: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactSecrets())
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        logging.getLogger(name).addFilter(RedactSecrets())
    handler.setFormatter(JsonFormatter() if json_logs else
                         logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)   # our middleware logs requests


class Metrics:
    """Minimal thread-safe counters and latency histograms in Prometheus text format."""
    BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)

    def __init__(self):
        self.lock = threading.Lock()
        self.counters: Dict[Tuple[str, Tuple], float] = defaultdict(float)
        self.hist: Dict[Tuple[str, Tuple], list] = {}
        self.gauges: Dict[str, float] = {}

    def inc(self, name: str, value: float = 1, **labels) -> None:
        with self.lock:
            self.counters[(name, tuple(sorted(labels.items())))] += value

    def observe(self, name: str, seconds: float, **labels) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self.lock:
            h = self.hist.setdefault(key, [0] * len(self.BUCKETS) + [0, 0.0])   # buckets..., count, sum
            for i, b in enumerate(self.BUCKETS):
                if seconds <= b:
                    h[i] += 1
            h[-2] += 1
            h[-1] += seconds

    def set_gauge(self, name: str, value: float) -> None:
        with self.lock:
            self.gauges[name] = value

    def render(self) -> str:
        def lab(labels, extra=()):
            items = list(labels) + list(extra)
            return '{' + ','.join(f'{k}="{v}"' for k, v in items) + '}' if items else ''
        lines = []
        with self.lock:
            for (name, labels), v in sorted(self.counters.items()):
                lines.append(f'{name}{lab(labels)} {v}')
            for (name, labels), h in sorted(self.hist.items()):
                for b, c in zip(self.BUCKETS, h):
                    lines.append(f'{name}_bucket{lab(labels, [("le", b)])} {c}')
                lines.append(f'{name}_bucket{lab(labels, [("le", "+Inf")])} {h[-2]}')
                lines.append(f'{name}_count{lab(labels)} {h[-2]}')
                lines.append(f'{name}_sum{lab(labels)} {h[-1]:.6f}')
            for name, v in sorted(self.gauges.items()):
                lines.append(f'{name} {v}')
        return '\n'.join(lines) + '\n'


METRICS = Metrics()
access_log = logging.getLogger('trident.access')

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Frame-Options': 'DENY',
    'Permissions-Policy': 'geolocation=(self), camera=(), microphone=()',
    # map tiles come from OpenStreetMap (or CARTO with a key); camera feeds are MJPEG <img> from the
    # ROV's own address, hence http/https in img-src; everything else is same-origin
    'Content-Security-Policy': ("default-src 'self'; img-src 'self' data: blob: https://*.basemaps.cartocdn.com https://*.tile.openstreetmap.org http: https:; "
                                "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws: wss:; "
                                "font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"),
}


BODY_LIMITS = (('/api/v1/rov/vision/frame', 1_000_000), ('/api/v1/telemetry', 2_000_000),
               ('/api/telemetry/', 2_000_000))
DEFAULT_BODY_LIMIT = 256_000
_RID = re.compile(r'^[A-Za-z0-9._-]{1,32}$')


def body_limit(path: str) -> int:
    return next((n for prefix, n in BODY_LIMITS if path.startswith(prefix)), DEFAULT_BODY_LIMIT)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get('x-request-id', '')
        request.state.request_id = rid if _RID.match(rid) else secrets.token_hex(8)
        length = request.headers.get('content-length')
        if length and length.isdigit() and int(length) > body_limit(request.url.path):
            from starlette.responses import JSONResponse
            return JSONResponse({'error': {'code': 'too_large', 'message': 'Request body too large'},
                                 'request_id': request.state.request_id}, status_code=413,
                                headers={**SECURITY_HEADERS, 'X-Request-ID': request.state.request_id})
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # answered here so the server does not also log a second traceback and drop the connection
            logging.getLogger('trident.errors').exception('unhandled error on %s %s', request.method, request.url.path)
            from starlette.responses import JSONResponse
            response = JSONResponse({'error': {'code': 'internal_error', 'message': 'Internal server error'},
                                     'request_id': request.state.request_id}, status_code=500)
        dt = time.perf_counter() - t0
        route = request.scope.get('route')
        path = getattr(route, 'path', 'unmatched')
        METRICS.inc('http_requests_total', method=request.method, route=path, status=response.status_code)
        METRICS.observe('http_request_seconds', dt, route=path)
        response.headers['X-Request-ID'] = request.state.request_id
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.path.startswith('/api/'):
            response.headers.setdefault('Cache-Control', 'no-store')     # personal data: never cached
        if not path.startswith('/api/v1/telemetry'):                 # 1 frame per device per 1.5 s: too chatty
            access_log.info('%s %s %s %.1fms', request.method, request.url.path, response.status_code, dt * 1000,
                            extra={'request_id': request.state.request_id})
        return response
