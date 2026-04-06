"""多維度故事評估系統主控器。

本模組負責協調整個六維度評估流程，包含：

1. 文檔來源管理：偵測故事資料夾、載入內容、處理缺失情況
2. 模型生命週期：建立各維度檢測器、支援共享與快取
3. 評估排程：決定最佳維度執行順序與是否並行處理
4. 結果整合：組合分數、建議、降級報告，並支援對齊校準

六大評估維度如下：
- entity_consistency      實體一致性
- completeness            故事完整性
- coherence               故事情節連貫性
- readability             兒童可讀性
- factuality              事實正確性
- emotional_impact        情感影響力

所有主要類別與函式皆附有繁體中文的說明，協助開發者快速理解模組設計。"""

# 標準庫導入
import logging
import os
import json
import gc
import math
import re
import string
from datetime import datetime
import yaml
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from collections import Counter
from dataclasses import dataclass
from .completeness import CompletenessChecker
from .coherence import CoherenceChecker  
from .readability import ReadabilityChecker
from .factual import FactualityChecker
from .emotion import EmotionalImpactChecker
from .consistency import AdvancedStoryChecker  # 實體一致性
from .genre import GenreDetector
from .shared.score_governance import build_score_governance
from .shared.score_policy import apply_cross_dimension_constraints, compute_consensus_adjustment
from .shared.story_data import collect_branch_story_paths, collect_full_story_paths, find_metadata_for_story
from .shared.ai_safety import (
    build_dimension_fallback_payload,
    get_dimension_fallback_score,
    normalize_confidence_0_1,
    normalize_score_0_100,
)
from .utils import (
    get_default_model_path,
    load_spacy_model,
    get_kg_path,
    get_semantic_model_candidates,
    resolve_model_path,
)
import numpy as np  # 用於特徵處理
logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available, will fall back to simple aggregation")

# 校準開關：設定 DISABLE_CALIBRATION=true 可完全跳過 XGBoost / 人類對齊校準
CALIBRATION_DISABLED = os.environ.get('DISABLE_CALIBRATION', 'false').lower() in ('true', '1', 'yes')
if CALIBRATION_DISABLED:
    logger.info("校準已停用 (DISABLE_CALIBRATION=true)，將使用純先驗權重加總")

# 常數定義
DEFAULT_KG_PATH = get_kg_path()
DEFAULT_MODEL_PATH = get_default_model_path("Qwen2.5-14B")
DEFAULT_CONFIG_PATH = "aspects_sources.yaml"
DEFAULT_TARGET_AGE_GROUP = "children_7_8"
DEFAULT_SEMANTIC_MODEL_PATH = get_semantic_model_candidates()[0]

# 簡易情緒詞典（避免依賴額外套件）
_POSITIVE_LEXICON = {
    "delight",
    "joy",
    "happy",
    "kind",
    "brave",
    "love",
    "bright",
    "cheerful",
    "grace",
    "hope",
}
_NEGATIVE_LEXICON = {
    "sad",
    "anger",
    "dark",
    "fear",
    "lonely",
    "cruel",
    "cry",
    "danger",
    "terrible",
    "gloom",
}

# 簡化停用詞列表，專注英文童話常見功能詞
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "had", "has", "have", "he", "her", "his", "in", "is", "it", "its",
    "of", "on", "or", "she", "that", "the", "their", "them", "there",
    "they", "this", "to", "was", "were", "with", "would", "you", "your"
}

# 標準文檔類型僅保留全文來源（其他格式已不再使用）
STANDARD_DOCUMENT_TYPES = {
    'full_story.txt': 'full_story.txt'
}

@dataclass
class DocumentSource:
    """描述單一文檔來源及其內容資訊。

    屬性說明：
        doc_type:   文檔類型標籤（例如 'full_story.txt'）
        file_path:  原始檔案路徑或記憶體來源描述
        weight:     在該維度評估中的權重
        available:  檔案是否可用（存在且有內容）
        content:    預先載入的文字內容（若已讀取）
        error:      若載入失敗，記錄錯誤訊息以供診斷
    """
    doc_type: str
    file_path: Union[str, List[str]]
    weight: float
    available: bool
    content: Optional[str] = None
    error: Optional[str] = None


class DocumentSourceManager:
    """故事文檔來源管理器（精簡版）。

    整個系統現僅依賴 `full_story.txt` 作為輸入來源，因此此管理器僅負責：
      1. 快取全文內容（支援檔案路徑與 memory:// 文字）
      2. 提供統一的來源查詢介面
      3. 在缺少全文時回傳空集合，讓上層自行處理失敗狀態
    """

    def __init__(self, config_path: str = "aspects_sources.yaml"):
        self.config_path = config_path  # 保留欄位供外部追蹤，但不再讀取配置
        self.registered_documents: Dict[str, Union[str, List[str]]] = {}
        self.document_cache: Dict[str, DocumentSource] = {}

    def register_documents(self, document_paths: Dict[str, Union[str, List[str]]]) -> None:
        """註冊故事文檔。目前僅保留 full_story.txt。"""
        self.registered_documents = {}
        self.document_cache.clear()

        full_story = document_paths.get('full_story.txt')
        if full_story is not None:
            self.registered_documents['full_story.txt'] = full_story
            self._load_document('full_story.txt', full_story)

    def _load_document(self, doc_type: str, file_path: Union[str, List[str], Dict[str, str]]) -> DocumentSource:
        if doc_type in self.document_cache:
            return self.document_cache[doc_type]

        doc_source = DocumentSource(
            doc_type=doc_type,
            file_path=file_path,
            weight=1.0,
            available=False
        )

        try:
            if isinstance(file_path, dict):
                content = file_path.get('content') or file_path.get('text')
                if content is not None:
                    text = str(content).strip()
                    if text:
                        doc_source.content = text
                        doc_source.available = True
                    else:
                        doc_source.error = "文檔為空"
                    self.document_cache[doc_type] = doc_source
                    return doc_source
                if 'path' in file_path:
                    file_path = file_path['path']
                    doc_source.file_path = file_path

            if isinstance(file_path, str) and file_path.startswith("memory://"):
                content = file_path.replace("memory://", "")
                if content and content != doc_type:
                    doc_source.content = content
                    doc_source.available = True
                else:
                    doc_source.error = "記憶體文檔缺少實際內容"
            elif isinstance(file_path, list):
                merged: List[str] = []
                available_files: List[str] = []
                for path in file_path:
                    if os.path.exists(path):
                        try:
                            with open(path, 'r', encoding='utf-8') as handle:
                                text = handle.read().strip()
                                if text:
                                    merged.append(text)
                                    available_files.append(path)
                        except Exception:
                            continue
                if merged:
                    doc_source.content = "\n\n".join(merged)
                    doc_source.available = True
                    doc_source.file_path = available_files
                else:
                    doc_source.error = "沒有可用的文件"
            elif isinstance(file_path, str) and os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as handle:
                    text = handle.read().strip()
                    if text:
                        doc_source.content = text
                        doc_source.available = True
                    else:
                        doc_source.error = "文檔為空"
            else:
                doc_source.error = "文檔不存在"
        except Exception as exc:
            doc_source.error = f"讀取失敗: {exc}"

        self.document_cache[doc_type] = doc_source
        return doc_source

    def get_aspect_sources(self, dimension: str) -> Dict[str, float]:
        """始終回傳 full_story.txt，若不可用則回傳空集合。"""
        doc_source = self.document_cache.get('full_story.txt')
        if doc_source and doc_source.available:
            return {'full_story.txt': 1.0}
        return {}

    def get_document_content(self, doc_type: str) -> Optional[str]:
        doc_source = self.document_cache.get(doc_type)
        if doc_source and doc_source.available:
            return doc_source.content
        return None

    def get_documents_by_types(self, doc_types: Iterable[str]) -> Dict[str, str]:
        documents: Dict[str, str] = {}
        for doc_type in doc_types:
            content = self.get_document_content(doc_type)
            if content:
                documents[doc_type] = content
        return documents

    def is_dimension_viable(self, dimension: str, min_total_weight: float = 0.3) -> bool:
        return bool(self.document_cache.get('full_story.txt') and self.document_cache['full_story.txt'].available)

    def get_degradation_report(self) -> Dict[str, Dict]:
        report: Dict[str, Dict[str, Any]] = {}
        full_story = self.document_cache.get('full_story.txt')
        if full_story is None:
            report['full_story.txt'] = {
                'status': 'missing',
                'reason': 'not_registered',
            }
            return report

        if not full_story.available:
            report['full_story.txt'] = {
                'status': 'missing',
                'reason': full_story.error or 'unavailable',
                'path': full_story.file_path,
            }
        return report

@dataclass
class DimensionResult:
    """單個維度的評估結果"""
    dimension: str
    score: float
    detailed_results: Dict
    issues_count: int
    suggestions: List[str]
    processing_time: float
    status: str  # 'success', 'degraded', 'failed', 'skipped'
    degradation_info: Optional[str] = None
    normalized_summary: Optional[Dict[str, Any]] = None

@dataclass
class MultiAspectReport:
    """多維度評估總報告"""
    story_title: str
    # 對齊後（若啟用）之最終分數；為相容性，overall_score 等於 calibrated 分數
    overall_score: float
    # 新增：未對齊的原始加權總分（只做六維度聚合、未做人類等化/對齊）
    overall_score_raw: float
    # 新增：對齊/等化後總分（若無可用快照對齊模型，則等於 base）
    overall_score_calibrated: float
    dimension_scores: Dict[str, float]
    dimension_results: List[DimensionResult]
    processing_summary: Dict
    degradation_report: Dict
    recommendations: List[str]
    timestamp: str
    branch_id: str = "canonical"
    source_document: Optional[str] = None
    story_metadata: Optional[Dict[str, Any]] = None
    evaluation_scope: str = "canonical"
    alignment_details: Optional[Dict[str, Union[float, str, Dict[str, float], None]]] = None
    governance: Optional[Dict[str, Any]] = None
    dimension_summaries: Optional[Dict[str, Dict[str, Any]]] = None

