# CUDA 疑難排解手冊

當 `torch.cuda.is_available()` 回傳 `False`，或專案搬到另一台電腦後執行失敗時，請使用本手冊。

## 步驟 1：執行專案診斷

```powershell
python scripts/doctor.py --workspace-root . --expect-cuda auto
```

若你明確要求一定要用 GPU，請改用：

```powershell
python scripts/doctor.py --workspace-root . --expect-cuda yes --strict
```

## 步驟 2：判讀常見失敗型態

### 型態 A
- `nvidia-smi` 可正常執行
- 但 `torch.cuda.is_available()` 為 `False`

可能原因：
- PyTorch wheel 的 CUDA profile 與主機驅動能力不匹配
- 目前啟用的 Python 環境不正確
- 多次安裝後殘留混雜版本 wheel

處理方式：
1. 重新執行 `Build_GenAI.bat`。
2. 若仍失敗，用 `scripts/setup_env.py --gpu-series 50` 或 `40` 強制指定 GPU profile。
3. 再次執行 doctor。

### 型態 B
- 找不到 `nvidia-smi`

可能原因：
- NVIDIA 驅動未安裝或異常
- PATH 未包含 NVIDIA 工具路徑

處理方式：
1. 安裝或更新 NVIDIA 驅動。
2. 重新開機。
3. 再次執行 doctor。

### 型態 C
- CUDA 可用，但模型載入失敗

可能原因：
- `models/` 目錄缺漏
- 模型檔案拷貝不完整
- GPTQ 套件版本不匹配

處理方式：
1. 檢查 `models/` 目錄與檔案完整性。
2. 確認 `requirements.txt` 中的版本釘選。
3. 用 `scripts/setup_env.py` 重建環境後再跑 doctor。

## 步驟 3：在當前環境直接驗證

```powershell
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"
```

## 步驟 4：Docker 專用檢查

```powershell
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu22.04 nvidia-smi
```

若這一步失敗，通常代表主機的 Docker GPU runtime 尚未正確設定。

## 已知穩定套件組合

本專案 GPTQ 堆疊建議使用：
- `optimum==1.23.3`
- `auto-gptq==0.7.1`

## 最後判斷原則

若同一個模型在 A 機器可跑、B 機器不可跑，請先視為環境/執行期不匹配；除非診斷已證實模型檔本身損壞。
