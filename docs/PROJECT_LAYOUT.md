# 專案目錄規劃

這份文件的目的，是讓專案不要再次把所有模組都塞回根目錄。

## 根目錄應該放什麼

根目錄建議只保留以下幾類：

- 主要流程入口
  - `chief.py`
  - `story.py`
  - `image.py`
  - `trans.py`
  - `voice.py`

其中 `chief.py` 現在是相容入口；
真正的主控 orchestration 實作已移到 `pipeline/chief_runner.py`，
CLI/entry 則已拆到 `pipeline/entry.py`。

`story.py` 目前也偏向相容與公開 API 表面；
設定型別與 standalone 入口已拆到：

- `story_core/`

- 少數高層共用模組
  - `utils.py`
  - `evaluator.py`
  - `kg.py`

- 啟動與部署入口
  - `Dockerfile`
  - `docker-compose.yml`
  - `Build_GenAI.bat`
  - `Build_GenAI_Docker.bat`
  - `Start_GenAI.bat`
  - `Start_GenAI_Docker.bat`

也就是說，根目錄應該偏向「使用者一眼就知道怎麼跑系統」的地方，而不是塞模型細節。

## 應該移進子目錄的類型

### `backends/`

放所有模型後端、provider registry、模型家族切換相關邏輯。

目前建議集中放：

- `backends/llm.py`
- `backends/llm_runtime_strategy.py`
- `backends/image.py`
- `backends/translation.py`
- `backends/voice.py`
- `backends/common.py`
- `backends/translation_common.py`

這一層的特色是：

- 會接觸第三方模型套件
- 會處理 device / dtype / quantization
- 會處理 provider 切換
- 會集中模型能力 / runtime readiness / selection policy
- 不應該直接負責故事流程或輸出檔案規劃

### `runtime/`

放執行期相容修補、shim、第三方套件 patch。

目前建議集中放：

- `runtime/compat.py`
- `runtime/compat_transformers.py`
- `runtime/exllamav2_shim.py`
- `runtime/story_files.py`

這一層的特色是：

- 不是業務流程
- 不是模型能力本身
- 是為了讓不同版本套件能正常合作
- 或集中主流程之間共用的檔案掃描/資產定位規則

例如 `runtime/story_files.py` 現在會集中管理：
- narration 頁面掃描
- story 語言偵測
- 最新故事資料夾定位
- resource 目錄搜尋
- image / audio 輸出檔探索

### `pipeline/`

放多模態主控流程的 orchestration 實作。

目前第二階段已集中：

- `pipeline/entry.py`
- `pipeline/options.py`
- `pipeline/chief_runner.py`
- `pipeline/chief_runtime.py`
- `pipeline/chief_verification.py`
- `pipeline/chief_workload_stats.py`
- `pipeline/chief_observability.py`
- `pipeline/__main__.py`

這一層的特色是：

- 協調各 stage 的執行順序
- 把 CLI/entry 與 runner 實作分離
- 把 request/runtime context、observability、驗證、統計邏輯拆到鄰近模組
- 保留 root-level `chief.py` 當相容入口
- 讓「入口檔」與「真正主控實作」分離，更接近實務專案安排

### `story_core/`

故事文字模組的內部 helper 已集中在 `story_core/`：

- `story_core/story_helpers.py`
  - generation params、token/分頁、prompt 長度檢查等共用工具
- `story_core/story_types.py`
  - `StoryInput`、`StoryRunConfig`、`PipelineOptions`
- `story_core/story_entry.py`
  - `main()`、`cli()`、`generate_story_id()`
- `story_core/story_state_io.py`
  - page structure 與 `<state_json>` snapshot 的讀寫/解析
- `story_core/story_outputs.py`
  - canonical branch 選擇、cover context、story meta、分支頁面蒐集等輸出產物協調
- `story_core/story_page_flow.py`
  - 頁碼區間決策、既有頁面預載、plan/write retry 輔助、full story 落盤
- `story_core/story_text_normalize.py`
  - 角色名稱一致性、文字清理、coref/alias 處理
- `story_core/story_branching.py`
  - 分支建立、切換、頁面繼承與 full story 組裝

root 保留 `story.py` 當對外入口，內部實作則進到 `story_core/`，避免 root 再次膨脹。

### `docs/`

放文件，而不是讓說明散在根目錄備忘錄或 README 的單一長文裡。

目前已經有：

- `docs/ENV_SETUP.md`
- `docs/RUNTIME_COMPAT.md`
- `docs/MODEL_BACKENDS.md`
- `docs/PROJECT_LAYOUT.md`
- `docs/LEGACY_FILES.md`
- `docs/archive/PHASE0_CONTRACT.md`
- `docs/archive/PHASE1_MIGRATION_MAP.md`

歷史研究筆記建議集中在：

- `docs/archive/`

例如原本在根目錄的 `sideproject.md` 已移到 `docs/archive/sideproject.md`。

### `scripts/`

放診斷、安裝、維運、自動化工具。

例如：

- `scripts/setup_env.py`
- `scripts/doctor.py`
- `scripts/run_experiment.py`
- `scripts/analyze_observability.py`
- `scripts/smoke_gate.py`
- `scripts/kg_demo.py`
- `scripts/check_root_layout.py`

### `research/`

放研究與論文分析資產，不與主線 runtime 混放。

目前已整理到：

- `research/paper/`

這些內容屬於研究分析路徑，不是 `chief.py` 主線執行依賴。

### `evaluation/`

放正式評測系統主線實作，屬於 runtime 能力的一部分。

目前由 root 入口腳本呼叫：

- `Build_GenAI.bat`（包含評測 extras 安裝）
- `Start_GenAI.bat --eval-only ...`
- `Build_GenAI_Docker.bat`
- `Start_GenAI_Docker.bat --eval-only ...`

## 目前採用的原則

這次整理後，專案採用以下原則：

1. 主流程檔留在根目錄。
2. 主控 orchestration 逐步放進 `pipeline/`。
3. 模型細節盡量放進 `backends/`。
4. 相容修補盡量放進 `runtime/`。
5. 文件放進 `docs/`。
6. 腳本放進 `scripts/`。
7. 故事內部 helper 集中在 `story_core/`，root 只保留對外入口。

另外已加上 root policy 檢查：

```bash
python scripts/check_root_layout.py --workspace-root . --strict
```

## 為什麼不一次把所有東西都搬光

因為這個專案目前仍有：

- 舊版流程
- 教學用途
- 可能被外部腳本直接 import 的檔案
- 暫時不想碰的檔案，例如 `story_qwen35_9b.py`

所以整理策略會偏向：

- 先把新架構的入口整理好
- 再逐步把實作搬進合適資料夾
- 最後才刪除不再需要的舊路徑

這樣風險比較低，也比較適合學生理解每一層在做什麼。
