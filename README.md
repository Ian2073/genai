# 🎨 多模態兒童故事生成系統

> **全流程本地化 AI 故事書生產線** | 支援多分支互動故事、多語言翻譯、圖像生成與語音合成

[![PyTorch](https://img.shields.io/badge/PyTorch-2.8.0-EE4C2C?logo=pytorch)](https://pytorch.org/)
[![CUDA](https://img.shields.io/badge/CUDA-12.8-76B900?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)

一個專為 NVIDIA RTX 50 系列 GPU 優化的完整 AI 故事生成系統，從零到完整有聲繪本，支援知識圖譜驅動、多分支互動劇情、自動插圖與多語音軌。

---

## ✨ 核心特性

### 📚 智慧故事生成
- **知識圖譜驅動 (KG-Driven)**：基於年齡、類別、主題的智慧推薦系統
- **多分支互動架構**：支援 2-3 歲線性故事、4-5 歲單轉折、6-8 歲多結局
- **狀態快照管理**：精準追蹤角色狀態、情緒、世界條件，確保跨分支一致性
- **自動融合結局**：不同選擇的分支可自然匯聚到共同的溫馨結局

### 🎨 多模態資產生成
- **文本**：Qwen2.5-14B-Instruct-GPTQ-Int4（預設主模型） + Qwen3-8B（備援） - 大綱、正文、旁白、對話
- **圖像**：Stable Diffusion XL - 封面、角色肖像、場景插圖、自動去背
- **語音**：XTTS-v2 - 多語言自然語音合成（支援自訂說話人）
- **翻譯**：NLLB-200-3.3B - 200 種語言神經機器翻譯

### 🔬 企業級可觀測性
- **記憶體監控**：即時追蹤 GPU/CPU/RAM 使用量、碎片化率
- **效能分析**：核心（Kernel）層級的 GPU 操作分析、每步驟 Token 計數
- **品質追蹤**：自動偵測重複、長度異常、時態錯誤
- **多格式報告**：Parquet、SQLite、Excel 自動導出

### ⚡ 效能優化
- **低顯存模式**：支援 8GB VRAM 運行（量化 + 動態卸載）
- **批次處理**：多故事並行生成，自動資源隔離
- **階段式清理**：激進式 CUDA 快取管理，防止記憶體洩漏

---

## 🚀 快速開始

在跨電腦部署或移機前，建議先閱讀文件索引：
- 文件總覽：`docs/README.md`

第一次部署建議優先看：
- 環境建置總覽：`docs/ENV_SETUP.md`
- CUDA 排障手冊：`docs/CUDA_TROUBLESHOOTING.md`
- 主控流程架構：`docs/PIPELINE_ARCHITECTURE.md`

### 系統需求

| 項目 | 最低需求 | 推薦配置 |
|------|---------|---------|
| **作業系統** | Windows 10/11 | Windows 11 |
| **Python** | 3.11.0+ | 3.11.14 |
| **GPU** | RTX 40 系列 (12GB+) | RTX 50 系列 (16GB+) |
| **CUDA** | 12.8+ | 12.8+ |
| **RAM** | 32GB | 64GB |
| **儲存** | 100GB 可用空間 | 500GB SSD |

> **注意**: RTX 50 系列 (sm_120 架構) 必須使用 PyTorch 2.8.0+cu128；RTX 40 系列可使用較舊 CUDA 組合設定。建議直接用本專案的自動安裝腳本做硬體判斷。

### 0️⃣ 建議先做環境診斷

```bash
python scripts/doctor.py --workspace-root . --expect-cuda auto
```

若你在目標機器「一定要使用 CUDA」，可改用嚴格模式：

```bash
python scripts/doctor.py --workspace-root . --expect-cuda yes --strict
```

若你想先做低風險自動修復（建立缺少的必要資料夾）：

```bash
python scripts/doctor.py --workspace-root . --expect-cuda auto --fix
```

若你也要一併自動補裝缺少的關鍵 Python 套件：

```bash
python scripts/doctor.py --workspace-root . --expect-cuda auto --fix --fix-packages
```

### 選擇執行方式

- **方式 A：本機自動環境 (`genai_env`)** — 推薦日常使用，安裝與啟動最一致
- **方式 B：本機模式 (Conda)** — 保留給既有手動流程或除錯需求
- **方式 C：Docker 模式** — 環境一致、部署方便

---

### A. 本機自動環境 (`genai_env`) 安裝步驟

#### 0️⃣ 一鍵自動安裝（推薦）

```bash
# Windows 一鍵入口
Build_GenAI.bat

# 或直接執行（可自訂環境路徑）
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series auto
```

自動腳本 `scripts/setup_env.py` 會做以下事情：
- 偵測 GPU：`RTX 50 / RTX 40 / CPU`
- 依硬體套用對應 PyTorch 組合
- 安裝 requirements（過濾 torch 相關版本衝突）
- 補裝 spaCy 特殊模型 wheel 與專案相容例外
- 執行基本驗證（`pip check`、GPTQ quantizer 初始化、`run_experiment` 匯入）

目前預設 profile：

| 硬體 | 自動安裝組合 |
|------|--------------|
| RTX 50 | `torch==2.8.0+cu128` `torchvision==0.23.0+cu128` `torchaudio==2.8.0+cu128` `torchcodec==0.7.0` |
| RTX 40 | `torch==2.6.0+cu124` `torchvision==0.21.0+cu124` `torchaudio==2.6.0+cu124` `torchcodec==0.6.0` |
| CPU | `torch==2.8.0` `torchvision==0.23.0` `torchaudio==2.8.0` |

可手動覆蓋判斷：

```bash
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series 50
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series 40
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series cpu
```

安裝完成後，建議用以下方式進入專案執行環境：

```bash
Start_GenAI.bat
```

評測改為同一入口執行：

```bash
Start_GenAI.bat --eval-only --input output --branch auto --post-process none
```

如果你要在 Windows 上做 MSVC/環境檢查與自動修復：

```bash
Build_GenAI_DevTools.bat
```

### A-2. 建置與啟動（本機）

- 建置：`Build_GenAI.bat`
- 啟動終端：`Start_GenAI.bat`
- 評測執行：`Start_GenAI.bat --eval-only --input output --branch auto --post-process none`
- 啟動 dashboard：`Start_GenAI.bat --dashboard`

### B. 本機模式 (Conda) 手動流程

#### 1️⃣ 建立 Conda 環境

```bash
conda create -n genai python=3.11 -y
conda activate genai
```

#### 2️⃣ 安裝 PyTorch（手動選擇硬體）

RTX 50：

```bash
pip install torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
```

RTX 40（相容組合）：

```bash
pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124 torchaudio==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
```

#### 3️⃣ 安裝專案依賴

```bash
pip install -r requirements.txt
```

> **Windows 編譯需求**: 語音合成需要 Visual Studio C++ Build Tools
> 
> 下載: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022

#### 4️⃣ 下載模型

系統需要以下模型 (總計約 80GB)：

```plaintext
models/
├── Qwen2.5-14B-Instruct-GPTQ-Int4/  # ~9GB  | 預設文本生成
├── Qwen3-8B/                        # ~16GB | 備援 / 非 GPTQ 相容路徑
├── nllb-200-3.3B/                   # ~13GB | 翻譯
├── stable-diffusion-xl-base-1.0/    # ~7GB  | 圖像生成
├── stable-diffusion-xl-refiner-1.0/ # ~6GB  | 圖像精煉
└── XTTS-v2/                         # ~2GB  | 語音合成
    └── samples/                     # 說話人樣本 (自備)
```

**模型來源**:
- Qwen2.5-14B-Instruct-GPTQ-Int4: https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4
- Qwen3-8B: https://huggingface.co/Qwen/Qwen3-8B
- NLLB: https://huggingface.co/facebook/nllb-200-3.3B
- SDXL: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
- XTTS: https://huggingface.co/coqui/XTTS-v2

#### 5️⃣ 驗證安裝

```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Arch: {torch.cuda.get_arch_list()}')"
python -c "from optimum.gptq.quantizer import GPTQQuantizer; GPTQQuantizer(bits=4); print('GPTQ OK')"
python -c "from scripts import run_experiment; print('scripts.run_experiment import OK')"
```

預期輸出: `CUDA: True, Arch: [..., 'sm_120']`

---

### C. Docker 模式 (建議部署)

#### 1️⃣ 先決條件

- 已安裝 Docker Desktop（含 Docker Compose）
- NVIDIA Driver 正常（`nvidia-smi` 可用）
- Docker 可存取 GPU（Windows + WSL2 + NVIDIA Container Toolkit）

#### 2️⃣ 建構映像

```bash
docker compose build genai story-checker coref-service
```

Windows 一鍵建置：

```bash
Build_GenAI_Docker.bat
```

`Start_GenAI_Docker.bat` 預設會使用既有 `genai:latest` 映像，
只有在映像不存在時才自動觸發一次建置；要強制重建請手動執行 `Build_GenAI_Docker.bat`。

啟動時會預設同時拉起整合評測服務（`story-checker`、`coref-service`），
若只想跑生成可加 `--genai-only`。

> Docker 路線現在會沿用與 `scripts/setup_env.py` 相同的安裝策略，包含 spaCy 模型 wheel、版本鎖定回補與映像匯入基本驗證。

#### 3️⃣ 使用 Compose 執行

```bash
# 預設：生成 1 本故事
docker compose run --rm genai

# 單次執行（可帶 chief.py 參數）
docker compose run --rm genai --count 1 --age 6-8 --category educational
```

Windows 也可直接用一鍵入口：

```bash
Start_GenAI_Docker.bat
Start_GenAI_Docker.bat --genai-only
```

#### 4️⃣ Docker Dashboard（Windows）

```bash
Start_GenAI_Docker.bat --dashboard
Start_GenAI_Docker.bat --dashboard --dashboard-port 8766 --dashboard-no-open
```

### C-2. 建置與啟動（Docker）

- 建置：`Build_GenAI_Docker.bat`
- 啟動終端：`Start_GenAI_Docker.bat`
- 啟動 dashboard：`Start_GenAI_Docker.bat --dashboard`

#### 5️⃣ 掛載目錄說明

- `./models -> /app/models`（唯讀）
- `./output -> /app/output`
- `./logs -> /app/logs`
- `./runs -> /app/runs`

> 目前 compose 會整合 `genai`、`story-checker`、`coref-service`。
> `Start_GenAI_Docker.bat` 會先檢查 Docker CLI、Compose 與 daemon 狀態，再進入 build/run。

---

## 📖 使用指南

### 一鍵生成 (推薦)

```bash
# 最簡單：只輸入本數
python -m pipeline --count 1

# 批次生成 10 本書
python -m pipeline --count 10

# 單本失敗時，整本自動重跑 1 次（不自動降級）
python -m pipeline --count 2 --max-retries 1

# 指定年齡與類別
python -m pipeline --age 6-8 --category educational --count 1
```

相容舊入口仍可用：

```bash
python chief.py --count 1
```

**支援的參數**:
- `--age`: 年齡範圍 (2-3, 4-5, 6-8)
- `--category`: 故事類別 (adventure, educational, fun, cultural)
- `--count`: 生成數量
- `--pages`: 指定頁數 (0=自動)
- `--max-retries`: 單本失敗時整本重跑次數
- `--status-file`: 即時狀態 JSON 輸出檔（供儀表板或外部監看）
- `--low-vram`: 啟用低顯存模式
- `--story-quantization`: LLM 量化 (4bit, 8bit, none)
- `--photo/--no-photo`: 啟用或停用圖像階段
- `--translation/--no-translation`: 啟用或停用翻譯階段
- `--voice/--no-voice`: 啟用或停用語音階段
- `--verify/--no-verify`: 啟用或停用最終驗證
- `--strict-translation/--no-strict-translation`: 翻譯失敗是否視為整本失敗
- `--strict-voice/--no-strict-voice`: 語音失敗是否視為整本失敗

預設為嚴格模式：翻譯或語音失敗會讓該本書失敗（並依 `--max-retries` 重跑）。

### Dashboard 模式 (可視化操作)

```bash
# 啟動本地儀表板（預設 http://127.0.0.1:8765）
python -m pipeline --dashboard
```

Windows 本機一鍵入口：

```bash
Start_GenAI.bat --dashboard
```

Windows Docker 一鍵入口：

```bash
Start_GenAI_Docker.bat --dashboard
```

自訂連接埠範例（本機或 Docker 皆可加同參數）：

```bash
Start_GenAI.bat --dashboard --dashboard-port 8766 --dashboard-no-open
Start_GenAI_Docker.bat --dashboard --dashboard-port 8766 --dashboard-no-open
```

可用參數：
- `--dashboard-host`: 指定儀表板綁定 IP
- `--dashboard-port`: 指定儀表板連接埠
- `--dashboard-no-open`: 啟動時不自動打開瀏覽器

儀表板內建：
- 簡易模式（只填本數與重跑次數）
- 進階選項（年齡/類別/頁數/隨機種子與各階段開關）
- 即時狀態輪詢（目前進行書籍、階段、成功/失敗數）

### 實驗與分析腳本

為了讓根目錄更乾淨，輔助型腳本已收進 `scripts/`：

```bash
python scripts/run_experiment.py --num 1
python scripts/analyze_observability.py runs
python scripts/smoke_gate.py
python scripts/check_root_layout.py --workspace-root . --strict
```

研究分析資產可放在 `research/`，但目前預設由 `.gitignore` 排除（避免大型檔案進入版本庫）：

- `research/paper/`

### 評測系統（正式主線）

評測模組已納入主線路徑 `evaluation/`，並由主線入口統一調度：

- `Build_GenAI.bat` 會先安裝生成主線，再把 `evaluation/requirements.txt` 當 extras 併入同一 `genai_env`，且套用 root `requirements.txt` constraint（生成版本優先）。

```bash
Build_GenAI.bat
Start_GenAI.bat --eval-only --input output --post-process none
```

Docker 路徑：

```bash
Build_GenAI_Docker.bat
Start_GenAI_Docker.bat --eval-only --input output --post-process none
```

**輸出位置**: `output/<Category>/<Age>/<Title>/`

**目錄結構**:
```
output/Educational/6-8/Grandpa_Tom_s_Kindness_Lesson/
├── en/                              # 英文版本
│   ├── branches/                    # 多分支架構
│   │   ├── option_1/               # 分支 1
│   │   │   ├── full_story.txt      # 完整故事
│   │   │   ├── outline.txt         # 大綱
│   │   │   ├── title.txt           # 標題
│   │   │   ├── metadata.json       # 分支元數據
│   │   │   ├── page_*.txt          # 分頁內容
│   │   │   ├── page_*_narration.txt # 旁白
│   │   │   ├── page_*_dialogue.txt  # 對話
│   │   │   ├── page_*_state.json   # 狀態快照
│   │   │   ├── resource/           # 資源檔案
│   │   │   │   ├── story_meta.json
│   │   │   │   ├── character_*.txt # 角色外觀
│   │   │   │   ├── page_*_prompt.txt # 場景提示
│   │   │   │   └── book_cover_prompt.txt
│   │   │   ├── image/              # 圖片輸出
│   │   │   │   ├── main/
│   │   │   │   ├── original/
│   │   │   │   └── nobg/
│   │   │   └── voice/              # 語音檔案
│   │   │       └── narration_full.wav
│   │   └── option_2/               # 分支 2 (如有)
├── zh-cn/                          # 簡體中文
├── zh-tw/                          # 繁體中文
├── resource/                       # 根層級資源
│   ├── story_meta.json
│   └── kg_profile.json
└── logs/
    ├── generation.log              # 故事生成日誌
    ├── photo.log                   # 圖像生成日誌
    ├── translation.log             # 翻譯日誌
    └── voice.log                   # 語音日誌
```

### 獨立模組使用

#### 📝 故事生成

```python
# 編輯 story.py 中的配置
DEFAULT_STORY_INPUT = StoryInput(
    language="en",
    age_group="6-8",
    category="educational",
    theme="kindness"  # 可選，留空則自動推薦
)
```

```bash
python story.py
```

**支援的類別與主題**:
- **Adventure** (冒險): Forest, Space, Ocean, Mountain
- **Educational** (教育): Kindness, Honesty, Courage, Responsibility
- **Fun** (趣味): Animal_Friends, Magic, Music, Sports
- **Cultural** (文化): Tradition, Festival, History

#### 🎨 圖像生成

```bash
# 自動偵測最新故事
python image.py

# 指定故事
python image.py --story-root "output/Educational/6-8/My_Story"

# 跳過精煉 (2倍速度)
python image.py --skip-refiner

# 低顯存模式
python image.py --low-vram
```

**技術細節**:
- Base Model: 8 steps @ 1024x1024
- Refiner: 4 steps (可選)
- DPM++ SDE Karras scheduler
- VAE 分塊處理 (記憶體優化)

#### 🌍 多語言翻譯

```bash
# 翻譯為簡中、日文、法文
python trans.py --languages zh-cn ja fr

# 指定故事
python trans.py --story-root "output/Educational/6-8/My_Story"

# 使用 8-bit 量化 (低顯存)
python trans.py --quantize
```

**支援語言**: 200 種語言 (完整列表見 NLLB 文檔)

#### 🎙️ 語音合成

```bash
# 自動偵測所有語言
python voice.py

# 指定語言與說話人
python voice.py --language zh-cn --speaker-wav "samples/narrator_male.wav"

# 只合成特定頁面
python voice.py --page-start 1 --page-end 5

# 調整音量 (預設 1.0)
python voice.py --gain 1.2
```

**說話人樣本需求**:
- 格式: 16-bit WAV, 22050 Hz
- 長度: 3-10 秒
- 內容: 清晰、無背景噪音

---

## 🧠 知識圖譜系統 (KG)

### 設計理念

本系統採用**知識圖譜驅動生成** (KG-Driven Generation)，而非簡單的隨機選擇。每個故事的年齡、類別、主題、場景、角色都經過精心配對，確保內容適齡且教育意義明確。

### 核心概念

#### 1. 年齡分層 (Age Stratification)

| 年齡 | 頁數 | 分支 | 特色 |
|------|------|------|------|
| 2-3 歲 | 6-8 頁 | 線性 | 單一主線，簡單句型 |
| 4-5 歲 | 8-10 頁 | 單轉折 | 一個選擇點，兩個結局 |
| 6-8 歲 | 10-12 頁 | 多分支 | 複雜劇情，多重結局 |

#### 2. 分支架構 (Branch Architecture)

```
故事開始 (P1-P4 共同主線)
    ↓
轉折點 P5 (決策頁面)
    ├─→ 選擇 A → 分支 1 (P6-P8)
    └─→ 選擇 B → 分支 2 (P6-P8)
         ↓           ↓
         ↓           ↓
      融合結局 (P9-P10)
```

**關鍵技術**:
- **狀態快照 (State Snapshot)**: 每頁儲存 `character_goal`, `character_emotion`, `world_condition`
- **融合結局 (Converged Ending)**: 不同分支透過 `convergence_anchor` 自然匯聚
- **分支隔離 (Branch Isolation)**: 提示詞強制 LLM 不洩漏其他路線資訊

#### 3. 主題語義圖譜

```json
{
  "educational": {
    "kindness": {
      "scenes": ["helping_friend", "sharing_toys", "comforting_sad"],
      "characters": ["grandpa", "child", "friend"],
      "moral": "Kindness makes everyone happy"
    }
  }
}
```

### 自訂知識圖譜

編輯 `kg.py` 中的 `STORY_KG` 字典來擴展內容：

```python
STORY_KG = {
    "age_groups": {
        "6-8": {
            "pages": 10,
            "branch_count": 2,
            "turning_point": 5
        }
    },
    "categories": {
        "educational": {
            "themes": {
                "honesty": {
                    "label": "Honesty",
                    "scenes": ["telling_truth", "admitting_mistake"]
                }
            }
        }
    }
}
```

---

## 📊 可觀測性與監控

### 自動化報告

每次執行 `chief.py` 都會生成完整的可觀測性報告：

```
runs/20260118-124844_book-01_of_01_run-01/
├── chief-<uuid>.jsonl              # 原始事件日誌
├── chief-<uuid>.parquet            # Parquet 格式 (最快)
├── chief-<uuid>.db                 # SQLite 資料庫
└── chief-<uuid>.xlsx               # Excel 報表
```

### 監控指標

| 類別 | 指標 | 用途 |
|------|------|------|
| **Kernel** | GPU 操作、CUDA 時間 | 效能瓶頸分析 |
| **Memory** | VRAM/RAM 使用、碎片率 | 記憶體洩漏偵測 |
| **Model** | Token 數、溫度、重試次數 | 生成品質追蹤 |
| **Pipeline** | 階段時間、模型切換 | 流程優化 |
| **Reliability** | 錯誤率、降級策略 | 穩定性監控 |

---

## ⚙️ 進階配置

### 低顯存模式 (8GB VRAM)

```bash
# 全局配置
python chief.py --low-vram --story-quantization 4bit

# 個別模組
python story.py  # 自動啟用 4-bit 量化
python image.py --low-vram --skip-refiner
python trans.py --quantize
```

**優化策略**:
- LLM: 4-bit 量化 + CPU Offload
- SDXL: 跳過 Refiner + VAE 分塊
- NLLB: 8-bit 量化
- 激進式 CUDA 快取清理

### 自訂生成參數

編輯 `pipeline/options.py` 中的 `DEFAULT_CHIEF_OPTIONS`（`chief.py` 目前是相容入口）:

```python
DEFAULT_CHIEF_OPTIONS = ChiefOptions(
    # === 故事生成 ===
    story_temperature=0.8,        # 創意度 (0.7-1.0)
    story_top_p=0.9,              # 核心採樣
    story_max_tokens=600,         # 每頁最大 Token
    story_pages_expected=10,      # 預期頁數 (0=自動)
    
    # === 圖像生成 ===
    photo_steps=8,                # 採樣步數 (6-15)
    photo_guidance=7.5,           # CFG 引導強度
    photo_refiner_steps=4,        # 精煉步數
    photo_skip_refiner=False,     # 跳過精煉 (2倍速)
    
    # === 翻譯 ===
    translation_beam_size=5,      # Beam Search 寬度
    strict_translation=True,      # 嚴格模式 (失敗則中止)
    
    # === 語音 ===
    voice_volume_gain=1.0,        # 音量增益
)
```

### 提示詞模板

所有模板位於 `prompts/*.txt`，採用雙區塊格式：

```
###SYSTEM
You are a children's book author...
###USER
Task: Write a story for age {age_group}...
Theme: {theme}
```

**動態變數**:
- `{age_group}`, `{category}`, `{theme}`: 基本資訊
- `{kg_guidelines}`: 知識圖譜注入的寫作準則
- `{system_announcement}`: 動態指令 (如轉折點、收斂提示)
- `{branch_context}`: 當前分支資訊
- `{state_snapshot}`: 角色狀態快照

---

## 🛠️ 故障排除

### GPU 無法使用

**症狀**: `torch.cuda.is_available() = False`

**解決方案**:
1. 確認 CUDA 版本:
   ```bash
   nvidia-smi  # 驗證驅動支援 CUDA 12.8+
   ```
2. 重新安裝 PyTorch:
   ```bash
    # 建議直接走自動腳本，避免 40/50 profile 混用
    python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series auto
   ```
3. 驗證 GPU 架構:
   ```python
   import torch
   print(torch.cuda.get_arch_list())  # 應包含 'sm_120'
   ```

### CUDA Out of Memory (OOM)

**症狀**: `RuntimeError: CUDA out of memory`

**解決方案**:
1. **啟用低顯存模式**:
   ```bash
   python chief.py --low-vram --story-quantization 4bit
   ```
2. **降低批次大小** (編輯配置檔)
3. **關閉其他 GPU 程式**
4. **監控 VRAM**:
   ```bash
   nvidia-smi -l 1  # 每秒更新
   ```

### 語音合成失敗

**症狀**: `ImportError: Microsoft Visual C++ 14.0 or greater is required`

**解決方案**:
1. 下載並安裝 Build Tools:
   https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
2. 重新安裝 TTS:
   ```bash
   pip uninstall TTS
   pip install TTS==0.22.0 --no-cache-dir
   ```

### Docker 無法使用 GPU

**症狀**: 容器內 `torch.cuda.is_available()` 為 `False`

**解決方案**:
1. 驗證宿主機 GPU：
    ```bash
    nvidia-smi
    ```
2. 驗證 Docker GPU Runtime：
    ```bash
    docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu22.04 nvidia-smi
    ```
3. 重新啟動 Docker Desktop，並確認使用 WSL2 backend。

### Docker 容器名稱衝突

**症狀**: `Conflict. The container name "/genai" is already in use`

**解決方案**:
```bash
docker rm -f genai
docker compose run --rm genai --count 1
```

### Docker 內 GPTQ 模型缺少套件

**症狀**: `ImportError: Loading a GPTQ quantized model requires optimum`

**解決方案**:
1. 重新建置映像（讓新依賴寫入容器）：
    ```bash
    docker build --progress=plain --no-cache -t genai:latest .
    ```
2. 若需在現有容器快速熱修：
    ```bash
    pip install optimum==1.23.3 auto-gptq==0.7.1 exllamav2==0.3.2 peft==0.11.1
    ```
3. 驗證容器內套件：
    ```bash
    python -c "from optimum.gptq.quantizer import GPTQQuantizer; GPTQQuantizer(bits=4); print('gptq deps ok')"
    ```

### Python 3.13 安裝失敗（safetensors 觸發 Rust 編譯）

**症狀**: 安裝時出現 `safetensors` metadata build error / Rust toolchain 錯誤

**原因**: 使用 Python 3.13 時，部分 pin 版本沒有對應 wheel，會退回原始碼編譯。

**解決方案**:
1. 使用 Python 3.11 建立環境（本專案標準）
2. 或執行自動腳本時明確指定 3.11：
   ```bash
   python scripts/setup_env.py --env-path genai_env --base-python C:/Users/<you>/miniconda3/envs/genai/python.exe
   ```

### 翻譯卡住不動

**症狀**: 翻譯進度停滯在某個百分比

**解決方案**:
1. **降低 Beam Size** (編輯 `trans.py`):
   ```python
   Config(beam_size=1)  # 犧牲品質換取速度
   ```
2. **啟用量化**:
   ```bash
   python trans.py --quantize
   ```

---

## 📦 套件版本確認

### 核心依賴版本

| 套件 | 版本 | 用途 | 相容性 |
|------|------|------|--------|
| **torch** | RTX50:`2.8.0+cu128` / RTX40:`2.6.0+cu124` | 深度學習框架 | ✅ 由自動腳本依硬體選擇 |
| **transformers** | 4.46.1 | LLM 推理 | ✅ 與 GPTQ 堆疊穩定相容 |
| **diffusers** | 0.30.0 | SDXL 推理 | ✅ 最新穩定版 |
| **accelerate** | 1.12.0 | 模型加速 | ✅ |
| **bitsandbytes** | 0.43.0+ | 量化支援 | ✅ Windows 相容 |
| **TTS** | 0.22.0 | 語音合成 | ✅ XTTS-v2 |
| **sentencepiece** | 0.1.99 | 分詞器 | ✅ NLLB 必需 |
| **safetensors** | 0.4.3 | 模型載入 | ✅ |

### 版本驗證

```bash
# 檢查核心套件
pip list | grep -E "torch|transformers|diffusers|TTS"

# 驗證 CUDA 版本
python -c "import torch; print(torch.version.cuda)"

# 驗證 GPTQ 相容路徑
python -c "from optimum.gptq.quantizer import GPTQQuantizer; GPTQQuantizer(bits=4); print('GPTQ path OK')"
```

### 已知相容性問題

⚠️ **注意事項**:
- 專案目前固定 `transformers==4.46.1` 以維持 GPTQ/runtime 穩定；Qwen3 會走相容 fallback 路徑，品質可能低於原生 Qwen3 支援。
- `torch 2.7` 不支援 sm_120，RTX 50 系列請使用 `torch 2.8.0+cu128`。
- `bitsandbytes` 在 Windows 上需要 CUDA 12.8+
- `TTS` 需要 Visual Studio C++ Build Tools
- `rembg` (去背功能) 為可選套件

---

## 🔐 資料隱私與安全

### 本地化優勢

本系統**完全本地運行**，無需網路連線或雲端 API：
- ✅ 所有模型在本機執行
- ✅ 故事內容不會外傳
- ✅ 無資料收集或遙測
- ✅ 符合 GDPR / COPPA 等隱私法規

### 模型授權

- **Qwen3-8B**: Apache 2.0 (商用友善)
- **NLLB**: CC-BY-NC 4.0 (非商用)
- **SDXL**: CreativeML Open RAIL++-M (限制生成內容)
- **XTTS**: Coqui Public Model License (研究/個人使用)

**商業使用須知**: 部分模型有非商用限制，商用前請檢查授權條款。

---

## 🚧 已知限制

1. **硬體需求高**: 至少需要 RTX 40 系列 (12GB VRAM) 才能流暢運行
2. **模型下載大**: 總計約 80GB，初次設定耗時
3. **英文為主**: 雖然支援多語翻譯，但 LLM 在英文上表現最佳
4. **XTTS 樣本需求**: 必須自備說話人樣本，無預設語音
5. **Windows 限定**: 主要針對 Windows 開發，macOS/Linux 需調整

---

## 🗺️ 開發路線圖

### v1.1 (計劃中)
- [ ] 支援 macOS/Linux
- [ ] Web UI (Gradio)
- [ ] 更多藝術風格模板
- [ ] 角色一致性增強 (LoRA 訓練)

### v1.2 (研究中)
- [ ] 即時語音生成 (Streaming TTS)
- [ ] 互動式故事編輯器
- [ ] 社群知識圖譜貢獻
- [ ] PDF/EPUB 自動排版

---

## 🙏 致謝

感謝以下開源專案:
- [Qwen](https://github.com/QwenLM/Qwen) by Alibaba Cloud
- [NLLB](https://github.com/facebookresearch/fairseq/tree/nllb) by Meta AI
- [Diffusers](https://github.com/huggingface/diffusers) by Hugging Face
- [TTS](https://github.com/coqui-ai/TTS) by Coqui AI

---

<div align="center">

**⭐ 如果這個專案對你有幫助，歡迎給我們一個 Star！**

用 ❤️ 為每個孩子打造

</div>
