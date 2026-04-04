# 第 1 階段 Root 瘦身遷移地圖

本文件追蹤第 1 階段的具體 root 清理動作。

## 1. Root 層責任

Root 應主要保留：

1. 使用者入口（`chief.py`、啟動/建置腳本）
2. 為相容性保留的核心頂層模組（`story.py`、`image.py`、`trans.py`、`voice.py`、`kg.py`、`utils.py`、`evaluator.py`）
3. 專案設定/文件（`README.md`、`requirements.txt`、`Dockerfile`、`docker-compose.yml`）
4. 主要套件（`pipeline`、`backends`、`runtime`、`observability`、`scripts`、`docs`）

## 2. 本批次已完成

1. 啟動/建置腳本集合正規化為兩種環境（local/docker），並支援終端 + 儀表板模式。
2. 移除已淘汰的 wrapper 啟動/建置腳本。
3. 移除 root 的 legacy 筆記檔。
4. 新增 smoke gate 腳本：`scripts/smoke_gate.py`。
5. 新增第 0 階段契約文件：`docs/PHASE0_CONTRACT.md`。

## 3. 第一批實體搬移（已完成）

1. `kg_demo.py` -> `scripts/kg_demo.py`
2. `sideproject.md` -> `docs/archive/sideproject.md`

## 4. 第二批實體搬移（已完成）

1. `paper/` -> `research/paper/`
2. `Generative-AI-evaluation-system-main/` -> `research/Generative-AI-evaluation-system-main/`
3. 移除 root `__pycache__/`
4. 更新 `research/paper/_tmp_pick7.py` 為相對路徑讀檔

## 5. 第三批實體搬移（已完成）

1. `story_branching.py` -> `story_core/story_branching.py`
2. `story_entry.py` -> `story_core/story_entry.py`
3. `story_helpers.py` -> `story_core/story_helpers.py`
4. `story_outputs.py` -> `story_core/story_outputs.py`
5. `story_page_flow.py` -> `story_core/story_page_flow.py`
6. `story_state_io.py` -> `story_core/story_state_io.py`
7. `story_text_normalize.py` -> `story_core/story_text_normalize.py`
8. `story_types.py` -> `story_core/story_types.py`
9. Root 相容回滾：恢復 `evaluator.py`
10. 後續收斂：移除 root `shim.py`，統一使用 `runtime/exllamav2_shim.py`

## 6. Root 防護（已完成）

1. 新增 `scripts/check_root_layout.py`
2. 在 smoke gate 新增整合步驟：`root_layout_policy`

## 7. Phase 1 剩餘候選項

1. 將歷史實驗快照移出靠近 root 的主動工作流位置。
2. 若 root 契約變更，需同步更新 `scripts/check_root_layout.py` 內 allowlist。

## 8. Phase 2 邊界治理（已完成）

1. 新增 `scripts/check_archive_boundaries.py`。
2. 在 smoke gate 新增整合步驟：`archive_boundary_policy`。
3. 在 `docs/PHASE0_CONTRACT.md` 增加 archive gate 契約命令。

## 9. 驗證命令

```bash
python scripts/smoke_gate.py
python scripts/smoke_gate.py --skip-dashboard
python scripts/check_root_layout.py --workspace-root . --strict
python scripts/check_archive_boundaries.py --workspace-root . --strict
```
