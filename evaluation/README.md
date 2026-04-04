# Generative-AI 兒童故事評估系統

一個專為 AI 生成兒童故事打造的**自動化品質閘門（Quality Gate）**，提供六大維度的多層次評估。
系統全面使用開源模型，在 Docker + NVIDIA GPU 環境下運行，可批次處理約 100 本故事。

---

## ✨ 系統特色

- **六維度評估**：可讀性、情感影響力、連貫性、實體一致性、完整性、事實正確性
- **深度情感分析**：整合 GoEmotions（28 類情感分類器），取代純關鍵字匹配
- **單一 LLM 架構**：Qwen2.5-14B（INT4 量化），兼顧效能與 VRAM 效率
- **整合單入口部署**：由 root `Build_GenAI* / Start_GenAI*` 統一調度（生成優先）
- **智慧降級**：缺少模型或檔案時自動調整權重，標記降級報告
- **商用治理層**：每次評分輸出信心分數、風險旗標與人工覆核建議
- **視覺化報告**：自動生成六維度雷達圖與 JSON 詳細報告

---

## 🎓 Student Friendly Entry

如果你是第一次接觸這個專案，建議先走這條路：

1. 先看 [STUDENT_GUIDE.md](STUDENT_GUIDE.md)
2. 準備 `output/你的故事/full_story.txt`
3. 跑最簡單指令：

```bash
python main.py --input output/你的故事
```

這個入口會在 `output/你的故事/assessment_report.json` 輸出完整評估結果，
不需要先理解整個系統架構。

若你是後續維護者（大學生接手），請直接看：
- [MAINTAINER_GUIDE.md](MAINTAINER_GUIDE.md)
- [MODULE_AUDIT.md](MODULE_AUDIT.md)
- [DIMENSION_AUDIT.md](DIMENSION_AUDIT.md)

---

## 📋 環境需求

| 項目 | 需求 |
|------|------|
| **Python** | 3.11（本地 venv 模式） |
| **GPU** | NVIDIA GPU（建議 16 GB VRAM 以上，如 RTX 5070 Ti） |
| **驅動** | NVIDIA 驅動 + CUDA 12.4 |
| **Docker** | Docker Desktop（含 Docker Compose） |
| **NVIDIA Container Toolkit** | 用於容器內 GPU 存取 |
| **磁碟空間** | 約 35 GB（模型 + Docker 映像） |
| **作業系統** | Windows 10/11 或 Ubuntu 22.04+ |

---

## 🤖 使用的 AI 模型

所有模型需下載至 `models/` 資料夾。系統總模型大小約 **32.8 GB**。

### 核心模型

| 模型 | 路徑 | 大小 | 用途 |
|------|------|------|------|
| **Qwen2.5-14B** | `models/Qwen2.5-14B` | ~27.5 GB | 唯一 LLM，文字理解、推理分析、生成建議（INT4 量化） |
| **roberta-base-go_emotions** | `models/roberta-base-go_emotions` | ~0.93 GB | GoEmotions 28 類情感分類器，情感影響力分析 |
| **bge-large-zh-v1.5** | `models/bge-large-zh-v1.5` | ~1.21 GB | 語義相似度計算（中英文雙語） |
| **gliner_large-v2.1** | `models/gliner_large-v2.1` | ~1.66 GB | 命名實體識別（角色、地點提取） |

### 圖像分析模型（多模態評估，未來擴充用）

| 模型 | 路徑 | 大小 | 用途 |
|------|------|------|------|
| **BLIP** | `models/blip-image-captioning-base` | ~0.92 GB | 圖像描述生成 |
| **OWL-ViT** | `models/owlvit-base-patch16` | ~0.57 GB | 零樣本物件偵測 |
| **YOLOv8n** | `models/yolov8n.pt` | ~0.01 GB | 物件偵測 |

### NLP 模型（SpaCy，Docker 內自動安裝）

系統按優先順序嘗試載入：
1. `en_core_web_trf`（Transformer，最準確）
2. `en_core_web_lg`（大型）
3. `en_core_web_md`（中型）
4. `en_core_web_sm`（小型，最低需求）

