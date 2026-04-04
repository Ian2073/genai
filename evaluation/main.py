# =============================================================================
# main.py - 多維度故事評估系統主控程式
# =============================================================================
# 
# 【系統概述】
# 這是一個專為兒童故事設計的智能評估系統，提供六大維度的全面分析：
# 1. 實體一致性 (Entity Consistency) - 檢查角色、地點等實體的命名和描述是否一致
# 2. 完整性 (Completeness) - 評估故事結構是否完整（開頭、發展、高潮、結局）
# 3. 連貫性 (Coherence) - 檢查情節是否流暢、邏輯是否合理
# 4. 可讀性 (Readability) - 評估語言是否適合目標年齡層
# 5. 事實正確性 (Factuality) - 驗證故事中的事實陳述是否準確
# 6. 情感影響力 (Emotional Impact) - 分析故事的情感表達和感染力
#
# 【主要功能】
# - 單一故事評估：對單個故事進行全方位品質檢測
# - 批次評估：一次評估多個故事，生成對比報告
# - 多文檔支持：可處理分段式故事（標題、大綱、正文、旁白、對話）
# - 視覺化報告：生成雷達圖、JSON 報告等多種格式
# - 智能快取：自動管理模型載入，避免重複加載提升效能
#
# 【使用方式】
# python main.py                              # 評估 output 資料夾中的所有故事
# python main.py --input output/MyStory       # 評估單一故事
# python main.py --aspects coherence readability  # 只評估特定維度
#
# =============================================================================

import json
import logging
import os
import glob
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# 導入六維度評估系統的主控制器
from evaluator import MultiAspectEvaluator
from shared.story_data import collect_branch_story_paths, discover_story_dirs

# 導入終端美化工具（用於在命令列顯示漂亮的評估結果表格）
from rich.console import Console
from rich.table import Table

# 導入工具函數
from utils import (
    DEFAULT_ASPECTS,      # 預設的六大評估維度
    get_bool_env,         # 從環境變數讀取布林值
    get_int_env,          # 從環境變數讀取整數值
    normalise_dimensions, # 標準化維度名稱
)

# 設定 matplotlib 為無頭模式（不開啟視窗，直接儲存圖片）
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import math

# 導入系統平台偵測工具（用於選擇適當的中文字型）
import platform

logger = logging.getLogger(__name__)

# =============================================================================
# 配置類別與輔助函數
# =============================================================================

def _configure_matplotlib_fonts() -> None:
    """
    設定 matplotlib 的中文字型支援
    
    根據不同作業系統選擇合適的中文字型，避免圖表中的中文顯示為亂碼：
    - Windows: 使用微軟雅黑、SimHei 等系統字型
    - macOS: 使用 Arial Unicode MS、黑體等系統字型  
    - Linux: 使用文泉驛微米黑等開源字型
    
    同時禁用負號的 Unicode 顯示，避免負號顯示異常。
    """
    system = platform.system()
    if system == "Windows":
        fonts: List[str] = ["Microsoft YaHei", "SimHei", "DejaVu Sans", "Arial"]
    elif system == "Darwin":  # macOS 的系統名稱是 Darwin
        fonts = ["Arial Unicode MS", "Heiti TC", "DejaVu Sans", "Arial"]
    else:  # Linux 及其他系統
        fonts = ["WenQuanYi Micro Hei", "DejaVu Sans", "Arial"]
    
    plt.rcParams['font.sans-serif'] = fonts
    plt.rcParams['axes.unicode_minus'] = False  # 解決負號顯示問題


@dataclass(frozen=True)
class EvaluatorConfig:
    """
    評估器配置類別
    
    封裝評估系統的性能配置參數，控制系統的執行方式：
    
    屬性:
        parallel_enabled: 是否啟用並行處理（同時評估多個維度，提升速度）
        max_parallel_dimensions: 最大並行維度數（避免 CPU/GPU 過載）
        preload_models: 是否預先載入所有 AI 模型（記憶體換取速度）
    
    使用 frozen=True 確保配置一經建立就不可更改，提高安全性。
    """
    parallel_enabled: bool = True
    max_parallel_dimensions: int = 3
    preload_models: bool = False

    @classmethod
    def from_env(cls) -> "EvaluatorConfig":
        """
        從環境變數讀取配置
        
        支援的環境變數：
        - EVAL_PARALLEL_ENABLED: 保留相容欄位（目前維度評估採順序執行）
        - EVAL_MAX_PARALLEL_DIMENSIONS: 保留相容欄位（目前不生效）
        - EVAL_PRELOAD_MODELS: 是否預載模型 (true/false)
        
        這讓使用者可以在不修改程式碼的情況下調整性能參數。
        """
        return cls(
            parallel_enabled=get_bool_env('EVAL_PARALLEL_ENABLED', True),
            max_parallel_dimensions=get_int_env('EVAL_MAX_PARALLEL_DIMENSIONS', 3),
            preload_models=get_bool_env('EVAL_PRELOAD_MODELS', False),
        )


def _create_evaluator(config: Optional[EvaluatorConfig] = None) -> MultiAspectEvaluator:
    """
    建立評估器實例
    
    根據配置創建一個多維度評估器。評估器會管理六大檢測模組：
    - 實體一致性檢測器
    - 完整性檢測器
    - 連貫性檢測器
    - 可讀性檢測器
    - 事實正確性檢測器
    - 情感影響力檢測器
    
    參數:
        config: 評估器配置，若未提供則從環境變數讀取
        
    返回:
        已配置的 MultiAspectEvaluator 實例
    """
    cfg = config or EvaluatorConfig.from_env()
    return MultiAspectEvaluator(
        enable_parallel_processing=cfg.parallel_enabled,      # 是否並行處理
        max_parallel_dimensions=cfg.max_parallel_dimensions,  # 最大並行數
        enable_model_caching=True,                            # 啟用模型快取
        preload_all_models=cfg.preload_models,                # 是否預載模型
        batch_size_optimization=True,                         # 批次大小優化
    )


