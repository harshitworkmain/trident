# Two stages: build the web console with Node, then a slim Python runtime that serves API + UI.

FROM node:22-slim AS web
WORKDIR /web
COPY src/frontend/web/package.json src/frontend/web/package-lock.json ./
RUN npm ci
COPY src/frontend/web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TRIDENT_ENV=production
WORKDIR /code
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt
# only what serving needs: code, configs and exported models (no raw datasets)
COPY app.py ./
COPY src/backend ./src/backend
COPY src/ml ./src/ml
COPY models ./models
COPY --from=web /web/dist ./src/frontend/web/dist
RUN useradd --create-home trident && mkdir -p /code/data/databases && chown -R trident /code/data
USER trident
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["sh", "-c", "uvicorn src.backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
