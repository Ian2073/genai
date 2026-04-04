# Maintainer Guide (Student Edition)

這份文件給「後續要維護專案」的大學生。
重點是：簡單、單一路徑、不要太多模式。

## 維護原則

1. 優先維持單一路徑流程，不新增分支模式。
2. 新功能先補測試腳本，再改核心邏輯。
3. 能在 README 與本文件一句話講清楚的，才算完成。
4. 若功能需要太多開關，先問：是不是可以用一個預設做完？

## 你每天會用到的 3 個指令

1. 跑完整檢查：
```bash
python scripts/run_ops_pipeline.py --evaluated-dir output
```

2. 只看監控摘要：
```bash
python scripts/ops_dashboard.py --roots output --output reports/evaluation/ops_dashboard.json
```

3. 看系統健康（含策略回歸）：
```bash
python scripts/validate.py --evaluated-dir output
```

## 重要檔案（先看這些）

1. 核心評分：`evaluator.py`
2. 治理層：`shared/score_governance.py`
3. 總分策略：`shared/score_policy.py`
4. 全模組整理：`MODULE_AUDIT.md`
5. 六大維度整理：`DIMENSION_AUDIT.md`
6. 主配置：
   - `config/rating_weights.yaml`
   - `config/governance.yaml`
   - `config/score_policy.yaml`

## 變更流程（最小可行）

1. 修改配置（優先）：
- 先調 YAML，不要先改程式。

2. 修改程式（必要才做）：
- 改完先跑：
  - `python scripts/validate.py --evaluated-dir output`
  - `python scripts/ops_dashboard.py --roots output`

3. 更新文件：
- README 加 1 段說明
- 本文件加 1 條維護注意

## 常見維護任務

1. 風險太高（high/critical 比例偏高）
- 先看 `config/governance.yaml`
- 再看 `shared/score_policy.py` 的硬約束是否過嚴

2. 分數不穩
- 跑 `scripts/stability_check.py`
- 看 `reports/evaluation/stability_check_report.json`

3. 跑太慢
- 先看 `ops_dashboard.json` 的 p95 latency
- 再檢查模型/容器資源

## 不建議做的事

1. 為了單一案例加一堆例外模式。
2. 同時新增多個配置入口（會讓接手者很痛苦）。
3. 只改程式不改文件。

## 交接清單（給下一位維護者）

每次大改版前，請至少提供：
1. 你改了哪些檔案
2. 你跑了哪些驗證指令
3. 風險分佈有沒有變化
4. 哪些行為是「刻意改變」
