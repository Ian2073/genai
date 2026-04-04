# 模組化獨立工作台規劃

## 1. 目標

把目前「一次跑完整 pipeline」的操作模式，擴充成「每個模組都能獨立運作」的工作台介面，並保留既有一鍵全流程能力。

核心要求：

1. 文本、圖片、翻譯、語音都能單獨啟動。
2. 每個模組介面都提供完整可調參數（像市面常見生成工具）。
3. 圖片可針對單張查看原始提示詞與生成參數，並做局部重生成。
4. 所有模組共享同一套任務管理（佇列、狀態、日誌、歷史）。

## 2. UI 架構

在現有 Dashboard 之上新增 `Modules` 分頁，底下再分 4 個工作台：

1. Text Studio
2. Image Studio
3. Translation Studio
4. Voice Studio

保留現有 `Overview`（全流程編排）和 `Run Detail`。

建議資訊架構：

1. 左側：輸入與參數設定
2. 右側：預覽、結果、歷史版本
3. 下方：任務日誌與錯誤診斷

## 3. 後端統一任務模型

新增「模組任務」層，不綁定 chief 全流程。

任務型別：

1. `pipeline`
2. `story`
3. `image`
4. `translation`
5. `voice`

共用任務欄位：

1. `job_id`
2. `job_type`
3. `status`（queued/running/completed/failed/stopped）
4. `payload`
5. `created_at`
6. `started_at`
7. `finished_at`
8. `error`
9. `artifacts`

建議儲存檔：

1. `runs/dashboard_jobs.json`
2. `runs/dashboard_job_events.json`
3. `runs/dashboard_module_history.json`

## 4. API 契約（規劃）

### 4.1 通用模組 API

1. `GET /api/modules/jobs`
2. `GET /api/modules/job-detail?job_id=...`
3. `POST /api/modules/run`
4. `POST /api/modules/stop`

`POST /api/modules/run` 範例：

```json
{
  "job_type": "image",
  "payload": {
    "story_root": "output/Cultural/4-5/The_Mysterious_Map_and_Magic_Tree",
    "task_type": "page",
    "task_id": "page_3",
    "positive_prompt": "...",
    "negative_prompt": "...",
    "width": 1024,
    "height": 768,
    "steps": 40,
    "guidance": 7.0,
    "seed": 12345,
    "skip_refiner": false,
    "refiner_steps": 10
  }
}
```

### 4.2 圖片工作台 API

1. `GET /api/images/items?story_root=...`
2. `GET /api/images/item-detail?story_root=...&task_id=...`
3. `POST /api/images/regenerate`
4. `GET /api/images/file?path=...`

`item-detail` 要回傳：

1. 圖片路徑
2. 原始 prompt（正/負）
3. 生成參數（尺寸、steps、guidance、seed、refiner）
4. 來源 prompt 檔路徑
5. 上次生成時間
6. 可回滾版本列表

## 5. 各模組欄位規格

### 5.1 Text Studio

1. 語言、年齡、類別、主題、子類別
2. `preset/custom` 輸入模式
3. 使用者素材與自由提示詞
4. 文字生成參數：temperature、top_p、top_k、max_tokens、repetition_penalty
5. 輸出路徑與 pages

### 5.2 Image Studio

1. 正向提示詞、負向提示詞
2. 寬高、steps、guidance、seed
3. Base/Refiner 參數
4. 去背開關
5. 任務類別：cover/character/page
6. 單張重生成（可覆寫部分參數）

### 5.3 Translation Studio

1. 輸入故事根目錄
2. source language
3. target languages
4. beam size、length penalty
5. 僅翻特定語言或全量翻譯

### 5.4 Voice Studio

1. 輸入故事根目錄或直接文本
2. speaker wav / speaker dir
3. language、volume gain
4. page range
5. concat / keep raw
6. 預覽與重生成

## 6. 圖片「可編輯重生成」關鍵設計

為了讓單張圖可完整重現與修改，必須把每個任務的最終輸入做落盤。

建議新增 manifest：

1. `image/_meta/tasks_manifest.json`
2. 每個 task 含：
   - `task_id`
   - `task_type`
   - `positive_prompt`
   - `negative_prompt`
   - `width`
   - `height`
   - `steps`
   - `guidance`
   - `seed`
   - `skip_refiner`
   - `refiner_steps`
   - `output_paths`
   - `source_prompt_file`
   - `updated_at`

重生成流程：

1. UI 載入 `item-detail`
2. 使用者修改任一欄位
3. `POST /api/images/regenerate`
4. 成功後更新 manifest 與縮圖

## 7. 實作分期

### Phase A（先落地，1-2 天）

1. 先完成 Image Studio 端到端：
   - items/detail/regenerate API
   - 圖片預覽 + 右側參數編輯器
2. 與現有 Overview 並存，不破壞主流程

### Phase B（2-4 天）

1. 補 Text Studio 獨立啟動
2. 補 Translation Studio、Voice Studio
3. 全部接入共用模組任務佇列

### Phase C（1-2 天）

1. 加版本管理（參數預設、最近設定）
2. 加資源防護（單 GPU 同時只跑一個重任務）
3. 補完整驗證與錯誤提示

## 8. 風險與對策

1. 風險：單機 GPU 同時多任務 OOM
2. 對策：模組任務層預設序列化執行，必要時加優先權佇列

1. 風險：圖片重生成無法回推原始參數
2. 對策：強制 manifest 落盤，無 manifest 時回退到 prompt 檔推斷

1. 風險：介面複雜導致使用成本高
2. 對策：每個 Studio 提供 Basic/Advanced 兩層模式

## 9. 驗收標準

1. 四個模組都能獨立執行，不經過 chief 全流程。
2. Image Studio 可對單張圖查看與編輯原參數再重生成。
3. 每個模組任務都有可查詢的 job 狀態與日誌。
4. 不影響原有 Overview 全流程工作模式。
