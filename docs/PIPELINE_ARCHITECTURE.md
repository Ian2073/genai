# 主控流程架構

這份文件說明專案在第二階段專案級重構後，`chief` 相關程式碼的安排方式。

## 為什麼要有 `pipeline/`

在真實專案裡，常見做法是：

- 根目錄保留清楚的啟動入口
- 真正的 orchestration 放在 package 裡
- 內部腳本盡量依賴 package，而不是依賴相容殼層

這樣做的好處是：

- 對使用者仍然好啟動
- 對開發者更容易擴充
- 對學生更容易看出「入口」和「實作」的差別

## 目前結構

- `chief.py`
  - 相容入口
  - 保留既有啟動方式
  - 轉呼叫 `pipeline.entry`

- `pipeline/entry.py`
  - CLI 參數解析
  - `main()` 入口
  - 建立 `ChiefRunner` 並輸出 summary

- `pipeline/options.py`
  - `ChiefOptions`
  - 預設設定
  - CLI parser 與 dtype 解析

- `pipeline/chief_runner.py`
  - 真正的主控流程實作
  - 主要保留 `ChiefRunner`
  - 專注在 stage orchestration 與生命週期控制
  - `main()` 只做相容轉呼叫

- `pipeline/chief_runtime.py`
  - 單本書執行時的 context / request metadata / result summary 組裝
  - 讓 `ChiefRunner` 不必同時兼任資料組裝器

- `pipeline/chief_observability.py`
  - observability 初始化、報表與 stage outcome 記錄

- `pipeline/chief_verification.py`
  - 最終故事產物驗證

- `pipeline/chief_workload_stats.py`
  - LLM / image / translation / TTS workload 與 prompt 統計

- `pipeline/__main__.py`
  - 允許使用 `python -m pipeline`

## 實務上這代表什麼

這種安排對應到較常見的團隊開發習慣：

1. 入口檔維持穩定
2. 內部重構集中在 package 內
3. 其他工具腳本直接 import package
4. 未來若再拆 stage、verification、metrics，也有地方可以繼續擴充
5. `ChiefRunner` 不必再同時背負 CLI parser 與 options 定義
6. 單本書 request context 與 runtime summary 可獨立演進，不必塞回 runner

## 目前內部依賴方向

現在建議的依賴方向是：

- 對外啟動：`chief.py`
- 內部程式：`pipeline`

也就是說：

- 使用者仍可以跑 `python chief.py`
- 專案內部腳本則應優先從 `pipeline` import

## 下一階段可擴充方向

如果之後還要再更細拆，可以從這裡往下拆：

- `pipeline/stages/`
- `pipeline/verification/`
- `pipeline/metrics/`
- `pipeline/context/`

目前其實已經做到：

- 入口與主控實作分離
- request/runtime context 與 orchestration 分離
- verification / workload stats / observability 分離
- story pipeline 的 state I/O / output coordination 分離
- story pipeline 的 page generation flow helper 分離

所以下一階段若再動，就比較像把單一 stage 變成獨立 package，而不是再把所有責任塞回 `chief_runner.py`。
