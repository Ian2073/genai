# 環境設定指南

本文件是此儲存庫的執行環境基準，特別用於專案搬移到另一台電腦時的部署與排錯。

## 1. Windows 首選流程（建議）

1. 在專案根目錄執行 `Build_GenAI.bat`。
	- 腳本會自動偵測 C++ Build Tools，若缺失會嘗試自動安裝。
	- 若你不希望自動安裝，可用 `Build_GenAI.bat --no-install-msvc-if-missing`。
2. 此腳本會自動完成：
- 建立或更新 `genai_env`
- 在可用時自動定位 Python 3.11
- 偵測 GPU 類型（RTX 50 / RTX 40 / CPU）
- 安裝對應的 PyTorch profile
- 依 `requirements.txt` 安裝過濾後依賴
- 安裝專用 spaCy 模型 wheel 並套用專案 allowlist
- 清理 `torch_extensions` 下舊的 `exllamav2_ext` JIT 快取（避免 MSVC toolset 變動後 linker 符號錯誤）
- 執行 `scripts/doctor.py` 診斷
- 若缺少 `cl.exe` 則給出警告，但不阻斷安裝
3. 用 `Start_GenAI.bat` 開啟執行 shell。
4. 儀表板模式使用 `Start_GenAI.bat --dashboard`。
5. 若需要檢查並修復 MSVC/C++ 工具鏈與本機環境，使用 `Build_GenAI_DevTools.bat`。

### Windows 一鍵流程涵蓋範圍

Windows 路線的目標是在新機器上做到「盡可能接近一鍵完成」。

可自動化項目：
- Python 環境建立
- 依 GPU 自動選擇 torch profile
- 過濾依賴安裝
- spaCy 模型安裝
- smoke 測試與 doctor 檢查
- MSVC 偵測（支援 `VSINSTALLDIR`、`vswhere`、`%ProgramFiles%` 與 `%ProgramFiles(x86)%` 路徑回退）

無法完全自動化項目：
- NVIDIA 驅動安裝
- Visual Studio Build Tools 安裝
- 模型 checkpoint 下載/拷貝
- 受限電腦權限設定

目前缺少 `cl.exe` 會被視為效能警告，而不是預設 GPTQ 文本路徑的硬性阻擋條件。
在此情況下，系統可能略過 exllamav2 JIT kernel，改用較慢的 AutoGPTQ fallback，而非靜默切換到其他文本模型。

若 `vcvars64.bat` 未被偵測到，但 shell 已有可用的 `cl.exe`，`Build_GenAI_DevTools.bat` 會視為 MSVC 可用，不再誤報 `MSVC tools: not found`。

## 2. 各 GPU Profile 的安裝內容

- RTX 50 profile：
- `torch==2.8.0+cu128`
- `torchvision==0.23.0+cu128`
- `torchaudio==2.8.0+cu128`
- `torchcodec==0.7.0`

- RTX 40 profile：
- `torch==2.6.0+cu124`
- `torchvision==0.21.0+cu124`
- `torchaudio==2.6.0+cu124`
- `torchcodec==0.7.0`

`scripts/setup_env.py` 會先安裝 profile 釘選的 `torchcodec`，若該版本在目標機器不可用（例如 PyPI 移除舊版），會自動退回安裝可用最新版，避免整體建置直接失敗。

- CPU profile：
- `torch==2.8.0`
- `torchvision==0.23.0`
- `torchaudio==2.8.0`

## 3. 手動設定（不使用 bat 腳本時）

```powershell
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series auto
genai_env\Scripts\activate
python scripts/doctor.py --expect-cuda auto
```

若要強制指定 profile，可使用：

```powershell
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series 50
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series 40
python scripts/setup_env.py --env-path genai_env --install-scope full --gpu-series cpu
```

## 4. Docker 模式

```powershell
docker build --progress=plain -t genai:latest .
docker compose up --build
```

Windows 互動式 shell：

```powershell
Start_GenAI_Docker.bat
```

Windows Docker 儀表板：

```powershell
Start_GenAI_Docker.bat --dashboard
Start_GenAI_Docker.bat --dashboard --dashboard-port 8766 --dashboard-no-open
```

Windows 一鍵 Docker 建置：

```powershell
Build_GenAI_Docker.bat
```

Docker 模式現在與 `scripts/setup_env.py` 使用相同依賴策略，包含：
- CUDA 12.8 對應的 torch profile 釘選
- 專用 spaCy 模型 wheel 安裝
- 安裝 spaCy 模型後，恢復釘選 GPTQ/runtime 套件
- image build 期間執行 import smoke 驗證

## 5. Runtime 腳本對照

- `Build_GenAI.bat`：本地環境一鍵建置 + 診斷
- `Build_GenAI_Docker.bat`：Docker image 一鍵建置
- `Build_GenAI_DevTools.bat`：開啟含 MSVC 的 shell（供編譯/JIT 排錯）
- `Start_GenAI.bat`：本地終端模式啟動
- `Start_GenAI.bat --dashboard`：本地儀表板模式啟動
- `Start_GenAI_Docker.bat`：Docker 終端模式啟動
- `Start_GenAI_Docker.bat --dashboard`：Docker 儀表板模式啟動

`Start_GenAI_Docker.bat` 會優先重用既有 `genai:latest`，只有 image 缺失時才自動建置。
- `scripts/run_experiment.py`：批次實驗入口
- `scripts/analyze_observability.py`：觀測摘要分析工具
- `scripts/setup_env.py`：GPU 感知依賴安裝器
- `scripts/doctor.py`：執行期與 CUDA 診斷工具

## 6. 跨機遷移檢查清單

1. 確認可看到 NVIDIA 驅動（`nvidia-smi`）。
2. 確認實際使用的是專案指定 Python 環境。
3. 確認同一環境中 `torch.cuda.is_available()` 為 `True`。
4. 確認目標機器 `models/` 下模型資料夾完整存在。
5. 確認 GPTQ 堆疊版本已釘選（`optimum==1.23.3`、`auto-gptq==0.7.1`）。

## 7. Qwen3 相容性說明

目前專案固定使用 `transformers==4.46.1`，以維持整體 GPTQ/runtime 堆疊穩定。

這有一個重要取捨：

- `models/Qwen3-8B` 是原生 Qwen3 checkpoint
- `transformers 4.46.1` 不原生支援 Qwen3
- 執行期因此退回 legacy Qwen2 相容路徑

實務上該 fallback 雖可執行，但輸出品質可能低於原生 Qwen3 支援路徑。
專案 doctor 已明確對此提出警示。

因此目前預設偏好：

- 主要本地文本模型：`models/Qwen2.5-14B-Instruct-GPTQ-Int4`
- 相容 fallback：`models/Qwen3-8B`

若你在不依賴舊 GPTQ 堆疊的機器上追求較佳 Qwen3 品質，建議：

- 升級 `transformers` 至 `4.51+`
- 或將預設本地文本模型改為 Qwen2.5 相容 checkpoint

## 8. 重要提醒

第二台機器上的 CUDA 失敗，多數是環境不匹配，不是模型檔損壞。
常見根因包括：
- 使用了錯誤的 Python 環境
- torch CUDA wheel 與驅動/toolkit 不匹配
- GPU runtime 可見性缺失
- 模型資料夾缺漏或 checkpoint 拷貝不完整
