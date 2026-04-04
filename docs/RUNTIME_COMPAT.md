# 執行期相容性指南

這份文件說明專案目前使用的執行期相容修補。

重點不是把 patch 藏起來，而是把它們整理成「看得懂、找得到、改得動」的結構。
這對之後讓大專生接觸與學習這套系統特別重要。

## 單一入口

請先從 `runtime/compat.py` 開始看。

這個檔案把相容層分成三種情境：

- `prepare_tts_runtime()`
  - 在載入 XTTS 前呼叫
  - 套用 TTS 需要的 transformers 相容修補
- `patch_tts_instance_after_load(tts_instance)`
  - 在 XTTS 建立後呼叫
  - 補上 decoder 的 `generate()` 相容性
- `prepare_gptq_runtime()`
  - 在載入 GPTQ 模型前呼叫
  - 註冊 `auto_gptq` 需要的 `exllamav2_kernels` shim
- `prepare_evaluator_runtime()`
  - 在 evaluator 載入 spaCy 模型前呼叫
  - 處理舊版 RoBERTa 權重在新版 transformers 下的載入差異

## 為什麼學生需要先理解這一層

學習這個專案時，最好先分清楚兩種東西：

- **專案本身的業務邏輯**
  - 故事生成
  - 圖像生成
  - 翻譯
  - 語音合成
- **第三方套件的相容處理**
  - API 差異
  - 舊 checkpoint 載入差異
  - 版本升級造成的行為不一致

如果把這兩者混在一起，初學者會很難分辨「這是系統設計」還是「這是相容性補丁」。

## 目前相容性地圖

### TTS / XTTS

- 主流程檔案：`voice.py`
- 統一入口：`runtime/compat.py`
- 底層 patch：`runtime/compat_transformers.py`

### GPTQ / exllamav2

- 主流程檔案：`story.py`
- 統一入口：`runtime/compat.py`
- 底層 shim：`runtime/exllamav2_shim.py`

### Evaluator / spaCy transformers

- 主流程檔案：`evaluator.py`
- 統一入口：`runtime/compat.py`

## 後續維護規則

未來如果需要新增相容 patch，建議遵守以下規則：

1. 優先新增或重用 `runtime/compat.py` 裡的函式入口。
2. 盡量讓 patch 可重複呼叫，不要造成二次覆寫副作用。
3. 在文件中說明「如果不 patch，會壞在哪裡」。
4. 清楚標記它是：
   - import 前要做
   - model load 前要做
   - model 建立後才做

這樣可以讓專案保持可教學、可維護，而不是變成到處散落的黑魔法。
