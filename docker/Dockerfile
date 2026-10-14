# RockForge — API and worker share one image; the worker installs the ML extra.
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web

FROM base AS api
# [psarc]: the API decrypts .psarc files too (the PSARC check, the tone
# collection scan).
RUN pip install --no-cache-dir ".[postgres,psarc]"
EXPOSE 8000
CMD ["uvicorn", "rockforge.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
# The build runs here, so [psarc] is what makes the .psarc (without it only the
# DLC Builder bundle comes out). The ML stack (PyTorch via demucs) makes this
# stage large: PyTorch from PyPI on Linux brings its CUDA libraries.
RUN pip install --no-cache-dir ".[ml,psarc,postgres]"
CMD ["celery", "-A", "rockforge.interfaces.worker.celery_app:celery_app", "worker", "--loglevel=info", "--concurrency=1"]
