# Yield Intelligence — single-container build
# Multi-stage: build frontend with Node, then assemble Python runtime

FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend ./frontend
RUN cd frontend && npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

# System deps (gcc for any pip package that needs to compile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python deps — use backend/requirements.txt (the lighter one at root works too)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend ./backend
COPY scripts ./scripts

# Copy built frontend into backend/static so FastAPI serves the SPA
COPY --from=frontend-builder /build/frontend/dist ./backend/static

# Railway provides $PORT dynamically
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "cd backend && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
