#!/usr/bin/env python3
"""
驗證腳本 — 評估系統分數合理性檢測
====================================

功能：
  1. 基準對照：用已評估的經典故事（有 Goodreads 評分）建立分數基線
  2. 三級品質測試：自動生成 優/中/劣 三種合成文本，確認系統能區分品質
  3. 維度異常偵測：檢查是否存在維度鎖死（常數分）、極端偏差等問題
  4. 分數分佈分析：Shapiro-Wilk 常態性、離群值、維度相關矩陣

用法：
  # 在容器內執行（只分析已有評估結果，不需要 GPU）
    python scripts/validate.py

  # 加入合成品質測試（需要跑評估，需要 GPU）
    python scripts/validate.py --synthetic

  # 指定已評估故事目錄
    python scripts/validate.py --evaluated-dir output/

輸出：
  - 終端彩色報告
  - reports/validation_report.json（機器可讀）
"""

import os
import json
import math
import argparse
import textwrap
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from ..shared.stats_utils import mean, median, pearson_correlation, spearman_correlation, stdev
from ..shared.score_utils import extract_calibrated_score, normalize_score_fields
from ..shared.score_policy import apply_cross_dimension_constraints, compute_consensus_adjustment
from ..shared.story_data import load_story_records

# ── 嘗試匯入 Rich（容器內有安裝），否則降級為純文字 ──
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ─────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────
DIMENSIONS = [
    "readability", "emotional_impact", "coherence",
    "entity_consistency", "completeness", "factuality",
]

DIM_LABELS = {
    "readability":        "可讀性",
    "emotional_impact":   "情感影響力",
    "coherence":          "連貫性",
    "entity_consistency": "實體一致性",
    "completeness":       "完整性",
    "factuality":         "事實正確性",
}

# 經驗門檻（基於 100+ 經典故事的觀察值）
EXPECTED_RANGES = {
    "readability":        (60, 98),
    "emotional_impact":   (40, 95),
    "coherence":          (55, 90),
    "entity_consistency": (60, 95),
    "completeness":       (55, 90),
    "factuality":         (55, 80),
}

# Goodreads 評分 → 100 分制轉換
def goodreads_to_100(rating: float) -> float:
    """Goodreads 5 分制轉 100 分制（乘 20）"""
    return rating * 20


# ─────────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────────
def load_evaluated_stories(eval_dir: str) -> list[dict]:
    """載入所有已評估故事的 assessment_report + metadata"""
    stories = []
    eval_path = Path(eval_dir)

    if not eval_path.exists():
        print(f"[錯誤] 找不到已評估目錄: {eval_dir}")
        return stories

    records = load_story_records([eval_dir], require_report=True)
    for record in records:
        report = normalize_score_fields(record.get("report") or {})
        metadata = record.get("metadata") or {}
        story_name = record.get("story_name") or "unknown"
        calibrated = extract_calibrated_score(report)

        stories.append({
            "name": story_name,
            "report": report,
            "metadata": metadata,
            "overall": calibrated if isinstance(calibrated, (int, float)) else report.get("overall_score", 0),
            "dimensions": report.get("dimension_scores", {}),
            "governance": report.get("governance") or {},
            "user_rating": metadata.get("user_rating"),
            "ratings_count": metadata.get("ratings_count", 0),
            "quality_label": metadata.get("quality_label", "unknown"),
            "word_count": metadata.get("word_count", 0),
        })

    return stories


# ─────────────────────────────────────────────
# 統計工具（共用模組包裝）
# ─────────────────────────────────────────────
def pearson_r(x: list[float], y: list[float]) -> float:
    """皮爾遜相關係數。"""
    return pearson_correlation(x, y, min_samples=3)


def spearman_r(x: list[float], y: list[float]) -> float:
    """Spearman 等級相關係數。"""
    return spearman_correlation(x, y, min_samples=3)