def _log_performance_config(config: EvaluatorConfig) -> None:
    """
    在終端顯示當前的性能配置
    
    讓使用者清楚了解系統正在使用的配置參數，方便除錯和優化。
    """
    logger.info(
        "性能配置: 順序執行(並行參數僅保留相容), 並行旗標=%s, 最大並行=%s, 預載模型=%s",
        config.parallel_enabled,
        config.max_parallel_dimensions,
        config.preload_models,
    )
    if get_bool_env('EVAL_FAST_MODE', False):
        logger.info("快速模式已啟用")


# =============================================================================
# 核心評估函數
# =============================================================================

def evaluate_all(story_text: str, story_title: str = "Story", aspects: Optional[List[str]] = None) -> Dict:
    """
    快速評估單一故事文本
    
    這是最簡單的評估接口，適合用於：
    - 快速測試和驗證
    - API 集成（接收文字，返回評分）
    - 互動式評估（使用者貼上故事文字）
    
    參數:
        story_text: 完整的故事文本內容
        story_title: 故事標題（用於報告顯示）
        aspects: 要評估的維度列表，若為 None 則評估所有維度
                可選值: ['entity_consistency', 'completeness', 'coherence', 
                         'readability', 'factuality', 'emotional_impact']
    
    返回:
        包含評估結果的字典：
        - overall_score: 總分 (0-100)
        - dimension_scores: 各維度分數
        - governance: 商用治理資訊（信心分、風險、覆核建議）
        - key_issues: 發現的問題總數
        - recommendations: 改進建議（前三項）
        - processing_time: 處理時間（秒）
    
    範例:
        >>> result = evaluate_all("Once upon a time...", "My Story")
        >>> print(f"總分: {result['overall_score']}")
    """
    # 簡單流程：
    # 1) 標準化維度 → 2) 讀取環境設定、建立評估器 → 3) 執行評估 → 4) 回傳精簡結果
    # 標準化維度名稱（處理使用者可能的拼寫差異）
    dimensions = normalise_dimensions(aspects)
    
    # 從環境變數載入配置
    config = EvaluatorConfig.from_env()
    evaluator = _create_evaluator(config)

    # 顯示配置資訊（方便使用者了解系統狀態）
    _log_performance_config(config)
    logger.info("預設處理順序: %s", " → ".join(evaluator.optimal_dimension_order))

    try:
        # 執行評估（使用記憶體模式，不需要建立實體檔案）
        report = evaluator.evaluate_story(
            document_paths={"full_story.txt": {"content": story_text}},
            story_title=story_title,
            enabled_dimensions=dimensions
        )
        
        # 整理並返回簡化的結果
        return {
            "overall_score": report.overall_score,
            "dimension_scores": report.dimension_scores,
            "dimension_summaries": getattr(report, "dimension_summaries", {}),
            "governance": report.governance,
            "key_issues": sum(r.issues_count for r in report.dimension_results),
            "recommendations": report.recommendations[:3],  # 只返回前三項建議
            "processing_time": report.processing_summary["total_processing_time"]
        }
    except Exception as e:
        # 錯誤處理：返回錯誤資訊而非直接崩潰
        return {
            "overall_score": 0.0,
            "dimension_scores": {},
            "dimension_summaries": {},
            "governance": {
                "confidence": 0.0,
                "confidence_score": 0.0,
                "risk_level": "critical",
                "review_recommendation": "manual_review_required",
                "risk_flags": [
                    {
                        "severity": "critical",
                        "code": "evaluation_failure",
                        "message": str(e),
                    }
                ],
            },
            "key_issues": 0,
            "recommendations": [f"評估失敗: {str(e)}"],
            "processing_time": 0.0
        }


def evaluate_multi_document(document_paths: Dict[str, str], story_title: str = "Story", aspects: List[str] = None) -> Dict:
    """
    評估多文檔故事
    
    適合評估結構化的故事專案，支援多個文檔來源：
    - title.txt: 故事標題
    - outline.txt: 故事大綱
    - full_story.txt: 完整故事文本
    - narration.txt: 旁白部分
    - dialogue.txt: 對話部分
    
    不同的檢測器會根據需要選擇合適的文檔來源進行分析。
    
    參數:
        document_paths: 文檔路徑字典，例如 {'full_story.txt': '/path/to/story.txt'}
        story_title: 故事標題
        aspects: 要評估的維度列表
        
    返回:
        包含評估結果的字典
    """
    config = EvaluatorConfig.from_env()
    evaluator = _create_evaluator(config)
    dims = normalise_dimensions(aspects)

    # 執行評估
    report = evaluator.evaluate_story(document_paths, story_title, dims)
    
    # 返回精簡結果
    return {
        'overall_score': report.overall_score,
        'dimension_scores': report.dimension_scores,
        'dimension_summaries': getattr(report, 'dimension_summaries', {}),
        'governance': report.governance,
        'recommendations': report.recommendations
    }