### 模型下載方式

```bash
# 安裝 Hugging Face CLI
pip install huggingface_hub

# 核心模型（必要）
huggingface-cli download Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4 --local-dir models/Qwen2.5-14B
huggingface-cli download BAAI/bge-large-zh-v1.5 --local-dir models/bge-large-zh-v1.5
huggingface-cli download urchade/gliner_large-v2.1 --local-dir models/gliner_large-v2.1
huggingface-cli download SamLowe/roberta-base-go_emotions --local-dir models/roberta-base-go_emotions

# 圖像模型（可選，未來多模態擴充用）
huggingface-cli download google/owlvit-base-patch16 --local-dir models/owlvit-base-patch16
huggingface-cli download Salesforce/blip-image-captioning-base --local-dir models/blip-image-captioning-base
# YOLOv8 由 ultralytics 自動下載，或手動放置至 models/yolov8n.pt
```

---

## 🚀 快速開始（整合單入口）

### 1. 取得程式碼

```bash
git clone https://github.com/your-username/Generative-AI-evaluation-system.git
cd Generative-AI-evaluation-system
```

### 2. 下載模型

按照上方「模型下載方式」，將核心模型下載至 `models/` 資料夾。

### 3. 建立必要資料夾

```powershell
# Windows PowerShell
mkdir models, output, reports
```

```bash
# Linux/macOS
mkdir -p models output reports
```

### 4. 本地整合模式（單一入口）

```cmd
Build_GenAI.bat
Start_GenAI.bat --eval-only --input output --post-process none
```

本地模式重點：
- ✅ 單一環境：`genai_env`
- ✅ 先安裝 root 生成主線 `requirements.txt`（生成優先）
- ✅ 再安裝 evaluation `requirements.txt`（評測專屬 extras）
- ✅ 評測命令由 `Start_GenAI.bat --eval-only ...` 直接執行
- ✅ 避免雙環境漂移，確保執行環境一致

#### 4.1 預設 Python 執行環境（標準化）

- 預設解譯器：`genai_env/Scripts/python.exe`
- 建議所有本地命令走同一路徑：

```cmd
Start_GenAI.bat --eval-only --input output\故事名稱
genai_env\Scripts\python.exe evaluation\scripts\validate.py --evaluated-dir output
```

- 若需要直接用 Python 跑（例如 CI 或實驗環境），可使用：

```cmd
genai_env\Scripts\python.exe main.py --input output\故事名稱
```

若你在 workspace root 執行，請改用：

```cmd
genai_env\Scripts\python.exe evaluation\main.py --input output\故事名稱
```

### 5. Docker 模式（部署推薦）

```cmd
Build_GenAI_Docker.bat
Start_GenAI_Docker.bat --eval-only --input output --post-process none
```

Docker 模式重點：
- ✅ 分離 build 與 start，避免每次啟動都重建映像
- ✅ 啟動 `story-checker` + `coref-service`
- ✅ 等待 coref 健康檢查，支援 `--genai-only` / `--eval-only`

### 6. 手動啟動（跨平台）

```bash
# 建置並啟動容器
docker compose up -d --build

# 等待 coref 服務就緒
docker compose exec story-checker bash -lc "
  until curl -sf http://coref-service:8001/health; do sleep 5; done
"

# 進入容器
docker compose exec story-checker bash
```

---

## 🎯 使用方式

所有評估命令可在 **本地 venv 或容器內** 執行：

### 基本使用

```bash
# 評估 output/ 中所有故事
python main.py

# 評估單一故事
python main.py --input output/故事名稱

# 只評估特定維度
python main.py --aspects coherence readability emotional_impact
```

### 支援的六大維度

| 維度 | 參數名稱 | 說明 |
|------|----------|------|
| 可讀性 | `readability` | 語言是否適合目標讀者（兒童） |
| 情感影響力 | `emotional_impact` | 情感多樣性、強度、共鳴力、真實性 |
| 連貫性 | `coherence` | 情節是否流暢合理 |
| 實體一致性 | `entity_consistency` | 角色、地點命名的一致性 |
| 完整性 | `completeness` | 故事結構是否完整（起承轉合） |
| 事實正確性 | `factuality` | 事實陳述是否準確（虛構作品自動降權） |