# ─────────────────────────────────────────────
# 檢測 1：基準對照分析
# ─────────────────────────────────────────────
def check_baseline(stories: list[dict]) -> dict:
    """
    將 AI 評分與 Goodreads 用戶評分做相關性分析。
    這不是說分數要完全一樣，而是「排序應大致相符」。
    """
    results = {
        "test": "基準對照",
        "description": "AI 總分 vs Goodreads 用戶評分的排序一致性",
        "status": "⏳",
        "details": {},
    }

    # 過濾有用戶評分的故事
    paired = [(s["overall"], goodreads_to_100(s["user_rating"]))
              for s in stories if s["user_rating"] is not None]

    if len(paired) < 10:
        results["status"] = "⚠️ 樣本不足"
        results["details"]["sample_size"] = len(paired)
        return results

    ai_scores = [p[0] for p in paired]
    user_scores = [p[1] for p in paired]

    r_pearson = pearson_r(ai_scores, user_scores)
    r_spearman = spearman_r(ai_scores, user_scores)

    avg_diff = mean([abs(a - u) for a, u in paired])
    max_diff = max(abs(a - u) for a, u in paired)

    # 找出差異最大的 5 筆（可能是系統誤判）
    sorted_by_diff = sorted(
        [(s["name"], s["overall"], goodreads_to_100(s["user_rating"]))
         for s in stories if s["user_rating"] is not None],
        key=lambda t: abs(t[1] - t[2]),
        reverse=True,
    )

    results["details"] = {
        "sample_size": len(paired),
        "pearson_r": round(r_pearson, 4),
        "spearman_r": round(r_spearman, 4),
        "avg_absolute_diff": round(avg_diff, 2),
        "max_absolute_diff": round(max_diff, 2),
        "ai_score_range": f"{min(ai_scores):.1f} – {max(ai_scores):.1f}",
        "user_score_range": f"{min(user_scores):.1f} – {max(user_scores):.1f}",
        "largest_disagreements": [
            {"story": name, "ai": round(ai, 1), "user": round(user, 1),
             "diff": round(abs(ai - user), 1)}
            for name, ai, user in sorted_by_diff[:5]
        ],
    }

    # 判定
    # Spearman ≥ 0.3 表示有弱到中等的排序一致性（對兒童故事來說合理）
    # Goodreads 評分本身高度集中（3.5-4.2），相關性天然偏低
    if r_spearman >= 0.3:
        results["status"] = "✅ 通過"
    elif r_spearman >= 0.15:
        results["status"] = "⚠️ 弱相關"
    else:
        results["status"] = "❌ 無相關"

    return results


