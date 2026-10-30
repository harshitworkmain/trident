"""Entry point: TRIDENT command-center API + web console.

    python app.py                                          # dev server on :8000
    uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --proxy-headers   # production
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backend.app.main import app  # noqa: E402  (re-exported for ASGI servers)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('src.backend.app.main:app', host=os.environ.get('HOST', '127.0.0.1'),
                port=int(os.environ.get('PORT', 8000)), reload=os.environ.get('TRIDENT_ENV') != 'production')
