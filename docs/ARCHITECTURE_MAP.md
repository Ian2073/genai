# 架構地圖

這份文件是快速理解「內容應該放在哪裡」的導覽圖。

## 1. 頂層分層

1. 執行入口層（root）
2. 核心實作套件層（`pipeline`、`backends`、`runtime`、`observability`、`story_core`）
3. 工具與文件層（`scripts`、`docs`、`prompts`）
4. 產物與資料層（`models`、`output`、`logs`、`runs`、`reports`）
5. 研究與封存層（`research`、`backups`）

## 2. Root 應維持精簡

Root 僅保留以下內容：

1. 入口腳本與入口模組（`chief.py`、`story.py`、`image.py`、`trans.py`、`voice.py`）
2. 建置/啟動腳本（`Build_*.bat`、`Start_*.bat`）
3. 核心專案設定（`README.md`、`requirements.txt`、`Dockerfile`、`docker-compose.yml`）
4. 仍需在 root 對外暴露的高層共用模組（`utils.py`、`kg.py`、`evaluator.py`）

可用以下檢查守住 root 乾淨度：

```bash
python scripts/check_root_layout.py --workspace-root . --strict
```

## 3. 資料夾責任

1. `pipeline/`
   - 流程編排與 CLI 入口實作。
   - 主要批次/儀表板執行流程。

2. `backends/`
   - 模型供應者介面與實作細節。
   - LLM/影像/翻譯/語音後端註冊與執行策略。

3. `runtime/`
   - 執行期相容修補與檔案探索輔助。
   - GPTQ/transformers 相容 shim。

4. `observability/`
   - 指標蒐集、效能剖析、報表、可靠性追蹤。

5. `story_core/`
   - 從 root 拆出的故事內部 helper。
   - 分支/狀態/輸出/頁面流程/文本正規化/型別模組。

6. `scripts/`
   - 維運與診斷工具（`setup_env`、`doctor`、`smoke_gate`、實驗腳本）。

7. `docs/`
   - 環境設定、架構、遷移契約與疑難排解文件。

8. `prompts/`
   - Prompt 範本與 Prompt 工具 helper。

9. `research/`
   - 非執行主線的研究資產與評估實驗。
   - 含 `research/paper` 與外部評估專案快照。

10. `backups/`
   - 僅供比對/回復的歷史快照。
   - 不屬於主線執行路徑。

## 4. 放置規則

1. 新的執行主線程式碼：
   - 實作放在 `pipeline`、`backends`、`runtime` 或 `observability`。
   - 除非是公開入口模組，否則不要把新執行模組直接放在 root。

2. 新工具：
   - 放在 `scripts/`。

3. 新文件：
   - 放在 `docs/`。

4. 新研究資料：
   - 放在 `research/`。

5. 生成輸出：
   - 必須放在 `output`、`logs`、`runs`、`reports`。