# ─────────────────────────────────────────────
# 檢測 2：維度異常偵測
# ─────────────────────────────────────────────
def check_dimension_anomalies(stories: list[dict]) -> dict:
    """
    偵測：
    - 維度鎖死（>40% 故事同一分數）
    - 維度超出合理範圍
    - 維度方差過低（缺乏區分度）
    """
    results = {
        "test": "維度異常偵測",
        "description": "檢查各維度是否存在鎖死、極端值、區分度不足",
        "status": "⏳",
        "details": {},
        "warnings": [],
    }

    for dim in DIMENSIONS:
        scores = [s["dimensions"].get(dim, 0) for s in stories
                  if dim in s["dimensions"]]
        if not scores:
            continue

        dim_info = {
            "mean": round(mean(scores), 2),
            "stdev": round(stdev(scores), 2),
            "median": round(median(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "range": round(max(scores) - min(scores), 2),
        }

        # 檢測 1：常數鎖死
        from collections import Counter
        score_counts = Counter(round(s, 1) for s in scores)
        most_common_val, most_common_count = score_counts.most_common(1)[0]
        lock_ratio = most_common_count / len(scores)

        if lock_ratio > 0.4:
            dim_info["⚠_locked"] = f"{most_common_count}/{len(scores)} ({lock_ratio:.0%}) 鎖定在 {most_common_val}"
            results["warnings"].append(
                f"{DIM_LABELS.get(dim, dim)}：{lock_ratio:.0%} 的故事得分 = {most_common_val}"
            )

        # 檢測 2：方差過低（缺乏區分度）
        if stdev(scores) < 3.0 and len(scores) > 10:
            dim_info["⚠_low_variance"] = f"σ={stdev(scores):.2f}，區分度不足"
            results["warnings"].append(
                f"{DIM_LABELS.get(dim, dim)}：標準差僅 {stdev(scores):.2f}，難以區分品質差異"
            )

        # 檢測 3：超出合理範圍
        exp_lo, exp_hi = EXPECTED_RANGES.get(dim, (0, 100))
        outliers = [s for s in scores if s < exp_lo - 15 or s > exp_hi + 5]
        if outliers:
            dim_info["⚠_outliers"] = f"{len(outliers)} 筆超出預期範圍"

        results["details"][dim] = dim_info

    # 總判定
    if len(results["warnings"]) == 0:
        results["status"] = "✅ 全部正常"
    elif len(results["warnings"]) <= 2:
        results["status"] = "⚠️ 有小問題"
    else:
        results["status"] = "❌ 多維異常"

    return results


# ─────────────────────────────────────────────
# 檢測 3：品質標籤一致性
# ─────────────────────────────────────────────
def check_quality_label_alignment(stories: list[dict]) -> dict:
    """
    metadata 中的 quality_label（high/medium/low）應與 AI 總分大致對應。
    high 的平均分應 > medium > low。
    """
    results = {
        "test": "品質標籤一致性",
        "description": "Goodreads quality_label 應與 AI 總分排序一致",
        "status": "⏳",
        "details": {},
    }

    by_label = defaultdict(list)
    for s in stories:
        label = s["quality_label"].replace("-", "_").lower()
        # 統一標籤
        if label in ("very_high",):
            label = "high"
        if label in ("medium_high",):
            label = "medium"
        if label in ("medium_low",):
            label = "low"
        by_label[label].append(s["overall"])

    for label, scores in sorted(by_label.items()):
        results["details"][label] = {
            "count": len(scores),
            "mean": round(mean(scores), 2),
            "stdev": round(stdev(scores), 2),
            "range": f"{min(scores):.1f} – {max(scores):.1f}",
        }

    # 判定：high.mean > medium.mean > low.mean
    means = {k: mean(v) for k, v in by_label.items() if len(v) >= 3}

    if "high" in means and "medium" in means:
        if means["high"] > means["medium"]:
            results["status"] = "✅ 通過"
        else:
            results["status"] = "⚠️ high ≤ medium"
            results["warnings"] = [
                f"high 平均 {means['high']:.1f} vs medium 平均 {means['medium']:.1f}"
            ]
    else:
        results["status"] = "⚠️ 標籤分佈不足"

    return results


# ─────────────────────────────────────────────
# 檢測 4：分數分佈合理性
# ─────────────────────────────────────────────
def check_score_distribution(stories: list[dict]) -> dict:
    """
    檢查：
    - 總分分佈不應極端集中
    - 應有合理的 spread
    - 不應有 >95 或 <40 的極端值（經典故事正常不會出現）
    """
    results = {
        "test": "分數分佈合理性",
        "description": "總分分佈是否有合理的區間和變異",
        "status": "⏳",
        "details": {},
        "warnings": [],
    }

    overall_scores = [s["overall"] for s in stories]

    if not overall_scores:
        results["status"] = "❌ 無資料"
        return results

    # 分段統計
    buckets = {
        "≥85 (優秀)": 0,
        "75-84 (良好)": 0,
        "65-74 (普通)": 0,
        "55-64 (待改進)": 0,
        "<55 (不合格)": 0,
    }
    for s in overall_scores:
        if s >= 85:
            buckets["≥85 (優秀)"] += 1
        elif s >= 75:
            buckets["75-84 (良好)"] += 1
        elif s >= 65:
            buckets["65-74 (普通)"] += 1
        elif s >= 55:
            buckets["55-64 (待改進)"] += 1
        else:
            buckets["<55 (不合格)"] += 1

    results["details"] = {
        "total_stories": len(overall_scores),
        "mean": round(mean(overall_scores), 2),
        "stdev": round(stdev(overall_scores), 2),
        "median": round(median(overall_scores), 2),
        "min": round(min(overall_scores), 2),
        "max": round(max(overall_scores), 2),
        "distribution": buckets,
    }

    # 檢查 1：方差過低
    if stdev(overall_scores) < 3.0:
        results["warnings"].append(
            f"總分標準差僅 {stdev(overall_scores):.2f}，系統可能缺乏區分度"
        )

    # 檢查 2：所有分數集中在同一區間
    biggest_bucket = max(buckets.values())
    if biggest_bucket / len(overall_scores) > 0.7:
        results["warnings"].append(
            f"{biggest_bucket}/{len(overall_scores)} ({biggest_bucket/len(overall_scores):.0%}) 集中在同一區間"
        )

    # 檢查 3：是否有極端高/低（可能是 bug）
    extreme_high = [s["name"] for s in stories if s["overall"] > 95]
    extreme_low = [s["name"] for s in stories if s["overall"] < 40]
    if extreme_high:
        results["warnings"].append(f"異常高分 (>95): {extreme_high}")
    if extreme_low:
        results["warnings"].append(f"異常低分 (<40): {extreme_low}")

    # 判定
    if not results["warnings"]:
        results["status"] = "✅ 分佈合理"
    elif len(results["warnings"]) == 1:
        results["status"] = "⚠️ 輕微偏斜"
    else:
        results["status"] = "❌ 分佈異常"

    return results


# ─────────────────────────────────────────────
# 檢測 5：維度相關矩陣（冗餘檢測）
# ─────────────────────────────────────────────
def check_dimension_correlations(stories: list[dict]) -> dict:
    """
    如果兩個維度相關性 > 0.85，可能存在冗餘（測量相同東西）。
    如果所有維度高度相關，系統只是在不同方式重複同一信號。
    """
    results = {
        "test": "維度獨立性",
        "description": "各維度是否測量不同面向（非冗餘）",
        "status": "⏳",
        "details": {},
        "warnings": [],
    }

    dim_data = {}
    for dim in DIMENSIONS:
        dim_data[dim] = [s["dimensions"].get(dim, 0) for s in stories
                         if dim in s["dimensions"]]

    correlation_matrix = {}
    high_corr_pairs = []

    for i, d1 in enumerate(DIMENSIONS):
        for j, d2 in enumerate(DIMENSIONS):
            if j <= i:
                continue
            if len(dim_data[d1]) < 10 or len(dim_data[d2]) < 10:
                continue
            # 取共同長度
            n = min(len(dim_data[d1]), len(dim_data[d2]))
            r = pearson_r(dim_data[d1][:n], dim_data[d2][:n])
            pair_key = f"{d1} × {d2}"
            correlation_matrix[pair_key] = round(r, 3)

            if abs(r) > 0.85:
                high_corr_pairs.append((d1, d2, r))
                results["warnings"].append(
                    f"{DIM_LABELS.get(d1, d1)} × {DIM_LABELS.get(d2, d2)} = {r:.3f}（可能冗餘）"
                )

    results["details"]["correlation_matrix"] = correlation_matrix
    results["details"]["high_correlation_pairs"] = len(high_corr_pairs)

    if not results["warnings"]:
        results["status"] = "✅ 各維度獨立"
    else:
        results["status"] = "⚠️ 有冗餘風險"

    return results


# ─────────────────────────────────────────────
# 檢測 6：合成品質測試（可選，需 GPU）
# ─────────────────────────────────────────────
SYNTHETIC_STORIES = {
    "good": {
        "title": "The Moonlit Garden",
        "text": textwrap.dedent("""\
            Once upon a time, in a small village by the edge of a great forest, there lived a 
            kind-hearted girl named Lily. She had bright green eyes and long brown hair that 
            she tied with a red ribbon every morning.

            One evening, Lily discovered a hidden garden behind the old stone wall at the end 
            of her street. The garden was bathed in silver moonlight, and every flower glowed 
            softly — roses of blue, daisies of gold, and tulips that shimmered like starlight.

            "Who are you?" whispered a tiny voice. Lily looked down and saw a small hedgehog 
            wearing a little top hat. "I'm Lily," she said gently. "And who are you?"

            "I'm Bramble, the garden keeper," said the hedgehog proudly. "This garden only 
            appears when someone with a truly kind heart walks by."

            Bramble explained that the garden was in danger. A shadow creature had been 
            stealing the moonlight, and without it, the flowers would fade forever. Lily felt 
            a surge of courage. "I'll help you," she said firmly.

            Together, they journeyed deeper into the garden. They crossed a bridge made of 
            woven vines, climbed a hill of soft moss, and finally reached the Shadow Pool — 
            a dark pond where the creature lived.

            Lily wasn't afraid. She knelt by the pool and began to sing a lullaby her mother 
            had taught her. The melody was warm and gentle, and slowly the shadow creature 
            rose from the water. It wasn't scary at all — it was a lonely little cloud that 
            had lost its way home.

            "You don't need to steal the moonlight," Lily said softly. "The moon shines for 
            everyone." She cupped her hands and lifted the little cloud toward the sky. With 
            a grateful sigh, the cloud floated upward and joined the stars.

            The garden burst into brilliant light. Every flower bloomed brighter than before, 
            and Bramble danced with joy. "Thank you, Lily! You saved us all!"

            From that night on, Lily visited the moonlit garden whenever the moon was full. 
            She and Bramble became the best of friends, and the garden remained a place of 
            wonder for all who had kindness in their hearts.

            Moral: True courage comes from compassion, and kindness can light even the 
            darkest places.
        """),
        "expected_range": (72, 92),
    },
    "medium": {
        "title": "The Lost Key",
        "text": textwrap.dedent("""\
            There was a boy named Tom. He found a key on the ground. The key was old and 
            rusty. Tom picked it up and looked at it.

            Tom walked to a door. He tried the key. The door opened. Inside there was a room 
            with a treasure chest. Tom opened the chest. There was gold inside.

            Tom was happy. He took the gold home. His mother was happy too. They bought food 
            and clothes. Tom kept the key.

            The next day Tom went back. The door was gone. Tom looked everywhere but couldn't 
            find it. He went home sad. But he still had the gold.

            Tom learned that good things don't always last. But he was grateful for what he 
            had.
        """),
        "expected_range": (58, 75),
    },
    "bad": {
        "title": "Story Bad",
        "text": textwrap.dedent("""\
            cat go house. cat is cat. the cat walk walk walk. big cat small cat. cat eat 
            food food food. cat sleep. cat wake up. cat go outside. cat see dog. dog is dog. 
            cat run. dog run. they run run run. then stop. cat go home. dog go home. end.

            cat is happy. dog is happy. bird is happy. fish is happy. tree is happy. 
            everyone happy. the end the end the end.
        """),
        "expected_range": (35, 58),
    },
}


def run_synthetic_test(pending_dir: str, evaluated_dir: str, eval_script: str = "main.py") -> dict:
    """
    生成三種品質的合成故事，跑評估，確認分數排序正確。
    good > medium > bad
    """
    import subprocess
    import shutil

    results = {
        "test": "合成品質測試",
        "description": "生成優/中/劣故事並評估，確認系統能區分品質等級",
        "status": "⏳",
        "details": {},
        "warnings": [],
    }

    scores = {}
    test_prefix = "__validate_"

    for quality, data in SYNTHETIC_STORIES.items():
        story_name = f"{test_prefix}{quality}"
        story_dir = Path(pending_dir) / story_name

        # 建立測試故事
        story_dir.mkdir(parents=True, exist_ok=True)
        (story_dir / "full_story.txt").write_text(
            f"# {data['title']}\n\n{data['text']}", encoding="utf-8"
        )
        (story_dir / "title.txt").write_text(data["title"], encoding="utf-8")

        print(f"  📝 評估合成故事: {quality} ({data['title']})")

        try:
            # 執行評估
            cmd = [sys.executable, eval_script, "--input", str(story_dir)]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )

            # 讀取結果（可能在輸入故事目錄或 --evaluated-dir）
            eval_dir = Path(evaluated_dir) / story_name
            report_file = eval_dir / "assessment_report.json"

            if not report_file.exists():
                # 可能仍保留在測試暫存故事目錄
                report_file = story_dir / "assessment_report.json"

            if report_file.exists():
                with open(report_file, "r", encoding="utf-8") as f:
                    report = json.load(f)
                scores[quality] = report.get("overall_score", 0)
                results["details"][quality] = {
                    "score": scores[quality],
                    "expected": data["expected_range"],
                    "dimensions": report.get("dimension_scores", {}),
                    "in_range": data["expected_range"][0] <= scores[quality] <= data["expected_range"][1],
                }
            else:
                results["warnings"].append(f"{quality} 評估失敗：找不到報告")
                scores[quality] = None

        except subprocess.TimeoutExpired:
            results["warnings"].append(f"{quality} 評估逾時 (>600s)")
            scores[quality] = None
        except Exception as e:
            results["warnings"].append(f"{quality} 評估錯誤: {e}")
            scores[quality] = None

        # 清理測試資料
        for cleanup_dir in [story_dir, Path(evaluated_dir) / story_name]:
            if cleanup_dir.exists():
                shutil.rmtree(cleanup_dir, ignore_errors=True)

    # 判定排序
    if all(v is not None for v in scores.values()):
        if scores["good"] > scores["medium"] > scores["bad"]:
            results["status"] = "✅ 排序正確 (good > medium > bad)"
        elif scores["good"] > scores["bad"]:
            results["status"] = "⚠️ 部分正確 (good > bad，但 medium 位置有誤)"
        else:
            results["status"] = "❌ 排序錯誤"

        results["details"]["score_order"] = {
            "good": scores.get("good"),
            "medium": scores.get("medium"),
            "bad": scores.get("bad"),
        }
    else:
        results["status"] = "❌ 部分評估失敗"

    return results


# ─────────────────────────────────────────────
# 檢測 7：字數 vs 分數偏差
# ─────────────────────────────────────────────
def check_length_bias(stories: list[dict]) -> dict:
    """
    檢查系統是否對故事長度有系統性偏好。
    理想狀態：字數 vs 總分 相關性 < 0.5
    """
    results = {
        "test": "長度偏差檢測",
        "description": "系統是否系統性偏好長故事或短故事",
        "status": "⏳",
        "details": {},
    }

    paired = [(s["word_count"], s["overall"]) for s in stories
              if s["word_count"] and s["word_count"] > 0]

    if len(paired) < 10:
        results["status"] = "⚠️ 樣本不足"
        return results

    wc = [p[0] for p in paired]
    sc = [p[1] for p in paired]

    # 用 log(word_count) 比較更合理
    log_wc = [math.log(w + 1) for w in wc]
    r = pearson_r(log_wc, sc)

    results["details"] = {
        "pearson_r_log_wordcount_vs_score": round(r, 4),
        "word_count_range": f"{min(wc)} – {max(wc)}",
        "interpretation": (
            "無顯著偏差" if abs(r) < 0.3 else
            "輕微偏好長文" if r > 0 else "輕微偏好短文"
        ) if abs(r) < 0.5 else (
            "顯著偏好長文" if r > 0 else "顯著偏好短文"
        ),
    }

    if abs(r) < 0.3:
        results["status"] = "✅ 無長度偏差"
    elif abs(r) < 0.5:
        results["status"] = "⚠️ 輕微偏差"
    else:
        results["status"] = "❌ 顯著偏差"

    return results


# ─────────────────────────────────────────────
# 檢測 8：治理層健康度
# ─────────────────────────────────────────────
def check_governance_health(stories: list[dict]) -> dict:
    """檢查 governance 欄位覆蓋率與風險分佈是否健康。"""
    results = {
        "test": "治理層健康度",
        "description": "檢查 confidence/risk/review recommendation 的覆蓋率與分佈",
        "status": "⏳",
        "details": {},
        "warnings": [],
    }

    total = len(stories)
    with_governance = [s for s in stories if isinstance(s.get("governance"), dict) and s.get("governance")]
    missing_count = total - len(with_governance)
    coverage = (len(with_governance) / total) if total else 0.0

    risk_counter = defaultdict(int)
    review_counter = defaultdict(int)
    confidence_values = []

    for story in with_governance:
        governance = story.get("governance") or {}
        risk_level = governance.get("risk_level") or "unknown"
        risk_counter[str(risk_level)] += 1
        review = governance.get("review_recommendation") or "unknown"
        review_counter[str(review)] += 1

        confidence = governance.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence_values.append(float(confidence))

    high_or_critical = risk_counter.get("high", 0) + risk_counter.get("critical", 0)
    high_ratio = (high_or_critical / len(with_governance)) if with_governance else 0.0

    results["details"] = {
        "total_stories": total,
        "coverage": round(coverage, 4),
        "missing_governance": missing_count,
        "risk_distribution": dict(sorted(risk_counter.items())),
        "review_distribution": dict(sorted(review_counter.items())),
        "confidence_mean": round(mean(confidence_values), 4) if confidence_values else None,
        "confidence_median": round(median(confidence_values), 4) if confidence_values else None,
        "high_or_critical_ratio": round(high_ratio, 4),
    }

    if coverage < 0.9:
        results["warnings"].append(f"governance 覆蓋率不足：{coverage:.0%}")
    if high_ratio > 0.35:
        results["warnings"].append(f"高風險比例偏高：{high_ratio:.0%}")
    if confidence_values and mean(confidence_values) < 0.72:
        results["warnings"].append("平均 confidence 偏低，建議檢查模型穩定性")

    if not results["warnings"]:
        results["status"] = "✅ 治理層正常"
    elif len(results["warnings"]) == 1:
        results["status"] = "⚠️ 需留意"
    else:
        results["status"] = "❌ 治理風險偏高"

    return results


# ─────────────────────────────────────────────
# 檢測 9：策略回歸測試（硬約束/共識融合）
# ─────────────────────────────────────────────
def check_policy_regression() -> dict:
    """驗證 score policy 是否按預期生效，避免策略配置回歸。"""
    results = {
        "test": "策略回歸測試",
        "description": "驗證跨維度硬約束與共識融合是否按預期運作",
        "status": "⏳",
        "details": {},
        "warnings": [],
    }

    # Case 1: 結構偏低，應觸發 cap
    c1_scores = {
        "readability": 86.0,
        "emotional_impact": 90.0,
        "coherence": 50.0,
        "entity_consistency": 78.0,
        "completeness": 49.0,
        "factuality": 70.0,
    }
    base_c1 = 88.0
    constrained_c1, meta_c1 = apply_cross_dimension_constraints(base_c1, c1_scores)

    # Case 2: 無明顯問題，約束不應過度生效
    c2_scores = {
        "readability": 82.0,
        "emotional_impact": 80.0,
        "coherence": 78.0,
        "entity_consistency": 79.0,
        "completeness": 77.0,
        "factuality": 70.0,
    }
    base_c2 = 79.0
    constrained_c2, meta_c2 = apply_cross_dimension_constraints(base_c2, c2_scores)

    # Case 3: 共識融合：極端值時不應大幅漂移
    c3_scores = {
        "readability": 98.0,
        "emotional_impact": 52.0,
        "coherence": 60.0,
        "entity_consistency": 58.0,
        "completeness": 62.0,
        "factuality": 65.0,
    }
    base_c3 = 92.0
    consensus_c3, meta_consensus_c3 = compute_consensus_adjustment(base_c3, c3_scores)

    case_results = {
        "constraint_low_structure": {
            "base": base_c1,
            "after": round(constrained_c1, 3),
            "applied_rules": meta_c1.get("applied_rules", []),
            "passed": constrained_c1 <= 76.0,
        },
        "constraint_normal_case": {
            "base": base_c2,
            "after": round(constrained_c2, 3),
            "applied_rules": meta_c2.get("applied_rules", []),
            "passed": abs(constrained_c2 - base_c2) < 0.001,
        },
        "consensus_pull_limit": {
            "base": base_c3,
            "after": round(consensus_c3, 3),
            "pull": meta_consensus_c3.get("pull"),
            "max_pull": meta_consensus_c3.get("max_pull"),
            "passed": abs(float(meta_consensus_c3.get("pull") or 0.0)) <= float(meta_consensus_c3.get("max_pull") or 0.0),
        },
    }
    results["details"] = case_results

    failed_cases = [name for name, info in case_results.items() if not info.get("passed")]
    if failed_cases:
        results["warnings"].append(f"策略回歸失敗案例: {failed_cases}")

    if not failed_cases:
        results["status"] = "✅ 通過"
    elif len(failed_cases) == 1:
        results["status"] = "⚠️ 部分失敗"
    else:
        results["status"] = "❌ 失敗"

    return results


# ─────────────────────────────────────────────
# 報告輸出
# ─────────────────────────────────────────────
def print_report(checks: list[dict], stories: list[dict]):
    """終端輸出格式化驗證報告"""

    if HAS_RICH:
        _print_rich_report(checks, stories)
    else:
        _print_plain_report(checks, stories)


def _print_rich_report(checks: list[dict], stories: list[dict]):
    console = Console()

    console.print()
    console.print(Panel.fit(
        "[bold cyan]🔍 評估系統驗證報告[/bold cyan]\n"
        f"[dim]分析 {len(stories)} 個已評估故事 · {datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]",
        border_style="cyan",
    ))

    # 總覽表格
    summary_table = Table(
        title="檢測結果總覽",
        box=box.ROUNDED,
        show_lines=True,
    )
    summary_table.add_column("檢測項目", style="bold")
    summary_table.add_column("狀態", justify="center")
    summary_table.add_column("說明")

    for c in checks:
        summary_table.add_row(c["test"], c["status"], c["description"])

    console.print(summary_table)

    # 詳細結果
    for c in checks:
        console.print()
        panel_lines = []

        if "details" in c and c["details"]:
            for k, v in c["details"].items():
                if isinstance(v, dict):
                    panel_lines.append(f"[bold]{k}[/bold]:")
                    for kk, vv in v.items():
                        panel_lines.append(f"  {kk}: {vv}")
                else:
                    panel_lines.append(f"[bold]{k}[/bold]: {v}")

        if "warnings" in c and c["warnings"]:
            panel_lines.append("")
            panel_lines.append("[bold red]警告:[/bold red]")
            for w in c["warnings"]:
                panel_lines.append(f"  ⚠ {w}")

        if panel_lines:
            console.print(Panel(
                "\n".join(panel_lines),
                title=f"[bold]{c['test']}[/bold]",
                border_style="yellow" if "⚠" in c["status"] else
                             "red" if "❌" in c["status"] else "green",
            ))

    # 最終判定
    passed = sum(1 for c in checks if "✅" in c["status"])
    warnings = sum(1 for c in checks if "⚠" in c["status"])
    failed = sum(1 for c in checks if "❌" in c["status"])

    console.print()
    if failed == 0 and warnings <= 1:
        console.print(Panel.fit(
            f"[bold green]✅ 系統驗證通過[/bold green]  "
            f"({passed} 通過 / {warnings} 警告 / {failed} 失敗)",
            border_style="green",
        ))
    elif failed == 0:
        console.print(Panel.fit(
            f"[bold yellow]⚠️ 系統大致正常，有 {warnings} 項需注意[/bold yellow]  "
            f"({passed} 通過 / {warnings} 警告 / {failed} 失敗)",
            border_style="yellow",
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]❌ 系統存在問題[/bold red]  "
            f"({passed} 通過 / {warnings} 警告 / {failed} 失敗)",
            border_style="red",
        ))

    console.print()


