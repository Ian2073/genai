# 專案經理視角

本文件提供儲存庫的管理層操作視角。

## 1. 優先優化目標

1. 新加入成員可在 10 分鐘內完成系統啟動。
2. Root 目錄維持穩定且易理解。
3. Runtime 程式碼與研究程式碼在實體路徑上明確分離。
4. 相容入口清楚、可控且可驗證。

## 2. 目前版面（決議）

1. Runtime 對外表面（root）：
   - `chief.py`、`story.py`、`image.py`、`trans.py`、`voice.py`
   - `Build_*.bat`、`Start_*.bat`
   - `README.md`、`requirements.txt`、`Dockerfile`、`docker-compose.yml`
   - 為相容性保留於 root 的共用模組：`utils.py`、`kg.py`、`evaluator.py`

2. Runtime 實作層：
   - `pipeline/`：流程編排與入口處理
   - `backends/`：模型供應者與策略
   - `runtime/`：相容 shim 與執行期 helper
   - `observability/`：指標/可靠性/報告
   - `story_core/`：故事內部 helper 模組
   - `evaluation/`：評測系統主線（品質閘門、分支評估、治理報告）

3. 非 Runtime 區域：
   - `research/`：實驗、論文資產、外部評估專案
   - `backups/`：歷史快照（僅封存）

## 3. 權責邊界

1. 產品/Runtime 變更：
   - 修改 `pipeline/`、`backends/`、`runtime/`、`story_core/`、`evaluation/`

2. 工具/維運變更：
   - 修改 `scripts/`

3. 文件變更：
   - 修改 `docs/`

4. 僅研究變更：
   - 修改 `research/`

## 4. 護欄機制

1. Root policy gate：

```bash
python scripts/check_root_layout.py --workspace-root . --strict
```

2. Archive boundary gate：

```bash
python scripts/check_archive_boundaries.py --workspace-root . --strict
```

3. Smoke gate：

```bash
python scripts/smoke_gate.py
```

4. Functional gate（合併前）：

```bash
python scripts/smoke_gate.py --run-functional
```

## 5. 變更管制規則

1. 未經明確核准，不得移除相容檔案（`chief.py`、`story.py`、`image.py`、`trans.py`、`voice.py`、`evaluator.py`）。
2. 任何新增 root 檔案都必須有正當理由，並同步反映到 `scripts/check_root_layout.py`。
3. 任何資料夾搬移後都必須執行：
   - import/path 驗證
   - smoke gate 驗證
   - 更新 `README.md` 與相關 docs 文件

## 6. 實務導覽（新成員）

1. 「我要怎麼跑起來？」
   - 先看 `README.md`
   - 依序執行 `Build_GenAI.bat` 與 `Start_GenAI.bat`

2. 「Pipeline 核心邏輯在哪？」
   - 從 `pipeline/chief_runner.py` 開始

3. 「故事生成內部邏輯在哪？」
   - 從 `story.py` 開始，再看 `story_core/`

4. 「模型相關細節在哪？」
   - 在 `backends/`

5. 「相容性修補在哪？」
   - 在 `runtime/`
