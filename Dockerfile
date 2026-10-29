# ==============================================================================
# Stage 1: Build the Next.js Frontend (Standalone)
# ==============================================================================
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ==============================================================================
# Stage 2: Final Unified Container (FastAPI + Next.js)
# ==============================================================================
FROM python:3.12-slim-bookworm

# Install curl (for health checks) and Node.js runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy Backend application
COPY backend/ ./backend/

# Copy Next.js standalone build & static assets
COPY --from=frontend-builder /build/.next/standalone ./frontend/
COPY --from=frontend-builder /build/.next/static ./frontend/.next/static

# Ensure static assets are reachable regardless of standalone nesting
RUN if [ -d "./frontend/frontend" ]; then \
      mkdir -p ./frontend/frontend/.next && \
      cp -r ./frontend/.next/static ./frontend/frontend/.next/static ; \
    fi

# Copy startup script
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 10000

ENV PORT=10000 \
    BACKEND_URL=http://127.0.0.1:8000 \
    NEXT_PUBLIC_API_BASE_URL=/backend \
    PYTHONUNBUFFERED=1

CMD ["/bin/sh", "/app/start.sh"]
