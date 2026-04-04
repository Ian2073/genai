# 模型後端架構說明

本專案現在把「流程」與「模型實作」分開，目的不是增加抽象，而是讓未來更換模型時，不必重改整條 pipeline。

## 核心原則

每個會接模型的模組，都盡量遵守同一個結構：

1. 主流程檔
   例如 `story.py`、`image.py`、`trans.py`、`voice.py`
   這一層負責：
   - 收集輸入
   - 組合任務
   - 管理輸出檔案
   - 呼叫 backend

2. backend 檔
   例如 `backends/llm.py`、`backends/image.py`、`backends/translation.py`、`backends/voice.py`
   這一層負責：
   - 模型載入
   - device / dtype / quantization 細節
   - 第三方套件相容性處理
   - provider registry

   如果不同模組有重複規則，會再往下一層收斂到 shared helper，
   例如：
   - `backends/common.py`：共用 device / dtype 決策
   - `backends/translation_common.py`：翻譯語言代碼與文字分塊規則
   - `backends/llm_runtime_strategy.py`：文本模型的 capability / readiness / selection policy

3. config
   每個模型模組的 `Config` 都開始提供：
   - `provider`
   - `model_family`

這代表未來換模型時，優先先改設定，而不是直接改主流程。

## 目前狀態

- 文本生成
  - 主流程：`story.py`
  - backend：`backends/llm.py`
  - 已正式由主流程透過 `build_llm()` 建立後端
  - 模型候選選擇已進一步抽到 `backends/llm_runtime_strategy.py`
  - 這層會把「模型能力」、「runtime readiness」、「selection policy」分開

- 翻譯
  - 主流程：`trans.py`
  - backend：`backends/translation.py`
  - 已正式由主流程透過 `build_translation_backend()` 建立後端

- 語音
  - 主流程：`voice.py`
  - backend：`backends/voice.py`
  - 已正式由主流程透過 `build_voice_backend()` 建立後端
  - 故事頁面掃描、story 自動偵測、輸出探索規則已抽到 `runtime/story_files.py`

- 圖像
  - 主流程：`image.py`
  - backend：`backends/image.py`
  - 主流程已改用 `backends/image.py` 的 builder 建立 backend
  - `image.py` 現在只保留流程編排、任務蒐集、輸出存檔與後處理

## 為什麼這樣做

如果未來要把：

- 文本模型從 Qwen 換成其他 LLM
- 圖像模型從 SDXL 換成其他 diffusion backend
- 翻譯模型從 NLLB 換成 MarianMT / M2M100
- 語音模型從 XTTS 換成其他 TTS

理想狀況下，應該只需要新增新的 backend class，再註冊 provider，而不是回頭修改 orchestration。

如果只是更換本地文本模型，而不是更換整個 provider，則優先調整：

1. `backends/llm_runtime_strategy.py` 的候選池
2. capability / readiness 規則
3. 預設設定（例如 `pipeline/options.py`、`story_core/story_types.py`）

而不是回頭修改 `story.py` 或 `chief.py`。

## 新增模型的基本做法

以任何模組為例，流程都一樣：

1. 在對應的 backend 檔新增一個 class
2. 讓它符合該模組的 `Base...Backend` 介面
3. 用 `register_*_provider()` 註冊新 provider 名稱
4. 在 `Config.provider` 指向新的 provider

## 對學生的意義

這樣的拆法比較容易回答幾個常見問題：

- 故事流程在哪裡？
- 模型實際載入在哪裡？
- 要換模型時改哪一層？
- 相容性 patch 應該放哪裡？

如果學生要學習系統設計，先看主流程；如果學生要學模型切換，直接看 backend 檔即可。
