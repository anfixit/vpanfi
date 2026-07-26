FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system --gid 10001 vpanfi \
    && adduser --system --uid 10001 --ingroup vpanfi --home /app vpanfi

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY docker-entrypoint.sh /usr/local/bin/vpanfi-entrypoint
RUN chmod 0755 /usr/local/bin/vpanfi-entrypoint

USER vpanfi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"

ENTRYPOINT ["/usr/local/bin/vpanfi-entrypoint"]
