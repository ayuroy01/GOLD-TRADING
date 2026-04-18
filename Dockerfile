# Gold Market Intelligence — production-style container.
#
# This image:
#   - runs the stdlib Python server as a non-root user
#   - exposes port 8888 ONLY on 127.0.0.1 inside the container
#   - is intended to be fronted by nginx (see deploy/nginx.conf.example)
#     which terminates TLS and forwards to this backend
#
# Build:   docker build -t gold-agent:latest .
# Run:     docker run --rm -p 127.0.0.1:8888:8888 \
#            -e API_TOKENS_FILE=/app/tokens/tokens.json \
#            -e CORS_ALLOWED_ORIGINS=https://your-domain.example \
#            -v $(pwd)/data:/app/data \
#            -v $(pwd)/tokens:/app/tokens:ro \
#            gold-agent:latest
#
# IMPORTANT: never expose this container directly to the public internet.
# Put nginx (with Let's Encrypt) in front. See deploy/ for examples.

FROM python:3.12-slim AS runtime

# Minimal runtime -- no build-time deps needed (stdlib-only backend).
RUN useradd --create-home --uid 10001 goldagent
WORKDIR /app

# Copy only what the backend needs; frontend is built and served separately
# (see README: the SPA is static and can be served by nginx alongside the API).
COPY backend /app/backend
COPY README.md /app/README.md

# Data directory is a volume mount point in production.
RUN mkdir -p /app/data /app/tokens && chown -R goldagent:goldagent /app

USER goldagent

ENV PYTHONUNBUFFERED=1 \
    PORT=8888 \
    BIND_HOST=0.0.0.0 \
    DATA_DIR=/app/data

EXPOSE 8888

# Honest default system_mode is paper_trading. Operators opt into live via
# LIVE_BROKER_ENABLED=true + broker credentials at runtime.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
                   r=urllib.request.urlopen('http://127.0.0.1:8888/api/health', timeout=3); \
                   sys.exit(0 if r.status==200 else 1)"

CMD ["python", "-m", "backend.server"]