def evaluate_story_by_dimension(story_folder_path: str, 
                               target_dimensions: List[str] = None) -> Dict:
    """
    按維度評估故事（舊版相容接口）
    
    這個函數保留用於向後相容，建議使用 evaluate_story_directory 替代。
    
    參數:
        story_folder_path: 故事資料夾路徑
        target_dimensions: 目標評估維度
        
    返回:
        評估結果字典
    """
    from consistency import AutoStoryProcessor
    
    processor = AutoStoryProcessor()
    result = processor.check_story_by_dimension(story_folder_path, target_dimensions)
    return result


def evaluate_story_directory(
    story_dir: str,
    aspects: List[str] = None,
    *,
    evaluator: Optional[MultiAspectEvaluator] = None,
    config: Optional[EvaluatorConfig] = None,
    branch: str = "auto",
) -> Dict:
    """
    評估單一故事資料夾
    
    自動掃描資料夾中的故事檔案並進行評估。支援的檔案結構：
    
    story_folder/
        ├── title.txt          # 故事標題
        ├── outline.txt        # 故事大綱
        ├── full_story.txt     # 完整故事（必要）
        ├── narration.txt      # 旁白（可選）
        └── dialogue.txt       # 對話（可選）
    
    或使用語言子資料夾結構：
    
    story_folder/
        └── en/                # 英文版本
            ├── full_story.txt
            ├── narration.txt
            └── dialogue.txt
    
    參數:
        story_dir: 故事資料夾路徑
        aspects: 要評估的維度列表
        evaluator: 可選的評估器實例（用於批次處理時重用）
        config: 可選的配置實例
        
    返回:
        包含詳細評估結果的字典：
        - overall_score: 總分
        - dimension_scores: 各維度分數
        - key_issues: 問題數量
        - recommendations: 改進建議
        - processing_time: 處理時間
        - degradation_report: 降級報告（當某些檔案缺失時）
    """
    # 簡單流程：
    # 1) 取得或建立評估器 → 2) 自動找檔 → 3) 執行評估 → 4) 回傳精簡結果
    # 使用現有評估器或建立新的
    local_evaluator = evaluator
    if local_evaluator is None:
        local_config = config or EvaluatorConfig.from_env()
        local_evaluator = _create_evaluator(local_config)
    
    enabled_dimensions = normalise_dimensions(aspects)
    
    try:
        story_title = os.path.basename(story_dir)
        branch_sources = collect_branch_story_paths(story_dir, branch_mode=branch)
        if not branch_sources:
            raise ValueError(f"在目錄 {story_dir} 中未找到可評估文本（branch={branch}）")

        requested_mode = (branch or "canonical").strip()
        requested_mode_lower = requested_mode.lower()
        if requested_mode_lower == "auto":
            effective_mode = "all" if len(branch_sources) >= 2 else "canonical"
        else:
            effective_mode = requested_mode

        effective_mode_lower = effective_mode.lower()

        if effective_mode_lower in {"all", "*"}:
            branch_results: List[Dict[str, object]] = []
            for branch_id, source_path in branch_sources:
                report = local_evaluator.evaluate_story(
                    document_paths={"full_story.txt": str(source_path)},
                    story_title=story_title,
                    enabled_dimensions=enabled_dimensions,
                    branch_id=branch_id,
                    source_document=str(source_path),
                    evaluation_scope=effective_mode,
                )
                branch_results.append(
                    {
                        "branch_id": branch_id,
                        "overall_score": report.overall_score,
                        "dimension_scores": report.dimension_scores,
                        "dimension_summaries": getattr(report, "dimension_summaries", {}),
                        "key_issues": sum(r.issues_count for r in report.dimension_results),
                        "recommendations": report.recommendations,
                        "processing_time": report.processing_summary["total_processing_time"],
                        "degradation_report": report.degradation_report,
                        "source_document": str(source_path),
                    }
                )

            overall_values = [float(item.get("overall_score", 0.0)) for item in branch_results]
            overall_avg = round(sum(overall_values) / len(overall_values), 1) if overall_values else 0.0
            return {
                "overall_score": overall_avg,
                "evaluation_scope": effective_mode,
                "branch_results": branch_results,
                "branches_evaluated": [item["branch_id"] for item in branch_results],
            }

        selected_branch_id, selected_path = branch_sources[0]
        report = local_evaluator.evaluate_story(
            {"full_story.txt": str(selected_path)},
            story_title,
            enabled_dimensions,
            branch_id=selected_branch_id,
            source_document=str(selected_path),
            evaluation_scope=effective_mode,
        )

        return {
            "overall_score": report.overall_score,
            "dimension_scores": report.dimension_scores,
            "dimension_summaries": getattr(report, "dimension_summaries", {}),
            "key_issues": sum(r.issues_count for r in report.dimension_results),
            "recommendations": report.recommendations,
            "processing_time": report.processing_summary["total_processing_time"],
            "degradation_report": report.degradation_report,
            "branch_id": selected_branch_id,
            "source_document": str(selected_path),
            "evaluation_scope": effective_mode,
        }
    
    except Exception as e:
        return {"error": f"評估目錄 {story_dir} 失敗: {str(e)}"}


