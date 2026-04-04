# 生成系統效能優化與降低資源需求

[收集資料](https://www.notion.so/2af3023ad3c98095854afba433b69184?pvs=21)

## 0. 概念設定

- 角色設定：
    - **工程＋系統方法論** 兼具
- 核心一句話：
    
    > 在單 GPU、現實的文字→圖像→語音生成流程裡，
    > 
    > 
    > 加一層「推論控制層」，讓多模態 pipeline 在**看清自己在做什麼**的前提下，自動調整排程與記憶體使用，減少端到端延遲與浪費。
    > 

---

## 1. 背景與問題現況

### 1.1 背景：生成式多模態已經是常態

- 應用型態：
    - 文字故事生成 → 圖像插畫 → 語音朗讀（故事書、互動助理等）。
- 現況：
    - 社群與產業多半把「加速」放在單一模型上（LLM / Diffusion / TTS），
        
        用 TensorRT、FlashAttention、DeepSpeed 等工具優化 layer 或 operator。
        

### 1.2 真實系統的尷尬點

實際 pipeline 是**串起來的一整串流程**：

> 文本 → LLM → 圖像 → Diffusion → 語音 → TTS
> 

在這種情境下，即使每個模型各自很快，整體還是會出問題：

- 模態切換時 GPU 閒置時間長（LLM 跑完等 Diffusion、Diffusion 跑完等 TTS）。
- 每個框架各自 alloc/free：
    - Diffusers、Transformers、TTS 各管一塊 →
        
        峰值顯存高、碎片嚴重，無法塞進更多工作或更大模型。
        
- 端到端 latency 高，GPU 利用率平均偏低。

---

## 2. 專案定位與目標

### 2.1 專案定位：系統層的「推論控制層」

- 不改模型權重、不發明新網路架構。
- 加一層**System-level Inference Controller**，包在多模態 pipeline 外面。
- 專注在：
    - 任務何時啟動／切換
    - GPU／記憶體怎麼被使用
    - 哪些步驟可以重疊、哪些一定要順序
    - 在單 GPU、順序制程的現實限制下，**把空轉與碎片壓到最低**。

### 2.2 量化目標（暫定）

| 指標 | 目標值（端到端） |
| --- | --- |
| GPU 利用率 | 提升到 > 80 % |
| 延遲（端到端） | 降低 30–50 % |
| 峰值 VRAM | 降低 25–40 % |
| 品質差異 | ≤ 5 %（自動評估＋人評） |

---

## 3. 核心概念：控制層的閉環 (Sense → Think → Act)

控制層不是一堆 if else，而是一個**閉環系統**：

1. **觀測 (Sense)**
    - 知道「現在在跑哪一段」（LLM / Diffusion / TTS / I/O）
    - 知道 GPU 利用率、顯存水位、kernel timeline、idle 區段
    - 有事件流：TEXT_PAGE_DONE、IMG_STEP、TTS_CHUNK、MEM_HIGH…
2. **判斷 (Think)**
    - 用有限狀態機 + 規則/代價模型來決定：
        - 現在能不能預熱下一模態？
        - 要不要調 batch / 精度？
        - 該不該暫停預渲、釋放記憶體？
    - 未來可升級成 QoS / RL policy，但 v1 用啟發式就足夠。
3. **執行 (Act)**
    - 實際調度：
        - 啟動/暫停某模態
        - 調整 CUDA streams / Graphs
        - 調整 batch / micro-batch / precision
        - 使用/釋放/重用記憶體池

這三層加起來，才構成一個有「方法論」的控制層，而不是一次性的工程調教。

---

## 4. 三個技術層級：Kernel / Memory / QoS

這三層對應你想要的三個深化方向，也對應現有研究 vs 缺口。

### 4.1 Kernel-interaction 層：CUDA Graphs / Kernel Fusion

**已有工作：**

- **PyGraph (2025)**：
    - 讓 PyTorch 自動使用 CUDA Graph，解決參數複製與靜態圖限制。
- **Grape (MICRO 2023)**：
    - 在動態模型裡處理 Graph 無法捕捉的控制流、shape 變動問題。
- **SD-Acc (2025)**：
    - 為 Stable Diffusion 特化 fused op + 分階段壓縮演算法。

**缺口：**

- 幾乎都停在「**單模型內**」的 graph best-effort 優化（例如 transformer layer 內）。
- 沒有人處理「**跨模態子模型** 的 graph 捕捉與融合」：
    - 比如 LLM + Diffusion + TTS 串起來形成 pipeline-aware 的 Graph。
- 沒有工具幫忙自動分析：
    - 哪些 op 可以跨模態合併？
    - 哪些因 shape / dependency 不能合？

**你可以做的：**

> 一個 pipeline-aware 的 Graph 捕捉與融合策略：
> 
> - 把多模態 pipeline 拆成可捕捉的 Graph Block
> - 建規則或分析框架決定哪些 block 可以 Graph 化／併在一起重放
> - 專門為「文字→圖像→語音」這種 multi-stage 生成系統設計

---

### 4.2 Memory-architecture 層：分層 allocator / 張量重用 / 碎片控制

**已有工作：**

- **GMLake (ASPLOS 2024)**：
    - 虛擬記憶體 stitch，小區塊合併降低碎片。
- **Google tensor reuse（2020 左右）**：
    - 以生存期分析，在靜態圖裡重用中間 tensor 空間。
- **ZeRO-Inference**：
    - 把模型分層放在 CPU/NVMe，GPU 只做算。
- **PagedAttention / vLLM**：
    - 用 paging 管理 attention cache。

**缺口：**

- 這些方案各自解一塊，缺乏**統一的推論記憶體管理模組**。
- 沒有人專門針對「多模態生成」的特性（文字小、圖像大、語音連續）做分層配置。
- 沒人把「碎片 aware 的 allocator」和「模態執行順序與排程」整合在一起。

**你可以做的：**

> 做一個專門給多模態推論用的記憶體管理器：
> 
> - 支援 latent / mel / embedding 等異質張量的重用
> - 有 lifetime map + fragmentation 監控
> - 能與 pipeline 排程互相知道對方在做什麼（不是各自亂 alloc）

---

### 4.3 QoS 自適應策略層：動態精度 / batch / 排程切換

**已有工作：**

- **Proteus (ASPLOS 2024)**：
    - 高負載時自動切 precision 與 batch 大小。
- **Loki (2024)**：
    - multi-stage pipeline 裡根據瓶頸子模型做自適應降級。
- **Clipper / Triton / InferLine**：
    - 提供動態 batching、模型切換等 serving 策略。

**缺口：**

- 大多聚焦在「單一任務 / 單模型服務」的吞吐與 tail latency。
- 幾乎沒人處理：
    - 多模態生成中「模態互相影響」下的 QoS 控制
    - 根據 GPU 使用率 / VRAM 壓力 / 任務重要度**綜合決策**
    - 把「使用者主觀感知品質」納入策略（例如畫面略模糊 vs 少等 2 秒）。

**你可以做的：**

> 設計一個多模態 pipeline-aware 的 QoS 控制器：
> 
> - 輸入：負載、VRAM 水位、佇列長度、模態重要度
> - 輸出：精度、batch、排程順序、是否做草稿圖 / 精修
> - 可先用 rule-based，之後升級成 cost model 或 RL policy

---

## 5. 三大實作模組：SCHED / POOL / GRAPHS

這三個是你專案的「主角」，跟上面三層是交錯對應關係。

| 模組 | 縮寫 | 核心功能 | 對應層級重點 |
| --- | --- | --- | --- |
| Pipeline Controller | SCHED | 透過 CUDA Streams / Events 進行跨模態排程、短片段交錯、頁面流水線 | 排程（時間維度） |
| Memory Manager | POOL | buffer pool、lifetime tracking、碎片控制 | Memory-architecture |
| Profiler Wrapper + CUDA Graphs | GRAPHS | 統一 profiling、捕捉重複路徑、Graph block 執行 | Kernel-interaction＋觀測基礎 |

### 5.1 SCHED：Pipeline Controller

- 用途：
    - 消除模態切換 idle
    - 做「短片段交錯」而不是不切實際的長時間併行
    - 支援：跨頁流水線（Page N 圖像 × Page N+1 文本）

### 5.2 POOL：Memory Manager

- 用途：
    - 建立異質張量池（latent/mel/embedding）
    - 用 lifetime map 決定重用／延遲釋放
    - 實做 fragmentation-aware allocator

### 5.3 GRAPHS：Profiler Wrapper + CUDA Graphs

- 用途：
    - 整個 pipeline 的端到端 profile
    - 對 LLM 解碼 / UNet block / vocoder 做 Graph capture
    - 提供 SCHED/POOL 決策的觀測基礎

---

## 6. Baseline 設計：從觀察到疊加

為了避免「全都開」之後看不出貢獻來源，用多層 baseline：

1. **Baseline-0：No-ops（純觀察版）**
    - 只保留基本設定（FP16、固定 seed、pinned memory）
    - 關掉 streams / graphs / 重用 / 量化
    - 目的：看清楚原始 pipeline 的瓶頸與顯存行為，是「最乾淨的地板」。
2. **Baseline-1：Best-practice（實務基準）**
    - 開啟常見工程優化：
        - async copy、合適 batch/micro-batch、KV-cache、cuDNN/cublas autotune
    - 目的：反映「一般工程師會做」的正常水準。
3. **Optimized：Proposed System（SCHED＋POOL＋GRAPHS）**
    - 在 Baseline-1 之上啟用三個模組
    - 目的：量化你方法的**獨立貢獻**。
4. **External Baseline：Flash-Attn / TensorRT 等**
    - Baseline-1 + 外部加速庫
    - 不啟用 SCHED/POOL/GRAPHS
    - 目的：當作「既有外部加速方案」參考線。
5. **External + Optimized：共存驗證**
    - Baseline-1 + 外部加速庫 + SCHED/POOL/GRAPHS
    - 目的：證明你的控制層**可插拔、可疊加**，不是和外部庫互斥。

重點比較：

- Baseline-1 vs Optimized → 你自己的貢獻。
- External vs External+Optimized → 你的方法加在既有加速之上還有沒有價值。

---

## 7. 實驗設計與評估指標

### 7.1 測試情境矩陣

多模態情境至少要涵蓋：

- 文字長度：短 / 中 / 長
- 圖像解析度：768 / 1024
- 音訊長度：10s / 30s

組合出幾個代表性場景，例如：

- 短文 + 768 + 10s（輕負載）
- 中文 + 1024 + 10s（中等）
- 長文 + 1024 + 30s（重負載）

### 7.2 評估指標

- GPU 利用率（平均、時間分布）
- 端到端延遲（P50/P95）
- 峰值 VRAM + Fragmentation 指標
- 品質差異（自動 + 人評，目標 ≤ 5%）

### 7.3 消融實驗

- 只開 SCHED
- 只開 POOL
- 只開 GRAPHS
- 全開 SCHED + POOL + GRAPHS

看每個模組對各指標的貢獻。

---

## 8. 方法論 vs 工程：你到底在「研究」什麼？

如果只看「加快了 30–50%」，那是工程成果。

要變成「方法論」，核心在於：

1. **你有一個通用的控制模型：**
    - 觀測層 → 判斷層 → 執行層的閉環架構
    - 任務被抽象成事件流＋狀態機，而不是硬寫在程式裡。
2. **你提出一組可重用的原則與策略：**
    - 依賴圖驅動的跨模態排程
    - lifetime aware 的記憶體重用
    - graph block 單位的執行模型
    - 簡單 QoS 規則（甚至未來可以 RL）
3. **任何文字→圖像→語音系統，只要提供依賴描述與幾個成本參數，就能：**
    - 套上你的控制層
    - 自動做出合理的排程／記憶體分配
    - 得到「可預測」的效能改善

這樣你就不是只在優化**你的系統**，而是在給一套「多模態推論該怎麼被管」的方法。

---

## 9. 預期成果與 Roadmap

### 9.1 第一階段（可運行版本）

- 完成 SCHED / POOL / GRAPHS 的初版實作
- 有 Baseline-0 / 1 / Optimized 的完整數據
- 可以清楚說明：
    - 哪裡是最主要瓶頸
    - 控制層怎麼介入
    - 各模組貢獻多少

### 9.2 第二階段（記憶體與 kernel 深入）

- Memory-architecture：
    - 池化＋lifetime map＋碎片監控完整落地
- Kernel-interaction：
    - 針對 1–2 個熱路徑做 fused op / graph 多版本 bucket

### 9.3 第三階段（QoS / 自適應策略）

- 設計簡單 QoS policy：
    - 根據 VRAM / GPU 利用率 / 載入長度，自動切換 batch / 精度 / 排程策略
- 若有時間再考慮：
    - 用代價模型 / RL 取代 rule-based 的部分決策