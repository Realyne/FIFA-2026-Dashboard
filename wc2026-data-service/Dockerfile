# ---- build stage -----------------------------------------------------------
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml ./
COPY wc2026 ./wc2026
RUN pip install --no-cache-dir --prefix=/install .

# ---- runtime stage ----------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app
COPY --from=build /install /usr/local
COPY wc2026 ./wc2026
COPY data/static ./data/static
COPY db ./db
RUN useradd -r appuser && mkdir -p debug && chown appuser debug
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz',timeout=4).status==200 else 1)"
CMD ["uvicorn", "wc2026.main:app", "--host", "0.0.0.0", "--port", "8000"]
