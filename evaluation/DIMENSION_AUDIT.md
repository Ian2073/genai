# Dimension Audit (六大維度整理)

這份文件只整理六大評估維度：
- 可讀性 `readability`
- 情感影響力 `emotional_impact`
- 連貫性 `coherence`
- 實體一致性 `entity_consistency`
- 完整性 `completeness`
- 事實正確性 `factuality`

用途：給後續維護者快速看懂每個維度「吃什麼輸入、怎麼算、吐什麼輸出、有哪些風險」。

更新時間：2026-03-31

---

## 1. 可讀性（readability.py）

### 主要職責
- 評估故事語言是否適合兒童閱讀。
- 核心包含詞彙、句法、表達品質、認知友善度。

### 主要輸入
- `story_text`
- `target_age`（可選，未指定時會自動估）

### 本地依賴
- `consistency`（KG 與 AI 分析輔助）
- `utils`（句子切分、spaCy 載入）

### 典型輸出欄位
- `children_readability.scores.vocabulary_quality`
- `children_readability.scores.sentence_quality`
- `children_readability.scores.expression_quality`
- `children_readability.scores.cognitive_friendliness`
- `children_readability.scores.final`

### 維護風險
- 年齡分組門檻與詞彙表為硬編碼，調整成本高。
- 模型/資源失敗時會降級，分數穩定性可能改變。

---

## 2. 情感影響力（emotion.py）

### 主要職責
- 分析故事情感張力與感染力。
- 核心子分數：多樣性、強度、共鳴、真實性。

### 主要輸入
- `text`
- `story_title`

### 本地依賴
- `consistency`（AI/KG）
- `genre`（文體調整）
- `kb`（關鍵詞資源）

### 典型輸出欄位
- `emotional_impact.scores.diversity`
- `emotional_impact.scores.intensity`
- `emotional_impact.scores.resonance`
- `emotional_impact.scores.authenticity`
- `emotional_impact.scores.final`
- `emotional_impact.scores.confidence`

### 維護風險
- GoEmotions 模型不可用時會降級到關鍵詞模式。
- 短文/文體補償規則較多，容易造成分數偏高或偏低。

---

## 3. 連貫性（coherence.py）

### 主要職責
- 評估故事在語義、結構、主題、時間四個面向的連貫程度。

### 主要輸入
- `story_text`
- `documents`（可選，多來源文本）

### 本地依賴
- `consistency`（AI/KG）
- `kb`（時間詞、對比詞等語料）
- `shared.story_data`（故事檔掃描）

### 典型輸出欄位
- `coherence.scores.semantic`
- `coherence.scores.structural`
- `coherence.scores.thematic`
- `coherence.scores.temporal`
- `coherence.scores.final`
- `coherence.scores.confidence`

### 維護風險
- 語義模型為延遲載入，載入狀態會影響結果。
- 權重有 fallback 邏輯，調參時需看短文與長文差異。

---

## 4. 實體一致性（consistency.py）

### 主要職責
- 檢查角色/地點/稱呼是否前後一致。
- 子分數常見為命名、屬性、概念、指代四類。

### 主要輸入
- `text`
- `story_title`（可選）

### 本地依賴
- `kb`
- `utils`
- 延遲依賴：`evaluator` 的 `DocumentSourceManager`

### 典型輸出欄位
- `entity_consistency.scores.naming`
- `entity_consistency.scores.attribute`
- `entity_consistency.scores.conceptual`
- `entity_consistency.scores.reference`
- `entity_consistency.scores.final`
- `entity_consistency.scores.confidence`

### 維護風險
- 檔案非常大，責任集中，修改時回歸範圍大。
- 與 `evaluator.py` 存在延遲耦合，需避免直接硬耦合加深。
- 低實體數量有保守分數機制，會影響邊界案例。

---

## 5. 完整性（completeness.py）

### 主要職責
- 檢查故事結構是否完整。
- 核心四層：結構、語義、邏輯、功能。

### 主要輸入
- `story_text`
- `story_title`
- `language`

### 本地依賴
- `consistency`
- `genre`
- `kb`
- `utils`

### 典型輸出欄位
- `completeness.scores.structural`
- `completeness.scores.semantic`
- `completeness.scores.logical`
- `completeness.scores.functional`
- `completeness.scores.final`
- `completeness.scores.confidence`

### 維護風險
- 短文與文體有額外調整邏輯，規則較多。
- 模板關鍵詞偏硬編碼，擴充新文體需小心。

---

## 6. 事實正確性（factual.py）

### 主要職責
- 對可驗證敘述做事實核對與風險分級。
- 流程通常是聲明抽取 → 驗證 → 風險整合。

### 主要輸入
- `story_text`
- `story_title`
- 內部配置與驗證資源（可選）

### 本地依賴
- `consistency`（AI/KG）
- `kb`（多知識來源能力）
- `utils`（NLP 輔助）

### 典型輸出欄位
- `factuality.scores.claim_accuracy`
- `factuality.scores.verification_coverage`
- `factuality.scores.risk_assessment`
- `factuality.scores.final`
- `factuality.verification_results`

### 維護風險
- 虛構故事存在快速路徑（固定分附近），需避免誤判真實敘述。
- 多知識庫不可用時能力下降，分數解讀要看降級標記。

---

## 維度間共同維護建議

1. 先調配置，再改演算法。
2. 每次改維度邏輯後，至少跑一次：
   - `python scripts/validate.py --evaluated-dir output`
   - `python scripts/ops_dashboard.py --roots output --output reports/evaluation/ops_dashboard.json`
3. 若只改單一維度，仍要觀察總分策略（governance/policy）是否連動變化。