class MultiAspectEvaluator:
    """六維度故事評估總控中心。

    本類別封裝故事評估的整體工作流程，負責：
        • 準備文檔來源並判斷可用性
        • 延遲載入各維度檢測器並共享模型資源
        • 控制評估順序與並行策略
        • 蒐集並整合各維度的評估結果
        • 產生降級報告與人類評分對齊資訊
    """

    def __init__(self, 
                 kg_path: str = DEFAULT_KG_PATH,
                 model_path: str = DEFAULT_MODEL_PATH,
                 config_path: str = DEFAULT_CONFIG_PATH,
                 use_multiple_ai_prompts: bool = False,
                 enable_web_search: bool = False,
                 target_age_group: str = DEFAULT_TARGET_AGE_GROUP,
                 # 新增性能優化選項
                 enable_parallel_processing: bool = True,
                 max_parallel_dimensions: int = 3,
                 enable_model_caching: bool = True,
                 preload_all_models: bool = False,
                 batch_size_optimization: bool = True):
        """建立評估器並初始化必要的管理器與配置。"""

        # 啟動文檔來源管理器（處理多文檔權重分配）
        self.source_manager = DocumentSourceManager(config_path)
        
        # 儲存基礎配置參數
        self.kg_path = kg_path
        self.model_path = model_path
        self.use_multiple_ai_prompts = use_multiple_ai_prompts
        self.enable_web_search = enable_web_search
        self.target_age_group = target_age_group
        
        # 性能優化配置
        self.enable_parallel_processing = enable_parallel_processing
        self.max_parallel_dimensions = max_parallel_dimensions
        self.enable_model_caching = enable_model_caching
        self.preload_all_models = preload_all_models
        self.batch_size_optimization = batch_size_optimization
        
        # 延遲載入策略（按需初始化各維度檢測器）
        self.checkers = {} # 已載入的檢測器快取
        self.loaded_models = {} # 已載入的模型元件追蹤
        
        # 並行處理已移除（改為順序執行）
        self.executor = None
        self.model_lock = None
        
        # 各維度模型需求對照表（用於智能共享模型元件）
        # 按模型需求數量排序：3個模型 → 4個模型
        self.dimension_model_requirements = {
            # 3個模型的維度（較輕量）
            'coherence': {'ai_model', 'spacy_model', 'kg'},           # 3個模型
            'readability': {'ai_model', 'spacy_model', 'kg'},         # 3個模型  
            'factuality': {'ai_model', 'spacy_model', 'kg'},          # 3個模型
            'emotional_impact': {'ai_model', 'spacy_model', 'kg', 'goemotion_model'},  # 4個模型 (GoEmotions)
            
            # 4個模型的維度（較重量，現在使用 GLiNER）
            'completeness': {'ai_model', 'gliner_model', 'semantic_model', 'kg'},      # 4個模型
            'entity_consistency': {'ai_model', 'gliner_model', 'semantic_model', 'kg'}, # 4個模型
        }
        
        # 計算最佳處理順序（減少重複載入模型）
        # 維度依賴關係
        self.dimension_dependencies = {
            'coherence': ['entity_consistency'],  # 連貫性依賴實體一致性
        }

        self.optimal_dimension_order = self._calculate_optimal_processing_order()
        
        # 保留結構但不再使用維度權重（總分改為簡單平均）
        self.dimension_weights = {}
        
        self.processing_stats = {
            'total_evaluations': 0,
            'successful_evaluations': 0,
            'degraded_evaluations': 0,
            'failed_evaluations': 0
        }

        # 人類評分對齊模型與上下文（延遲載入）
        self.calibration_model: Optional[Dict[str, Union[float, Dict[str, float]]]] = None
        self.current_story_metadata: Optional[Dict] = None
        self.alignment_info: Optional[Dict] = None
        self.current_story_text_features: Optional[Dict[str, float]] = None
        # 評分聚合權重與文體偵測（僅用全文）
        self.rating_weight_config: Optional[Dict[str, Any]] = None
        self.genre_detector: Optional[GenreDetector] = GenreDetector()
        self.detected_genre_info: Optional[Dict[str, Any]] = None
        # Longformer 文本嵌入資源（延遲載入）
        self.longformer_tokenizer = None
        self.longformer_model = None
        self.longformer_device = "cpu"
        self._longformer_unavailable = False
    
    def _calculate_optimal_processing_order(self) -> List[str]:
        """計算維度執行順序以降低模型載入成本。

        演算法步驟：
            1. 先依「每個維度所需模型數量」由少到多排序。
            2. 在同組內，優先選擇能與既有載入模型重疊最多的維度。
            3. 逐步更新「已載入模型集合」，確保後續決策能最大化重用率。

        回傳值:
            維度名稱列表，代表建議的執行順序。
        """
        dimensions = list(self.dimension_model_requirements.keys())
        
        if not dimensions:
            return []
        
        # 按模型需求數量排序（從少到多），然後考慮模型重用
        dimension_model_counts = [
            (dim, len(self.dimension_model_requirements[dim]))
            for dim in dimensions
        ]
        
        # 先按模型需求數量排序
        dimension_model_counts.sort(key=lambda x: x[1])
        
        # 進一步優化：在相同模型需求數量的維度中，優先選擇能重用更多已載入模型的
        ordered_dimensions = []
        current_loaded_models = set()
        
        # 按模型需求數量分組
        groups_by_model_count = {}
        for dim, count in dimension_model_counts:
            if count not in groups_by_model_count:
                groups_by_model_count[count] = []
            groups_by_model_count[count].append(dim)
        
        # 按模型需求數量從少到多處理每個組
        for model_count in sorted(groups_by_model_count.keys()):
            group = groups_by_model_count[model_count]
            
            # 在同一組內，按模型重用程度排序
            while group:
                if not current_loaded_models:
                    # 如果還沒有載入任何模型，選擇第一個
                    next_dim = group.pop(0)
                else:
                    # 選擇與已載入模型重疊最多的維度
                    best_dim = max(group, 
                                 key=lambda d: len(self.dimension_model_requirements[d] & current_loaded_models))
                    group.remove(best_dim)
                    next_dim = best_dim
                
                ordered_dimensions.append(next_dim)
                current_loaded_models.update(self.dimension_model_requirements[next_dim])
        
        return self._apply_dependency_order(ordered_dimensions)

    def _apply_dependency_order(self, preferred_order: List[str]) -> List[str]:
        """在既有偏好順序上，套用維度依賴約束。"""
        unique_order: List[str] = []
        for dimension in preferred_order:
            if dimension not in unique_order:
                unique_order.append(dimension)

        if not unique_order:
            return []

        order_index = {dimension: idx for idx, dimension in enumerate(unique_order)}
        dependencies: Dict[str, List[str]] = {
            dimension: [
                dep for dep in self.dimension_dependencies.get(dimension, [])
                if dep in order_index
            ]
            for dimension in unique_order
        }

        in_degree: Dict[str, int] = {
            dimension: len(dependencies.get(dimension, []))
            for dimension in unique_order
        }
        dependents: Dict[str, List[str]] = {dimension: [] for dimension in unique_order}
        for dimension, deps in dependencies.items():
            for dep in deps:
                dependents.setdefault(dep, []).append(dimension)

        ready: List[str] = sorted(
            [dimension for dimension, degree in in_degree.items() if degree == 0],
            key=lambda item: order_index[item],
        )
        ordered: List[str] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for dependent in dependents.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
            ready.sort(key=lambda item: order_index[item])

        if len(ordered) != len(unique_order):
            remaining = [item for item in unique_order if item not in ordered]
            remaining.sort(key=lambda item: order_index[item])
            ordered.extend(remaining)

        return ordered
    
    def _load_dimension_checker(self, dimension: str):
        """建立或取回指定維度的檢測器實例。

        邏輯流程：
            1. 若檢測器已在快取中，直接返回。
            2. 根據維度需求判斷需額外載入的模型組件。
            3. 初始化對應維度的檢測器並注入共享模型。
            4. 將實例存入快取以便後續重用。

        參數:
            dimension: 維度識別字串。

        例外:
            ValueError: 當傳入未知維度時拋出。
        """
        if dimension in self.checkers:
            return self.checkers[dimension]
        
        logger.info("📋 載入檢測器: %s", dimension)
        
        # 檢查需要的模型
        required_models = self.dimension_model_requirements.get(dimension, set())
        
        # 檢查哪些模型已經載入，哪些需要新載入
        need_to_load = required_models - set(self.loaded_models.keys())
        
        if need_to_load:
            # 載入需要的模型組件
            self._ensure_models_loaded(need_to_load)
        
        # 創建檢測器
        if dimension == 'completeness':
            checker = CompletenessChecker(self.kg_path, self.model_path, self.use_multiple_ai_prompts,
                                         ai=self.loaded_models.get('ai_model'),
                                         kg=self.loaded_models.get('kg'),
                                         nlp=self.loaded_models.get('spacy_model'),
                                         semantic_model=self.loaded_models.get('semantic_model'),
                                         eager_load_semantic=False)
        elif dimension == 'coherence':
            checker = CoherenceChecker(self.kg_path, self.model_path, self.use_multiple_ai_prompts,
                                       ai=self.loaded_models.get('ai_model'),
                                       kg=self.loaded_models.get('kg'),
                                       nlp=self.loaded_models.get('spacy_model'),
                                       semantic_model=self.loaded_models.get('semantic_model'),
                                       eager_load_semantic=False)
        elif dimension == 'readability':
            checker = ReadabilityChecker(self.kg_path, self.model_path, self.target_age_group, self.use_multiple_ai_prompts,
                                         ai=self.loaded_models.get('ai_model'),
                                         kg=self.loaded_models.get('kg'),
                                         nlp=self.loaded_models.get('spacy_model'))
        elif dimension == 'entity_consistency':
            checker = AdvancedStoryChecker(
                self.kg_path,
                self.model_path,
                self.use_multiple_ai_prompts,
                preloaded_ai=self.loaded_models.get('ai_model'),
                preloaded_kg=self.loaded_models.get('kg'),
                preloaded_spacy=self.loaded_models.get('spacy_model'),
                preloaded_semantic=self.loaded_models.get('semantic_model'),
                preloaded_gliner=self.loaded_models.get('gliner_model')
            )
        elif dimension == 'factuality':
            checker = FactualityChecker(self.kg_path, self.model_path, self.use_multiple_ai_prompts, self.enable_web_search,
                                        ai=self.loaded_models.get('ai_model'),
                                        kg=self.loaded_models.get('kg'),
                                        nlp=self.loaded_models.get('spacy_model'))
        elif dimension == 'emotional_impact':
            checker = EmotionalImpactChecker(self.kg_path, self.model_path, self.use_multiple_ai_prompts,
                                           ai=self.loaded_models.get('ai_model'),
                                           kg=self.loaded_models.get('kg'),
                                           nlp=self.loaded_models.get('spacy_model'),
                                           goemotion_model=self.loaded_models.get('goemotion_model'))
        else:
            raise ValueError(f"未知維度: {dimension}")
        
        # 共享已載入的模型組件
        if 'ai_model' in self.loaded_models and hasattr(checker, 'ai'):
            checker.ai = self.loaded_models['ai_model']
        if 'kg' in self.loaded_models and hasattr(checker, 'kg'):
            checker.kg = self.loaded_models['kg']
            # 注入 GLiNER 到 KG
            if 'gliner_model' in self.loaded_models:
                checker.kg.gliner = self.loaded_models['gliner_model']
        if 'spacy_model' in self.loaded_models and hasattr(checker, 'nlp'):
            checker.nlp = self.loaded_models['spacy_model']
        if 'gliner_model' in self.loaded_models:
            # 注入 GLiNER 到 checker
            if hasattr(checker, 'gliner'):
                checker.gliner = self.loaded_models['gliner_model']
            # 注入 GLiNER 到 entity_checker（針對 AdvancedStoryChecker）
            if hasattr(checker, 'entity_checker') and hasattr(checker.entity_checker, 'gliner'):
                checker.entity_checker.gliner = self.loaded_models['gliner_model']
        if 'semantic_model' in self.loaded_models and hasattr(checker, 'semantic_model'):
            semantic_model_data = self.loaded_models['semantic_model']
            if semantic_model_data and isinstance(semantic_model_data, dict):
                # 為 consistency checker 創建合適的語義模型對象
                if hasattr(checker, '_create_simple_encoder'):
                    try:
                        checker.semantic_model = checker._create_simple_encoder(
                            semantic_model_data['model'], 
                            semantic_model_data['tokenizer']
                        )
                    except Exception as e:
                        logger.warning("    ⚠️ 語義模型共享失敗: %s", e)
                        checker.semantic_model = None
                else:
                    checker.semantic_model = semantic_model_data
        
        self.checkers[dimension] = checker
        return checker
    
    def _ensure_models_loaded(self, required_models: set):
        """逐一確認並載入評估所需的模型組件。"""
        for model_type in required_models:
            if model_type not in self.loaded_models:
                self._load_model_component(model_type)
    
    def _load_model_component(self, model_type: str):
        """載入單一模型組件並快取，以供各維度共享。"""
        if model_type in self.loaded_models:
            return
        
        logger.info("  📦 載入模型組件: %s", model_type)
        
        if model_type == 'ai_model':
            from .consistency import AIAnalyzer
            self.loaded_models['ai_model'] = AIAnalyzer(self.model_path, self.use_multiple_ai_prompts)
            
        elif model_type == 'kg':
            from .consistency import ComprehensiveKnowledgeGraph
            self.loaded_models['kg'] = ComprehensiveKnowledgeGraph(self.kg_path)
            
        elif model_type == 'spacy_model':
            try:
                nlp = load_spacy_model()
                loaded_name = getattr(nlp, '_loaded_model_name', nlp.meta.get('name', 'unknown'))
                gpu_enabled = bool(getattr(nlp, '_gpu_enabled', False))
                self.loaded_models['spacy_model'] = nlp
                logger.info("    ✅ 載入 spaCy: %s (gpu=%s)", loaded_name, gpu_enabled)
            except Exception as e:
                import spacy
                logger.warning("    ⚠️ spaCy 載入失敗: %s，退回 blank(en)", e)
                self.loaded_models['spacy_model'] = spacy.blank("en")
        
        elif model_type == 'gliner_model':
            try:
                from gliner import GLiNER
                gliner_path = resolve_model_path("gliner_large-v2.1")
                gliner_local_path = os.path.abspath(str(gliner_path))
                if not os.path.isdir(gliner_local_path):
                    raise FileNotFoundError(f"GLiNER model directory not found: {gliner_local_path}")

                # GLiNER checkpoints use gliner_config.json; create a compatibility config.json
                # to suppress HubMixin warnings on local directory loading.
                gliner_config_path = os.path.join(gliner_local_path, "gliner_config.json")
                hf_config_path = os.path.join(gliner_local_path, "config.json")
                if os.path.isfile(gliner_config_path) and not os.path.isfile(hf_config_path):
                    try:
                        with open(gliner_config_path, 'r', encoding='utf-8') as src:
                            gliner_config_payload = json.load(src)
                        with open(hf_config_path, 'w', encoding='utf-8') as dst:
                            json.dump(gliner_config_payload, dst, ensure_ascii=False, indent=2)
                        logger.info("    ℹ️ 建立 GLiNER 相容設定檔: %s", hf_config_path)
                    except Exception as cfg_exc:
                        logger.warning("    ⚠️ 無法建立 GLiNER config.json 相容檔: %s", cfg_exc)

                # Work around protobuf/sentencepiece incompatibility seen on some Windows envs.
                os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

                gliner = GLiNER.from_pretrained(gliner_local_path, local_files_only=True)
                
                # 優先使用 GPU
                import torch
                if torch.cuda.is_available():
                    gliner = gliner.to('cuda')
                    logger.info("    ✅ 載入 GLiNER 到 GPU: %s", gliner_local_path)
                else:
                    logger.info("    ✅ 載入 GLiNER 到 CPU: %s", gliner_local_path)
                
                self.loaded_models['gliner_model'] = gliner
            except Exception as e:
                logger.warning("    ⚠️ GLiNER 載入失敗: %s，退回使用 SpaCy", e)
                # Keep gliner_model type-safe; spaCy should stay in spacy_model slot only.
                self.loaded_models['gliner_model'] = None
                
        elif model_type == 'goemotion_model':
            try:
                from .emotion import GoEmotionsAnalyzer
                analyzer = GoEmotionsAnalyzer()
                analyzer._load_model()
                self.loaded_models['goemotion_model'] = analyzer
                logger.info("    ✅ 載入 GoEmotions 模型")
            except Exception as e:
                logger.warning("    ⚠️ GoEmotions 模型載入失敗: %s，退回關鍵詞模式", e)
                self.loaded_models['goemotion_model'] = None

        elif model_type == 'semantic_model':
            try:
                from transformers import AutoTokenizer, AutoModel
                # 使用統一候選路徑（可透過環境變數覆寫）
                model_paths = get_semantic_model_candidates()
                
                loaded = False
                for model_path in model_paths:
                    try:
                        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                        model = AutoModel.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                        
                        self.loaded_models['semantic_model'] = {
                            "tokenizer": tokenizer,
                            "model": model,
                            "model_name": model_path.split("/")[-1]
                        }
                        logger.info("    ✅ 載入語義模型: %s", model_path.split('/')[-1])
                        loaded = True
                        break
                    except Exception:
                        continue
                
                if not loaded:
                    raise Exception("所有語義模型載入失敗")
                    
            except Exception as e:
                logger.warning("    ⚠️ 語義模型載入失敗: %s", e)
                self.loaded_models['semantic_model'] = None

    def _release_unused_models(self, current_dimension: str, next_dimensions: List[str]):
        """根據後續需求釋放多餘的模型資源。

        此函數會分析目前維度與剩餘待執行維度所需的模型集合，
        僅釋放在未來不再使用、且非高頻模型的資源，避免頻繁載入。"""
        if not next_dimensions:
            return
        
        current_models = self.dimension_model_requirements.get(current_dimension, set())
        future_needed_models = set()
        
        # 收集後續維度需要的模型
        for dim in next_dimensions:
            future_needed_models.update(self.dimension_model_requirements.get(dim, set()))
        
        # 找出可以釋放的模型
        models_to_release = current_models - future_needed_models
        
        # 保留常用模型以避免重複載入（按使用頻率排序）
        common_models = {'ai_model', 'spacy_model', 'kg'}  # 最常用的模型
        models_to_release = models_to_release - common_models
        
        if models_to_release:
            for model_type in models_to_release:
                if model_type in self.loaded_models:
                    self._release_model_component(model_type)

    def _release_model_component(self, model_type: str):
        """釋放單一模型組件並回收記憶體資源。"""
        if model_type not in self.loaded_models:
            return
        
        try:
            if model_type == 'ai_model':
                ai_model = self.loaded_models['ai_model']
                try:
                    if ai_model and hasattr(ai_model, 'release'):
                        ai_model.release()
                except Exception:
                    pass  # 靜默處理釋放錯誤
                del self.loaded_models['ai_model']
                
            elif model_type == 'semantic_model':
                semantic_model = self.loaded_models['semantic_model']
                if semantic_model and isinstance(semantic_model, dict):
                    try:
                        if 'model' in semantic_model:
                            if hasattr(semantic_model['model'], 'to'):
                                semantic_model['model'].to('cpu')
                            del semantic_model['model']
                        if 'tokenizer' in semantic_model:
                            del semantic_model['tokenizer']
                    except Exception:
                        pass
                del self.loaded_models['semantic_model']

            elif model_type == 'goemotion_model':
                goemotion = self.loaded_models['goemotion_model']       
                if goemotion and hasattr(goemotion, 'release'):
                    try:
                        goemotion.release()
                    except Exception:
                        pass
                elif goemotion and hasattr(goemotion, 'to'):
                    try:
                        goemotion.to('cpu')
                    except Exception:
                        pass
                del self.loaded_models['goemotion_model']

            else:
                # 其他模型組件的簡單釋放
                component = self.loaded_models[model_type]
                if hasattr(component, 'to'):
                    try:
                        component.to('cpu')
                    except Exception:
                        pass
            # 清理GPU記憶體
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
                    
        except Exception as e:
            # 靜默處理釋放錯誤，避免干擾主流程
            pass
    
    def auto_detect_story_documents(
        self,
        story_dir: str,
        *,
        branch_mode: str = "canonical",
    ) -> Dict[str, Union[str, List[str]]]:
        """掃描故事資料夾並建立標準文檔映射。

        搜尋順序：
            1. 優先檢查是否存在 `en/` 子資料夾，以支援多語故事結構。
            2. 在基底資料夾中尋找預定義檔名（title/outline/full_story/narration/dialogue）。
            3. 若未找到核心檔案，退回選擇第一個 `.txt` 作為全文來源。

        回傳值:
            doc_type -> 路徑 的字典，用於後續來源管理器註冊。
        """
        document_paths = {}

        branch_sources = collect_branch_story_paths(story_dir, branch_mode=branch_mode)
        if branch_sources:
            document_paths['full_story.txt'] = str(branch_sources[0][1])
            return document_paths

        full_story_candidates = collect_full_story_paths(story_dir)
        if full_story_candidates:
            document_paths['full_story.txt'] = str(full_story_candidates[0])
            return document_paths

        # 最後回退：沿用原行為，取基底資料夾第一個 .txt
        en_dir = os.path.join(story_dir, "en")
        base_dir = en_dir if os.path.exists(en_dir) else story_dir
        if os.path.isdir(base_dir):
            for item in sorted(os.listdir(base_dir)):
                if item.endswith('.txt'):
                    document_paths['full_story.txt'] = os.path.join(base_dir, item)
                    break
        
        return document_paths
    
    def _load_story_metadata(
        self,
        document_paths: Dict[str, Union[str, List[str]]],
        story_title: str
    ) -> Dict[str, Union[str, float, int]]:
        """尋找並載入故事的 metadata.json 檔。

        搜尋策略：
            • 先檢查現有文檔所在資料夾（處理 en/ 子資料夾情境）。
            • 若失敗，再依故事標題推測 `output/<title>/metadata.json`，並相容舊版 `evaluated/pending`。
            • 捕捉 JSON 讀取錯誤並靜默回退，確保評估流程不中斷。
        """
        metadata = find_metadata_for_story(document_paths, story_title)
        return metadata

    def evaluate_story(self, document_paths: Dict[str, Union[str, List[str]]], story_title: str = "Story",
                      enabled_dimensions: Optional[List[str]] = None,
                      image_paths: Optional[List[str]] = None,
                      *,
                      branch_id: str = "canonical",
                      source_document: Optional[str] = None,
                      evaluation_scope: str = "canonical") -> MultiAspectReport:
        """以檔案路徑為輸入，完成整體六維度評估。

        參數:
            document_paths: 文檔類型對應的檔案路徑或路徑列表。
            story_title:   故事標題，影響報告與提示內容。
            enabled_dimensions: 指定要執行的維度，None 代表全部。
            image_paths:   保留多模態擴充用，目前未使用。

        回傳:
            MultiAspectReport 物件，包含各維度分數、建議、降級報告等。

        注意:
            函數會自動處理文檔註冊、模型共享、評估排序與統計資料更新。
        
        簡單流程（一步一行，好讀版）:
            1) 註冊文件、讀取故事 metadata
            2) 確定要跑哪些維度（若未指定則跑全部）
            3) 依「最佳順序」逐維度執行（最大化重用模型）
            4) 彙總分數、建議與降級報告，產出報告物件
        """
        start_time = datetime.now()
        
        # 註冊文檔到來源管理器
        self.source_manager.register_documents(document_paths)
        self.current_story_metadata = self._load_story_metadata(document_paths, story_title)
        self.alignment_info = None
        # 僅用全文進行文體偵測，供權重覆蓋（若有設定）
        try:
            full_story_text = self.source_manager.get_document_content('full_story.txt') or ""
            if self.genre_detector and full_story_text:
                self.detected_genre_info = self.genre_detector.detect(full_story_text, story_title)
            else:
                self.detected_genre_info = None
            self.current_story_text_features = self._compute_text_alignment_features(
                full_story_text,
                story_title,
                self.detected_genre_info,
                self.current_story_metadata
            ) if full_story_text else None
        except Exception:
            self.detected_genre_info = None
            self.current_story_text_features = None
        
        # 確定要評估的維度
        if enabled_dimensions is None:
            enabled_dimensions = list(self.dimension_model_requirements.keys())
        
        # 檢查維度可行性
        viable_dimensions = self._check_dimension_viability(enabled_dimensions)

        # 按最佳順序 + 依賴約束排序維度（必要時自動補齊相依維度）
        ordered_dimensions = self._resolve_dimension_execution_order(viable_dimensions)
        
        # 顯示智能處理順序和模型重用情況
        self._display_processing_plan(ordered_dimensions)
        
        # 順序執行各維度評估（簡化：移除並行處理）
        dimension_results = []
        for i, dimension in enumerate(ordered_dimensions):
            remaining_dimensions = ordered_dimensions[i+1:]
            
            logger.info("")
            logger.info("%s", "=" * 60)
            logger.info("🔍 評估維度 %s/%s: %s", i + 1, len(ordered_dimensions), dimension)
            logger.info("%s", "=" * 60)
            
            # 載入當前維度檢測器
            result = self._evaluate_dimension(dimension, document_paths, story_title, image_paths)
            dimension_results.append(result)
            
            logger.info("✅ %s 完成 - 分數: %.1f/100 (耗時: %.2fs)", dimension, result.score, result.processing_time)
            
            # 不再釋放模型，保留給下一本故事重用
            # 只清理 GPU 快取避免記憶體累積
            if i == len(ordered_dimensions) - 1:
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
        
    # 計算綜合分數與對齊資訊
        overall_score = self._calculate_overall_score(dimension_results)
        alignment_info = self.alignment_info

        # 兩種分數都輸出：
        # - raw: 未對齊之六維度加權分（套用聚合權重，未做人類等化）
        # - calibrated: 對齊/等化後分數（若關閉對齊，則與 raw 相同）
        raw_score = None
        calibrated_score = float(overall_score)
        if isinstance(alignment_info, dict):
            try:
                raw_score = float(alignment_info.get('base_weighted_score'))
            except Exception:
                raw_score = None
            try:
                calibrated_score = float(alignment_info.get('final_score', overall_score))
            except Exception:
                calibrated_score = float(overall_score)
        if raw_score is None:
            # 後備：若 alignment_info 缺失，raw 視同 overall（關閉對齊情境）
            raw_score = float(overall_score)

        # 生成綜合建議
        recommendations = self._generate_comprehensive_recommendations(dimension_results, overall_score)
        
        # 獲取降級報告（文檔來源 + 維度執行）
        degradation_report = self._build_degradation_report(dimension_results)
        
        # 處理統計
        processing_time = (datetime.now() - start_time).total_seconds()
        processing_summary = self._generate_processing_summary(dimension_results, processing_time)

        governance = build_score_governance(
            overall_score=calibrated_score,
            raw_score=raw_score,
            calibrated_score=calibrated_score,
            dimension_scores={r.dimension: r.score for r in dimension_results},
            dimension_results=dimension_results,
            processing_summary=processing_summary,
            degradation_report=degradation_report,
            alignment_details=alignment_info,
        )
        
        # 更新統計
        self.processing_stats['total_evaluations'] += 1
        if any(r.status == 'failed' for r in dimension_results):
            self.processing_stats['failed_evaluations'] += 1
        elif any(r.status == 'degraded' for r in dimension_results):
            self.processing_stats['degraded_evaluations'] += 1
        else:
            self.processing_stats['successful_evaluations'] += 1
        
        default_source_document = document_paths.get('full_story.txt') if isinstance(document_paths.get('full_story.txt'), str) else None

        report = MultiAspectReport(
            story_title=story_title,
            overall_score=calibrated_score,
            overall_score_raw=round(raw_score, 1),
            overall_score_calibrated=round(calibrated_score, 1),
            dimension_scores={r.dimension: r.score for r in dimension_results},
            dimension_results=dimension_results,
            processing_summary=processing_summary,
            degradation_report=degradation_report,
            recommendations=recommendations,
            timestamp=datetime.now().isoformat(),
            branch_id=branch_id or "canonical",
            source_document=source_document or default_source_document,
            story_metadata=self.current_story_metadata,
            evaluation_scope=evaluation_scope or "canonical",
            alignment_details=alignment_info,
            governance=governance,
            dimension_summaries={
                r.dimension: (r.normalized_summary or self._build_standardized_dimension_summary(
                    r.dimension,
                    r.score,
                    r.status,
                    r.degradation_info,
                    r.suggestions,
                    r.issues_count,
                ))
                for r in dimension_results
            },
        )
        # 重置情境以免影響下一本故事
        self.current_story_metadata = None
        self.alignment_info = None
        self.current_story_text_features = None
        return report
    
    def _check_dimension_viability(self, enabled_dimensions: List[str]) -> List[str]:
        """根據文檔可用性過濾可執行的維度。"""
        viable_dimensions = []
        
        for dimension in enabled_dimensions:
            if dimension not in self.dimension_model_requirements:
                logger.warning("⚠️ 未知維度: %s", dimension)
                continue
                
            # 檢查文檔可用性
            if self.source_manager.is_dimension_viable(dimension):
                viable_dimensions.append(dimension)
            else:
                logger.warning("⚠️ 維度 %s 不可行：缺少必要文檔", dimension)
        
        return viable_dimensions

    def _resolve_dimension_execution_order(self, viable_dimensions: List[str]) -> List[str]:
        """在可行維度中套用依賴約束，輸出最終執行順序。"""
        if not viable_dimensions:
            return []

        preferred: List[str] = [d for d in self.optimal_dimension_order if d in viable_dimensions]
        for dimension in viable_dimensions:
            if dimension not in preferred:
                preferred.append(dimension)
        return self._apply_dependency_order(preferred)

    def _build_degradation_report(self, dimension_results: List[DimensionResult]) -> Dict[str, Dict[str, Any]]:
        """彙總文檔與維度層級的降級/失敗訊號。"""
        report: Dict[str, Dict[str, Any]] = dict(self.source_manager.get_degradation_report())

        dimension_entries: Dict[str, Dict[str, Any]] = {}
        for result in dimension_results:
            if result.status in {'success'} and not result.degradation_info:
                continue
            dimension_entries[result.dimension] = {
                'status': result.status,
                'reason': result.degradation_info,
                'score': result.score,
                'issues_count': result.issues_count,
                'processing_time': result.processing_time,
                'confidence': (result.normalized_summary or {}).get('confidence'),
            }

        if dimension_entries:
            report['dimensions'] = dimension_entries

        return report
    
    def _display_processing_plan(self, ordered_dimensions: List[str]):
        """輸出精簡的維度處理順序，方便追蹤流程。"""
        # 計算模型重用效率（不輸出詳細信息）
        cumulative_models = set()
        for dim in ordered_dimensions:
            required_models = self.dimension_model_requirements.get(dim, set())
            cumulative_models.update(required_models)
        
        # 僅輸出簡潔的處理順序
        logger.info("🎯 處理順序: %s", " → ".join(ordered_dimensions))

    def _build_standardized_dimension_summary(
        self,
        dimension: str,
        score: float,
        status: str,
        degradation_info: Optional[str],
        suggestions: List[str],
        issues_count: int,
        confidence: float = 0.6,
    ) -> Dict[str, Any]:
        safe_score = normalize_score_0_100(score, get_dimension_fallback_score(dimension))
        safe_status = status if status in {'success', 'degraded', 'failed', 'skipped'} else 'degraded'
        safe_confidence = normalize_confidence_0_1(confidence, 0.6)
        return {
            'dimension': dimension,
            'score': safe_score,
            'status': safe_status,
            'error': degradation_info,
            'confidence': round(safe_confidence, 3),
            'issues_count': max(0, int(issues_count or 0)),
            'suggestions': [str(s) for s in (suggestions or [])[:5]],
        }
    
    def _evaluate_dimension(self, dimension: str, document_paths: Dict[str, Union[str, List[str]]], 
                          story_title: str, image_paths: Optional[List[str]] = None) -> DimensionResult:
        """執行單一維度評估並封裝結果。"""
        start_time = datetime.now()
        
        try:
            # 獲取維度的文檔來源權重
            sources = self.source_manager.get_aspect_sources(dimension)
            
            if not sources:
                fallback_score = get_dimension_fallback_score(dimension)
                fallback_result = build_dimension_fallback_payload(
                    dimension,
                    "無可用文檔來源",
                    fallback_score,
                )
                fallback_suggestions = [f"維度 {dimension} 無可用文檔來源，已使用降級評分"]
                summary = self._build_standardized_dimension_summary(
                    dimension,
                    fallback_score,
                    'degraded',
                    "無可用文檔來源",
                    fallback_suggestions,
                    1,
                    confidence=0.3,
                )
                fallback_result.setdefault('_normalized', summary)
                return DimensionResult(
                    dimension=dimension,
                    score=fallback_score,
                    detailed_results=fallback_result,
                    issues_count=1,
                    suggestions=fallback_suggestions,
                    processing_time=0.0,
                    status='degraded',
                    degradation_info="無可用文檔來源",
                    normalized_summary=summary,
                )
            
            # 按需載入檢測器
            checker = self._load_dimension_checker(dimension)
            
            # 準備文檔內容
            document_contents = self.source_manager.get_documents_by_types(sources.keys())
            if not document_contents:
                fallback_full_story = self.source_manager.get_document_content('full_story.txt')
                if fallback_full_story:
                    document_contents = {'full_story.txt': fallback_full_story}
            
            # 調用檢測器
            result = self._call_dimension_checker(
                dimension,
                checker,
                document_contents,
                sources,
                story_title,
                image_paths
            )
            if not isinstance(result, dict):
                fallback_score = get_dimension_fallback_score(dimension)
                result = build_dimension_fallback_payload(
                    dimension,
                    "檢測器回傳非字典結果",
                    fallback_score,
                )
                status = 'degraded'
                degradation_info = '檢測器回傳非字典結果'
            else:
                result_status = str(result.get('status', '')).strip().lower()
                if result_status in {'degraded', 'failed', 'skipped'}:
                    status = result_status
                    degradation_info = str(result.get('error') or result.get('reason') or f'維度狀態: {result_status}')
                elif result.get('error'):
                    status = 'degraded'
                    degradation_info = str(result.get('error'))
                else:
                    status = 'success'
                    degradation_info = None

            fallback_score = get_dimension_fallback_score(dimension)
            extracted_score = self._extract_score_from_result(result)
            if extracted_score is None:
                extracted_score = fallback_score
            safe_score = normalize_score_0_100(
                extracted_score,
                fallback_score,
            )
            issues_count = self._count_issues_in_result(result)
            suggestions = self._extract_suggestions_from_result(result)
            summary = self._build_standardized_dimension_summary(
                dimension,
                safe_score,
                status,
                degradation_info,
                suggestions,
                issues_count,
                confidence=self._extract_confidence_from_result(result),
            )
            if isinstance(result, dict):
                result.setdefault('_normalized', summary)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return DimensionResult(
                dimension=dimension,
                score=safe_score,
                detailed_results=result,
                issues_count=issues_count,
                suggestions=suggestions,
                processing_time=processing_time,
                status=status,
                degradation_info=degradation_info,
                normalized_summary=summary,
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.exception("❌ 維度 %s 評估失敗: %s", dimension, e)
            fallback_score = get_dimension_fallback_score(dimension)
            fallback_result = build_dimension_fallback_payload(
                dimension,
                f"評估例外: {str(e)}",
                fallback_score,
            )
            fallback_suggestions = [f"維度 {dimension} 發生例外，已使用降級評分"]
            summary = self._build_standardized_dimension_summary(
                dimension,
                fallback_score,
                'degraded',
                f"評估失敗: {str(e)}",
                fallback_suggestions,
                1,
                confidence=0.2,
            )
            fallback_result.setdefault('_normalized', summary)
            
            return DimensionResult(
                dimension=dimension,
                score=fallback_score,
                detailed_results=fallback_result,
                issues_count=1,
                suggestions=fallback_suggestions,
                processing_time=processing_time,
                status='degraded',
                degradation_info=f"評估失敗: {str(e)}",
                normalized_summary=summary,
            )
    
    def _call_dimension_checker(self, dimension: str, checker, document_contents: Dict[str, str],
                              source_weights: Dict[str, float], story_title: str,
                              image_paths: Optional[List[str]] = None) -> Dict:
        """呼叫具體維度檢測器並回傳原始結果字典。"""
        selected_documents = self._select_documents_for_dimension(dimension, checker, document_contents)
        if not selected_documents:
            selected_documents = document_contents

        weight_map = self._get_checker_weight_map(dimension, checker, source_weights)
        main_text = self._build_weighted_text(selected_documents, weight_map)

        if not main_text and document_contents:
            main_text = self._build_weighted_text(document_contents, weight_map)
        if not main_text:
            main_text = next(iter(document_contents.values()), '') if document_contents else ''
        
        if dimension == 'completeness':
            return checker.check(main_text, story_title)
        
        elif dimension == 'coherence':
            return checker.check(main_text, story_title, documents=selected_documents)
        
        elif dimension == 'readability':
            dialogue_text = selected_documents.get('dialogue.txt') if isinstance(selected_documents, dict) else None
            narration_text = selected_documents.get('narration.txt') if isinstance(selected_documents, dict) else None
            return checker.check(main_text, story_title, dialogue_text=dialogue_text, narration_text=narration_text, target_age=self.target_age_group)
        
        elif dimension == 'entity_consistency':
            # 使用現有的AdvancedStoryChecker
            return checker.comprehensive_analysis(main_text, story_title, available_documents=selected_documents)
        
        elif dimension == 'factuality':
            outline_text = selected_documents.get('outline.txt') if isinstance(selected_documents, dict) else None
            narration_text = selected_documents.get('narration.txt') if isinstance(selected_documents, dict) else None
            return checker.check(main_text, story_title, outline_text=outline_text, narration_text=narration_text)
        
        elif dimension == 'emotional_impact':
            return checker.check(main_text, story_title)
        
        else:
            raise ValueError(f"未知維度: {dimension}")

    def _select_documents_for_dimension(self, dimension: str, checker, documents: Dict[str, str]) -> Dict[str, str]:
        selector_name = f"get_documents_for_{dimension}"
        if hasattr(checker, selector_name):
            try:
                selected = getattr(checker, selector_name)(documents)
                if isinstance(selected, dict) and selected:
                    return selected
            except Exception as exc:
                logger.warning("⚠️ 文檔選擇器 %s 執行失敗: %s", selector_name, exc)
        return documents

    def _get_checker_weight_map(self, dimension: str, checker, source_weights: Dict[str, float]) -> Dict[str, float]:
        weight_method = f"get_document_weights_for_{dimension}"
        if hasattr(checker, weight_method):
            try:
                weights = getattr(checker, weight_method)()
                if isinstance(weights, dict) and weights:
                    filtered = {k: float(v) for k, v in weights.items() if isinstance(v, (int, float)) and v > 0}
                    if filtered:
                        return filtered
            except Exception as exc:
                logger.warning("⚠️ 無法取得 %s: %s", weight_method, exc)
        return source_weights or {'full_story.txt': 1.0}

    def _build_weighted_text(self, documents: Dict[str, str], weights: Dict[str, float]) -> str:
        if not documents:
            return ""

        weighted_docs = []
        for doc_type, content in documents.items():
            if not content:
                continue
            weight = float(weights.get(doc_type, 0.0)) if weights else 0.0
            weighted_docs.append((weight, doc_type, content.strip()))

        weighted_docs = [item for item in weighted_docs if item[2]]
        if not weighted_docs:
            return ""

        weighted_docs.sort(key=lambda x: (x[0], x[1]), reverse=True)
        multiple_documents = len(weighted_docs) > 1

        combined_sections = []
        for weight, doc_type, content in weighted_docs:
            if multiple_documents:
                combined_sections.append(f"=== {doc_type} (weight {weight:.2f}) ===\n{content}")
            else:
                combined_sections.append(content)

        return "\n\n".join(combined_sections)
    
    def _release_all_models(self):
        """釋放所有已載入模型與檢測器快取，釋出記憶體。"""
        logger.info("🧹 釋放所有模型...")

        released_refs = set()
        for model_type in list(self.loaded_models.keys()):
            component = self.loaded_models.get(model_type)
            if component is not None:
                released_refs.add(id(component))
            self._release_model_component(model_type)

        # 釋放各檢測器的內部模型（如共指消解的 FCoref、AIAnalyzer 的 LLM）
        for dim, checker in self.checkers.items():
            coref = getattr(checker, 'coref', None)
            if coref is not None and hasattr(coref, 'release') and id(coref) not in released_refs:
                try:
                    coref.release()
                except Exception:
                    pass

            ai = getattr(checker, 'ai', None)
            if ai is not None and hasattr(ai, 'release') and id(ai) not in released_refs:
                try:
                    ai.release()
                except Exception:
                    pass

            # 斷開檢測器對大型元件的引用，避免延遲 GC。
            try:
                checker.coref = None
            except Exception:
                pass
            try:
                checker.ai = None
            except Exception:
                pass
        
        # 清理檢測器快取
        self.checkers.clear()
        
        # 最終清理
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass

        logger.info("✅ 模型釋放完成")
        
    
    def _extract_score_from_result(self, result: Dict) -> Optional[float]:
        """在多種結果結構中尋找代表性分數。"""
        # 嘗試不同的分數字段
        score_paths = [
            ['completeness', 'scores', 'final'],
            ['coherence', 'scores', 'final'],
            ['readability', 'scores', 'final'],
            ['children_readability', 'scores', 'final'],
            ['consistency', 'scores', 'overall'],
            ['factuality', 'scores', 'final'],
            ['emotional_impact', 'scores', 'final'],
            ['score'],
            ['scores', 'final'],
            ['scores', 'overall'],
            ['final_score'],
            ['overall_score']
        ]
        
        for path in score_paths:
            try:
                value = result
                for key in path:
                    value = value[key]
                if isinstance(value, (int, float)):
                    return normalize_score_0_100(value, 0.0)
            except (KeyError, TypeError):
                continue
        
        # 如果找不到分數，交由呼叫端使用維度 fallback
        return None
    
    def _count_issues_in_result(self, result: Dict) -> int:
        """統計結果物件中代表問題的項目數量。"""
        issue_fingerprints = set()

        def _add_issue(issue_item: Any) -> None:
            if isinstance(issue_item, dict):
                fingerprint = "|".join(
                    str(issue_item.get(key, ""))
                    for key in ("dimension", "issue_type", "location", "description", "severity")
                )
            else:
                fingerprint = str(issue_item)

            fingerprint = fingerprint.strip()
            if fingerprint:
                issue_fingerprints.add(fingerprint)
        
        # 嘗試不同的問題字段
        issue_paths = [
            ['completeness', 'suggestions'],
            ['coherence', 'issues'],
            ['readability', 'issues'],
            ['children_readability', 'issues'],
            ['consistency', 'issues'],
            ['factuality', 'verification_results'],
            ['emotional_impact', 'suggestions'],
            ['issues'],
            ['problems'],
            ['recommendations']
        ]
        
        for path in issue_paths:
            try:
                value = result
                for key in path:
                    value = value[key]
                if isinstance(value, list):
                    for issue in value:
                        _add_issue(issue)
                elif isinstance(value, dict):
                    # 優先使用 all 清單，避免同時累加分維度與 all 導致重複計數。
                    all_items = value.get('all')
                    if isinstance(all_items, list):
                        for issue in all_items:
                            _add_issue(issue)
                    else:
                        for item_list in value.values():
                            if isinstance(item_list, list):
                                for issue in item_list:
                                    _add_issue(issue)
            except (KeyError, TypeError):
                continue
        
        return len(issue_fingerprints)
    
    def _extract_suggestions_from_result(self, result: Dict) -> List[str]:
        """整合結果物件中的建議文字並限制長度。"""
        suggestions = []
        
        # 嘗試不同的建議字段
        suggestion_paths = [
            ['completeness', 'suggestions'],
            ['coherence', 'suggestions'],
            ['readability', 'suggestions'],
            ['children_readability', 'suggestions'],
            ['recommendations'],
            ['suggestions'],
            ['factuality', 'suggestions'],
            ['emotional_impact', 'suggestions']
        ]
        
        for path in suggestion_paths:
            try:
                value = result
                for key in path:
                    value = value[key]
                if isinstance(value, list):
                    suggestions.extend([str(s) for s in value])
                elif isinstance(value, dict):
                    for v in value.values():
                        if isinstance(v, list):
                            suggestions.extend([str(s) for s in v])
            except (KeyError, TypeError):
                continue

        # 去重並保留原順序，避免同一句建議在多路徑重複出現。
        unique_suggestions = []
        seen = set()
        for suggestion in suggestions:
            normalized = str(suggestion).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_suggestions.append(normalized)

        return unique_suggestions[:5]  # 限制建議數量
    
    def _calculate_overall_score(self, dimension_results: List[DimensionResult]) -> float:
        """依權重與懲罰機制計算故事的整體評分。

        簡要說明：
        - 權重偏向讀者體驗（可讀性、連貫性、情感）
        - 完整性/事實性比重較低（對童話友好）
        - 若文檔缺失，會對該維度權重做降級調整
        - 最後再套用「人類對齊」做小幅校準
        """
        if not dimension_results:
            return 0.0
        # 取出各維度分數（先只收可用結果）
        scores = {r.dimension: r.score for r in dimension_results if r.status in ['success', 'degraded']}
        if not scores:
            return 0.0

        # 依各維度信心值調整振幅：低信心分數向中性分數(60)收斂，降低誤判波動
        raw_scores = dict(scores)
        status_map = {r.dimension: r.status for r in dimension_results}
        confidence_map = {
            r.dimension: self._extract_confidence_from_result(r.detailed_results)
            for r in dimension_results
            if r.dimension in scores
        }
        for dim, original_score in list(scores.items()):
            conf = normalize_confidence_0_1(confidence_map.get(dim, 0.6), 0.6)
            reliability = 0.5 + 0.5 * conf  # 0.5~1.0
            if status_map.get(dim) == 'degraded':
                reliability *= 0.75
            adjusted_score = 60.0 + (original_score - 60.0) * reliability
            scores[dim] = normalize_score_0_100(adjusted_score, original_score)

        # 極端分歧抑制：當維度分差過大且整體信心偏低時，輕度向中位數收斂
        if len(scores) >= 4:
            values = list(scores.values())
            spread = max(values) - min(values)
            avg_conf = sum(confidence_map.values()) / max(1, len(confidence_map))
            if spread >= 45.0 and avg_conf < 0.55:
                median_score = float(np.median(values))
                for dim, value in list(scores.items()):
                    scores[dim] = normalize_score_0_100(median_score + (value - median_score) * 0.9, value)
        # 取得聚合權重（支援 config 覆蓋與文體覆蓋，否則回退至快照或預設）
        base_weights = self._get_aggregation_weights(scores)

        used_weights = {dim: base_weights[dim] for dim in scores.keys() if dim in base_weights}

        # 虛構內容偵測：若 factuality 是硬編碼常數（70.0 或 62-66 區間），
        # 表示該維度對此故事無區分力，將其權重歸零並重分配
        factuality_s = scores.get('factuality', None)
        if 'factuality' in used_weights and isinstance(factuality_s, (int, float)):
            # 虛構內容快速跳過回傳 70.0；不可驗證上限回傳 62-66
            if abs(factuality_s - 70.0) < 0.5 or (62.0 <= factuality_s <= 66.0):
                redistributed = used_weights.pop('factuality', 0.0)
                if used_weights:
                    # 按現有比例重分配
                    total_remaining = sum(used_weights.values()) or 1.0
                    for k in used_weights:
                        used_weights[k] += redistributed * (used_weights[k] / total_remaining)

        # 動態抑制：當文本品質失衡時降低情感權重，避免情感分數主導導致偏移
        if 'emotional_impact' in used_weights:
            emo_w = used_weights['emotional_impact']
            coherence_s = scores.get('coherence', None)
            completeness_s = scores.get('completeness', None)
            readability_s = scores.get('readability', None)
            emotional_s = scores.get('emotional_impact', None)

            scale = 1.0
            # 完整性嚴重偏低 → 適度降低（單層，不疊加）
            if isinstance(completeness_s, (int, float)) and completeness_s < 55.0:
                scale = 0.80
            elif isinstance(completeness_s, (int, float)) and completeness_s < 62.0:
                scale = 0.90

            # 情感遠高於基礎品質 → 降低情感影響（但限制幅度）
            if (
                isinstance(emotional_s, (int, float)) and
                isinstance(readability_s, (int, float)) and
                emotional_s - readability_s >= 20.0 and
                isinstance(completeness_s, (int, float)) and completeness_s < 60.0
            ):
                scale = min(scale, 0.80)

            # 上限保護
            cap = 0.28
            emo_w = min(emo_w * scale, cap)
            emo_w = max(0.0, emo_w)
            used_weights['emotional_impact'] = emo_w

            # 重新正規化權重和，保持總和為 1
            total_w = sum(used_weights.values()) or 1.0
            used_weights = {k: v / total_w for k, v in used_weights.items()}

        if not used_weights:
            return round(sum(scores.values()) / len(scores), 1)

        total_w = sum(used_weights.values()) or 1.0
        normalized_weights = {k: w / total_w for k, w in used_weights.items()}

        # 權重再校正：低信心與降級維度降低權重，減少對總分的誤導。
        confidence_weighted = {}
        for dim, base_w in normalized_weights.items():
            conf = normalize_confidence_0_1(confidence_map.get(dim, 0.6), 0.6)
            conf_factor = 0.7 + 0.3 * conf  # 0.7 ~ 1.0
            if status_map.get(dim) == 'degraded':
                conf_factor *= 0.75
            confidence_weighted[dim] = base_w * conf_factor
        cw_total = sum(confidence_weighted.values()) or 1.0
        normalized_weights = {k: confidence_weighted[k] / cw_total for k in confidence_weighted}

        weighted = sum(scores[k] * normalized_weights.get(k, 0) for k in scores.keys())
        base_score = max(0.0, min(100.0, weighted))

        if CALIBRATION_DISABLED:
            # ── 校準已停用：直接使用先驗權重加總的基礎分 ──
            calibrated_score = base_score
            adjustments = None
        else:
            # 嘗試使用 XGBoost 模型進行預測
            xgb_prediction = self._predict_with_xgboost_model(scores)
            if xgb_prediction is not None:
                # XGBoost 預測成功，使用 alpha 混合策略 (可通過環境變數調整)
                try:
                    alpha = float(os.environ.get('XGBOOST_ALPHA', '0.1'))
                    alpha = max(0.0, min(1.0, alpha))
                except (TypeError, ValueError):
                    alpha = 0.1
                
                calibrated_score = (1 - alpha) * base_score + alpha * xgb_prediction
                calibrated_score = max(0.0, min(100.0, calibrated_score))
                
                adjustments = {
                    'xgboost_prediction': round(xgb_prediction, 2), 
                    'base_score': round(base_score, 2),
                    'xgboost_alpha': round(alpha, 2),
                    'blend_method': 'xgboost_alpha_blend'
                }
                logger.info("[XGBoost 校準] 基礎分數=%.1f → XGBoost=%.1f → Alpha混合(%.2f)=%.1f",
                            base_score, xgb_prediction, alpha, calibrated_score)
            else:
                # XGBoost 不可用，使用原始對齊邏輯
                calibrated_score, adjustments = self._apply_human_alignment(scores, base_score)
        
        # 🎯 高分段防失控：避免校準將 70-75 分推到 95-100
        if base_score >= 68.0 and calibrated_score > base_score + 15.0:
            max_boost = max(8.0, 18.0 - (base_score - 68.0) * 0.25)
            calibrated_score = min(calibrated_score, base_score + max_boost)
        
        # 🎯 短板懲罰：用戶更在意「最差維度」而非「最佳維度」
        all_dim_scores = [v for v in scores.values() if isinstance(v, (int, float))]
        if len(all_dim_scores) >= 3:
            bottom3 = sorted(all_dim_scores)[:3]
            bottom3_mean = sum(bottom3) / 3
            penalty_coef = 0.12
            penalty_threshold = 68.0
            if bottom3_mean < penalty_threshold:
                penalty = (penalty_threshold - bottom3_mean) * penalty_coef
                calibrated_score = max(0.0, calibrated_score - penalty)
        
        degraded_dimensions = [
            dim for dim, st in status_map.items()
            if st in {'degraded', 'failed'} and dim in scores
        ]

        constrained_score, constraints_meta = apply_cross_dimension_constraints(
            calibrated_score,
            scores,
            confidence_map=confidence_map,
            degraded_dimensions=degraded_dimensions,
        )
        consensus_score, consensus_meta = compute_consensus_adjustment(
            constrained_score,
            scores,
            confidence_map=confidence_map,
            degraded_dimensions=degraded_dimensions,
        )
        final_score = max(0.0, min(100.0, consensus_score))

        self.alignment_info = {
            'mode': 'human_calibrated' if adjustments else 'model_only',
            'base_weighted_score': round(base_score, 2),
            'final_score': round(final_score, 2),
            'adjustments': adjustments,
            'aggregation': {
                'confidence_adjusted_scores': {k: round(v, 2) for k, v in scores.items()},
                'raw_scores': {k: round(v, 2) for k, v in raw_scores.items()},
                'confidence_map': {k: round(v, 3) for k, v in confidence_map.items()},
            },
            'policy': {
                'constraints': constraints_meta,
                'consensus': consensus_meta,
            },
        }

        return round(final_score, 1)

    def _get_aggregation_weights(self, scores: Dict[str, float]) -> Dict[str, float]:
        """載入並決定最終聚合權重（支援 YAML 先驗 + 校準快照自動融合）。

        流程：
        1) 建立內建預設（讀者體驗導向）。
        2) 讀取 YAML 先驗（global 或 by_genre）→ 得到 priors。
        3) 讀取校準快照 aggregation_weights（若存在）→ 得到 snapshot。
        4) 根據模型品質（samples/R2/RMSE/confidence）自動計算融合係數 alpha，或依設定固定。
        5) 最終權重 = (1-alpha)*priors + alpha*snapshot，並做正規化與守門（可選）。
        """
        # 1) 內建預設（偏向讀者體驗＋敘事穩定度）
        default_weights = {
            'readability': 0.28,
            'coherence': 0.22,
            'emotional_impact': 0.25,
            'entity_consistency': 0.13,
            'completeness': 0.10,
            'factuality': 0.02
        }
        dims_all = list(default_weights.keys())
        available_dims = set(scores.keys()) if scores else set(dims_all)

        # 2) YAML 先驗（priors）
        cfg = self._load_rating_weight_config() or {}
        rating = cfg.get('rating_score') if isinstance(cfg, dict) else None
        rating = rating if isinstance(rating, dict) else cfg if isinstance(cfg, dict) else {}
        chosen: Optional[Dict[str, Any]] = None
        if isinstance(rating, dict):
            by_genre = rating.get('by_genre')
            if isinstance(by_genre, dict) and self.detected_genre_info:
                dominant = str(self.detected_genre_info.get('dominant') or '').strip()
                if dominant and dominant in by_genre and isinstance(by_genre[dominant], dict):
                    chosen = by_genre[dominant]
            if chosen is None and isinstance(rating.get('global'), dict):
                chosen = rating.get('global')
        priors_raw = {k: float(v) for k, v in (chosen or default_weights).items() if k in default_weights}
        sum_pr = sum(priors_raw.values()) or 1.0
        priors = {k: priors_raw.get(k, default_weights[k]) / sum_pr for k in default_weights}

        # ── 校準停用時直接使用先驗權重，跳過快照融合 ──
        if CALIBRATION_DISABLED:
            pr_used = {k: priors[k] for k in default_weights if k in available_dims}
            s = sum(pr_used.values()) or 1.0
            return {k: pr_used[k] / s for k in pr_used}

        # 3) 載入 XGBoost 校準模型
        json_path = os.environ.get('CALIBRATION_MODEL_PATH', 'calibration/models/latest.json')
        xgb_path = json_path.replace('.json', '.xgb')
        data = None
        snapshot = None
        alpha_auto = 0.0
        xgb_model = None
        feature_means = None
        feature_stds = None
        feature_names = None
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = None

        if isinstance(data, dict):
            # 載入 XGBoost 模型
            if XGBOOST_AVAILABLE and os.path.exists(xgb_path):
                try:
                    xgb_model = xgb.Booster()
                    xgb_model.load_model(xgb_path)
                    feature_means = np.array(data.get('feature_means', []))
                    feature_stds = np.array(data.get('feature_stds', []))
                    feature_names = data.get('feature_names', [])
                    logger.info(f"[校準] 成功載入 XGBoost 模型: {xgb_path}")
                except Exception as e:
                    logger.warning(f"[校準] 無法載入 XGBoost 模型: {e}")
                    xgb_model = None
            
            # 回退方案：使用聚合權重
            agg = data.get('aggregation_weights')
            if isinstance(agg, dict):
                cleaned = {k: float(v) for k, v in agg.items() if k in default_weights and isinstance(v, (int, float))}
                s = sum(cleaned.values())
                if s > 0:
                    snapshot = {k: cleaned.get(k, 0.0) / s for k in default_weights}

            # 估計自動融合強度（alpha）
            try:
                base_conf = float(data.get('confidence', 0.0) or 0.0)
                r2 = float(data.get('r2', 0.0) or 0.0)
                rmse = float(data.get('rmse', 0.0) or 0.0)
                samples = int(data.get('samples', 0) or 0)

                # 數值夾制
                base_conf = max(0.0, min(1.0, base_conf))
                r2 = max(0.0, min(1.0, r2))
                rmse = max(0.0, rmse)
                samples = max(0, samples)

                # 如果有 XGBoost 模型，使用更激進的 alpha
                if xgb_model is not None:
                    if samples >= 20 and r2 >= 0.5:
                        alpha_auto = min(0.95, 0.5 + r2 * 0.5)  # R²=0.5→0.75, R²=1.0→1.0
                    elif samples >= 10:
                        alpha_auto = min(0.7, base_conf * 0.8)
                    else:
                        alpha_auto = 0.0
                else:
                    # 原始保守邏輯
                    if samples < 20:
                        alpha_auto = 0.0
                    elif samples < 30 or r2 < 0.15:
                        alpha_auto = max(0.0, min(0.15, base_conf * 0.20))
                    elif r2 < 0.30 or rmse > 15.0:
                        alpha_auto = max(0.0, min(0.25, base_conf * 0.40))
                    else:
                        # RMSE 因子
                        if rmse <= 3.0:
                            rmse_factor = 1.0
                        elif rmse <= 9.0:
                            rmse_factor = 1.0 - (rmse - 3.0) / 6.0 * 0.40
                        elif rmse <= 12.0:
                            rmse_factor = 0.60 - (rmse - 9.0) / 3.0 * 0.30
                        else:
                            rmse_factor = max(0.10, 0.30 - (rmse - 12.0) / 3.0 * 0.20)

                        # 樣本數因子
                        if samples < 50:
                            sample_factor = 0.10 + (samples - 30) / 20.0 * 0.08 if samples >= 30 else 0.10
                        elif samples < 200:
                            sample_factor = 0.18 + math.sqrt((samples - 50) / 150.0) * 0.42
                        elif samples < 600:
                            sample_factor = 0.60 + (samples - 200) / 400.0 * 0.25
                        else:
                            sample_factor = min(1.0, 0.85 + (samples - 600) / 400.0 * 0.15)

                        # R2 因子
                        if r2 < 0.30:
                            r2_factor = r2 * 1.5
                        elif r2 < 0.60:
                            r2_factor = 0.45 + (r2 - 0.30) * 1.5
                        else:
                            r2_factor = 0.90 + (r2 - 0.60) * 0.25

                        conf_factor = math.sqrt(base_conf)
                        trust = (
                            0.15 * conf_factor +
                            0.40 * r2_factor +
                            0.25 * rmse_factor +
                            0.20 * sample_factor
                        )
                        sample_discount = math.sqrt(samples / 100.0) if samples < 100 else 1.0
                        alpha_auto = max(0.0, min(1.0, trust * sample_discount))
            except Exception as e:
                logger.warning(f"[校準] alpha 計算失敗: {e}")
                alpha_auto = 0.0

        # 4) 融合係數設定（優先固定，其次自動，並套上下限）
        blend_cfg = (rating.get('blend') if isinstance(rating, dict) else None) or {}
        mode = str(blend_cfg.get('mode', 'auto')).lower()
        fixed_alpha = blend_cfg.get('fixed_alpha')
        min_alpha = float(blend_cfg.get('min_alpha', 0.0) or 0.0)
        max_alpha = float(blend_cfg.get('max_alpha', 1.0) or 1.0)
        if isinstance(fixed_alpha, (int, float)) and mode == 'fixed':
            alpha = float(fixed_alpha)
        else:
            alpha = float(alpha_auto)
        alpha = max(min_alpha, min(max_alpha, alpha))
        if snapshot is None:
            alpha = 0.0  # 沒有快照權重就不融合

        # 5) 計算最終權重（維度對齊 + 正規化 + 守門）
        blended_raw: Dict[str, float] = {}
        for k in default_weights:
            if k not in available_dims:
                continue
            sp = snapshot.get(k, priors[k]) if snapshot else priors[k]
            blended_raw[k] = (1.0 - alpha) * priors[k] + alpha * sp

        total = sum(blended_raw.values()) or 1.0
        blended = {k: blended_raw[k] / total for k in blended_raw}

        # 可選守門：每維度最小/最大（避免極端）
        guards = (rating.get('guards') if isinstance(rating, dict) else None) or {}
        min_map = guards.get('min_per_dim') if isinstance(guards, dict) else None
        max_map = guards.get('max_per_dim') if isinstance(guards, dict) else None
        if isinstance(min_map, dict) or isinstance(max_map, dict):
            # 先套上下限，再重新正規化
            for k in list(blended.keys()):
                v = blended[k]
                vmin = float(min_map.get(k, 0.0)) if isinstance(min_map, dict) and k in min_map else 0.0
                vmax = float(max_map.get(k, 1.0)) if isinstance(max_map, dict) and k in max_map else 1.0
                blended[k] = max(vmin, min(vmax, v))
            s2 = sum(blended.values()) or 1.0
            blended = {k: blended[k] / s2 for k in blended}

        # 確保所有使用到的維度都有權重
        for k in list(blended.keys()):
            if k not in available_dims:
                blended.pop(k, None)
        # 若清除後為空，回退到 priors（只含可用維度）
        if not blended:
            pr_used = {k: priors[k] for k in default_weights if k in available_dims}
            s3 = sum(pr_used.values()) or 1.0
            return {k: pr_used[k] / s3 for k in pr_used}

        return blended

    def _load_rating_weight_config(self) -> Optional[Dict[str, Any]]:
        """載入評分聚合權重設定（YAML）。以快取避免重複 IO。"""
        if self.rating_weight_config is not None:
            return self.rating_weight_config
        path = os.environ.get('RATING_WEIGHTS_PATH', os.path.join('config', 'rating_weights.yaml'))
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    if isinstance(data, dict):
                        self.rating_weight_config = data
                        return self.rating_weight_config
        except Exception:
            pass
        self.rating_weight_config = None
        return None

    def _ensure_longformer_model(self) -> bool:
        """延遲載入 Longformer，用於產生長文本嵌入特徵。"""
        if self._longformer_unavailable:
            return False
        if self.longformer_model is not None and self.longformer_tokenizer is not None:
            return True
        try:
            import torch
            from transformers import AutoTokenizer, AutoModel
        except Exception:
            self._longformer_unavailable = True
            return False

        model_path = os.environ.get('LONGFORMER_MODEL_PATH', resolve_model_path('longformer-base-4096'))
        try:
            self.longformer_tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            self.longformer_model = AutoModel.from_pretrained(model_path, local_files_only=True)
            self.longformer_model.eval()
            if torch.cuda.is_available():
                device_id = os.environ.get('LONGFORMER_DEVICE', 'cuda')
            else:
                device_id = 'cpu'
            self.longformer_device = device_id
            self.longformer_model.to(device_id)
            return True
        except Exception:
            self.longformer_tokenizer = None
            self.longformer_model = None
            self._longformer_unavailable = True
            return False

    def _predict_with_xgboost_model(self, scores: Dict[str, float]) -> Optional[float]:
        """使用 XGBoost 模型預測用戶評分（0-100 分制）。
        
        Args:
            scores: 各維度分數字典
            
        Returns:
            預測分數（0-100），失敗返回 None
        """
        # 載入模型資料（從 _get_aggregation_weights 中提取的資料）
        json_path = os.environ.get('CALIBRATION_MODEL_PATH', 'calibration/models/latest.json')
        xgb_path = json_path.replace('.json', '.xgb')
        
        if not XGBOOST_AVAILABLE:
            logger.debug("[XGBoost] XGBOOST_AVAILABLE=%s", XGBOOST_AVAILABLE)
            return None
        
        if not os.path.exists(xgb_path):
            logger.debug("[XGBoost] 模型文件不存在: %s", xgb_path)
            return None
            
        try:
            # 載入模型
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            xgb_model = xgb.Booster()
            xgb_model.load_model(xgb_path)
            feature_means = np.array(data.get('feature_means', []))
            feature_stds = np.array(data.get('feature_stds', []))
            feature_names = data.get('feature_names', [])
            
            if len(feature_means) == 0 or len(feature_stds) == 0 or len(feature_names) == 0:
                logger.warning("[XGBoost] 缺少特徵標準化參數")
                return None
            
            # 構建基礎特徵（必須與訓練時一致）
            base_features = {}
            for dim in ['entity_consistency', 'completeness', 'coherence', 
                       'readability', 'factuality', 'emotional_impact']:
                base_features[f'dim_{dim}'] = scores.get(dim, 0.0)
            
            # 構建交互特徵（與 calibrate.py 中的邏輯一致）
            interaction_features = {}
            dim_keys = list(base_features.keys())
            for i, k1 in enumerate(dim_keys):
                for k2 in dim_keys[i+1:]:
                    inter_key = f"{k1}_x_{k2}"
                    interaction_features[inter_key] = base_features[k1] * base_features[k2]
            
            # 構建平方特徵
            squared_features = {f"{k}_squared": v**2 for k, v in base_features.items()}
            
            # 合併所有特徵
            all_features = {**base_features, **interaction_features, **squared_features}
            
            # 按照訓練時的特徵順序組裝特徵向量
            feature_vector = np.array([all_features.get(name, 0.0) for name in feature_names])
            
            # 標準化
            feature_vector = (feature_vector - feature_means) / (feature_stds + 1e-10)
            
            # 預測
            dmatrix = xgb.DMatrix(feature_vector.reshape(1, -1))
            prediction = xgb_model.predict(dmatrix)[0]
            
            return float(prediction)
            
        except Exception as e:
            logger.warning(f"[XGBoost] 預測失敗: {e}")
            return None

    def _apply_human_alignment(
        self,
        scores: Dict[str, float],
        base_score: float
    ) -> Tuple[float, Optional[Dict[str, float]]]:
        """利用快照的人類對齊模型將分數校準（無模式開關）。"""

        model = self._load_human_alignment_model()
        if not model:
            return base_score, None

        weights = model.get('weights')
        if not isinstance(weights, dict) or not weights:
            return base_score, None

        metadata = self.current_story_metadata or {}
        feature_values = self._build_alignment_features(scores, metadata)
        if not feature_values:
            return base_score, None

        intercept = float(model.get('bias', 0.0) or 0.0)
        aligned = intercept
        contributors: Dict[str, Dict[str, float]] = {}

        for feature_name, weight in weights.items():
            if not isinstance(weight, (int, float)):
                continue
            value = feature_values.get(feature_name)
            if value is None:
                continue
            value_f = float(value)
            weight_f = float(weight)
            impact = value_f * weight_f
            aligned += impact
            contributors[feature_name] = {
                'weight': round(weight_f, 6),
                'value': round(value_f, 4),
                'impact': round(impact, 4)
            }

        aligned = max(0.0, min(100.0, aligned))

        # 若存在單調等化映射，對 aligned 進一步等化
        iso_aligned = None
        iso_x = model.get('iso_x')
        iso_y = model.get('iso_y')
        if isinstance(iso_x, list) and isinstance(iso_y, list) and len(iso_x) == len(iso_y) and len(iso_x) >= 2:
            import bisect
            x_vals = [float(x) for x in iso_x]
            y_vals = [float(y) for y in iso_y]
            if aligned <= x_vals[0]:
                iso_aligned = float(y_vals[0])
            elif aligned >= x_vals[-1]:
                iso_aligned = float(y_vals[-1])
            else:
                idx = bisect.bisect_left(x_vals, aligned)
                x0, x1 = x_vals[idx-1], x_vals[idx]
                y0, y1 = y_vals[idx-1], y_vals[idx]
                t = 0.0 if x1 == x0 else (aligned - x0) / (x1 - x0)
                iso_aligned = float(y0 + t * (y1 - y0))
            iso_aligned = max(0.0, min(100.0, iso_aligned))

        effective_aligned = iso_aligned if iso_aligned is not None else aligned

        base_confidence = float(model.get('confidence', 0.0) or 0.0)
        rmse = float(model.get('rmse', 0.0) or 0.0)
        iso_r2 = model.get('iso_r2')
        iso_rmse = model.get('iso_rmse')
        samples = int(model.get('samples', 0) or 0)

        rmse_penalty = 1.0
        if rmse > 4.5:
            rmse_penalty = max(0.45, 1.0 - (rmse - 4.5) / 14.0)

        sample_penalty = 1.0
        if samples < 80:
            sample_penalty = max(0.55, 0.55 + samples / 150.0)

        # 單一路徑：依模型品質與差距做動態混合（快照來源固定，可重現）
        blend = base_confidence * rmse_penalty * sample_penalty
        if isinstance(iso_r2, (int, float)):
            iso_r2_val = float(iso_r2)
            if iso_r2_val >= 0.9:
                blend = max(blend, 0.92)
            elif iso_r2_val >= 0.8:
                blend = max(blend, 0.85)
            elif iso_r2_val >= 0.7:
                blend = max(blend, 0.78)

        gap = abs(effective_aligned - base_score)
        if gap >= 12.0:
            blend += 0.25
        elif gap >= 6.0:
            blend += 0.12

        if effective_aligned < base_score:
            blend += 0.05

        try:
            max_blend = float(model.get('max_blend', 0.45))
        except (TypeError, ValueError):
            max_blend = 0.45
        max_blend = max(0.0, min(0.98, max_blend))

        blend = min(blend, max_blend)
        blend = max(0.0, min(0.98, blend))

        if blend <= 0.0:
            final = base_score
            blend_mode = 'none'
        else:
            final = base_score * (1 - blend) + effective_aligned * blend
            final = max(0.0, min(100.0, final))
            blend_mode = 'partial'

        original_final = final
        max_positive_delta = 9.0 if base_score < 80.0 else 7.0
        if effective_aligned < base_score:
            dynamic_drop = max(12.0, min(30.0, gap * 1.2))
            max_negative_delta = -dynamic_drop
        else:
            max_negative_delta = -12.0

        delta = final - base_score
        if delta > max_positive_delta:
            final = base_score + max_positive_delta
        elif delta < max_negative_delta:
            final = base_score + max_negative_delta

        delta_clipped = final != original_final
        delta = final - base_score

        adjustments = {
            'confidence': round(base_confidence, 4),
            'effective_blend': round(blend, 4),
            'blend_mode': blend_mode,
            'human_aligned_score': round(aligned, 2),
            'isotonic_aligned_score': round(iso_aligned, 2) if iso_aligned is not None else None,
            'delta': round(delta, 2),
            'delta_clipped': delta_clipped,
            'bias': round(intercept, 3),
            'r2': round(float(model.get('r2', 0.0)), 4),
            'rmse': round(rmse, 3),
            'iso_r2': round(float(iso_r2), 4) if isinstance(iso_r2, (int, float)) else None,
            'iso_rmse': round(float(iso_rmse), 3) if isinstance(iso_rmse, (int, float)) else None,
            'rmse_penalty': round(rmse_penalty, 4),
            'sample_penalty': round(sample_penalty, 4),
            'contributors': contributors,
            'alignment_mode': 'snapshot_dynamic_blend'
        }

        return final, adjustments

    def _load_human_alignment_model(self) -> Optional[Dict[str, Union[float, Dict[str, float]]]]:
        """僅從快照載入對齊模型；失敗則不校準。"""
        if self.calibration_model is not None:
            return self.calibration_model

        model_path = os.environ.get('CALIBRATION_MODEL_PATH', 'calibration/models/latest.json')

        try:
            with open(model_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            self.calibration_model = None
            return None

        if isinstance(data, dict) and 'weights' in data:
            self.calibration_model = data
            return self.calibration_model

        self.calibration_model = None
        return None

    def _build_alignment_features(
        self,
        scores: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
        text_features: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """以六大維度分數衍生對齊模型所需的特徵。

        metadata 參數保留作為相容性介面，但目前不再納入任何額外特徵。"""
        if not scores:
            return {}

        feature_values: Dict[str, float] = {}
        primary_dims = [
            'coherence',
            'readability',
            'completeness',
            'entity_consistency',
            'factuality',
            'emotional_impact'
        ]

        _ = metadata  # 保留參數僅為相容介面，不再納入額外特徵

        # 只採用六大維度與衍生統計量/交互項作為校正特徵（推論期只需文本分數），降低過度擬合風險
        valid_scores: Dict[str, float] = {}
        for dim in primary_dims:
            value = scores.get(dim)
            if isinstance(value, (int, float)):
                numeric = float(value)
                feature_values[f'dim_{dim}'] = numeric
                valid_scores[dim] = numeric

        if not valid_scores:
            return {}

        values = list(valid_scores.values())
        sorted_values = sorted(values)
        mean_value = sum(values) / len(values)
        feature_values['dim_mean'] = float(mean_value)
        feature_values['dim_min'] = float(sorted_values[0])
        feature_values['dim_max'] = float(sorted_values[-1])
        feature_values['dim_range'] = feature_values['dim_max'] - feature_values['dim_min']
        variance = sum((v - mean_value) ** 2 for v in values) / len(values)
        feature_values['dim_std'] = math.sqrt(max(0.0, variance))
        feature_values['dim_var'] = max(0.0, variance)

        if len(sorted_values) >= 3:
            top_k = sorted_values[-3:]
            bottom_k = sorted_values[:3]
        else:
            top_k = bottom_k = sorted_values

        feature_values['dim_top3_mean'] = float(sum(top_k) / len(top_k))
        feature_values['dim_bottom3_mean'] = float(sum(bottom_k) / len(bottom_k))

        # bottom3 標準差：用戶更在意短板的一致性（波動大通常意味著有明顯弱點）
        if len(bottom_k) >= 2:
            bmean = sum(bottom_k) / len(bottom_k)
            bvar = sum((v - bmean) ** 2 for v in bottom_k) / len(bottom_k)
            feature_values['dim_bottom3_std'] = math.sqrt(max(0.0, bvar))
        else:
            feature_values['dim_bottom3_std'] = 0.0

        # 交互項（縮放至同一量級，避免極大值）：以 /100 做簡單正規化
        def _g(name: str) -> Optional[float]:
            v = valid_scores.get(name)
            return float(v) if isinstance(v, (int, float)) else None

        r = _g('readability')
        c = _g('coherence')
        cmpl = _g('completeness')
        emo = _g('emotional_impact')
        cons = _g('entity_consistency')
        fact = _g('factuality')

        def _mul(a: Optional[float], b: Optional[float]) -> Optional[float]:
            if a is None or b is None:
                return None
            return (a / 100.0) * (b / 100.0)

        inter_features = {
            'inter_readability_completeness': _mul(r, cmpl),
            'inter_readability_emotion': _mul(r, emo),
            'inter_coherence_completeness': _mul(c, cmpl),
            'inter_coherence_readability': _mul(c, r),
            'inter_consistency_coherence': _mul(cons, c),
        }
        for k, v in inter_features.items():
            if v is not None:
                feature_values[k] = float(v)

        # 差異特徵（保留原始尺度，反映維度間落差）
        if r is not None and emo is not None:
            feature_values['diff_readability_emotion'] = float(r - emo)
        if c is not None and cmpl is not None:
            feature_values['diff_coherence_completeness'] = float(c - cmpl)
        if emo is not None and c is not None:
            feature_values['diff_emotion_coherence'] = float(emo - c)
        if cons is not None and fact is not None:
            feature_values['diff_consistency_factuality'] = float(cons - fact)

        # 二元旗標：是否存在嚴重短板
        feature_values['flag_dim_below_60'] = 1.0 if any(v < 60.0 for v in valid_scores.values()) else 0.0
        feature_values['flag_emotion_dominant'] = 1.0 if emo is not None and r is not None and (emo - r) >= 12.0 else 0.0

        # 短板強度（對最小值距離 70 的缺口；<0 表示達標）
        try:
            feature_values['shortfall_gap_70'] = max(0.0, 70.0 - feature_values['dim_min'])
        except Exception:
            feature_values['shortfall_gap_70'] = 0.0

        # 訓練期可用的外部/中繼特徵（以 priv_ 為前綴，推論期不依賴）
        if isinstance(metadata, dict) and metadata:
            ratings_count_raw = metadata.get('ratings_count')
            if isinstance(ratings_count_raw, (int, float)) and ratings_count_raw >= 0:
                ratings_count_val = float(ratings_count_raw)
                feature_values['priv_log_ratings_count'] = math.log1p(ratings_count_val)
                feature_values['priv_ratings_count_per_k'] = ratings_count_val / 1000.0
            else:
                ratings_count_val = None

            word_count_meta = metadata.get('word_count')
            if isinstance(word_count_meta, (int, float)) and word_count_meta >= 0:
                wc_val = float(word_count_meta)
                feature_values['priv_log_word_count'] = math.log1p(wc_val)
                feature_values['priv_word_count_k'] = wc_val / 1000.0

                if ratings_count_val is not None:
                    feature_values['priv_ratings_per_word'] = ratings_count_val / max(1.0, wc_val)

            char_count_meta = metadata.get('char_count')
            if isinstance(char_count_meta, (int, float)) and char_count_meta >= 0:
                cc_val = float(char_count_meta)
                feature_values['priv_log_char_count'] = math.log1p(cc_val)
                feature_values['priv_char_count_k'] = cc_val / 1000.0

                if ratings_count_val is not None:
                    feature_values['priv_ratings_per_char'] = ratings_count_val / max(1.0, cc_val)

            def _slugify(value: str) -> str:
                cleaned = re.sub(r'[^a-z0-9]+', '_', value.strip().lower()).strip('_')
                return cleaned or 'unknown'

            quality_label = metadata.get('quality_label')
            if isinstance(quality_label, str) and quality_label.strip():
                feature_values[f"priv_quality_{_slugify(quality_label)}"] = 1.0

            age_value = metadata.get('age') or metadata.get('age_group')
            if isinstance(age_value, str) and age_value.strip():
                slug = _slugify(age_value)
                feature_values[f"priv_age_{slug}"] = 1.0
                if slug.startswith('children'):
                    feature_values['priv_is_children_target'] = 1.0

            platform = metadata.get('platform')
            if isinstance(platform, str) and platform.strip():
                feature_values[f"priv_platform_{_slugify(platform)}"] = 1.0

            publication_year = metadata.get('publication_year')
            if isinstance(publication_year, (int, float)):
                feature_values['priv_publication_year'] = float(publication_year)

            source_text = metadata.get('text_source') or metadata.get('source') or ""
            if isinstance(source_text, str) and source_text.strip():
                lower_source = source_text.lower()
                feature_values['priv_text_source_length'] = float(len(lower_source))
                keyword_flags = {
                    'priv_source_public_domain': 'public domain',
                    'priv_source_project_gutenberg': 'project gutenberg',
                    'priv_source_brothers_grimm': 'grimm',
                    'priv_source_andersen': 'andersen',
                    'priv_source_lang': 'lang',
                    'priv_source_wilde': 'wilde',
                }
                for key, marker in keyword_flags.items():
                    if marker in lower_source:
                        feature_values[key] = 1.0

            story_title = metadata.get('title')
            if isinstance(story_title, str) and story_title.strip():
                feature_values['priv_title_length'] = float(len(story_title))

            ratings_count = ratings_count_val
            word_count_signal = word_count_meta if isinstance(word_count_meta, (int, float)) else None
            if ratings_count is not None and word_count_signal is not None and word_count_signal > 0:
                feature_values['priv_log_ratings_per_kword'] = math.log1p(ratings_count / max(1.0, word_count_signal / 1000.0))

            if metadata.get('quality_label') == 'low' and ratings_count and ratings_count > 0:
                feature_values['priv_low_quality_signal'] = 1.0

        # 追加：純文本衍生特徵（推論期可從全文計算）
        merged_text_features: Optional[Dict[str, float]] = None
        if isinstance(text_features, dict):
            merged_text_features = text_features
        elif isinstance(self.current_story_text_features, dict):
            merged_text_features = self.current_story_text_features

        if merged_text_features:
            for key, value in merged_text_features.items():
                if value is None:
                    continue
                try:
                    feature_values[key] = float(value)
                except (TypeError, ValueError):
                    continue

        return feature_values

    def _compute_text_alignment_features(
        self,
        story_text: str,
        story_title: str = "",
        genre_info: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """從全文計算校準可用的純文本特徵。"""
        if not story_text:
            return {}

        text = story_text.strip()
        if not text:
            return {}

        try:
            words = re.findall(r"\b[\w']+\b", text)
        except re.error:
            words = text.split()
        word_count = len(words)
        unique_words = len({w.lower() for w in words}) if words else 0
        char_count = len(text)

        sentences = [s.strip() for s in re.split(r"[\.!?]+", text) if s and s.strip()]
        sentence_count = len(sentences)
        sentence_lengths = [len(re.findall(r"\b[\w']+\b", s)) for s in sentences] if sentences else []

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p and p.strip()]
        paragraph_count = len(paragraphs)
        paragraph_word_counts = [len(re.findall(r"\b[\w']+\b", p)) for p in paragraphs] if paragraphs else []

        quote_count = text.count('"') + text.count('“') + text.count('”')
        quote_pairs = quote_count // 2

        avg_sentence_len = word_count / max(1, sentence_count)
        if sentence_lengths:
            variance = sum((length - avg_sentence_len) ** 2 for length in sentence_lengths) / len(sentence_lengths)
            sentence_std = math.sqrt(max(0.0, variance))
            sorted_lengths = sorted(sentence_lengths)
            mid = len(sorted_lengths) // 2
            if len(sorted_lengths) % 2 == 0:
                sentence_median = (sorted_lengths[mid - 1] + sorted_lengths[mid]) / 2.0
            else:
                sentence_median = float(sorted_lengths[mid])
            long_sentence_ratio = sum(1 for length in sentence_lengths if length >= 25) / max(1, sentence_count)
        else:
            sentence_std = 0.0
            sentence_median = 0.0
            long_sentence_ratio = 0.0

        paragraph_density = paragraph_count / max(1, word_count)  # 段落密度
        dialogue_ratio = min(1.0, quote_pairs / max(1, sentence_count))
        unique_ratio = unique_words / max(1, word_count)
        chars_per_word = char_count / max(1, word_count)
        exclam_density = text.count('!') / max(1, word_count)
        question_density = text.count('?') / max(1, word_count)

        dialogue_word_total = 0
        try:
            for match in re.finditer(r'["“](.*?)["”]', text, flags=re.DOTALL):
                segment = match.group(1)
                if not segment:
                    continue
                dialogue_word_total += len(re.findall(r"\b[\w']+\b", segment))
        except re.error:
            dialogue_word_total = 0
        dialogue_word_ratio = dialogue_word_total / max(1, word_count)

        capitalized_tokens = [w for w in words if len(w) > 1 and w[0].isupper() and not w.isupper()]
        unique_named_entities = len({w.lower() for w in capitalized_tokens})
        capitalized_ratio = len(capitalized_tokens) / max(1, word_count)

        lower_words = [w.lower() for w in words]
        word_lengths = [len(w) for w in lower_words if w.isalpha()]
        numeric_tokens = sum(1 for w in lower_words if any(ch.isdigit() for ch in w))
        if word_lengths:
            word_len_mean = sum(word_lengths) / len(word_lengths)
            word_len_var = sum((l - word_len_mean) ** 2 for l in word_lengths) / len(word_lengths)
            word_len_std = math.sqrt(max(0.0, word_len_var))
        else:
            word_len_mean = 0.0
            word_len_std = 0.0

        pos_count = sum(1 for w in lower_words if w in _POSITIVE_LEXICON)
        neg_count = sum(1 for w in lower_words if w in _NEGATIVE_LEXICON)
        sentiment_balance = (pos_count - neg_count) / max(1, len(lower_words))
        sentiment_magnitude = (pos_count + neg_count) / max(1, len(lower_words))
        sentiment_polarity = 0.0
        if (pos_count + neg_count) > 0:
            sentiment_polarity = (pos_count - neg_count) / (pos_count + neg_count)

        stopword_count = sum(1 for w in lower_words if w in _STOPWORDS)
        stopword_ratio = stopword_count / max(1, len(lower_words))

        token_counter = Counter(lower_words) if lower_words else Counter()
        hapax_count = sum(1 for c in token_counter.values() if c == 1)
        dis_legomena_count = sum(1 for c in token_counter.values() if c == 2)
        type_count = max(1, len(token_counter))
        hapax_ratio = hapax_count / type_count if token_counter else 0.0
        dis_legomena_ratio = dis_legomena_count / type_count if token_counter else 0.0
        total_tokens = len(lower_words)
        if total_tokens:
            freq_probs = [count / total_tokens for count in token_counter.values()]
            word_entropy = -sum(p * math.log(p + 1e-9) for p in freq_probs if p > 0.0)
        else:
            word_entropy = 0.0

        punctuation_count = sum(1 for ch in text if ch in string.punctuation)
        punctuation_density = punctuation_count / max(1, char_count)
        narration_token_floor = max(0, word_count - dialogue_word_total)
        dialogue_narration_ratio = dialogue_word_total / max(1, narration_token_floor)
        paragraph_avg_sentence = sentence_count / max(1, paragraph_count)
        sentence_variation_ratio = sentence_std / max(1.0, avg_sentence_len)

        # 段落統計有助於把握敘事節奏
        if paragraph_word_counts:
            para_mean = sum(paragraph_word_counts) / len(paragraph_word_counts)
            para_var = sum((c - para_mean) ** 2 for c in paragraph_word_counts) / len(paragraph_word_counts)
            para_std = math.sqrt(max(0.0, para_var))
        else:
            para_mean = 0.0
            para_std = 0.0

        title_tokens = {t.lower() for t in re.findall(r"\b[\w']+\b", story_title)} if story_title else set()
        lower_word_set = set(lower_words)
        title_overlap = len(title_tokens & lower_word_set) / max(1, len(title_tokens)) if title_tokens else 0.0

        segment_size = max(1, len(lower_words) // 10)
        intro_tokens = lower_words[:segment_size]
        outro_tokens = lower_words[-segment_size:] if segment_size else []

        def _segment_sentiment(tokens: List[str]) -> Tuple[float, float]:
            if not tokens:
                return 0.0, 0.0
            pos = sum(1 for w in tokens if w in _POSITIVE_LEXICON)
            neg = sum(1 for w in tokens if w in _NEGATIVE_LEXICON)
            total = len(tokens)
            balance = (pos - neg) / max(1, total)
            magnitude = (pos + neg) / max(1, total)
            return balance, magnitude

        intro_balance, intro_magnitude = _segment_sentiment(intro_tokens)
        outro_balance, outro_magnitude = _segment_sentiment(outro_tokens)

        features: Dict[str, float] = {
            'txt_log_word_count': math.log1p(word_count),
            'txt_log_char_count': math.log1p(char_count),
            'txt_chars_per_word': chars_per_word,
            'txt_avg_sentence_length': avg_sentence_len,
            'txt_sentence_count': float(sentence_count),
            'txt_paragraph_density': paragraph_density,
            'txt_paragraph_avg_sentence': paragraph_avg_sentence,
            'txt_paragraph_count_per_k': paragraph_count / max(1.0, word_count / 1000.0),
            'txt_dialogue_ratio': dialogue_ratio,
            'txt_dialogue_turns': float(quote_pairs),
            'txt_dialogue_word_ratio': dialogue_word_ratio,
            'txt_dialogue_narration_ratio': dialogue_narration_ratio,
            'txt_unique_ratio': unique_ratio,
            'txt_exclam_density': exclam_density,
            'txt_question_density': question_density,
            'txt_punctuation_density': punctuation_density,
            'txt_sentence_length_std': sentence_std,
            'txt_sentence_length_median': sentence_median,
            'txt_long_sentence_ratio': long_sentence_ratio,
            'txt_sentence_variation_ratio': sentence_variation_ratio,
            'txt_capitalized_ratio': capitalized_ratio,
            'txt_named_entity_count': float(unique_named_entities),
            'txt_named_entity_density': unique_named_entities / max(1, sentence_count),
            'txt_word_length_mean': word_len_mean,
            'txt_word_length_std': word_len_std,
            'txt_sentiment_balance': sentiment_balance,
            'txt_sentiment_magnitude': sentiment_magnitude,
            'txt_sentiment_polarity': sentiment_polarity,
            'txt_positive_ratio': pos_count / max(1, len(lower_words)),
            'txt_negative_ratio': neg_count / max(1, len(lower_words)),
            'txt_stopword_ratio': stopword_ratio,
            'txt_numeric_token_ratio': numeric_tokens / max(1, len(lower_words)),
            'txt_hapax_ratio': hapax_ratio,
            'txt_dis_legomena_ratio': dis_legomena_ratio,
            'txt_word_entropy': word_entropy,
            'txt_paragraph_word_mean': para_mean,
            'txt_paragraph_word_std': para_std,
            'txt_title_overlap_ratio': title_overlap,
            'txt_intro_sentiment_balance': intro_balance,
            'txt_intro_sentiment_magnitude': intro_magnitude,
            'txt_outro_sentiment_balance': outro_balance,
            'txt_outro_sentiment_magnitude': outro_magnitude,
            'txt_sentiment_balance_delta': outro_balance - intro_balance,
            'txt_sentiment_magnitude_delta': outro_magnitude - intro_magnitude,
        }

        # 追加 genre 特徵（以全文推論，不依賴外部資訊）
        info = genre_info
        try:
            if info is None and self.genre_detector:
                info = self.genre_detector.detect(text, story_title)
        except Exception:
            info = None

        if isinstance(info, dict):
            confidence = float(info.get('confidence', 0.0) or 0.0)
            features['txt_genre_confidence'] = confidence
            scores = info.get('scores') if isinstance(info.get('scores'), dict) else {}
            for genre_name, score in scores.items():
                try:
                    features[f'txt_genre_{genre_name}'] = float(score)
                except (TypeError, ValueError):
                    continue
        else:
            features['txt_genre_confidence'] = 0.0

        # 可選的文本統計（供教師或診斷使用）
        min_sentence_len = min((len(s.split()) for s in sentences), default=0)
        max_sentence_len = max((len(s.split()) for s in sentences), default=0)
        features['txt_min_sentence_length'] = float(min_sentence_len)
        features['txt_max_sentence_length'] = float(max_sentence_len)

        # 若 metadata 已含詞數，確保一致性（用於教師特徵）
        if isinstance(metadata, dict):
            metadata.setdefault('word_count', word_count)

        # Longformer 嵌入統計
        lf_features = self._compute_longformer_features(story_text)
        if lf_features:
            features.update(lf_features)

        return features

    def _compute_longformer_features(self, story_text: str) -> Dict[str, float]:
        """使用 Longformer 產生全文嵌入統計特徵。"""
        if not story_text or not isinstance(story_text, str):
            return {}
        if not self._ensure_longformer_model():
            return {}

        try:
            import torch
        except Exception:
            return {}

        tokenizer = self.longformer_tokenizer
        model = self.longformer_model
        if tokenizer is None or model is None:
            return {}

        try:
            token_ids = tokenizer.encode(story_text, add_special_tokens=False)
        except Exception:
            return {}

        if not token_ids:
            return {}

        max_len = 4000
        chunks = [token_ids[i:i + max_len] for i in range(0, len(token_ids), max_len)]
        embeddings: List[torch.Tensor] = []

        try:
            for chunk in chunks:
                input_ids = torch.tensor([
                    tokenizer.build_inputs_with_special_tokens(chunk)
                ], device=self.longformer_device)
                attention_mask = torch.ones_like(input_ids, device=self.longformer_device)
                global_mask = torch.zeros_like(input_ids, device=self.longformer_device)
                global_mask[:, 0] = 1
                with torch.no_grad():
                    outputs = model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        global_attention_mask=global_mask
                    )
                cls_embed = outputs.last_hidden_state[:, 0, :].detach().cpu().float().squeeze(0)
                embeddings.append(cls_embed)
        except Exception:
            return {}

        if not embeddings:
            return {}

        emb_stack = torch.stack(embeddings)  # [num_chunks, hidden]
        norms = torch.norm(emb_stack, dim=1)
        norm_mean = norms.mean().item()
        norm_std = norms.std(unbiased=False).item() if emb_stack.size(0) > 1 else 0.0

        if emb_stack.size(0) > 1:
            # 連續 chunk 的餘弦相似度
            cos = torch.nn.functional.cosine_similarity(
                emb_stack[:-1], emb_stack[1:], dim=1
            )
            cos_consec_mean = cos.mean().item()
            cos_consec_std = cos.std(unbiased=False).item() if cos.numel() > 1 else 0.0
            global_mean_vec = emb_stack.mean(dim=0, keepdim=True)
            global_norm = torch.norm(global_mean_vec, dim=1).clamp_min(1e-6)
            centered = emb_stack - global_mean_vec
            spread = torch.norm(centered, dim=1)
            spread_mean = spread.mean().item()
            spread_std = spread.std(unbiased=False).item() if spread.numel() > 1 else 0.0
            cos_to_global = torch.nn.functional.cosine_similarity(
                emb_stack,
                global_mean_vec.expand_as(emb_stack),
                dim=1
            )
            cos_global_mean = cos_to_global.mean().item()
            cos_global_std = cos_to_global.std(unbiased=False).item() if cos_to_global.numel() > 1 else 0.0
        else:
            cos_consec_mean = 1.0
            cos_consec_std = 0.0
            spread_mean = 0.0
            spread_std = 0.0
            cos_global_mean = 1.0
            cos_global_std = 0.0

        return {
            'txt_lf_chunk_count': float(len(embeddings)),
            'txt_lf_norm_mean': float(norm_mean),
            'txt_lf_norm_std': float(norm_std),
            'txt_lf_cosine_consecutive_mean': float(cos_consec_mean),
            'txt_lf_cosine_consecutive_std': float(cos_consec_std),
            'txt_lf_spread_mean': float(spread_mean),
            'txt_lf_spread_std': float(spread_std),
            'txt_lf_cosine_global_mean': float(cos_global_mean),
            'txt_lf_cosine_global_std': float(cos_global_std),
        }

    @staticmethod
    def _pearson_correlation(x_values: List[float], y_values: List[float]) -> float:
        """計算皮爾遜相關係數"""
        n = len(x_values)
        if n < 2:
            return 0.0

        mean_x = mean(x_values)
        mean_y = mean(y_values)

        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
        sum_sq_x = sum((x - mean_x) ** 2 for x in x_values)
        sum_sq_y = sum((y - mean_y) ** 2 for y in y_values)

        denominator = math.sqrt(sum_sq_x * sum_sq_y)
        if denominator == 0:
            return 0.0
        return numerator / denominator

    def _extract_confidence_from_result(self, result: Dict[str, Any]) -> float:
        """抽取維度信心值並統一為 0~1。"""
        if not isinstance(result, dict):
            return 0.6

        confidence_paths = [
            ['coherence', 'scores', 'confidence'],
            ['children_readability', 'scores', 'confidence'],
            ['children_readability', 'ai_analysis', 'confidence'],
            ['emotional_impact', 'scores', 'confidence'],
            ['emotional_impact', 'ai_analysis', 'confidence'],
            ['consistency', 'scores', 'confidence'],
            ['completeness', 'scores', 'confidence'],
            ['factuality', 'scores', 'confidence'],
            ['factuality', 'ai_analysis', 'confidence'],
            ['meta', 'confidence'],
            ['_normalized', 'confidence'],
            ['confidence'],
        ]

        raw_value: Optional[float] = None
        for path in confidence_paths:
            try:
                value: Any = result
                for key in path:
                    value = value[key]
                if isinstance(value, (int, float)):
                    raw_value = float(value)
                    break
            except (KeyError, TypeError):
                continue

        if raw_value is None:
            return 0.6
        if raw_value > 1.0:
            return normalize_confidence_0_1(raw_value / 100.0, 0.6)
        return normalize_confidence_0_1(raw_value, 0.6)
    
    def _generate_comprehensive_recommendations(self, dimension_results: List[DimensionResult],
                                               overall_score: Optional[float] = None) -> List[str]:
        """依維度表現與整體分數生成自然語言建議清單。"""
        recommendations = []
        
        # 按優先級排序維度結果
        sorted_results = sorted(dimension_results, key=lambda x: x.score)
        
        # 關鍵問題建議
        critical_issues = [r for r in dimension_results if r.score < 50]
        if critical_issues:
            recommendations.append(f"🚨 發現 {len(critical_issues)} 個關鍵問題維度需要優先處理")
            for result in critical_issues[:3]:
                recommendations.append(f"   - {result.dimension}: {result.suggestions[0] if result.suggestions else '需要改進'}")
        
        # 中等問題建議
        moderate_issues = [r for r in dimension_results if 50 <= r.score < 75]
        if moderate_issues:
            recommendations.append(f"⚠️ {len(moderate_issues)} 個維度有改進空間")
        
        # 優秀表現
        good_results = [r for r in dimension_results if r.score >= 85]
        if good_results:
            recommendations.append(f"✅ {len(good_results)} 個維度表現優秀")
        
        # 降級警告
        degraded_results = [r for r in dimension_results if r.status == 'degraded']
        if degraded_results:
            recommendations.append(f"📉 {len(degraded_results)} 個維度因文檔缺失而降級評估")
        
        # 失敗警告
        failed_results = [r for r in dimension_results if r.status == 'failed']
        if failed_results:
            recommendations.append(f"❌ {len(failed_results)} 個維度評估失敗")
        
        # 整體建議
        if overall_score is None:
            overall_score = self._calculate_overall_score(dimension_results)
        if overall_score >= 90:
            recommendations.append("🎉 故事整體質量優秀，可以考慮發布")
        elif overall_score >= 75:
            recommendations.append("👍 故事質量良好，建議進行小幅調整")
        elif overall_score >= 60:
            recommendations.append("📝 故事有潛力，建議重點改進低分維度")
        else:
            recommendations.append("🔧 故事需要大幅改進，建議全面檢查")
        
        return recommendations
    
    def _generate_processing_summary(self, dimension_results: List[DimensionResult], 
                                   total_time: float) -> Dict:
        """彙整處理時間與成功率等統計資訊，供報告記錄。"""
        return {
            "total_processing_time": round(total_time, 2),
            "dimensions_processed": len(dimension_results),
            "successful_dimensions": len([r for r in dimension_results if r.status == 'success']),
            "degraded_dimensions": len([r for r in dimension_results if r.status == 'degraded']),
            "failed_dimensions": len([r for r in dimension_results if r.status == 'failed']),
            "average_dimension_time": round(sum(r.processing_time for r in dimension_results) / len(dimension_results), 2) if dimension_results else 0,
            "total_issues_found": sum(r.issues_count for r in dimension_results),
            "total_suggestions_generated": sum(len(r.suggestions) for r in dimension_results)
        }
    
    
    def get_processing_statistics(self) -> Dict:
        """返回自啟動以來的累積處理統計。"""
        return self.processing_stats.copy()
    
    def export_report(self, report: MultiAspectReport, output_path: str, format: str = 'json') -> bool:
        """將評估報告輸出為指定格式，目前支援 JSON。"""
        try:
            if format.lower() == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(self._report_to_dict(report), f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"不支持的格式: {format}")
            
            return True
        except Exception as e:
            logger.exception("❌ 報告導出失敗: %s", e)
            return False
    
    def _report_to_dict(self, report: MultiAspectReport) -> Dict:
        """把報告資料類型轉換為可序列化的原生字典。"""
        return {
            "story_title": report.story_title,
            "overall_score": report.overall_score,
            "overall_score_raw": report.overall_score_raw,
            "overall_score_calibrated": report.overall_score_calibrated,
            # 結構化的分數區塊（易讀命名），同時保留相容欄位於頂層
            "score": {
                "base": report.overall_score_raw,              # 模型加權分（未對齊）
                "aligned": report.overall_score_calibrated     # 對齊後分
            },
            "dimension_scores": report.dimension_scores,
            "dimension_results": [
                {
                    "dimension": r.dimension,
                    "score": r.score,
                    "issues_count": r.issues_count,
                    "suggestions": r.suggestions,
                    "processing_time": r.processing_time,
                    "status": r.status,
                    "degradation_info": r.degradation_info
                }
                for r in report.dimension_results
            ],
            "processing_summary": report.processing_summary,
            "degradation_report": {
                k: v.to_dict()
                for k, v in report.degradation_report.items()
            } if report.degradation_report else {},
            "recommendations": report.recommendations,
            "branch_id": getattr(report, "branch_id", "canonical"),
            "source_document": getattr(report, "source_document", None),
            "story_metadata": getattr(report, "story_metadata", None),
            "evaluation_scope": getattr(report, "evaluation_scope", "canonical"),
            "timestamp": report.timestamp,
            "alignment": report.alignment_details or {}
        }
    
    def quick_evaluate(self, story_text: str, story_title: str = "Story") -> Dict:
        """以單段文本快速評估基礎維度，適合開發或 Demo 使用。"""
        # 創建模擬文檔來源
        mock_doc = DocumentSource(
            doc_type="full_story.txt",
            file_path="memory://story_text",
            weight=1.0,
            available=True,
            content=story_text,
            error=None
        )
        
        # 手動設置文檔快取
        self.source_manager.registered_documents = {"full_story.txt": "memory://story_text"}
        self.source_manager.document_cache = {"full_story.txt": mock_doc}
        
        # 只評估核心維度（避免載入太多模型）
        core_dimensions = ['entity_consistency']  # 只用一個維度，節省記憶體
        
        try:
            report = self.evaluate_story(
                document_paths={"full_story.txt": "memory://story_text"},
                story_title=story_title,
                enabled_dimensions=core_dimensions
            )
            
            return {
                "overall_score": report.overall_score,
                "dimension_scores": report.dimension_scores,
                "key_issues": sum(r.issues_count for r in report.dimension_results),
                "recommendations": report.recommendations[:3],
                "processing_time": report.processing_summary["total_processing_time"]
            }
        except Exception as e:
            return {
                "overall_score": 0.0,
                "dimension_scores": {},
                "key_issues": 1,
                "recommendations": [f"評估失敗: {str(e)}"],
                "processing_time": 0.0
            }
    
    def evaluate_story_directory(
        self,
        story_dir: str,
        story_title: str = None,
        *,
        branch_mode: str = "canonical",
    ) -> MultiAspectReport:
        """直接指定故事資料夾進行評估，會自動偵測標準檔案結構。"""
        import os
        
        if story_title is None:
            story_title = os.path.basename(story_dir)
        
        # 自動檢測文檔
        document_paths = self.auto_detect_story_documents(story_dir, branch_mode=branch_mode)
        
        if not document_paths:
            raise ValueError(f"在目錄 {story_dir} 中未找到任何故事文檔")
        
        logger.info("📁 檢測到文檔: %s", list(document_paths.keys()))

        resolved_branch = branch_mode if branch_mode not in {"", "all", "*"} else "canonical"
        source_document = document_paths.get("full_story.txt") if isinstance(document_paths.get("full_story.txt"), str) else None
        
        return self.evaluate_story(
            document_paths=document_paths,
            story_title=story_title,
            branch_id=resolved_branch,
            source_document=source_document,
            evaluation_scope=branch_mode,
        )