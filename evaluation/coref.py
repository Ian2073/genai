# 共指消解服務 API
# 角色：專門處理代詞指代關係的微服務（他/她/它 → 具體人物）
# 用途：接收文本 → 找出所有代詞群組 → 回傳指代關係清單
from __future__ import annotations

from typing import Any, Dict, Optional
import os

COREF_IMPORT_ERROR: Optional[Exception] = None
try:
    from fastapi import FastAPI
    from pydantic import BaseModel
    from fastcoref import FCoref
except Exception as exc:  # Optional service dependencies may be absent in non-coref runtime.
    FastAPI = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]
    FCoref = None  # type: ignore[assignment]
    COREF_IMPORT_ERROR = exc

app = FastAPI() if FastAPI is not None else None

class CorefRequest(BaseModel): # 請求格式定義
    text: str # 要處理的文本內容

coref_model = None # 全域模型變數

def _load_model():
    # 服務啟動時載入共指消解模型（自動選 GPU/CPU）
    global coref_model
    if FCoref is None:
        print(f"fastcoref 服務依賴缺失: {COREF_IMPORT_ERROR}")
        coref_model = None
        return
    try:
        prefer_device = os.getenv("COREF_DEVICE", "auto").strip().lower()
        device = "cpu"
        if prefer_device == "cuda":
            device = "cuda:0"
        elif prefer_device == "cpu":
            device = "cpu"
        else:
            try:
                device = "cuda:0"
                _tmp = FCoref(device=device)
                coref_model = _tmp
                print("fastcoref 已載入於 GPU(cuda:0)")
                return
            except Exception:
                device = "cpu"
        coref_model = FCoref(device=device)
        print(f"fastcoref 已載入於 {device}")
    except Exception as e:
        print(f"fastcoref 載入失敗: {e}")
        coref_model = None # 載入失敗則設為空

def health() -> Dict[str, Any]:
    # 健康檢查端點（確認服務是否正常）
    return {
        "status": "ok",
        "model_loaded": coref_model is not None,
        "service_dependencies_ready": COREF_IMPORT_ERROR is None,
    }

def resolve(req: CorefRequest) -> Dict[str, Any]:
    # 主要功能：解析文本中的共指關係
    if FCoref is None:
        return {"clusters": [], "document": req.text, "error": f"missing_dependencies: {COREF_IMPORT_ERROR}"}
    if coref_model is None: # 模型未載入 → 回傳錯誤
        return {"clusters": [], "document": req.text, "error": "model_not_loaded"}
    try:
        # 執行共指消解：找出所有指代群組（增加批次 token 上限以處理長文本）
        try:
            max_tokens = int(os.getenv("COREF_MAX_TOKENS", "2048"))  # 增加到 2048
        except Exception:
            max_tokens = 2048
        preds = coref_model.predict(texts=[req.text], max_tokens_in_batch=max_tokens)
        clusters = preds[0].get_clusters(as_strings=True) # 取得群組結果
        return {"clusters": clusters, "document": req.text} # 成功回傳
    except Exception as e: # 處理失敗 → 回傳錯誤訊息
        return {"clusters": [], "document": req.text, "error": str(e)}


if app is not None:
    app.on_event("startup")(_load_model)
    app.get("/health")(health)
    app.post("/coref/resolve")(resolve)


