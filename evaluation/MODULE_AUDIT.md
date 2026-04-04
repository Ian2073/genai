# Module Audit (System-Wide)

這份文件是全系統模組整理清單，包含：
1. 每個模組做什麼
2. 每個模組引用哪些本地模組
3. 主要外部依賴
4. 需要注意的耦合點

更新時間：2026-03-31

## 1) 核心流程模組

### main.py
- 職責：CLI 入口、批次/單本故事評估流程。
- 本地引用：evaluator, consistency, utils, shared.story_data。
- 主要外部依賴：argparse, rich, matplotlib。

### evaluator.py
- 職責：六維度總控、權重融合、governance/policy 套用。
- 本地引用：coherence, completeness, consistency, emotion, factual, readability, utils, shared.score_governance, shared.score_policy, shared.story_data。
- 主要外部依賴：yaml, numpy, torch, transformers, spacy, gliner, xgboost(可選)。

### consistency.py
- 職責：實體一致性分析與 AutoStoryProcessor。
- 本地引用：kb, utils；延遲引用 evaluator.DocumentSourceManager。
- 主要外部依賴：requests, networkx, transformers, torch。
- 注意：
  - 存在延遲 import 的雙向耦合設計（與 evaluator）。
  - 檔尾示例字串含舊模組名 story_consistency_checker（非執行路徑）。

## 2) 六大評估維度模組

### coherence.py
- 職責：連貫性評估。
- 本地引用：consistency, utils, shared.story_data。
- 外部依賴：numpy, torch, transformers。

### completeness.py
- 職責：完整性評估。
- 本地引用：consistency, genre, kb, utils, shared.story_data。
- 外部依賴：networkx, numpy, torch, transformers。

### readability.py
- 職責：可讀性評估。
- 本地引用：consistency, utils。
- 外部依賴：numpy, statistics。

### emotion.py
- 職責：情感影響力評估（含 GoEmotions 流程）。
- 本地引用：consistency, genre, kb, utils。
- 外部依賴：numpy, torch, transformers。

### factual.py
- 職責：事實正確性評估。
- 本地引用：consistency, kb, utils。
- 外部依賴：yaml, concurrent.futures。

### genre.py
- 職責：文體偵測與文體分數輔助。
- 本地引用：kb。
- 外部依賴：dataclasses, statistics。

## 3) 支援與服務模組

### kb.py
- 職責：本地分類、字詞映射與知識查詢工具。
- 本地引用：無。
- 外部依賴：requests, yaml。

### utils.py
- 職責：共用工具（路徑、NLP 載入、字串處理）。
- 本地引用：無。
- 外部依賴：spacy。

### coref.py
- 職責：coref 服務 API（FastAPI）。
- 本地引用：無。
- 外部依賴：fastapi, fastcoref, pydantic。

### multimodal.py
- 職責：多模態評估（圖文一致性）。
- 本地引用：consistency, utils。
- 外部依賴：PIL, ultralytics, torch, transformers, yaml。

## 4) shared 共用模組

### shared/story_data.py
- 職責：故事資料掃描、metadata/報告讀取、story records 匯整。

### shared/score_utils.py
- 職責：raw/calibrated 欄位正規化與抽取。

### shared/stats_utils.py
- 職責：統計工具（mean/median/stdev/相關係數）。

### shared/score_governance.py
- 職責：信心、風險、覆核建議計算。

### shared/score_policy.py
- 職責：跨維度硬約束與共識融合策略。

## 5) scripts 工具模組

### scripts/validate.py
- 職責：品質驗證與策略回歸檢查。
- 本地引用：shared.score_policy, shared.score_utils, shared.stats_utils, shared.story_data。

### scripts/report.py
- 職責：統計報告與 Excel 輸出。
- 本地引用：shared.score_utils, shared.stats_utils, shared.story_data，延遲引用 evaluator。

### scripts/ops_dashboard.py
- 職責：營運監控摘要（score/risk/latency）。
- 本地引用：shared.story_data, shared.stats_utils。

### scripts/run_ops_pipeline.py
- 職責：一鍵執行 validate + report + dashboard。

### scripts/stability_check.py
- 職責：無標註擾動穩定性測試。
- 本地引用：main。

### scripts/calibrate.py
- 職責：校準資料流程與模型訓練工具。
- 本地引用：evaluator, shared.story_data。

### scripts/update_metadata_counts.py
- 職責：metadata 計數維護。
- 本地引用：shared.story_data。

## 6) KG 模組

### kg/kg.py
- 職責：知識圖譜建立與視覺化。
- 本地引用：kb。
- 外部依賴：networkx, pandas, numpy, plotly。

### kg/__init__.py
- 職責：導出 KG 類別。

## 7) 當前重點風險

1. consistency.py 和 evaluator.py 之間有延遲耦合，雖可運作但維護成本較高。
2. consistency.py 檔尾示例字串含舊名稱 story_consistency_checker，可能讓新維護者誤解。
3. 多數維度模組直接依賴 consistency.py 的大型類別，若重構需先抽介面再分拆。

## 8) 建議維護順序

1. 先動配置：config/rating_weights.yaml, config/governance.yaml, config/score_policy.yaml。
2. 再動 shared：避免統計/分數欄位在各腳本分散實作。
3. 最後才動 evaluator 與 consistency 主流程。