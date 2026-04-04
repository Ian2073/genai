# Student Guide (30-minute Quick Start)

這份指南給第一次接觸這個專案的大學生。
目標是：先玩得起來，再慢慢看細節。

## 1. 你會得到什麼

跑一次評估後，你會看到：
1. 總分（overall score）
2. 六個維度分數（readability、coherence 等）
3. 風險與信心（governance）
4. 改進建議（recommendations）

## 2. 最快開始方式（推薦）

### Step A. 準備一個故事資料夾

範例：

output/MyStory/full_story.txt

如果是多語言，可用：

output/MyStory/en/full_story.txt

### Step B. 跑單一故事評估

```bash
python main.py --input output/MyStory
```

完成後會在 `output/MyStory/assessment_report.json` 看到完整結果。

### Step C. 看重點欄位（可選）

先打開 `output/MyStory/assessment_report.json`，重點看：
1. `overall_score`（總分）
2. `dimension_scores`（六維度）
3. `governance`（風險與覆核建議）

## 3. 分數怎麼看（簡單版）

- 85+：A，整體很強
- 75-84：B，可用、還有優化空間
- 65-74：C，普通
- 55-64：D，需要明顯修改
- <55：E，建議重寫主要結構

## 4. governance 是什麼

governance 是「商用安全欄」：
1. confidence_score：模型對這次結果有多有把握
2. risk_level：low / medium / high / critical
3. review_recommendation：
   - auto_accept_recommended
   - spot_check_recommended
   - manual_review_required

理解方式：
- 高信心 + low risk：大致可靠
- 低信心 + high risk：要人工複查

## 5. 想進一步探索

1. 跑系統驗證：
```bash
python scripts/validate.py --evaluated-dir output
```

2. 跑營運監控摘要：
```bash
python scripts/ops_dashboard.py --roots output --output reports/evaluation/ops_dashboard.json
```

3. 一鍵跑整條流程：
```bash
python scripts/run_ops_pipeline.py --evaluated-dir output
```

## 6. 常見錯誤

1. 找不到 full_story.txt
- 檢查故事資料夾是否有 full_story.txt 或 en/full_story.txt

2. 模型沒載好
- 先看 README 的模型與 Docker 段落

3. 跑很慢
- 先只跑單一故事
- 再逐步增加批次

## 7. 你可以做的小專題

1. 比較不同文體（童話/寓言）在六維度上的差異
2. 寫一個故事改寫器，觀察改寫前後的治理風險變化
3. 做一份「高分但高風險」案例分析報告
