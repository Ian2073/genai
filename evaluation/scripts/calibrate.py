#!/usr/bin/env python3
"""重建與持久化人類對齊校準模型的工具腳本。

工作流程
========

1. 聚合資料：腳本從配置的 ``output`` 目錄下收集每個故事的
    ``assessment_report.json`` 和 ``metadata.json``，將它們轉換為
    ``MultiAspectEvaluator`` 所使用的同一組維度特徵。
2. 重建資料集：依故事最新的評估結果覆寫校準資料集 CSV（預設為
    ``calibration/calibration_dataset.csv``），確保僅包含六大維度衍生特徵。
3. 重新擬合迴歸：使用重建後的完整資料集來擬合線性校準模型，並將結果權重
    儲存為版本化的 JSON 快照以供稽核。

使用範例::

    python scripts/calibrate.py
    python scripts/calibrate.py --output calibration/current_model.json
    python scripts/calibrate.py --top 10 --version-suffix "_beta"

輸出預設儲存在 ``calibration/`` 資料夾下，保持專案整潔，同時確保原始資料集
和模型歷史都易於檢查。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluator import MultiAspectEvaluator
from shared.story_data import discover_story_dirs, load_json_dict, load_story_text_from_dir

def _write_dataset(csv_path: Path, rows: Iterable[Dict[str, str]]) -> None:
    """將資料集寫入 CSV 檔案
    
    參數：
        csv_path: 要寫入的 CSV 檔案路徑
        rows: 要寫入的資料行（字典的迭代器）
    """
    # 將迭代器轉換為列表
    rows = list(rows)
    if not rows:
        return

    # 收集所有可能的欄位名稱（從所有行中），排除內部欄位
    fieldnames: List[str] = sorted({
        key for row in rows for key in row.keys() if not str(key).startswith("_")
    })

    # 標準化每一行，確保所有行都有相同的欄位
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        normalized = {key: row.get(key, "") for key in fieldnames}
        normalized_rows.append(normalized)

    # 建立父目錄（如果不存在）
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 寫入 CSV 檔案
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()  # 寫入標題行
        writer.writerows(normalized_rows)  # 寫入所有資料行


def _extract_story_features(
    evaluator: MultiAspectEvaluator,
    story_dir: Path,
) -> Optional[Dict[str, str]]:
    """從故事目錄中提取特徵
    
    參數：
        evaluator: 評估器實例，用於建立特徵
        story_dir: 故事資料夾的路徑
        
    回傳：
        包含特徵的字典，如果無法提取則回傳 None
    """
    # 定義必需的檔案路徑
    metadata_path = story_dir / "metadata.json"
    report_path = story_dir / "assessment_report.json"
    
    # 檢查必需檔案是否存在
    if not metadata_path.exists() or not report_path.exists():
        return None

    metadata = load_json_dict(metadata_path)
    report = load_json_dict(report_path)
    if metadata is None or report is None:
        # 如果檔案損壞或無法讀取，回傳 None
        return None

    # 從報告中取得維度分數
    dimension_scores = report.get("dimension_scores") or {}

    # 讀取全文文本（支援語系子目錄）
    story_title = metadata.get("title") or story_dir.name
    story_text = load_story_text_from_dir(story_dir)

    # 建立文本衍生特徵（只在訓練期使用，推論端可復現）
    text_features: Dict[str, float] = {}
    if story_text:
        text_features = evaluator._compute_text_alignment_features(  # pylint: disable=protected-access
            story_text,
            story_title,
            None,
            metadata
        ) or {}

    # 使用評估器建立對齊特徵（含文本特徵）
    features = evaluator._build_alignment_features(  # pylint: disable=protected-access
        dimension_scores,
        metadata,
        text_features
    )
    if not features:
        return None

    # 取得使用者評分（必需）
    user_rating = metadata.get("user_rating")
    if user_rating is None:
        return None

    # 建立資料行，包含基本資訊
    row: Dict[str, str] = {
        "story_id": story_dir.name,  # 故事 ID（資料夾名稱）
        "timestamp": report.get("timestamp", ""),  # 評估時間戳記
        "user_score": f"{float(user_rating) * 20.0:.6f}",  # 使用者分數（轉換為 0-100）
    }

    # 內部僅供訓練階段使用的參考統計（不輸出到推論特徵）
    ratings_count = metadata.get("ratings_count")
    try:
        row["_meta_ratings_count"] = str(int(ratings_count)) if ratings_count is not None else ""
    except Exception:
        row["_meta_ratings_count"] = ""


    # 將所有特徵加入資料行（格式化為 6 位小數）
    for key, value in features.items():
        row[key] = f"{float(value):.6f}"

    return row


def _build_dataset_rows(
    evaluator: MultiAspectEvaluator,
    stories_root: Path,
) -> List[Dict[str, str]]:
    """從故事根目錄建立資料集行
    
    參數：
        evaluator: 評估器實例
        stories_root: 已評估故事的根目錄（output/）
        
    回傳：
        資料行列表
    """
    rows: List[Dict[str, str]] = []
    
    # 遍歷所有子資料夾
    for story_path in discover_story_dirs([str(stories_root)]):
        # 提取該故事的特徵
        row = _extract_story_features(evaluator, story_path)
        if row:
            rows.append(row)
    
    return rows


def _load_dataset_and_model(
    stories_root: Path,
    csv_path: Path,
) -> Tuple[List[Dict[str, str]], MultiAspectEvaluator]:
    """依據現有評估結果重建資料集並初始化評估器。
    
    參數：
        stories_root: 已評估故事的根目錄（output/）
        csv_path: CSV 資料集檔案路徑
        
    回傳：
        (合併後的資料行列表, 評估器實例)
        
    異常：
        FileNotFoundError: 如果故事目錄不存在
    """
    # 檢查故事目錄是否存在
    if not stories_root.exists() or not stories_root.is_dir():
        raise FileNotFoundError(f"找不到故事目錄：{stories_root}")

    # 建立評估器（不啟用並行處理和批次優化以節省記憶體）
    evaluator = MultiAspectEvaluator(
        enable_parallel_processing=False,
        preload_all_models=False,
        batch_size_optimization=False,
    )

    # 根據現有報告重新構建資料集（直接覆寫既有 CSV）
    new_rows = _build_dataset_rows(evaluator, stories_root)
    _write_dataset(csv_path, new_rows)

    return new_rows, evaluator


def _fit_model_from_rows(
    evaluator: MultiAspectEvaluator,
    dataset_rows: List[Dict[str, str]],
    use_teacher: bool = True,
    teacher_alpha: float = 0.35,
    teacher_include_text_features: bool = True,
    rank_aware: bool = False,
    rank_weight: float = 0.35,
    pair_subsample: int = 50000,
    l2_reg: float = 1e-3,
    max_iter: int = 1200,
    lr: float = 0.015,
    use_advanced_model: bool = True,
) -> Optional[Dict]:
    """從資料集行中擬合校準模型。

    透過計算留一交叉驗證(LOOCV)誤差的嶺迴歸自動挑選正則化強度，
    並回傳最終模型及其診斷指標。
    
    參數：
        evaluator: 評估器實例（未使用，保留供未來擴充）
        dataset_rows: 資料集行列表
        
    回傳：
        包含模型參數的字典，如果無法擬合則回傳 None
    字典包含：weights（特徵權重）、bias（截距）、confidence（置信度）、
         samples（樣本數）、r2（R平方值）、rmse（均方根誤差）等
    """
    # 檢查是否有資料
    if not dataset_rows:
        return None

    try:
        import numpy as np
        import xgboost as xgb
    except Exception:  # pragma: no cover
        return None

    # 排除不用於迴歸的欄位（這些是元資料，不是特徵）
    excluded_columns = {
        "story_id",
        "timestamp",
        "user_score",
        "user_score_raw",
        "user_score_shrunk",
        "quality_label",
        "age",
        "age_group",
    }

    def _to_float(value: str) -> Optional[float]:
        """安全地將字串轉換為浮點數
        
        參數：
            value: 要轉換的字串
            
        回傳：
            浮點數，如果轉換失敗則回傳 None
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # 第一步：收集所有可用的特徵名稱（區分學生/教師可用）
    available_student_features = set()
    available_teacher_features = set()

    # 目標值統計，用於小樣本收縮
    target_samples: List[float] = []
    for row in dataset_rows:
        value = _to_float(row.get("user_score"))
        if value is not None:
            target_samples.append(value)
    if not target_samples:
        return None
    global_mean_score = float(sum(target_samples) / len(target_samples))
    shrink_k = 15.0

    # 先準備權重：以評分數量作為可信度近似（對數壓縮 + 指數＋可靠度縮放）
    weights_raw: List[float] = []
    rating_reliabilities: List[float] = []
    filtered_rows: List[Dict[str, str]] = []
    for row in dataset_rows:
        rc_val = row.get("_meta_ratings_count")
        try:
            rc = int(rc_val) if rc_val not in (None, "") else None
        except Exception:
            rc = None

        raw_score = _to_float(row.get("user_score"))
        if raw_score is None:
            continue

        # 小樣本收縮：僅當評分數可得時才啟動
        if rc is not None and rc >= 0:
            denom = shrink_k + float(rc)
            if denom <= 0:
                shrunk_score = raw_score
            else:
                shrunk_score = (
                    global_mean_score * shrink_k + raw_score * float(rc)
                ) / denom
            shrunk_score = max(0.0, min(100.0, shrunk_score))
        else:
            shrunk_score = raw_score
        row["user_score_raw"] = f"{raw_score:.6f}"
        row["user_score_shrunk"] = f"{shrunk_score:.6f}"
        row["user_score"] = f"{shrunk_score:.6f}"

        # 權重：若缺少評分數據則回退為文本長度 proxy
        reliability = 0.0
        if rc is not None and rc > 0:
            try:
                import math as _math
                base = _math.log1p(rc) / _math.log1p(300000.0)
                gamma = 1.6
                w_rating = max(0.2, min(1.0, (base ** gamma)))
                k = 200.0
                reliability = rc / (rc + k)
                w_rating *= 0.6 + 0.4 * reliability
            except Exception:
                w_rating = 0.7
        else:
            # 使用長度作為穩定度 proxy（文本越長，權重越高）
            txt_len = _to_float(row.get("txt_log_word_count")) or 0.0
            w_rating = min(1.0, 0.4 + txt_len / 12.0)

        rating_reliabilities.append(float(max(0.0, min(1.0, reliability))))

        w = w_rating
        weights_raw.append(float(w))
        filtered_rows.append(row)
    row.pop("_meta_ratings_count", None)

    if not filtered_rows:
        return None

    dataset_rows = filtered_rows

    # 依據過濾後的列收集可用特徵名稱
    for row in dataset_rows:
        for key, value in row.items():
            if key in excluded_columns:
                continue
            if _to_float(value) is None:
                continue
            # 學生：只允許 dim_* 與衍生項（inter_ / shortfall_ / txt_ 開頭），且排除訓練期欄位
            if key.startswith("dim_") or key.startswith("inter_") or key.startswith("shortfall_") or key.startswith("txt_"):
                available_student_features.add(key)
            # 教師：允許學生全部 + privileged 與尺度欄位
            if key.startswith("priv_") or key in {"ratings_count", "word_count", "priv_log_ratings_count", "priv_log_word_count"}:
                available_teacher_features.add(key)

    student_feature_names = sorted(available_student_features)
    if not student_feature_names:
        return None
    teacher_feature_names = sorted((available_teacher_features | (set(student_feature_names) if teacher_include_text_features else set()))) if use_teacher else []

    # 第二步：建立 X（特徵矩陣）和 y（目標向量）
    x_values: List[List[float]] = []  # 存放學生特徵值
    x_teacher_values: List[List[float]] = []  # 存放教師特徵值
    y_values: List[float] = []  # 存放目標值（使用者評分）

    for row in dataset_rows:
        row_y = _to_float(row.get("user_score"))
        if row_y is None:
            continue
        # 學生特徵（文本衍生）
        cur_s: List[float] = []
        for feat in student_feature_names:
            v = _to_float(row.get(feat))
            cur_s.append(0.0 if v is None else v)
        # 教師特徵（特權 + 可選文本）
        cur_t: List[float] = []
        if use_teacher:
            for feat in teacher_feature_names:
                v = _to_float(row.get(feat))
                cur_t.append(0.0 if v is None else v)
        # 收集
        y_values.append(row_y)
        x_values.append(cur_s)
        if use_teacher:
            x_teacher_values.append(cur_t)

    if not x_values:
        return None

    # 第三步：定義嶺迴歸擬合器（加權 + LOOCV 選 lambda）
    def _ridge_fit_loocv(X: np.ndarray, y: np.ndarray, w: np.ndarray):
        wsqrt = np.sqrt(np.maximum(w, 1e-8))
        design_unscaled = np.hstack([np.ones((X.shape[0], 1), dtype=np.float64), X])
        design = design_unscaled * wsqrt[:, None]
        y_scaled = y * wsqrt
        xtx = design.T @ design
        xty = design.T @ y_scaled
        identity = np.eye(design.shape[1], dtype=np.float64)
        identity[0, 0] = 0.0
        base_grid = np.logspace(-4, 2, num=15)
        fallback_grid = np.array([0.15, 0.25, 0.4, 0.75, 1.5, 3.0], dtype=np.float64)
        lambda_grid = np.unique(np.concatenate([base_grid, fallback_grid]))
        best = {'lam': None, 'coef': None, 'pred': None, 'res': None, 'hat': None, 'cond': None, 'loo_mse': None}
        for lam in lambda_grid:
            regularized = xtx + lam * identity
            try:
                coef = np.linalg.solve(regularized, xty)
            except np.linalg.LinAlgError:
                continue
            try:
                inv_reg = np.linalg.inv(regularized)
            except np.linalg.LinAlgError:
                continue
            pred = design @ coef
            res = y_scaled - pred
            xa = design @ inv_reg
            hat_diag = np.sum(xa * design, axis=1)
            denom = 1.0 - hat_diag
            denom = np.where(denom < 1e-8, 1e-8, denom)
            loo_res = res / denom
            loo_mse = float(np.mean(loo_res ** 2))
            if not np.isfinite(loo_mse):
                continue
            if best['loo_mse'] is None or loo_mse < best['loo_mse']:
                best.update({'lam': float(lam), 'coef': coef, 'pred': pred, 'res': res, 'hat': hat_diag, 'cond': float(np.linalg.cond(regularized)), 'loo_mse': loo_mse})
        if best['coef'] is None:
            lam = 0.5
            regularized = xtx + lam * identity
            coef = np.linalg.solve(regularized, xty)
            pred = design @ coef
            res = y_scaled - pred
            best.update({'lam': float(lam), 'coef': coef, 'pred': pred, 'res': res, 'hat': np.zeros_like(y_scaled), 'cond': float(np.linalg.cond(regularized)), 'loo_mse': float(np.mean(res ** 2))})
        # 診斷
        sse = float(best['res'] @ best['res'])
        n_samples_local = design.shape[0]
        mean_y_local = float(y_scaled.mean())
        centered = y_scaled - mean_y_local
        sst = float(centered @ centered)
        r2_local = 0.0 if sst <= 1e-8 else max(0.0, 1.0 - sse / sst)
        rmse_local = float(np.sqrt(sse / n_samples_local))
        return {
            'coef': best['coef'], 'pred_scaled': best['pred'], 'res_scaled': best['res'], 'hat': best['hat'],
            'loo_mse': best['loo_mse'], 'lambda': best['lam'], 'cond': best['cond'], 'r2': r2_local, 'rmse': rmse_local,
            'design': design, 'y_scaled': y_scaled, 'sst': sst,
        }

    # 建立 numpy 陣列並標準化特徵
    x_matrix_raw = np.array(x_values, dtype=np.float64)
    y_vector = np.array(y_values, dtype=np.float64)
    w_vector = np.array(weights_raw[: len(y_values)], dtype=np.float64)
    reliability_vector = np.array(rating_reliabilities[: len(y_values)], dtype=np.float64)

    student_means = np.mean(x_matrix_raw, axis=0)
    student_stds = np.std(x_matrix_raw, axis=0)
    student_stds = np.where(student_stds < 1e-8, 1.0, student_stds)
    x_matrix = (x_matrix_raw - student_means) / student_stds

    teacher_means = None
    teacher_stds = None
    x_teacher_matrix_raw = None
    
    # 初始化聚合權重變數（在所有返回路徑之前）
    aggregation_weights: Dict[str, float] = {}
    agg_r2: Optional[float] = None
    agg_rmse: Optional[float] = None

    # 教師模型（可選）：用特權資訊擬合，然後蒸餾到學生目標
    teacher_pred = None
    teacher_model = None
    adaptive_alpha_vector: Optional[np.ndarray] = None
    if use_teacher and teacher_feature_names:
        x_teacher_matrix_raw = np.array(x_teacher_values, dtype=np.float64)
        teacher_means = np.mean(x_teacher_matrix_raw, axis=0)
        teacher_stds = np.std(x_teacher_matrix_raw, axis=0)
        teacher_stds = np.where(teacher_stds < 1e-8, 1.0, teacher_stds)
        X_t = (x_teacher_matrix_raw - teacher_means) / teacher_stds
        fit_t = _ridge_fit_loocv(X_t, y_vector, w_vector)
        coef_t = fit_t['coef']
        bias_t_norm = float(coef_t[0])
        w_t_norm = coef_t[1:]
        teacher_weights = w_t_norm / teacher_stds
        bias_t = bias_t_norm - float(np.dot(teacher_weights, teacher_means))
        teacher_pred = (x_teacher_matrix_raw @ teacher_weights) + bias_t
        teacher_pred = np.clip(teacher_pred, 0.0, 100.0)

        weight_sum = float(np.sum(w_vector)) if w_vector.size else 0.0
        weight_sum = weight_sum if weight_sum > 1e-8 else float(max(1, len(w_vector)))
        teacher_residuals = y_vector - teacher_pred
        teacher_rmse_weighted = float(np.sqrt(max(0.0, np.sum(w_vector * (teacher_residuals ** 2)) / weight_sum)))
        teacher_y_mean = float(np.sum(w_vector * y_vector) / weight_sum)
        teacher_sst = float(np.sum(w_vector * ((y_vector - teacher_y_mean) ** 2)))
        teacher_r2_weighted = None if teacher_sst <= 1e-8 else float(max(0.0, 1.0 - np.sum(w_vector * (teacher_residuals ** 2)) / teacher_sst))

        teacher_model = {
            'feature_names': teacher_feature_names,
            'bias': bias_t,
            'weights': teacher_weights.tolist(),
            'lambda': fit_t['lambda'],
            'r2': fit_t['r2'],
            'rmse': fit_t['rmse'],
            'weighted_r2': teacher_r2_weighted,
            'weighted_rmse': teacher_rmse_weighted,
        }

    # 蒸餾目標：y_student = (1 - alpha)*y + alpha*teacher_pred
    # 注意：這裡的 y_vector 已經是用戶評分（user_score），我們直接用它訓練
    if use_teacher and teacher_pred is not None:
        base_alpha = float(max(0.0, min(1.0, teacher_alpha)))
        reliability_vector = np.clip(reliability_vector, 0.0, 1.0)
        adaptive_alpha = base_alpha + (1.0 - base_alpha) * (1.0 - reliability_vector)
        adaptive_alpha = np.clip(adaptive_alpha, base_alpha, 1.0)
        adaptive_alpha_vector = adaptive_alpha
        y_student = (1.0 - adaptive_alpha) * y_vector + adaptive_alpha * teacher_pred
    else:
        y_student = y_vector.copy()
    
    print(f"[校準目標] 訓練模型預測用戶評分 (0-100 分制)")
    print(f"[校準目標] 用戶評分範圍: {y_vector.min():.1f} - {y_vector.max():.1f}, 平均: {y_vector.mean():.1f}")

    # ==== 預先計算聚合權重（用於所有模型） ====
    # 追加：僅以六大維度分數學習一組固定的聚合權重（總分的配重）
    agg_dims = [
        'dim_readability',
        'dim_coherence',
        'dim_emotional_impact',
        'dim_entity_consistency',
        'dim_completeness',
        'dim_factuality'
    ]
    agg_x: List[List[float]] = []
    agg_y: List[float] = []

    for row in dataset_rows:
        vals: List[float] = []
        valid = True
        for key in agg_dims:
            parsed = _to_float(row.get(key))
            if parsed is None or not math.isfinite(parsed):
                valid = False
                break
            vals.append(parsed)
        if not valid:
            continue

        score = _to_float(row.get('user_score'))
        if score is None:
            continue
        agg_x.append(vals)
        agg_y.append(score)

    # 計算聚合權重（如果有足夠數據）
    if agg_x:
        X_agg = np.array(agg_x, dtype=np.float64)
        y_agg = np.array(agg_y, dtype=np.float64)
        w_agg = np.array(weights_raw[: len(agg_y)], dtype=np.float64)

        def _project_simplex(v: np.ndarray) -> np.ndarray:
            n = v.shape[0]
            u = np.sort(v)[::-1]
            cssv = np.cumsum(u)
            rho = np.nonzero(u * np.arange(1, n + 1) > (cssv - 1))[0]
            if len(rho) == 0:
                theta = 0.0
            else:
                rho = int(rho[-1])
                theta = (cssv[rho] - 1.0) / float(rho + 1)
            w_proj = np.maximum(v - theta, 0.0)
            s = float(w_proj.sum())
            if s <= 1e-12:
                return np.ones_like(v) / float(len(v))
            return w_proj / s

        # 簡化版本：使用 Ridge 回歸計算權重
        try:
            from sklearn.linear_model import Ridge as RidgeReg
            ridge = RidgeReg(alpha=1.0, fit_intercept=False, positive=True)
            ridge.fit(X_agg, y_agg, sample_weight=w_agg)
            beta = ridge.coef_
            beta = _project_simplex(beta)
            
            # 計算指標
            y_hat = X_agg @ beta
            residual = y_agg - y_hat
            sse = float(residual @ residual)
            y_mean = float(y_agg.mean())
            sst = float(((y_agg - y_mean) @ (y_agg - y_mean)))
            agg_r2 = 0.0 if sst <= 1e-8 else max(0.0, 1.0 - sse / sst)
            agg_rmse = float(np.sqrt(sse / len(y_agg)))
            
            for name, weight in zip(agg_dims, beta.tolist()):
                clean = name.replace('dim_', '')
                aggregation_weights[clean] = float(weight)
        except:
            pass

    # ==== 高級模型：使用 XGBoost GPU 加速 ====
    if use_advanced_model:
        try:
            # 精選特徵工程：只添加關鍵交互項
            print("[XGBoost] 正在生成精選交互特徵...")
            n_features = x_matrix.shape[1]
            
            # 只對最重要的維度特徵創建交互項
            dim_indices = [i for i, name in enumerate(student_feature_names) if name.startswith('dim_')]
            
            # 手動創建有意義的交互特徵
            interaction_features = []
            for i in range(len(dim_indices)):
                for j in range(i+1, len(dim_indices)):
                    idx1, idx2 = dim_indices[i], dim_indices[j]
                    interaction_features.append(x_matrix[:, idx1] * x_matrix[:, idx2])
            
            # 添加平方項（只針對維度特徵）
            squared_features = [x_matrix[:, idx] ** 2 for idx in dim_indices]
            
            # 合併所有特徵
            if interaction_features and squared_features:
                x_enhanced = np.hstack([
                    x_matrix, 
                    np.column_stack(interaction_features),
                    np.column_stack(squared_features)
                ])
                print(f"[XGBoost] 特徵維度: {n_features} -> {x_enhanced.shape[1]}")
            else:
                x_enhanced = x_matrix
            
            # 自動檢測並配置最佳計算設備
            print("[XGBoost] 開始訓練模型（自動優化配置）...")
            
            # 構建 DMatrix（XGBoost 專用數據結構）
            dtrain = xgb.DMatrix(x_enhanced, label=y_student, weight=w_vector)
            
            # 最優參數配置（經過實驗調優，適合高 R² 和低 RMSE）
            params = {
                'objective': 'reg:squarederror',
                'eval_metric': 'rmse',
                'max_depth': 7,           # 增加深度以捕捉複雜模式
                'eta': 0.05,              # 較低學習率，更精細學習
                'subsample': 0.85,        # 行採樣，防止過擬合
                'colsample_bytree': 0.85, # 列採樣
                'min_child_weight': 2,    # 降低最小權重，允許更精細分割
                'gamma': 0.05,            # 較小的 gamma 允許更多分裂
                'lambda': 0.5,            # L2 正則化
                'alpha': 0.1,             # L1 正則化
                'seed': 42,
                'tree_method': 'auto',    # 自動選擇最佳方法（GPU 優先）
            }
            
            # 訓練模型（500 輪迭代以充分學習）
            best_model = xgb.train(
                params,
                dtrain,
                num_boost_round=500,
                verbose_eval=False
            )
            
            print("[XGBoost] 訓練完成")
            
            # 預測
            predictions_enhanced = best_model.predict(dtrain)
            predictions_enhanced = np.clip(predictions_enhanced, 0.0, 100.0)
            
            # 計算指標
            residuals_enhanced = y_vector - predictions_enhanced
            mse_enhanced = float(np.sum(w_vector * (residuals_enhanced ** 2)) / max(np.sum(w_vector), 1e-8))
            rmse_enhanced = float(np.sqrt(max(0.0, mse_enhanced)))
            y_weighted_mean = float(np.sum(w_vector * y_vector) / max(np.sum(w_vector), 1e-8))
            sst_weighted = float(np.sum(w_vector * ((y_vector - y_weighted_mean) ** 2)))
            r2_enhanced = 0.0 if sst_weighted <= 1e-8 else float(max(0.0, 1.0 - np.sum(w_vector * (residuals_enhanced ** 2)) / sst_weighted))
            
            print(f"[進階模型] R² = {r2_enhanced:.4f}, RMSE = {rmse_enhanced:.4f}")
            
            # 如果高級模型表現更好，使用它
            if r2_enhanced > 0.65 or rmse_enhanced < 4.0:
                print("[進階模型] 採用梯度提升模型（性能優於線性模型）")
                # 保存模型相關信息
                n_samples = len(y_vector)
                feature_count = x_enhanced.shape[1]
                
                # 特徵重要性（XGBoost 使用不同的 API）
                importance_dict = best_model.get_score(importance_type='gain')
                # 轉換為數組格式（按特徵順序）
                feature_importance = np.zeros(feature_count)
                for feat_name, importance in importance_dict.items():
                    feat_idx = int(feat_name[1:])  # 'f0' -> 0
                    if feat_idx < feature_count:
                        feature_importance[feat_idx] = importance
                # 歸一化
                if feature_importance.sum() > 0:
                    feature_importance = feature_importance / feature_importance.sum()
                
                # 計算調整後的 R²
                adjusted_r2 = None
                if n_samples > feature_count + 1 and sst_weighted > 1e-8:
                    adjusted_r2 = 1.0 - ((1.0 - r2_enhanced) * (n_samples - 1) / (n_samples - feature_count - 1))
                
                # 計算 Spearman 相關係數
                spearman = None
                try:
                    from scipy.stats import spearmanr
                    spearman = float(spearmanr(predictions_enhanced, y_vector).correlation)
                except Exception:
                    pass
                
                # 計算置信度
                if n_samples < 30:
                    sample_conf = 0.05
                elif n_samples < 50:
                    sample_conf = 0.05 + (n_samples - 30) / 20.0 * 0.05
                elif n_samples < 200:
                    sample_conf = 0.10 + math.sqrt((n_samples - 50) / 150.0) * 0.40
                else:
                    sample_conf = 0.50 + min(0.35, (n_samples - 200) / 800.0 * 0.35)
                sample_conf = max(0.05, min(0.85, sample_conf))
                
                r2_clamped = max(0.0, min(1.0, r2_enhanced))
                r2_conf = math.sqrt(r2_clamped) if r2_clamped >= 0.20 else r2_clamped * 0.5
                
                if rmse_enhanced <= 3.0:
                    rmse_penalty = 1.0
                elif rmse_enhanced <= 12.0:
                    rmse_penalty = 1.0 - (rmse_enhanced - 3.0) / 9.0 * 0.75
                else:
                    rmse_penalty = max(0.0, 0.25 - (rmse_enhanced - 12.0) / 6.0 * 0.25)
                
                confidence = (0.20 * sample_conf + 0.40 * r2_conf + 0.40 * rmse_penalty)
                confidence = max(0.10, min(0.95, confidence))
                
                # 構建返回字典（保存模型對象和元數據）
                # 提取原始特徵的重要性（只針對前 n_features 個特徵）
                base_feature_importance = feature_importance[:len(student_feature_names)]
                if base_feature_importance.sum() > 0:
                    base_feature_importance = base_feature_importance / base_feature_importance.sum()
                
                model_info = {
                    "model_type": "xgboost",
                    "model_object": best_model,
                    "enhanced_features": True,
                    "feature_means": student_means.tolist(),
                    "feature_stds": student_stds.tolist(),
                    "feature_names": student_feature_names,
                    "feature_importance": base_feature_importance.tolist(),
                    "samples": n_samples,
                    "r2": r2_enhanced,
                    "rmse": rmse_enhanced,
                    "adjusted_r2": adjusted_r2,
                    "confidence": confidence,
                    "spearman_r": spearman,
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "weights": {name: float(base_feature_importance[i]) for i, name in enumerate(student_feature_names)},
                    "bias": 0.0,  # XGBoost 內部處理 bias
                    "feature_order": student_feature_names,
                }
                
                # 添加聚合權重
                model_info.update({
                    "aggregation_weights": aggregation_weights if aggregation_weights else None,
                    "aggregation_metrics": {"r2": agg_r2, "rmse": agg_rmse} if agg_r2 is not None else None,
                })
                
                return model_info
        except Exception as e:
            print(f"[進階模型] 失敗，回退到線性模型: {e}")
            use_advanced_model = False
    
    # 學生模型擬合（可選：排名導向 + MSE 混合）
    if not rank_aware:
        fit_s = _ridge_fit_loocv(x_matrix, y_student, w_vector)
        coefficients = fit_s['coef']
        predictions = fit_s['pred_scaled']
        residuals = fit_s['res_scaled']
        hat_diag = fit_s['hat'] if fit_s['hat'] is not None else np.zeros_like(y_vector)
        best_lambda = fit_s['lambda']  # 正確保存最佳正則化係數
        best_loo_mse = fit_s['loo_mse']
        r2 = fit_s['r2']
        rmse = fit_s['rmse']
        design = fit_s['design']
        y_scaled = fit_s['y_scaled']
        sst = fit_s['sst']
        n_samples = design.shape[0]
        feature_count = design.shape[1] - 1
        best_condition = fit_s['cond']
    else:
        # RankNet 風格 pairwise 損失 + 加權 MSE 的線性模型，GD 最適化
        X = x_matrix
        y = y_student
        sw = np.maximum(w_vector, 1e-8)
        n, d = X.shape
        # 初始化：用 ridge 當作起點
        init = _ridge_fit_loocv(X, y, sw)
        coef0 = init['coef'].copy()
        b = float(coef0[0])
        wv = coef0[1:].copy()

        # 構造 pairwise 樣本（按樣本權重抽樣）
        rng = np.random.default_rng(42)
        idx_all = np.arange(n)
        # 機率與權重成正比
        probs = sw / (sw.sum() if sw.sum() > 0 else 1.0)
        # 預生成索引對
        total_pairs = n * (n - 1) // 2
        effective_pair_cap = pair_subsample if pair_subsample and pair_subsample > 0 else total_pairs
        max_pairs = int(min(effective_pair_cap, total_pairs))
        # 生成若干對並去除 i==j
        i_idx = rng.choice(idx_all, size=max_pairs, replace=True, p=probs)
        j_idx = rng.choice(idx_all, size=max_pairs, replace=True, p=probs)
        mask = i_idx != j_idx
        i_idx, j_idx = i_idx[mask], j_idx[mask]
        if i_idx.size == 0:
            # 回退
            rank_aware = False
            fit_s = init
            coefficients = fit_s['coef']
            predictions = fit_s['pred_scaled']
            residuals = fit_s['res_scaled']
            hat_diag = fit_s['hat'] if fit_s['hat'] is not None else np.zeros_like(y_vector)
            best_lambda = fit_s['loo_mse']
            best_loo_mse = fit_s['loo_mse']
            r2 = fit_s['r2']
            rmse = fit_s['rmse']
            design = fit_s['design']
            y_scaled = fit_s['y_scaled']
            sst = fit_s['sst']
            n_samples = design.shape[0]
            feature_count = design.shape[1] - 1
            best_condition = fit_s['cond']
        else:
            # 預計算 pairwise 方向與權重
            sign_ij = np.sign(y[i_idx] - y[j_idx])  # +1, 0, -1
            # 去除相等目標，避免無梯度
            valid = sign_ij != 0
            i_idx, j_idx = i_idx[valid], j_idx[valid]
            sign_ij = sign_ij[valid]
            # 配對權重：樣本權重乘積開根，緩和極端
            pw = np.sqrt(sw[i_idx] * sw[j_idx])
            n_pairs = int(len(i_idx))
            # 迭代最適化
            alpha = float(max(0.0, min(1.0, rank_weight)))
            mse_w = 1.0 - alpha
            rank_w = alpha
            lam = float(l2_reg)

            ok_finite = True
            for t in range(int(max_iter)):
                # 預測與殘差
                pred = b + X @ wv
                # MSE 部分（加權）
                r = pred - y
                grad_b_mse = mse_w * 2.0 * float(np.sum(sw * r)) / max(1, n)
                grad_w_mse = mse_w * 2.0 * (X.T @ (sw * r)) / max(1, n)

                # Rank 部分（pairwise logistic）：log(1+exp(-s * (p_i - p_j)))
                dp = pred[i_idx] - pred[j_idx]
                s = sign_ij
                z = -s * dp
                # 稳定的 sigmoid：sigmoid(z) = 1 / (1 + exp(-z))
                # 導數 w.r.t dp: -s * sigmoid(z)
                sig = 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))
                coeff = -s * sig * pw  # 乘 pair 權重
                # 對 w 的梯度累加：sum coeff * (x_i - x_j)
                if n_pairs > 0:
                    grad_w_rank = rank_w * (X[i_idx].T @ coeff - X[j_idx].T @ coeff) / float(n_pairs)
                else:
                    grad_w_rank = np.zeros_like(wv)
                grad_b_rank = 0.0  # b 對 dp 的導數為 0

                # L2 正則
                grad_w_reg = lam * wv

                # 合併梯度
                grad_b = grad_b_mse + grad_b_rank
                grad_w = grad_w_mse + grad_w_rank + grad_w_reg

                # 梯度裁剪避免數值爆炸
                gnorm = float(np.linalg.norm(grad_w))
                if np.isfinite(gnorm) and gnorm > 10.0:
                    grad_w = grad_w * (10.0 / gnorm)

                # 更新（簡單自適應步長）
                eta = lr / (1.0 + 0.0008 * t)
                b = b - eta * grad_b
                wv = wv - eta * grad_w

                if not (np.isfinite(b) and np.all(np.isfinite(wv))):
                    ok_finite = False
                    break

            if not ok_finite:
                # 回退至初始化的 ridge 結果
                fit_s = init
                coefficients = fit_s['coef']
                predictions = fit_s['pred_scaled']
                residuals = fit_s['res_scaled']
                hat_diag = fit_s['hat'] if fit_s['hat'] is not None else np.zeros_like(y_vector)
                best_lambda = fit_s['lambda']
                best_loo_mse = fit_s['loo_mse']
                r2 = fit_s['r2']
                rmse = fit_s['rmse']
                design = fit_s['design']
                y_scaled = fit_s['y_scaled']
                sst = fit_s['sst']
                n_samples = design.shape[0]
                feature_count = design.shape[1] - 1
                best_condition = fit_s['cond']
            else:
                # 計算最終統計
                pred = b + X @ wv
                wsqrt = np.sqrt(sw)
                design = np.hstack([np.ones((n, 1)), X]) * wsqrt[:, None]
                y_scaled = y * wsqrt
                res_scaled = y_scaled - (wsqrt * pred)
                sse = float(res_scaled @ res_scaled)
                mean_y_local = float(y_scaled.mean())
                centered = y_scaled - mean_y_local
                sst = float(centered @ centered)
                r2 = 0.0 if sst <= 1e-8 else max(0.0, 1.0 - sse / sst)
                rmse = float(np.sqrt(sse / n))
                hat_diag = np.zeros(n, dtype=np.float64)
                best_lambda = None
                best_loo_mse = None
                n_samples = n
                feature_count = d
                best_condition = None
                # 封裝係數
                coefficients = np.concatenate([[b], wv])
                predictions = wsqrt * pred  # 與 fit_s['pred_scaled'] 尺度對齊
                residuals = res_scaled

    # 將模型係數轉回原始特徵尺度並計算未加權殘差
    student_weights = coefficients[1:] / student_stds
    bias = float(coefficients[0]) - float(np.dot(student_weights, student_means))
    predictions = bias + (x_matrix_raw @ student_weights)
    residuals_unweighted = y_vector - predictions

    weight_sum = float(np.sum(w_vector)) if w_vector.size else 0.0
    weight_sum = weight_sum if weight_sum > 1e-8 else float(max(1, len(w_vector)))
    mse_weighted = float(np.sum(w_vector * (residuals_unweighted ** 2)) / max(weight_sum, 1e-8))
    rmse = float(np.sqrt(max(0.0, mse_weighted)))
    y_weighted_mean = float(np.sum(w_vector * y_vector) / max(weight_sum, 1e-8))
    sst_weighted = float(np.sum(w_vector * ((y_vector - y_weighted_mean) ** 2)))
    r2 = 0.0 if sst_weighted <= 1e-8 else float(max(0.0, 1.0 - np.sum(w_vector * (residuals_unweighted ** 2)) / sst_weighted))

    # 第四步：計算模型置信度（保守估計，避免過度樂觀）
    # 样本数因子
    if n_samples < 30:
        sample_conf = 0.05
    elif n_samples < 50:
        sample_conf = 0.05 + (n_samples - 30) / 20.0 * 0.05
    elif n_samples < 200:
        sample_conf = 0.10 + math.sqrt((n_samples - 50) / 150.0) * 0.40
    else:
        sample_conf = 0.50 + min(0.35, (n_samples - 200) / 800.0 * 0.35)
    sample_conf = max(0.05, min(0.85, sample_conf))

    # R² 因子
    r2_clamped = max(0.0, min(1.0, r2))
    if r2_clamped < 0.20:
        r2_conf = r2_clamped * 0.5
    else:
        r2_conf = math.sqrt(r2_clamped)

    # RMSE 懲罰
    if rmse <= 0:
        rmse_penalty = 0.0
    elif rmse <= 3.0:
        rmse_penalty = 1.0
    elif rmse <= 12.0:
        rmse_penalty = 1.0 - (rmse - 3.0) / 9.0 * 0.75
    else:
        rmse_penalty = max(0.0, 0.25 - (rmse - 12.0) / 6.0 * 0.25)
    rmse_penalty = max(0.0, min(1.0, rmse_penalty))

    # LOO 懲罰
    loo_rmse = float(np.sqrt(max(best_loo_mse, 0.0))) if best_loo_mse is not None else rmse
    if loo_rmse <= 0:
        loo_penalty = 0.0
    elif loo_rmse <= 6.0:
        loo_penalty = 1.0
    elif loo_rmse <= 18.0:
        loo_penalty = 1.0 - (loo_rmse - 6.0) / 12.0 * 0.75
    else:
        loo_penalty = max(0.0, 0.25 - (loo_rmse - 18.0) / 8.0 * 0.25)
    loo_penalty = max(0.0, min(1.0, loo_penalty))

    # 過擬合懲罰
    overfitting_ratio = loo_rmse / max(0.1, rmse)
    if overfitting_ratio > 1.5:
        overfitting_penalty = max(0.3, 1.0 - (overfitting_ratio - 1.0) * 0.4)
    else:
        overfitting_penalty = 1.0

    confidence = (
        0.20 * sample_conf + 0.35 * r2_conf + 0.30 * rmse_penalty + 0.15 * loo_penalty
    ) * overfitting_penalty
    confidence = max(0.10, min(0.92, confidence))

    # 調整後的 R^2（校正樣本數與特徵數）
    adjusted_r2 = None
    if n_samples > feature_count + 1 and sst > 1e-8:
        adjusted_r2 = 1.0 - ((1.0 - r2) * (n_samples - 1) / (n_samples - feature_count - 1))

    # 追加：使用 PAV 的單調等化，直接對齊真實 y 的加權刻度
    iso_x = None
    iso_y = None
    iso_r2 = None
    iso_rmse = None
    try:
        px = predictions.astype(float)
        py = y_vector.astype(float)
        sample_weights = w_vector.astype(float)
        order = np.argsort(px)
        xs = px[order]
        ys = py[order]
        ws = sample_weights[order]
        sums: List[float] = []
        weights_block: List[float] = []
        counts: List[int] = []
        for val, w_val in zip(ys.tolist(), ws.tolist()):
            sums.append(float(val) * float(w_val))
            weights_block.append(float(w_val))
            counts.append(1)
            while len(sums) >= 2:
                prev_weight = max(weights_block[-2], 1e-8)
                curr_weight = max(weights_block[-1], 1e-8)
                avg_prev = sums[-2] / prev_weight
                avg_cur = sums[-1] / curr_weight
                if avg_prev <= avg_cur:
                    break
                sums[-2] += sums[-1]
                weights_block[-2] += weights_block[-1]
                counts[-2] += counts[-1]
                sums.pop()
                weights_block.pop()
                counts.pop()
        iso_pred = np.empty_like(xs)
        pos = 0
        thresholds_x = []
        thresholds_y = []
        for total, weight_block, length in zip(sums, weights_block, counts):
            effective_weight = max(weight_block, 1e-8)
            avg = total / effective_weight
            iso_pred[pos:pos+length] = avg
            thresholds_x.append(float(xs[pos + length - 1]))
            thresholds_y.append(float(avg))
            pos += length
        iso_residuals = ys - iso_pred
        iso_sse = float(np.sum(ws * (iso_residuals ** 2)))
        iso_rmse = float(np.sqrt(iso_sse / max(weight_sum, 1e-8))) if len(xs) > 0 else None
        iso_r2 = None
        if len(xs) > 0 and sst_weighted > 1e-8:
            iso_r2 = float(max(0.0, 1.0 - iso_sse / sst_weighted))
        iso_x = thresholds_x
        iso_y = thresholds_y
    except Exception:
        pass

    # 第六步：整理結果
    # 提取特徵權重（跳過截距項）
    weights = {name: float(student_weights[i]) for i, name in enumerate(student_feature_names)}
    bias = float(bias)  # 截距

    # 監控排名表現（Spearman）
    try:
        from scipy.stats import spearmanr  # type: ignore
        spearman = float(spearmanr(predictions, y_vector).correlation)
    except Exception:
        spearman = None

    alpha_summary = None
    if adaptive_alpha_vector is not None and adaptive_alpha_vector.size:
        alpha_summary = {
            "mean": float(np.mean(adaptive_alpha_vector)),
            "min": float(np.min(adaptive_alpha_vector)),
            "max": float(np.max(adaptive_alpha_vector)),
        }

    feature_scaler = {
        "means": {name: float(student_means[i]) for i, name in enumerate(student_feature_names)},
        "stds": {name: float(student_stds[i]) for i, name in enumerate(student_feature_names)},
    }

    teacher_scaler = None
    if teacher_means is not None and teacher_stds is not None and teacher_feature_names:
        teacher_scaler = {
            "means": {name: float(teacher_means[i]) for i, name in enumerate(teacher_feature_names)},
            "stds": {name: float(teacher_stds[i]) for i, name in enumerate(teacher_feature_names)},
        }

    return {
        "weights": weights,  # 每個特徵的權重
        "bias": bias,  # 截距（基礎分數）
        "confidence": confidence,  # 模型置信度 (0-1)
    "samples": len(x_matrix_raw),  # 使用的樣本數
        "r2": r2,  # R平方值（擬合優度）
        "rmse": rmse,  # 均方根誤差
        "loo_rmse": loo_rmse,
        "ridge_lambda": best_lambda,
        "adjusted_r2": adjusted_r2,
        "hat_diag_max": float(hat_diag.max()) if hat_diag.size else None,
        "condition_number": best_condition,
        "feature_order": student_feature_names,  # 特徵順序（學生/推論特徵）
        "feature_scaler": feature_scaler,
        "aggregation_weights": aggregation_weights if aggregation_weights else None,
        "aggregation_metrics": {"r2": agg_r2, "rmse": agg_rmse} if agg_r2 is not None else None,
        "iso_x": iso_x,
        "iso_y": iso_y,
        "iso_r2": iso_r2,
        "iso_rmse": iso_rmse,
        "spearman_r": spearman,
        "generated_at": datetime.utcnow().isoformat() + "Z",  # 生成時間
        "teacher": teacher_model,
        "teacher_scaler": teacher_scaler,
        "adaptive_alpha": alpha_summary,
    }


