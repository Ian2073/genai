# 第 0 階段契約與驗收關卡

本文件定義重構期間必須遵守的「不破壞契約」與驗收關卡。

## 1. 不破壞契約

重構期間，下列入口必須持續可用：

1. CLI 相容入口：`python chief.py --help`
2. 套件入口：`python -m pipeline --help`
3. 本地儀表板入口：`python -m pipeline --dashboard`
4. 執行期診斷入口：`python scripts/doctor.py --help`

建置/啟動腳本契約：

1. 本地建置：`Build_GenAI.bat`
2. Docker 建置：`Build_GenAI_Docker.bat`
3. 本地啟動終端/儀表板：`Start_GenAI.bat`、`Start_GenAI.bat --dashboard`
4. Docker 啟動終端/儀表板：`Start_GenAI_Docker.bat`、`Start_GenAI_Docker.bat --dashboard`

## 2. 驗收 Gate

## 2.1 CLI Gate

下列命令必須全數通過：

```bash
python chief.py --help
python -m pipeline --help
python scripts/doctor.py --help
python scripts/check_root_layout.py --workspace-root . --strict
python scripts/check_archive_boundaries.py --workspace-root . --strict
python scripts/smoke_gate.py
```

## 2.2 Functional Gate

最小單書執行（快速檢查可選、合併主線前必跑）：

```bash
python scripts/smoke_gate.py --run-functional
```

## 2.3 Artifact Gate

規則如下：

1. 執行期產物必須放在 `output`、`runs`、`logs`、`reports`。
2. 原始碼目錄不得被寫入執行產生檔案。
3. 故事輸出需維持分支結構並相容驗證流程。

## 2.4 文件 Gate

每一批重構後需同步：

1. 若使用者可見指令有變更，更新 `README.md`。
2. 若建置/啟動流程有變更，更新 `docs/ENV_SETUP.md`。
3. 保持本契約文件與實際命令一致。

## 3. 回滾流程

若某批次失敗：

1. 只回滾該批次實際變更過的檔案。
2. 重新執行 `python scripts/smoke_gate.py`。
3. 以更小範圍重新開批。

## 4. 回報格式

每一批重構應記錄：

1. Scope：變更檔案範圍
2. Risk：可能斷點/風險
3. Validation：實際執行的驗證命令
4. Outcome：通過/失敗與下一步

## 5. 最新基準

最近一次完成基準：

1. `python scripts/smoke_gate.py`
2. 結果：通過（CLI + root policy + dashboard 契約）
3. `python scripts/smoke_gate.py --run-functional`
4. 結果：通過（`functional_minimal` 成功）

完成 root 瘦身批次後，另外必須通過：

1. `python scripts/check_root_layout.py --workspace-root . --strict`