### 生成批次報告

```bash
python scripts/report.py
```

### 營運監控摘要（商用運維）

```bash
# 從 output 生成營運儀表摘要
python scripts/ops_dashboard.py --roots output --output reports/evaluation/ops_dashboard.json
```

輸出包含：
- 分數統計（mean/median/min/max）
- 延遲統計（mean/p50/p95/max）
- 治理覆蓋率與風險分佈
- 常見風險旗標 Top N

### 穩定性對抗測試（無需人工標註資料）

```bash
# 對單一故事執行擾動測試（段落打亂、截斷結尾、噪音注入）
python scripts/stability_check.py --input output/故事名稱/full_story.txt
```

輸出：
- `reports/evaluation/stability_check_report.json`
- 測試通過率（pass ratio）與穩定性狀態（good/warning/bad）

`scripts/validate.py` 亦已整合：
- 治理層健康度檢查（confidence/risk/review 分佈）
- 策略回歸測試（跨維度硬約束與共識融合）

### 一鍵營運管線

```bash
# 跑 validate + report + ops dashboard
python scripts/run_ops_pipeline.py --evaluated-dir output
```

可選：

```bash
# 含合成測試
python scripts/run_ops_pipeline.py --evaluated-dir output --with-synthetic

# 跳過 report，只做 validate + dashboard
python scripts/run_ops_pipeline.py --skip-report
```


---

## 📁 故事資料夾結構

### 待評估的故事放置位置

```
output/
└── 故事名稱/
    ├── full_story.txt      # 完整故事文本（必要）
    ├── title.txt           # 故事標題（可選）
    ├── outline.txt         # 故事大綱（可選）
    ├── narration.txt       # 旁白部分（可選）
    ├── dialogue.txt        # 對話部分（可選）
    └── resources/          # 多模態資源（可選）
        ├── page_01_prompt.txt
        ├── character_main.txt
        └── images/
            └── page_01.png
```

### 多語言支援

```
output/
└── 故事名稱/
    ├── en/                 # 英文版本
    │   ├── full_story.txt
    │   ├── narration.txt
    │   └── dialogue.txt
    └── zh/                 # 中文版本
        ├── full_story.txt
        ├── narration.txt
        └── dialogue.txt
```

系統會自動偵測並使用適當的語言版本。

### 已評估的故事

評估完成後，結果會直接寫回故事目錄（建議使用 root `output/`），並生成：

- `assessment_report.json`：詳細 JSON 評估報告
- `assessment_radar.png`：六維度雷達圖

---

## 📊 評分架構

### 評分治理輸出（商用建議）

每次評估結果會額外輸出 `governance` 欄位：

- `confidence` / `confidence_score`：模型信心（0-1 / 0-100）
- `risk_level`：`low` / `medium` / `high` / `critical`
- `review_recommendation`：`auto_accept_recommended` / `spot_check_recommended` / `manual_review_required`
- `risk_flags`：具體風險原因（例如維度失敗、降級、結構不一致）

此欄位可直接用於商用流程分流：
- 低風險高信心：自動通過
- 中風險：抽樣覆核
- 高風險或關鍵旗標：人工必審

### 權重分配

系統使用 YAML 先驗權重，不依賴校準模型：

| 維度 | 全域權重 | 童話權重 |
|------|----------|----------|
| 可讀性 | 28% | 28% |
| 情感影響力 | 25% | 28% |
| 連貫性 | 22% | 15% |
| 實體一致性 | 13% | 10% |
| 完整性 | 10% | 18% |
| 事實正確性 | 2% | 1% |

權重可在 `config/rating_weights.yaml` 中自訂。

### 情感影響力分析（GoEmotions 整合）

情感維度使用 `SamLowe/roberta-base-go_emotions` 模型，包含四個子維度：