def batch_evaluate_stories(stories_dir: str = "output", 
                          aspects: List[str] = None,
                          branch: str = "auto") -> Dict:
    """
    批次評估多個故事
    
    掃描指定資料夾中的所有故事並逐一評估，適合用於：
    - 評估整個故事集合
    - 生成批次比較報告
    - 找出表現最好和最差的故事
    
    支援的輸入格式：
       output/
           ├── Story1/
           │   └── full_story.txt
           ├── Story2/
           │   └── full_story.txt
           └── Story3/
               └── full_story.txt
    
    參數:
        stories_dir: 包含多個故事的根目錄（預設: output）
        aspects: 要評估的維度列表
        
    返回:
        批次評估結果字典：
        - meta: 統計資訊（總數、成功數、失敗數、平均分）
        - results: 所有成功評估的故事結果列表
        - failed_stories: 失敗的故事列表（含錯誤訊息）
    
    範例:
        >>> result = batch_evaluate_stories("output")
        >>> print(f"平均分: {result['meta']['average_score']}")
        >>> print(f"成功: {result['meta']['successful']}/{result['meta']['total_stories']}")
    """
    # 檢查目錄是否存在
    if not os.path.exists(stories_dir):
        return {"error": f"目錄 {stories_dir} 不存在"}
    
    # 標準化要評估的維度
    target_dimensions = normalise_dimensions(aspects)
    config = EvaluatorConfig.from_env()
    
    results = []          # 成功評估的故事
    failed_stories = []   # 評估失敗的故事
    
    # 先處理故事資料夾
    for story_path in discover_story_dirs([stories_dir]):
        try:
            result = evaluate_story_directory(str(story_path), target_dimensions, config=config, branch=branch)
            if isinstance(result.get("branch_results"), list):
                for item in result["branch_results"]:
                    enriched = dict(item)
                    enriched['story_directory'] = story_path.name
                    results.append(enriched)
            else:
                result['story_directory'] = story_path.name
                results.append(result)
        except Exception as e:
            failed_stories.append({
                'story_directory': story_path.name,
                'error': str(e)
            })

    # 再處理根目錄下的單一文本檔案
    for item in sorted(os.listdir(stories_dir)):
        story_path = os.path.join(stories_dir, item)
        if not os.path.isfile(story_path) or not item.endswith('.txt'):
            continue
        try:
            with open(story_path, 'r', encoding='utf-8') as f:
                content = f.read()
            result = evaluate_all(content, item.replace('.txt', ''), target_dimensions)
            result['story_file'] = item
            results.append(result)
        except Exception as e:
            failed_stories.append({
                'story_file': item,
                'error': str(e)
            })
    
    # 計算統計資訊
    scores = [r['overall_score'] for r in results if r.get('overall_score') is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    
    return {
        'meta': {
            'total_stories': len(results) + len(failed_stories),
            'successful': len(results),
            'failed': len(failed_stories),
            'average_score': avg_score
        },
        'results': results,
        'failed_stories': failed_stories
    }


# =============================================================================
# 報告生成與視覺化函數
# =============================================================================

def _ordered_dimension_labels(dim_scores: Dict[str, float], preferred_order: Iterable[str]) -> List[str]:
    """
    根據偏好順序排列維度標籤
    
    將維度按照指定的順序排列，未指定的維度排在後面。
    這讓報告的呈現更有邏輯性和一致性。
    """
    preferred = [dim for dim in preferred_order if dim in dim_scores]
    remaining = [dim for dim in dim_scores.keys() if dim not in preferred]
    return preferred + remaining


def _sanitize_file_suffix(value: str) -> str:
    """將任意字串轉為安全檔名後綴。"""
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    token = token.strip("_")
    return token or "canonical"


def _print_dimension_table(console: Console, dim_scores: Dict[str, float], order: Iterable[str]) -> None:
    """
    在終端顯示維度分數表格
    
    使用 rich 函式庫創建美觀的表格，方便使用者快速查看各維度分數。
    """
    table = Table(title="維度分數")
    table.add_column("維度", justify="left")
    table.add_column("分數", justify="right")
    for dim in order:
        table.add_row(dim, f"{dim_scores[dim]:.1f}")
    console.print(table)


def _generate_radar_chart(
    story_dir: str,
    story_title: str,
    dim_scores: Dict[str, float],
    order: List[str],
    *,
    branch_id: str = "canonical",
) -> Optional[str]:
    """
    生成六維度雷達圖
    
    將評估結果視覺化為雷達圖（蜘蛛圖），直觀展示故事在各維度的表現。
    雷達圖讓使用者能夠一眼看出：
    - 哪些維度表現優秀（外圈）
    - 哪些維度需要改進（內圈）
    - 整體均衡性如何
    
    參數:
        story_dir: 故事資料夾路徑（用於儲存圖片）
        story_title: 故事標題
        dim_scores: 各維度分數字典
        order: 維度顯示順序
        
    返回:
        生成的雷達圖檔案路徑，失敗時返回 None
    """
    if not order:
        return None
    
    # 設定中文字型
    _configure_matplotlib_fonts()
    
    # 準備資料（將分數轉換為封閉的多邊形）
    values = [dim_scores[d] for d in order]
    num_vars = len(order)
    angles = [n / float(num_vars) * 2 * math.pi for n in range(num_vars)]
    angles += angles[:1]  # 封閉多邊形
    values += values[:1]  # 封閉多邊形

    # 建立極座標圖
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, values, linewidth=2, color="#1f77b4")
    ax.fill(angles, values, color="#1f77b4", alpha=0.25)
    ax.set_thetagrids([a * 180 / math.pi for a in angles[:-1]], order)
    ax.set_ylim(0, 100)  # Score range 0-100
    ax.set_title(f"{story_title} - Six-Dimensional Assessment", pad=20)
    ax.grid(True)

    # 儲存圖片
    branch_token = _sanitize_file_suffix(branch_id)
    radar_name = "assessment_radar.png" if branch_token == "canonical" else f"assessment_radar_{branch_token}.png"
    radar_path = os.path.join(story_dir, radar_name)
    plt.tight_layout()
    plt.savefig(radar_path, dpi=150)
    plt.close(fig)
    return radar_path


