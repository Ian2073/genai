# ============================================================
# 多模態兒童故事生成系統 - Docker 建構檔
# 目標: 讓 Docker 路線與 scripts/setup_env.py 保持同一套安裝邏輯
# ============================================================

FROM nvidia/cuda:12.8.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    build-essential \
    git \
    wget \
    ca-certificates \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY scripts/ ./scripts/

# Docker 內統一使用 cu128 profile，避免與本機 venv 路線分岔。
RUN python scripts/setup_env.py \
    --env-path /opt/venv \
    --install-scope full \
    --gpu-series 50 \
    --skip-smoke

ENV PATH="/opt/venv/bin:$PATH"

COPY . .

# 建 image 時先做一次 import smoke，確保 backends/runtime 套件已被正確打包。
RUN python -c "import chief, scripts.run_experiment as run_experiment; print('docker image import smoke OK')"


FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    libsndfile1 \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

VOLUME ["/app/models", "/app/output", "/app/logs", "/app/runs"]

RUN mkdir -p /app/output /app/logs /app/runs

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import torch; assert torch.cuda.is_available()" || exit 1

ENTRYPOINT ["python", "chief.py"]
CMD ["--count", "1"]