1. **情感多樣性**：偵測故事中出現的情感家族數量（28 類 → 8 大家族）
2. **情感強度**：分析情感弧線的張力變化
3. **情感共鳴力**：評估情感表達的深度與感染力
4. **情感真實性**：檢測情感表達是否自然流暢

### 自動降權機制

- **事實正確性**：偵測到虛構內容固定分數（如 70.0）時，自動將 factuality 權重歸零並重分配
- **文體調整**：根據 `GenreDetector` 偵測結果套用文體權重（童話、寓言等）

---

## ⚙️ 進階配置

### 環境變數

| 變數 | 功能 | 預設值 |
|------|------|--------|
| `MODEL_ROOT_HOST_PATH` | Docker 掛載模型主機路徑 | `./models` |
| `DEFAULT_MODEL_PATH` | 主要 LLM 路徑 | `/app/models/Qwen2.5-14B` |
| `GENERATION_KG_MODULE_PATH` | 新生成系統 `kg.py` 路徑覆寫 | 自動探測 |
| `USE_4BIT_QUANTIZATION` | 啟用 INT4 量化 | `true` |
| `USE_CPU_HYBRID` | CPU/GPU 混合推理 | `true` |
| `USE_CPU_FOR_SEMANTIC` | 語義模型跑 CPU | `true` |
| `DISABLE_CALIBRATION` | 停用 XGBoost 校準 | `true` |
| `COREF_SERVICE_URL` | 共指服務 URL | `http://coref-service:8001` |
| `COREF_BACKEND_MODE` | 共指後端模式（`auto`/`remote`/`rules`） | `auto` |
| `COREF_TIMEOUT_SEC` | 共指遠端請求超時秒數 | `120` |
| `COREF_DEVICE` | coref 服務運算裝置偏好 | `auto` |
| `COREF_MAX_TOKENS` | coref 服務單批次 token 上限 | `2048` |
| `EVAL_PARALLEL_ENABLED` | 啟用並行處理 | `true` |
| `EVAL_MAX_PARALLEL_DIMENSIONS` | 最大並行維度數 | `3` |
| `EVAL_PRELOAD_MODELS` | 預載所有模型 | `false` |
| `EVAL_FAST_MODE` | 快速模式 | `false` |
| `GOVERNANCE_CONFIG_PATH` | 評分治理配置檔路徑 | `config/governance.yaml` |
| `SCORE_POLICY_CONFIG_PATH` | 共識與硬約束策略配置檔路徑 | `config/score_policy.yaml` |
| `EVAL_GPU_MEMORY_LIMIT` | 實體一致性模組 GPU 記憶體保守上限（GB） | `10` |
| `RATING_WEIGHTS_PATH` | 維度權重配置檔路徑 | `config/rating_weights.yaml` |

### .env.example 變數對應地圖

以下對應用於避免「有變數但不知道誰在吃」：

- `MODEL_ROOT_HOST_PATH`：由 `docker-compose.yml` 使用，掛載 `story-checker` 與 `coref-service` 的 `/app/models`。
- `DEFAULT_MODEL_PATH`：由 `utils.py` / `evaluator.py` / `consistency.py` 等模型載入入口使用。
- `GENERATION_KG_MODULE_PATH`：由 `utils.py` + `consistency.py` 的 KG 載入流程使用。
- `DISABLE_CALIBRATION`：由 `evaluator.py` 的校準開關使用。
- `USE_4BIT_QUANTIZATION`：由 `docker-compose.yml` 傳入主容器，供 LLM 載入策略讀取。
- `USE_CPU_HYBRID`：由 `docker-compose.yml` 傳入主容器，供推理模式讀取。
- `USE_CPU_FOR_SEMANTIC`：由 `coherence.py` / `completeness.py` 的語義模型裝置選擇使用。
- `COREF_SERVICE_URL`：由 `consistency.py` 的 coref adapter 與 `docker-compose.yml` 使用。
- `COREF_BACKEND_MODE`：由 `consistency.py` 的 coref adapter 使用（`auto` / `remote` / `rules`）。
- `COREF_TIMEOUT_SEC`：由 `consistency.py` 的 coref adapter 使用。
- `COREF_DEVICE`：由 `coref.py` 服務啟動時讀取。
- `COREF_MAX_TOKENS`：由 `coref.py` 服務推論批次上限讀取。
- `EVAL_PARALLEL_ENABLED`：由 `main.py` 讀取（相容保留欄位）。
- `EVAL_MAX_PARALLEL_DIMENSIONS`：由 `main.py` 讀取（相容保留欄位）。
- `EVAL_PRELOAD_MODELS`：由 `main.py` 讀取，控制模型預載。
- `EVAL_FAST_MODE`：由 `main.py` / `factual.py` / `consistency.py` 讀取。
- `EVAL_GPU_MEMORY_LIMIT`：由 `consistency.py` 讀取，限制部分模組 GPU 佔用。
- `GOVERNANCE_CONFIG_PATH`：由 `shared/score_governance.py` 讀取。
- `SCORE_POLICY_CONFIG_PATH`：由 `shared/score_policy.py` 讀取。
- `RATING_WEIGHTS_PATH`：由 `evaluator.py` 讀取。