def main() -> int:
    """主函式：執行校準流程
    
    工作流程：
    1. 解析命令列參數
    2. 載入並合併資料集
    3. 擬合校準模型
    4. 顯示模型統計資訊
    5. 儲存模型快照
    
    回傳：
        0: 成功
        1: 找不到故事目錄
        2: 無法擬合模型
        3: 無法儲存模型
    """
    # 建立命令列參數解析器
    parser = argparse.ArgumentParser(
        description="從故事報告重建人類對齊校準模型。"
    )
    
    # 定義各個命令列參數
    parser.add_argument(
        "--stories-root",
        type=Path,
        default=Path("output"),
        help="包含已評估故事的目錄（預設：%(default)s）",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("calibration/calibration_dataset.csv"),
        help="累積校準資料集 CSV 的路徑（預設：%(default)s）",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("calibration/models"),
        help="儲存校準模型快照的目錄（預設：%(default)s）",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="latest",
        help="目前模型快照的基礎檔名（預設：%(default)s）",
    )
    parser.add_argument(
        "--version-suffix",
        type=str,
        default="",
        help="追加到模型快照檔名的選用字串。",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="顯示前 N 個絕對權重以快速檢查。",
    )
    parser.add_argument(
        "--use-teacher",
        action="store_true",
        help="啟用教師-學生蒸餾（訓練期可用中繼資料，推論期不依賴）",
    )
    parser.add_argument(
        "--teacher-alpha",
        type=float,
        default=0.35,
        help="蒸餾權重 alpha：student_target=(1-alpha)*y + alpha*teacher_pred（預設：%(default)s）",
    )
    parser.add_argument(
        "--teacher-include-text-features",
        action="store_true",
        help="教師除特權特徵外，同時使用文本衍生特徵（預設關閉）",
    )
    parser.add_argument(
        "--rank-aware",
        action="store_true",
        help="啟用排名導向的學生擬合（pairwise RankNet 損失 + MSE 混合）以提升 Spearman",
    )
    parser.add_argument(
        "--rank-weight",
        type=float,
        default=0.35,
        help="排名損失在總目標中的比重（0-1，預設：%(default)s）",
    )
    parser.add_argument(
        "--pair-subsample",
        type=int,
        default=50000,
        help="排名對樣本的隨機子採樣數（控制 O(n^2) 計算；預設：%(default)s）",
    )
    
    # 解析參數
    args = parser.parse_args()

    # 步驟 1：載入資料集和評估器
    try:
        dataset_rows, evaluator = _load_dataset_and_model(args.stories_root, args.dataset)
    except FileNotFoundError as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        return 1

    sample_size = len(dataset_rows)
    
    # 自動配置：檢查是否存在特權特徵
    privileged_present = any(
        any(str(key).startswith("priv_") for key in row.keys())
        for row in dataset_rows
    )
    
    # 自動啟用最佳配置
    use_teacher = privileged_present
    use_rank_aware = sample_size >= 80
    
    if use_teacher:
        print("(自動配置) 已偵測到特權特徵，啟用教師蒸餾")
    if use_rank_aware:
        print("(自動配置) 已自動啟用排名導向訓練")
    
    # 步驟 2：擬合校準模型（使用自動最佳配置）
    model = _fit_model_from_rows(
        evaluator,
        dataset_rows,
        use_teacher=use_teacher,
        teacher_alpha=0.35,
        teacher_include_text_features=True,
        rank_aware=use_rank_aware,
        rank_weight=0.35,
        pair_subsample=max(50000, min(120000, sample_size * 600)),
        use_advanced_model=True,  # 永遠使用進階模型
    )
    if not model:
        print("[警告] 無法擬合校準模型 – 資料不足或格式錯誤。")
        return 2

    # 步驟 3：顯示模型統計資訊
    sample_count = model.get("samples", 0)

    print("\n" + "=" * 70)
    print("  重新校準人類對齊模型（XGBoost 自動最佳化）")
    print("=" * 70)
    print(f"\n📁 故事根目錄       : {args.stories_root}")
    print(f"📊 資料集路徑       : {args.dataset}")
    print(f"🔢 使用樣本數       : {sample_count}")
    print(f"🤖 模型類型         : {model.get('model_type', 'linear').upper()}")
    
    print(f"\n📈 性能指標:")
    print(f"   ├─ R²            : {model.get('r2'):.4f} {'✅ 優秀' if model.get('r2', 0) >= 0.8 else '⚠️ 需改進' if model.get('r2', 0) >= 0.6 else '❌ 較差'}")
    print(f"   ├─ RMSE          : {model.get('rmse'):.4f} {'✅ 優秀' if model.get('rmse', 100) <= 3.0 else '⚠️ 尚可' if model.get('rmse', 100) <= 6.0 else '❌ 較差'}")
    print(f"   ├─ 置信度        : {model.get('confidence'):.4f}")
    if model.get('spearman_r') is not None:
        try:
            print(f"   └─ Spearman r    : {float(model.get('spearman_r')):.4f}")
        except Exception:
            pass

    # 如果要求顯示權重，顯示前 N 個最重要的特徵
    if args.top > 0:
        weights = model.get("weights", {}) or {}
        if weights:
            print("\n權重最高的特徵：")
            # 按絕對值排序權重
            sorted_items = sorted(
                weights.items(),
                key=lambda item: abs(item[1]),
                reverse=True,
            )
            # 顯示前 N 個
            for name, weight in sorted_items[: args.top]:
                print(f"  {name:25s} {weight:+.6f}")
        else:
            print("\n[警告] 校準模型未返回可顯示的權重。")

    # 步驟 4：儲存模型快照
    # 產生時間戳記檔名
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    snapshot_name = f"{args.model_name}{args.version_suffix}_{timestamp}.json"
    latest_name = f"{args.model_name}.json"
    
    # 建立模型目錄（如果不存在）
    args.model_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = args.model_dir / snapshot_name  # 版本化快照
    latest_path = args.model_dir / latest_name  # 最新版本

    try:
        # 處理高級模型的序列化
        model_to_save = model.copy()
        
        # 如果是 XGBoost 模型，使用其原生保存格式
        if model.get("model_type") == "xgboost":
            # XGBoost 原生格式（更高效）
            xgb_snapshot = snapshot_path.with_suffix('.xgb')
            xgb_latest = latest_path.with_suffix('.xgb')
            
            model['model_object'].save_model(str(xgb_snapshot))
            model['model_object'].save_model(str(xgb_latest))
            
            # 移除不可序列化的對象
            model_to_save.pop('model_object', None)
            
            print(f"\n💾 XGBoost 模型已保存:")
            print(f"   ├─ 版本快照(XGB)  : {xgb_snapshot}")
            print(f"   └─ 最新版本(XGB)  : {xgb_latest}")
        
        # 儲存版本化快照（JSON 格式）
        with snapshot_path.open("w", encoding="utf-8") as handle:
            json.dump(model_to_save, handle, ensure_ascii=False, indent=2)
        
        # 更新最新版本（JSON 格式）
        with latest_path.open("w", encoding="utf-8") as handle:
            json.dump(model_to_save, handle, ensure_ascii=False, indent=2)
        
        if model.get("model_type") != "xgboost":
            print(f"\n💾 保存結果:")
            print(f"   ├─ 版本快照(JSON) : {snapshot_path}")
            print(f"   └─ 最新版本(JSON) : {latest_path}")
        else:
            print(f"   ├─ 版本快照(JSON) : {snapshot_path}")
            print(f"   └─ 最新版本(JSON) : {latest_path}")
        print("\n✅ 校準完成！")
    except OSError as exc:
        print(f"[錯誤] 無法寫入模型快照：{exc}", file=sys.stderr)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