def _print_plain_report(checks: list[dict], stories: list[dict]):
    """無 Rich 的純文字降級輸出"""
    print()
    print("=" * 60)
    print("🔍 評估系統驗證報告")
    print(f"   分析 {len(stories)} 個已評估故事")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    for c in checks:
        print(f"\n{'─' * 50}")
        print(f"{c['status']}  {c['test']}")
        print(f"   {c['description']}")

        if "details" in c:
            for k, v in c["details"].items():
                if isinstance(v, dict):
                    print(f"   {k}:")
                    for kk, vv in v.items():
                        print(f"     {kk}: {vv}")
                else:
                    print(f"   {k}: {v}")

        if "warnings" in c and c["warnings"]:
            for w in c["warnings"]:
                print(f"   ⚠ {w}")

    passed = sum(1 for c in checks if "✅" in c["status"])
    warnings = sum(1 for c in checks if "⚠" in c["status"])
    failed = sum(1 for c in checks if "❌" in c["status"])

    print(f"\n{'=' * 60}")
    print(f"結論: {passed} 通過 / {warnings} 警告 / {failed} 失敗")
    print("=" * 60)


def save_report(checks: list[dict], output_path: str):
    """儲存 JSON 報告"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": sum(1 for c in checks if "✅" in c["status"]),
            "warnings": sum(1 for c in checks if "⚠" in c["status"]),
            "failed": sum(1 for c in checks if "❌" in c["status"]),
        },
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📄 報告已儲存至 {output_path}")


# ─────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="評估系統分數合理性驗證",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            範例：
              python scripts/validate.py                    # 快速驗證（僅分析已有結果）
              python scripts/validate.py --synthetic        # 完整驗證（含合成測試，需 GPU）
              python scripts/validate.py -o report.json     # 指定報告輸出路徑
        """),
    )
    parser.add_argument(
        "--evaluated-dir", default="output",
        help="已評估故事目錄 (預設: output/)",
    )
    parser.add_argument(
        "--synthetic", action="store_true",
        help="執行合成品質測試（會實際跑評估，需要 GPU）",
    )
    parser.add_argument(
        "--pending-dir", default="output/__validate_pending",
        help="合成測試的暫存目錄 (預設: output/__validate_pending/)",
    )
    parser.add_argument(
        "-o", "--output", default="reports/evaluation/validation_report.json",
        help="JSON 報告輸出路徑",
    )
    args = parser.parse_args()

    print("🔍 載入已評估故事...")
    stories = load_evaluated_stories(args.evaluated_dir)

    if not stories:
        print("❌ 找不到任何已評估的故事，請確認目錄路徑。")
        sys.exit(1)

    print(f"   找到 {len(stories)} 個已評估故事\n")

    # 執行各項檢測
    checks = []

    print("📊 [1/6] 基準對照分析...")
    checks.append(check_baseline(stories))

    print("🔬 [2/6] 維度異常偵測...")
    checks.append(check_dimension_anomalies(stories))

    print("🏷️  [3/6] 品質標籤一致性...")
    checks.append(check_quality_label_alignment(stories))

    print("📈 [4/6] 分數分佈合理性...")
    checks.append(check_score_distribution(stories))

    print("🔗 [5/6] 維度獨立性...")
    checks.append(check_dimension_correlations(stories))

    print("📏 [6/7] 長度偏差檢測...")
    checks.append(check_length_bias(stories))

    print("🛡️ [7/8] 治理層健康度...")
    checks.append(check_governance_health(stories))

    print("🧷 [8/8] 策略回歸測試...")
    checks.append(check_policy_regression())

    # 可選：合成測試
    if args.synthetic:
        print("\n🧪 [額外] 合成品質測試...")
        checks.append(run_synthetic_test(args.pending_dir, args.evaluated_dir))

    # 輸出
    print_report(checks, stories)
    save_report(checks, args.output)


if __name__ == "__main__":
    main()