### 配置檔案

| 檔案 | 用途 |
|------|------|
| `config/rating_weights.yaml` | 評分維度權重、文體覆蓋、融合策略 |
| `config/governance.yaml` | 商用治理門檻（confidence/risk/review 規則） |
| `config/score_policy.yaml` | 總分共識融合與跨維度硬約束策略 |
| `aspects_sources.yaml` | 各維度對不同文檔來源的權重與降級策略 |
| `config/local_categories.yaml` | 自訂分類關鍵字 |

範例：

```bash
# 使用單一路徑配置（推薦，最容易維護）
python main.py --input output
```

若有特殊實驗需求，可用 `GOVERNANCE_CONFIG_PATH` 或 `SCORE_POLICY_CONFIG_PATH` 指向自訂檔案。

---

## 🐳 Docker 架構

系統由兩個容器組成：

```
┌─────────────────────────────────────────────┐
│  story-checker（主容器）                      │
│  ├─ Qwen2.5-14B (INT4, GPU)                 │
│  ├─ GoEmotions RoBERTa (GPU/CPU)            │
│  ├─ bge-large-zh-v1.5 (CPU)                 │
│  ├─ GLiNER Large v2.1                        │
│  └─ SpaCy NLP Models                        │
│                  ↓ HTTP                       │
│  coref-service（共指消解服務）                  │
│  └─ fastcoref (GPU)                          │
└─────────────────────────────────────────────┘
```

- **基礎映像**：`nvidia/cuda:12.4.1-devel-ubuntu22.04`
- **Python**：3.11
- **模型掛載**：`models/` 以唯讀方式掛載至 `/app/models/`
- **coref-service**：獨立容器，提供 REST API（`/health`、`/coref/resolve`）

### Coref 後端策略與容器退場路線

- 評測端已改為 backend adapter 架構：`shared/coref_backends.py`。
- 目前可用策略：
    - `auto`：優先 `remote_fastcoref`，失敗時自動降級 `fallback_rules`
    - `remote`：強制遠端，失敗時降級並標記 `degradation_reason`
    - `rules`：純規則降級模式（不依賴容器服務）
- `llm_coref` 已預留介面，尚未正式啟用。
- dedicated `coref-service` 的退場條件與流程，請參考 ADR：
    - [docs/adr/ADR-0001-coref-backend-retirement.md](docs/adr/ADR-0001-coref-backend-retirement.md)

---

## 🧑‍💻 專案結構