def _write_report(story_dir: str, report, adjusted_overall: float, *, branch_id: str = "canonical") -> str:
    """
    寫入 JSON 評估報告
    
    將完整的評估結果儲存為 JSON 檔案，包含：
    - 總分與各維度分數
    - 改進建議
    - 處理統計資訊
    - 降級報告（若有檔案缺失）
    - 對齊校準資訊（若有使用者評分）
    
    參數:
        story_dir: 故事資料夾路徑
        report: 評估報告物件
        adjusted_overall: 調整後的總分
        
    返回:
        報告檔案路徑
    """
    branch_token = _sanitize_file_suffix(branch_id)
    report_name = 'assessment_report.json' if branch_token == 'canonical' else f'assessment_report_{branch_token}.json'
    output_path = os.path.join(story_dir, report_name)
    payload = {
        'overall_score': adjusted_overall,  # 相容欄位，等於對齊/等化後
        'original_overall_score': report.overall_score,  # 保留相容欄位
        'overall_score_raw': getattr(report, 'overall_score_raw', adjusted_overall),
        'overall_score_calibrated': getattr(report, 'overall_score_calibrated', adjusted_overall),
        'dimension_scores': report.dimension_scores,
        'dimension_summaries': getattr(report, 'dimension_summaries', {}),
        'recommendations': report.recommendations,
        'processing_summary': report.processing_summary,
        'degradation_report': report.degradation_report,
        'governance': getattr(report, 'governance', None),
        'branch_id': getattr(report, 'branch_id', branch_id),
        'source_document': getattr(report, 'source_document', None),
        'story_metadata': getattr(report, 'story_metadata', None),
        'evaluation_scope': getattr(report, 'evaluation_scope', 'canonical'),
        'alignment': report.alignment_details or {
            'mode': 'model_only',
            'base_weighted_score': round(report.overall_score, 2),
            'final_score': round(report.overall_score, 2),
            'adjustments': None
        },
        'timestamp': report.timestamp
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_path


def _release_models(evaluator: MultiAspectEvaluator) -> None:
    """
    釋放評估器載入的所有 AI 模型
    
    評估完成後釋放記憶體中的大型模型，避免記憶體洩漏。
    這在批次處理大量故事時特別重要。
    """
    release_fn = getattr(evaluator, "_release_all_models", None)
    if callable(release_fn):
        try:
            release_fn()
            logger.info("✅ 已釋放所有模型資源")
        except Exception as exc:
            logger.warning("⚠️ 釋放模型時出錯: %s", exc)


# =============================================================================
# 命令列介面主程式
# =============================================================================

# =============================================================================
# 命令列介面主程式
# =============================================================================

if __name__ == "__main__":
    import argparse

    LANGUAGE_MARKERS = {
        'en', 'zh', 'zh-cn', 'zh-tw', 'zh-hant', 'zh-hans', 'ja', 'de', 'fr', 'es', 'it', 'ko', 'pt', 'ru', 'tr', 'ar', 'hi'
    }

    logging.basicConfig(
        level=getattr(logging, os.environ.get("EVAL_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(message)s"
    )

    def is_story_directory(path: str) -> bool:
        """
        判斷路徑是否為有效的故事資料夾
        
        必須包含 full_story.txt 檔案。
        支援兩種結構：
        1. 直接包含 full_story.txt
        2. 包含 en/full_story.txt（多語言支援）
        """
        if not os.path.isdir(path):
            return False

        candidates = [
            os.path.join(path, 'full_story.txt'),
            os.path.join(path, 'draft_story.txt'),
            os.path.join(path, 'en', 'full_story.txt'),
            os.path.join(path, 'en', 'draft_story.txt'),
        ]
        if any(os.path.exists(candidate) for candidate in candidates):
            return True

        branch_patterns = [
            os.path.join(path, 'branches', '*', 'full_story.txt'),
            os.path.join(path, 'branches', '*', 'draft_story.txt'),
            os.path.join(path, '*', 'branches', '*', 'full_story.txt'),
            os.path.join(path, '*', 'branches', '*', 'draft_story.txt'),
        ]
        if any(glob.glob(pattern) for pattern in branch_patterns):
            return True
        return False

    def find_story_directories(root: str) -> List[str]:
        """
        在根目錄中尋找所有故事資料夾
        
        掃描指定目錄的一層子資料夾，找出包含故事檔案的資料夾。
        
        參數:
            root: 根目錄路徑
            
        返回:
            故事資料夾路徑列表
        """
        if is_story_directory(root):
            return [root]

        def prune_nested_story_dirs(paths: List[str]) -> List[str]:
            """保留最上層故事根，排除被其包含的巢狀子目錄（如 option_1）。"""
            normalized = sorted(
                {os.path.abspath(p) for p in paths},
                key=lambda p: (Path(p).parts.__len__(), p.lower()),
            )
            kept: List[str] = []
            for candidate in normalized:
                nested = False
                for parent in kept:
                    try:
                        if os.path.commonpath([candidate, parent]) == parent:
                            nested = True
                            break
                    except ValueError:
                        continue
                if not nested:
                    kept.append(candidate)
            return kept
        story_dirs: List[str] = []
        for story_path in discover_story_dirs([root]):
            candidate = str(story_path)
            if is_story_directory(candidate):
                story_dirs.append(candidate)

        # 生成系統常見為多層階層（category/age/story）；若一層掃描沒找到，進行遞迴補掃。
        if not story_dirs:
            root_path = Path(root)
            discovered: set[str] = set()

            lang_markers = {'en', 'zh', 'ja', 'de', 'fr', 'es', 'it', 'ko', 'pt', 'ru'}

            for text_file in list(root_path.glob('**/full_story.txt')) + list(root_path.glob('**/draft_story.txt')):
                parent = text_file.parent
                if parent.name.lower() in lang_markers and parent.parent != parent:
                    discovered.add(str(parent.parent))
                else:
                    discovered.add(str(parent))

            for branch_file in list(root_path.glob('**/branches/*/full_story.txt')) + list(root_path.glob('**/branches/*/draft_story.txt')):
                try:
                    discovered.add(str(branch_file.parents[3]))
                except Exception:
                    continue

            for candidate in sorted(discovered):
                if is_story_directory(candidate):
                    story_dirs.append(candidate)
        return sorted(prune_nested_story_dirs(story_dirs))

    def discover_candidate_story_directories(root: str) -> List[str]:
        """收集潛在故事根目錄（含未完成故事），供前置輸出使用。"""
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            return []

        lang_markers = LANGUAGE_MARKERS
        candidates: set[str] = set()

        if is_story_directory(str(root_path)):
            candidates.add(os.path.abspath(str(root_path)))

        for option_dir in root_path.glob('**/branches/option_*'):
            try:
                parts_lower = [part.lower() for part in option_dir.parts]
                if 'tts' in parts_lower or 'tts_raw' in parts_lower:
                    continue

                branches_dir = option_dir.parent
                if branches_dir.name.lower() != 'branches':
                    continue
                base = branches_dir.parent
                if base.name.lower() in lang_markers and base.parent != base:
                    story_root = base.parent
                else:
                    story_root = base
                candidates.add(os.path.abspath(str(story_root)))
            except Exception:
                continue

        direct_text_files = list(root_path.glob('**/full_story.txt')) + list(root_path.glob('**/draft_story.txt'))
        for text_file in direct_text_files:
            text_path = str(text_file).lower()
            if '\\branches\\' in text_path or '\\tts\\' in text_path or '\\tts_raw\\' in text_path:
                continue
            parent = text_file.parent
            if parent.name.lower() in lang_markers and parent.parent != parent:
                story_root = parent.parent
            else:
                story_root = parent
            candidates.add(os.path.abspath(str(story_root)))

        if not candidates:
            for candidate in discover_story_dirs([str(root_path)]):
                candidates.add(os.path.abspath(str(candidate)))

        return sorted(candidates)

    def _normalise_story_language(value: str) -> str:
        token = (value or '').strip().lower()
        if token in {'zh', 'zh-cn', 'zh-tw', 'zh-hant', 'zh-hans'}:
            return 'zh'
        if token.startswith('en'):
            return 'en'
        if token == 'all':
            return 'all'
        return token

    def _detect_source_language(source_path: Path, story_root: str) -> str:
        root_path = Path(story_root)
        root_lang_token = _normalise_story_language(root_path.name)
        root_lang = root_lang_token if root_lang_token in {'en', 'zh'} else 'unknown'
        try:
            parts = [part.lower() for part in source_path.relative_to(root_path).parts]
        except Exception:
            parts = [part.lower() for part in source_path.parts]

        if 'branches' in parts:
            idx = parts.index('branches')
            if idx >= 1 and parts[idx - 1] in LANGUAGE_MARKERS:
                return _normalise_story_language(parts[idx - 1])

        if len(parts) >= 2 and parts[0] in LANGUAGE_MARKERS:
            return _normalise_story_language(parts[0])

        parent_name = source_path.parent.name.lower()
        if parent_name in LANGUAGE_MARKERS:
            return _normalise_story_language(parent_name)

        return root_lang

    def _filter_branch_sources_by_language(
        branch_sources: List[Tuple[str, Path]],
        story_root: str,
        requested_language: str,
    ) -> Tuple[List[Tuple[str, Path]], List[Tuple[str, Path, str]]]:
        target_language = _normalise_story_language(requested_language)
        if target_language == 'all':
            return branch_sources, []

        filtered: List[Tuple[str, Path]] = []
        skipped: List[Tuple[str, Path, str]] = []
        for branch_id, source_path in branch_sources:
            source_lang = _detect_source_language(source_path, story_root)
            # unknown 保留相容舊版單語料夾（無 en/zh 標記）。
            if source_lang in {target_language, 'unknown'}:
                filtered.append((branch_id, source_path))
            else:
                skipped.append((branch_id, source_path, source_lang))

        return filtered, skipped

    def _is_within_directory(path: str, root: str) -> bool:
        """檢查 path 是否位於 root 目錄內（含自身）。"""
        try:
            path_abs = os.path.abspath(path)
            root_abs = os.path.abspath(root)
            return os.path.commonpath([path_abs, root_abs]) == root_abs
        except ValueError:
            return False

    def _resolve_nonconflicting_destination(destination_base: str) -> str:
        """若目標資料夾已存在，附加流水號避免覆蓋既有成果。"""
        if not os.path.exists(destination_base):
            return destination_base
        suffix = 1
        while True:
            candidate = f"{destination_base}__dup{suffix}"
            if not os.path.exists(candidate):
                return candidate
            suffix += 1

    # 建立命令列參數解析器
    parser = argparse.ArgumentParser(
        description='多維度故事評估系統 - 自動掃描並評估故事品質',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
    %(prog)s                                    # 評估 output 資料夾中的所有故事
    %(prog)s --input output                     # 評估指定資料夾
    %(prog)s --input output/MyStory             # 評估單一故事
  %(prog)s --aspects coherence readability    # 只評估特定維度
    %(prog)s --story-language en                # 僅評估英文文本（預設）

支援的維度:
  - entity_consistency: 實體一致性（角色、地點命名的一致性）
  - completeness: 完整性（故事結構是否完整）
  - coherence: 連貫性（情節是否流暢合理）
  - readability: 可讀性（語言是否適合目標讀者）
  - factuality: 事實正確性（事實陳述是否準確）
  - emotional_impact: 情感影響力（情感表達的感染力）

環境變數配置:
    EVAL_PARALLEL_ENABLED=true        # 保留相容欄位（目前維度評估採順序執行）
    EVAL_MAX_PARALLEL_DIMENSIONS=3    # 保留相容欄位（目前不生效）
  EVAL_PRELOAD_MODELS=false         # 預載所有模型（預設關閉）
  EVAL_FAST_MODE=true               # 快速模式（犧牲準確性換取速度）
        """
    )
    parser.add_argument(
        '--input',
        type=str,
        default='output',
        help='故事根目錄或單一故事資料夾（預設: output）'
    )
    parser.add_argument(
        '--evaluated-dir',
        type=str,
        default='output/evaluated',
        help='已評估故事的輸出目錄（預設: output/evaluated）'
    )
    parser.add_argument(
        '--aspects',
        nargs='+',
        choices=DEFAULT_ASPECTS,
        default=list(DEFAULT_ASPECTS),
        help='要評估的維度（預設: 全部維度）'
    )
    parser.add_argument(
        '--post-process',
        choices=['none', 'copy', 'move'],
        default='none',
        help='評估後處理：none=不搬移, copy=複製到 output/evaluated, move=移動到 output/evaluated（預設: none）'
    )
    parser.add_argument(
        '--branch',
        type=str,
        default='auto',
        help='分支評估模式：auto（預設，多分支自動 all）、canonical、all（全部分支）或指定分支 ID（例如 option_2）',
    )
    parser.add_argument(
        '--story-language',
        choices=['en', 'all'],
        default='en',
        help='文本語言過濾（預設: en，只評估英文；all=不過濾）',
    )

    args = parser.parse_args()

    # 初始化評估器
    config = EvaluatorConfig.from_env()
    evaluator = _create_evaluator(config)
    _log_performance_config(config)
    target_dimensions = normalise_dimensions(args.aspects)

    # 尋找故事資料夾
    story_dirs = find_story_directories(args.input)
    if not story_dirs:
        logger.error("❌ 未找到故事資料夾：%s", args.input)
        logger.error("請確保資料夾中包含 full_story.txt 檔案")
        raise SystemExit(1)

    candidate_story_dirs = discover_candidate_story_directories(args.input)
    valid_story_dir_set = {os.path.abspath(path) for path in story_dirs}
    skipped_story_dirs = [
        path for path in candidate_story_dirs
        if os.path.abspath(path) not in valid_story_dir_set
    ]

    logger.info(
        "🧭 前置檢查：候選故事 %s，可評估 %s，跳過 %s",
        len(candidate_story_dirs),
        len(story_dirs),
        len(skipped_story_dirs),
    )
    if skipped_story_dirs:
        logger.info("⚠️ 跳過故事（缺少可評估文本 full_story/draft）：")
        preview = skipped_story_dirs[:20]
        for skipped in preview:
            logger.info("   - %s", skipped)
        remaining = len(skipped_story_dirs) - len(preview)
        if remaining > 0:
            logger.info("   - ... 其餘 %s 個", remaining)

    logger.info("✅ 找到 %s 個故事資料夾", len(story_dirs))
    logger.info("🌐 語言過濾: %s", args.story_language)

    # 建立美化的終端輸出
    console = Console()
    all_results = []
    skipped_by_language = 0
    evaluated_story_count = 0
    
    # 評估後搬移到 output/evaluated 資料夾的輔助函數
    def relocate_to_evaluated(source_dir: str, evaluated_root: str, mode: str) -> str:
        """將已評估故事安全地複製/移動到 output/evaluated，不覆蓋既有內容。"""
        import shutil
        source_abs = os.path.abspath(source_dir)
        evaluated_abs = os.path.abspath(evaluated_root)

        if mode == 'none':
            return source_abs
        if _is_within_directory(source_abs, evaluated_abs):
            return source_abs

        story_name = os.path.basename(source_abs)
        destination_base = os.path.join(evaluated_abs, story_name)
        dest_dir = _resolve_nonconflicting_destination(destination_base)

        os.makedirs(evaluated_abs, exist_ok=True)
        if mode == 'copy':
            shutil.copytree(source_abs, dest_dir)
        else:
            shutil.move(source_abs, dest_dir)
        return dest_dir
    
    # 逐一評估每個故事
    for story_dir in story_dirs:
        logger.info("")
        logger.info("%s", "=" * 60)
        logger.info("📖 評估故事：%s", os.path.basename(story_dir))
        logger.info("%s", "=" * 60)
        
        try:
            story_title = os.path.basename(story_dir)
            requested_branch_mode = (args.branch or 'canonical').strip()
            requested_branch_token = requested_branch_mode.lower()

            branch_sources = collect_branch_story_paths(story_dir, branch_mode=requested_branch_mode)
            if not branch_sources:
                raise ValueError(f"未找到可評估文本（branch={requested_branch_mode}）")

            branch_sources, skipped_sources = _filter_branch_sources_by_language(
                branch_sources,
                story_dir,
                args.story_language,
            )
            if skipped_sources:
                logger.info("   🌐 已略過非 %s 文本: %s", args.story_language, len(skipped_sources))
                for branch_id, source_path, source_lang in skipped_sources[:10]:
                    logger.info("      - 分支 %s [%s] %s", branch_id, source_lang, source_path)
                skipped_remaining = len(skipped_sources) - 10
                if skipped_remaining > 0:
                    logger.info("      - ... 其餘 %s 筆", skipped_remaining)

            if not branch_sources:
                skipped_by_language += 1
                logger.info("⏭️ 跳過故事（無符合語言 %s 的文本）: %s", args.story_language, story_title)
                continue

            effective_branch_mode = requested_branch_mode
            if requested_branch_token == 'auto':
                effective_branch_mode = 'all' if len(branch_sources) >= 2 else 'canonical'

            if requested_branch_token == 'auto':
                logger.info("🌿 分支模式: auto → %s，待評估分支數: %s", effective_branch_mode, len(branch_sources))
            else:
                logger.info("🌿 分支模式: %s，待評估分支數: %s", requested_branch_mode, len(branch_sources))

            branch_outputs: List[Dict[str, object]] = []
            for branch_id, source_path in branch_sources:
                logger.info("   ↳ 分支 %s 使用文本: %s", branch_id, source_path)
                try:
                    report = evaluator.evaluate_story(
                        {"full_story.txt": str(source_path)},
                        story_title,
                        target_dimensions,
                        branch_id=branch_id,
                        source_document=str(source_path),
                        evaluation_scope=effective_branch_mode,
                    )
                except Exception as branch_exc:
                    logger.exception("   ❌ 分支 %s 評估失敗: %s", branch_id, branch_exc)
                    continue

                adjusted_overall = round(float(report.overall_score), 1)
                output_path = _write_report(story_dir, report, adjusted_overall, branch_id=branch_id)

                logger.info("   ✅ 分支 %s 評估完成，總分: %.1f/100", branch_id, adjusted_overall)
                dim_scores = report.dimension_scores
                ordered_dims = _ordered_dimension_labels(dim_scores, target_dimensions)
                _print_dimension_table(console, dim_scores, ordered_dims)

                radar_path = None
                try:
                    radar_path = _generate_radar_chart(
                        story_dir,
                        story_title,
                        dim_scores,
                        ordered_dims,
                        branch_id=branch_id,
                    )
                except Exception as exc:
                    logger.warning("   ⚠️ 分支 %s 雷達圖生成失敗: %s", branch_id, exc)

                branch_outputs.append(
                    {
                        "branch_id": branch_id,
                        "overall_score": adjusted_overall,
                        "dimension_scores": dim_scores,
                        "output_path": output_path,
                        "radar_path": radar_path,
                    }
                )

            if not branch_outputs:
                raise RuntimeError("所有分支評估均失敗")

            evaluated_story_count += 1

            final_story_dir = os.path.abspath(story_dir)

            # 後處理：由使用者明確選擇 none/copy/move，避免隱式破壞性行為
            if args.post_process != 'none':
                try:
                    final_story_dir = relocate_to_evaluated(story_dir, args.evaluated_dir, args.post_process)
                    if os.path.abspath(final_story_dir) != os.path.abspath(story_dir):
                        action_label = '複製' if args.post_process == 'copy' else '移動'
                        logger.info("   📦 已%s至: %s", action_label, final_story_dir)
                except Exception as move_exc:
                    logger.warning("   ⚠️ 後處理失敗: %s", move_exc)

            moved = os.path.abspath(final_story_dir) != os.path.abspath(story_dir)
            for item in branch_outputs:
                final_output_path = str(item["output_path"])
                final_radar_path = item.get("radar_path")
                if moved:
                    final_output_path = os.path.join(final_story_dir, os.path.basename(final_output_path))
                    if isinstance(final_radar_path, str) and final_radar_path:
                        final_radar_path = os.path.join(final_story_dir, os.path.basename(final_radar_path))

                if final_radar_path:
                    logger.info("   📊 分支 %s 雷達圖: %s", item["branch_id"], final_radar_path)
                logger.info("   📄 分支 %s 報告: %s", item["branch_id"], final_output_path)

                all_results.append(
                    {
                        'story_directory': final_story_dir,
                        'branch_id': item['branch_id'],
                        'overall_score': float(item['overall_score']),
                        'dimension_scores': item['dimension_scores'],
                    }
                )
            
        except Exception as exc:
            logger.exception("❌ 評估失敗: %s", exc)

    # 顯示批次評估總結
    avg = sum(r['overall_score'] for r in all_results) / len(all_results) if all_results else 0.0
    failed_count = max(0, len(story_dirs) - evaluated_story_count - skipped_by_language)
    logger.info("")
    logger.info("%s", "=" * 60)
    logger.info("✅ 完成 %s 個故事評估", evaluated_story_count)
    if skipped_by_language:
        logger.info("⏭️ 因語言過濾跳過: %s", skipped_by_language)
    if failed_count:
        logger.info("⚠️ 失敗故事數: %s", failed_count)
    logger.info("📊 平均分數: %.1f/100", avg)
    logger.info("%s", "=" * 60)

    # 釋放模型資源
    _release_models(evaluator)