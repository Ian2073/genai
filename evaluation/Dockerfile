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
    curl \
    ca-certificates \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /workspace

# 先安裝生成主線依賴，確保版本以 root requirements 為準。
COPY requirements.txt ./requirements.txt
COPY scripts/ ./scripts/
RUN python scripts/setup_env.py \
    --env-path /opt/venv \
    --install-scope full \
    --gpu-series 50 \
    --skip-smoke

# 再安裝評測專屬 extras。
COPY evaluation/requirements.txt ./evaluation/requirements.txt
RUN /opt/venv/bin/python -m pip install -r ./evaluation/requirements.txt --constraint ./requirements.txt

# 複製評測模組內容。
COPY evaluation/ /app

# 下載 NLTK 資源（評測工具使用）。
RUN /opt/venv/bin/python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('averaged_perceptron_tagger')"

# 最小 import smoke（避免 image 打包壞掉）。
RUN /opt/venv/bin/python -c "import main; print('evaluation image import smoke OK')"

FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV PATH="/opt/venv/bin:$PATH"
ENV DEFAULT_MODEL_PATH="/app/models/Qwen2.5-14B"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    libsndfile1 \
    ffmpeg \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

VOLUME ["/app/models", "/app/output", "/app/reports"]

RUN mkdir -p /app/models /app/output /app/reports

CMD ["python", "main.py"]