```
.
├── main.py              # CLI 入口程式
├── evaluator.py         # 核心評估器（六維度調度、權重融合、模型管理）
├── consistency.py       # 實體一致性檢測
├── completeness.py      # 完整性檢測
├── coherence.py         # 連貫性檢測
├── readability.py       # 可讀性檢測
├── factual.py           # 事實正確性檢測
├── emotion.py           # 情感影響力檢測（GoEmotions 整合）
├── genre.py             # 文體偵測器
├── multimodal.py        # 多模態檢測（可選）
├── utils.py             # 共用工具函數
├── kb.py                # 知識庫系統
├── coref.py             # 共指服務封裝
├── scripts/
│   ├── report.py        # 報告與可視化生成腳本
│   ├── validate.py      # 評估品質驗證腳本
│   ├── stability_check.py # 無標註擾動穩定性測試腳本
│   ├── ops_dashboard.py # 營運監控摘要（風險/信心/延遲）
│   ├── run_ops_pipeline.py # 一鍵營運管線（validate/report/dashboard）
│   ├── calibrate.py     # 校準模型重建腳本
│   ├── update_metadata_counts.py # metadata 計數維護腳本
│   └── __init__.py
├── shared/
│   ├── story_data.py    # 故事目錄掃描、metadata/報告讀取、full_story 探勘
│   ├── score_utils.py   # raw/calibrated 分數欄位正規化與提取
│   ├── stats_utils.py   # 相關係數與統計函式
│   ├── coref_backends.py # 共指 backend adapter（remote/rules/llm 預留）
│   ├── score_governance.py # 商用評分治理（信心、風險、覆核建議）
│   ├── score_policy.py  # 共識融合與跨維度硬約束策略
│   └── __init__.py
├── aspects_sources.yaml # 文檔權重配置
├── requirements.txt     # Python 依賴
├── Dockerfile           # 主容器映像
├── Dockerfile.coref     # 共指服務映像
├── (由 root 入口統一管理)
│   - Build_GenAI.bat
│   - Start_GenAI.bat --eval-only ...
│   - Build_GenAI_Docker.bat
│   - Start_GenAI_Docker.bat --eval-only ...
├── STUDENT_GUIDE.md     # 給大學生的 30 分鐘快速指南
├── MAINTAINER_GUIDE.md  # 給後續維護者的單一路徑維護手冊
├── MODULE_AUDIT.md      # 全系統模組職責與引用關係整理
├── DIMENSION_AUDIT.md   # 六大維度的輸入/輸出/依賴與風險整理
├── config/
│   ├── rating_weights.yaml   # 評分權重
│   ├── governance.yaml      # 商用治理門檻設定
│   ├── score_policy.yaml    # 共識融合與跨維度硬約束設定
│   └── local_categories.yaml # 分類關鍵字
├── docs/
│   └── adr/
│       └── ADR-0001-coref-backend-retirement.md
└── kg/                  # 知識圖譜核心程式碼
    ├── __init__.py
    └── kg.py
```

---

## ❓ 常見問題

### Q: 最低需要哪些模型？

A: 至少需要 **Qwen2.5-14B** 和 **bge-large-zh-v1.5**，系統才能正常運作。
GoEmotions 模型缺失時會自動降級為關鍵字情感分析。GLiNER 缺失時使用 SpaCy NER。

### Q: 為什麼 factuality 分數很低？

A: 系統針對兒童故事（虛構內容）會偵測到固定分數並自動將 factuality 權重歸零，
不影響總分計算。這是預期行為。

### Q: 校準功能是什麼？

A: `scripts/calibrate.py` 提供基於人工評分的 XGBoost 校準，
目前已透過 `DISABLE_CALIBRATION=true` 停用。
純 YAML 先驗權重已能產生合理的評估結果。

### Q: 如何只評估部分維度？

```bash
python main.py --aspects coherence readability
```

### Q: Docker 容器內模型載入緩慢？

A: 可以：
- 將模型放在 SSD/NVMe 上
- 啟用 `EVAL_PRELOAD_MODELS=true` 預載所有模型
- 調整 `EVAL_MAX_PARALLEL_DIMENSIONS` 控制並行數

### Q: 缺少某些檔案會怎樣？

A: 系統會自動降級並繼續執行：
- 缺少語義模型 → 使用詞彙重疊代替語義相似度
- 缺少 GoEmotions → 降級為關鍵字情感分析
- 缺少 SpaCy 模型 → 使用規則分句

---

## 📝 授權與貢獻

歡迎針對評估邏輯、報告格式或多模態處理提出 Issue 或 Pull Request！

---

## 📞 聯絡資訊

如有問題或建議，請透過 GitHub Issues 聯繫。
