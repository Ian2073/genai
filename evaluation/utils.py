# =============================================================================
# utils.py - 共用工具函數模組
# =============================================================================
#
# 【模組概述】
# 提供整個評估系統共用的工具函數，包括：
# 1. 環境變數讀取與解析（支援多種資料類型）
# 2. SpaCy NLP 模型載入與管理
# 3. 文本分句處理
# 4. 維度名稱標準化
#
# 【設計原則】
# - 函數簡單、單一職責
# - 支援環境變數配置，提高靈活性
# - 提供合理的預設值，開箱即用
# - 失敗時優雅降級，不會導致系統崩潰
#
# =============================================================================

from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, TypeVar

import spacy

T = TypeVar("T")

# =============================================================================
# 預設配置常數
# =============================================================================

DEFAULT_ASPECTS: List[str] = [
    "entity_consistency",  # 實體一致性：檢查角色、地點等命名的一致性
    "completeness",        # 完整性：評估故事結構的完整度
    "coherence",          # 連貫性：檢查情節邏輯和流暢度
    "readability",        # 可讀性：評估語言適讀性
    "emotional_impact",   # 情感影響力：分析情感表達的感染力
    "factuality",         # 事實正確性：驗證事實陳述的準確性
]


# =============================================================================
# 環境變數讀取函數
# =============================================================================

def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    讀取環境變數並去除前後空白
    
    這是所有環境變數讀取函數的基礎，提供統一的處理邏輯：
    1. 讀取環境變數
    2. 去除前後空白
    3. 若為空字串則返回預設值
    
    參數:
        name: 環境變數名稱
        default: 預設值（當環境變數不存在或為空時使用）
        
    返回:
        環境變數的值（已去除空白），若不存在則返回預設值
        
    範例:
        >>> os.environ['MY_VAR'] = '  hello  '
        >>> get_env('MY_VAR')
        'hello'
        >>> get_env('NON_EXISTENT', 'default')
        'default'
    """
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def get_bool_env(name: str, default: bool = False) -> bool:
    """
    從環境變數讀取布林值
    
    支援多種常見的布林值表示方式，不區分大小寫：
    - True: "true", "1", "yes", "y", "on"
    - False: 其他所有值
    
    參數:
        name: 環境變數名稱
        default: 預設值（當環境變數不存在時使用）
        
    返回:
        布林值
        
    範例:
        >>> os.environ['ENABLE_FEATURE'] = 'true'
        >>> get_bool_env('ENABLE_FEATURE')
        True
        >>> os.environ['ENABLE_FEATURE'] = 'YES'
        >>> get_bool_env('ENABLE_FEATURE')
        True
        >>> get_bool_env('NON_EXISTENT', False)
        False
    """
    raw = get_env(name)
    if raw is None:
        return default
    return raw.lower() in {"true", "1", "yes", "y", "on"}


def get_int_env(name: str, default: int) -> int:
    """
    從環境變數讀取整數值
    
    嘗試將環境變數轉換為整數，若轉換失敗則返回預設值。
    這個設計確保系統不會因為配置錯誤而崩潰。
    
    參數:
        name: 環境變數名稱
        default: 預設值（當環境變數不存在或無法轉換時使用）
        
    返回:
        整數值
        
    範例:
        >>> os.environ['MAX_WORKERS'] = '4'
        >>> get_int_env('MAX_WORKERS', 1)
        4
        >>> os.environ['MAX_WORKERS'] = 'invalid'
        >>> get_int_env('MAX_WORKERS', 1)
        1
    """
    raw = get_env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_float_env(name: str, default: float) -> float:
    """
    從環境變數讀取浮點數值
    
    嘗試將環境變數轉換為浮點數，若轉換失敗則返回預設值。
    
    參數:
        name: 環境變數名稱
        default: 預設值（當環境變數不存在或無法轉換時使用）
        
    返回:
        浮點數值
        
    範例:
        >>> os.environ['THRESHOLD'] = '0.85'
        >>> get_float_env('THRESHOLD', 0.5)
        0.85
        >>> os.environ['THRESHOLD'] = 'invalid'
        >>> get_float_env('THRESHOLD', 0.5)
        0.5
    """
    raw = get_env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# =============================================================================
# 共用實例與配置工具
# =============================================================================

def ensure_instance(instance: Optional[T], factory: Callable[..., T], *args, **kwargs) -> T:
    """
    確保回傳可用的物件實例。

    若已傳入現有實例則直接返回，否則呼叫指定的 factory 建立新實例。
    這有助於統一模組內的依賴注入行為，避免重複撰寫相同的條件判斷。

    參數:
        instance: 現有實例或 None
        factory: 能建立實例的工廠函數或類別
        *args/**kwargs: 傳給 factory 的額外參數

    返回:
        可用的實例
    """
    if instance is not None:
        return instance
    return factory(*args, **kwargs)


def load_category_keywords(
    local_categories: Optional[Any],
    category: str,
    fallback: Optional[Iterable[str]] = None,
) -> List[str]:
    """
    從 LocalCategoryMatcher 取得關鍵字，若發生錯誤或缺值則套用備援清單。

    參數:
        local_categories: 具備 get_keywords 的匹配器，可為 None
        category: 要查詢的分類鍵值
        fallback: 當查無資料時使用的預設列表

    返回:
        關鍵字列表（淺拷貝），即使 fallback 為 None 也保證回傳列表
    """
    keywords: List[str] = []
    if local_categories is not None:
        try:
            keywords = list(local_categories.get_keywords(category) or [])
        except Exception:
            keywords = []

    if keywords:
        return keywords

    if fallback is not None:
        return list(fallback)

    return []


class SentenceSplitterMixin:
    """提供統一的分句行為，避免各模組重複定義。"""

    nlp: Optional["spacy.language.Language"] = None

    def _split_sentences(self, text: str) -> List[str]:
        return split_sentences(text, getattr(self, "nlp", None))


# =============================================================================
# 維度處理函數
# =============================================================================

def normalise_dimensions(
    dimensions: Optional[Iterable[str]], *, fallback: Sequence[str] = DEFAULT_ASPECTS
) -> List[str]:
    """
    標準化維度名稱列表
    
    將使用者提供的維度列表標準化：
    1. 若未提供維度，則使用預設的六大維度
    2. 若提供維度，則轉換為標準列表格式
    
    這個函數確保系統內部使用的維度名稱格式一致。
    
    參數:
        dimensions: 使用者提供的維度列表（可為 None）
        fallback: 當 dimensions 為 None 時使用的預設維度列表
        
    返回:
        標準化的維度名稱列表
        
    範例:
        >>> normalise_dimensions(None)
        ['entity_consistency', 'completeness', 'coherence', 'readability', 'emotional_impact', 'factuality']
        >>> normalise_dimensions(['coherence', 'readability'])
        ['coherence', 'readability']
    """
    return list(dimensions) if dimensions else list(fallback)


def get_model_root(default: str = "/app/models") -> str:
    """回傳模型根目錄，優先讀取 MODEL_ROOT 環境變數。"""
    model_root = get_env("MODEL_ROOT")
    if model_root:
        return model_root

    default_model_path = get_env("DEFAULT_MODEL_PATH")
    if default_model_path:
        return os.path.dirname(default_model_path.rstrip("/\\")) or default

    project_dir = Path(__file__).resolve().parent
    preferred_local = project_dir.parent / "models"
    legacy_local = project_dir / "models"
    candidates = [
        preferred_local,
        legacy_local,
        Path(default),
    ]
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_dir():
                return str(candidate)
        except Exception:
            continue

    # 本地優先：即使尚未建立也回傳工作區路徑，避免落到 /app/*。
    return str(preferred_local)


def get_kg_path(default: str = "/app/kg") -> str:
    """回傳知識圖譜根目錄，優先讀取 KG_PATH 環境變數。"""
    configured = get_env("KG_PATH")
    if configured:
        return configured

    project_dir = Path(__file__).resolve().parent
    preferred_local = project_dir.parent / "kg"
    candidates = [
        preferred_local,
        project_dir / "kg",
        Path(default),
    ]
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_dir():
                return str(candidate)
        except Exception:
            continue

    # 本地優先：即使尚未建立也回傳工作區路徑，避免落到 /app/*。
    return str(preferred_local)


def get_generation_kg_module_path(default: Optional[str] = None) -> str:
    """回傳新生成系統 `kg.py` 路徑，供舊評測系統優先載入。"""
    configured = get_env("GENERATION_KG_MODULE_PATH")
    if configured:
        return configured

    project_dir = Path(__file__).resolve().parent
    candidates = [
        project_dir.parent / "kg.py",
        project_dir / "kg.py",
    ]
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        except Exception:
            continue

    if default:
        return default
    return str(project_dir.parent / "kg.py")


def ensure_kg_module_importable(module_path: Optional[str] = None) -> Optional[str]:
    """確保 kg.py 所在目錄可被 import，回傳可用模組路徑。"""
    target = module_path or get_generation_kg_module_path()
    if not target:
        return None

    try:
        resolved = Path(target).resolve()
    except Exception:
        resolved = Path(target)

    if not resolved.exists() or not resolved.is_file():
        return None

    parent = str(resolved.parent)
    if parent and parent not in sys.path:
        sys.path.insert(0, parent)
    return str(resolved)


def resolve_model_path(model_name: str, *, model_root: Optional[str] = None) -> str:
    """將模型資料夾名稱解析為完整路徑。"""
    root = model_root or get_model_root()
    return os.path.join(root, model_name)


def get_default_model_path(default_model_name: str = "Qwen2.5-14B") -> str:
    """回傳預設 LLM 路徑，優先讀取 DEFAULT_MODEL_PATH。"""
    env_path = get_env("DEFAULT_MODEL_PATH")
    if env_path:
        env_candidate = Path(env_path)
        looks_like_local_path = (
            env_candidate.is_absolute()
            or env_path.startswith(".")
            or ("/" in env_path)
            or ("\\" in env_path)
        )
        if not looks_like_local_path:
            return env_path
        try:
            if env_candidate.exists():
                return env_path
        except Exception:
            pass

    # 將預設名稱映射到現有模型目錄，避免使用不存在的路徑。
    model_aliases = {
        "Qwen2.5-14B": [
            "Qwen2.5-14B",
            "Qwen2.5-14B-Instruct-GPTQ-Int4",
            "Qwen3.5-9B",
            "Qwen3-8B",
        ],
    }

    candidates = model_aliases.get(default_model_name, [default_model_name])
    for name in candidates:
        candidate_path = resolve_model_path(name)
        try:
            if Path(candidate_path).exists():
                return candidate_path
        except Exception:
            continue

    return resolve_model_path(default_model_name)


def get_semantic_model_candidates() -> List[str]:
    """回傳語義模型候選路徑列表。"""
    configured = get_env("SEMANTIC_MODEL_CANDIDATES")
    if configured:
        candidates = [item.strip() for item in configured.split(",") if item.strip()]
        if candidates:
            return candidates

    return [
        resolve_model_path("bge-large-zh-v1.5"),
        resolve_model_path("bge-m3"),
        resolve_model_path("all-mpnet-base-v2"),
    ]


# =============================================================================
# NLP 模型載入與管理
# =============================================================================

# SpaCy 模型優先級列表（從最強到最弱）
_DEFAULT_MODEL_NAMES: Iterable[str] = (
    "en_core_web_trf",  # Transformer 模型（最準確，但最慢）
    "en_core_web_lg",   # 大型模型（準確度高，速度適中）
    "en_core_web_md",   # 中型模型（平衡準確度與速度）
    "en_core_web_sm",   # 小型模型（速度快，但準確度較低）
)

# 本地模型目錄前綴（用於 Docker 容器環境）
_LOCAL_MODEL_DIR_PREFIX = "/app/models"


@lru_cache(maxsize=1)
def load_spacy_model(max_length: int = 5_000_000) -> "spacy.language.Language":
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import runtime.compat
        runtime.compat.prepare_evaluator_runtime()
    except Exception as e:
        pass
    
    """
    載入 spaCy NLP 模型（帶智能快取）
    
    這個函數實現了多層級的模型載入策略：
    1. 嘗試使用 GPU 加速（若可用）
    2. 按照優先級嘗試載入不同的模型
    3. 若都載入失敗，則建立空白的英文模型
    4. 使用 LRU 快取避免重複載入
    
    模型選擇策略：
    - 優先嘗試載入 Transformer 模型（最準確）
    - 若失敗，則嘗試大型、中型、小型模型
    - 若本地有模型檔案，則從本地載入
    - 最後才建立空白模型（基本功能）
    
    參數:
        max_length: 模型能處理的最大文本長度（字元數）
                   預設 5,000,000 字元（約 1,000 頁文字）
        
    返回:
        已載入的 spaCy Language 物件
        
    特性:
        - 使用 @lru_cache 確保同一程序中只載入一次
        - 自動偵測 GPU 並啟用加速
        - 容錯設計：即使所有模型都失敗，也能提供基本功能
        
    範例:
        >>> nlp = load_spacy_model()
        >>> doc = nlp("This is a sentence.")
        >>> for sent in doc.sents:
        ...     print(sent.text)
    """
    prefer_gpu = get_bool_env("SPACY_PREFER_GPU", True)
    require_gpu = get_bool_env("SPACY_REQUIRE_GPU", False)
    require_trf = get_bool_env("SPACY_REQUIRE_TRF", False)

    gpu_enabled = False
    if prefer_gpu or require_gpu:
        try:
            gpu_enabled = bool(spacy.prefer_gpu())
        except Exception:
            gpu_enabled = False

    if require_gpu and not gpu_enabled:
        raise RuntimeError("SPACY_REQUIRE_GPU=true 但 spaCy GPU 後端不可用")

    configured_priority = get_env("SPACY_MODEL_PRIORITY")
    if configured_priority:
        model_candidates = [item.strip() for item in configured_priority.split(",") if item.strip()]
    else:
        model_candidates = list(_DEFAULT_MODEL_NAMES)

    if require_trf:
        if "en_core_web_trf" not in model_candidates:
            model_candidates.insert(0, "en_core_web_trf")
        model_candidates = [name for name in model_candidates if name == "en_core_web_trf"]

    load_errors: List[str] = []
    for model_name in model_candidates:
        # 先嘗試套件模型，再嘗試本地掛載路徑
        for target in (model_name, f"{_LOCAL_MODEL_DIR_PREFIX}/{model_name}"):
            try:
                nlp = spacy.load(target)
                nlp.max_length = max_length
                setattr(nlp, "_loaded_model_name", model_name)
                setattr(nlp, "_gpu_enabled", gpu_enabled)
                return nlp
            except Exception as exc:
                load_errors.append(f"{target}: {exc}")

    if require_trf:
        err_preview = "; ".join(load_errors[:2]) if load_errors else "unknown error"
        raise RuntimeError(f"SPACY_REQUIRE_TRF=true 但 en_core_web_trf 載入失敗: {err_preview}")

    # 所有模型都載入失敗，建立空白英文模型（最基本功能）
    nlp = spacy.blank("en")
    nlp.max_length = max_length
    setattr(nlp, "_loaded_model_name", "blank_en")
    setattr(nlp, "_gpu_enabled", gpu_enabled)
    return nlp


# =============================================================================
# 文本處理函數
# =============================================================================

def split_sentences(text: str, nlp: Optional["spacy.language.Language"] = None) -> List[str]:
    """
    將文本分割成句子列表
    
    這個函數實現了兩層級的分句策略：
    1. 優先使用 spaCy 的句子分割器（基於機器學習，更準確）
    2. 若 spaCy 不可用或失敗，則使用正則表達式規則（簡單但可靠）
    
    分句規則（正則表達式模式）：
    - 以句號 (.)、驚嘆號 (!)、問號 (?) 結尾
    - 支援連續標點符號（如 "..."）
    
    參數:
        text: 要分割的文本
        nlp: 可選的 spaCy Language 物件，若未提供則不使用 spaCy
        
    返回:
        句子列表（已去除前後空白）
        
    特性:
        - 自動處理空文本
        - 自動去除前後空白
        - 過濾空句子
        - 優雅降級：spaCy 失敗時使用正則
        
    範例:
        >>> text = "Hello world! How are you? I'm fine."
        >>> sentences = split_sentences(text)
        >>> print(sentences)
        ['Hello world', 'How are you', "I'm fine"]
        
        >>> nlp = load_spacy_model()
        >>> sentences = split_sentences(text, nlp)
        >>> print(sentences)
        ['Hello world!', 'How are you?', "I'm fine."]
    """
    # 處理空文本
    if not text or not text.strip():
        return []

    text = text.strip()

    # 若提供了 spaCy 模型，則優先使用
    if nlp is not None and getattr(nlp, "pipe_names", None):
        doc = nlp(text)
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        if sentences:
            return sentences

    # 回退到正則表達式分句（簡單但可靠）
    # 以句號、驚嘆號、問號分割
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


# =============================================================================
# 數值與配置工具
# =============================================================================

def clamp_score(value: float, min_v: float = 0.0, max_v: float = 100.0) -> float:
    """將分數限制在指定範圍內，避免越界。

    - 非法輸入（無法轉成浮點）時回傳 min_v
    - 常用於最終分數或子分數裁切
    """
    try:
        return max(min_v, min(max_v, float(value)))
    except Exception:
        return min_v


def parse_weight_list(raw_list: List[str], default_weights: Dict[str, float]) -> Dict[str, float]:
    """將像 ['structural:0.35','semantic:0.25',...] 的字串列表解析為權重字典並正規化。

    規則：
    - 忽略格式錯誤的項目
    - 若結果為空或總和<=0，回傳 default_weights
    - 會依 default_weights 的鍵順序回傳，缺值以 default 填補再正規化
    """
    try:
        parsed: Dict[str, float] = {}
        for item in raw_list or []:
            if not isinstance(item, str) or ':' not in item:
                continue
            k, v = item.split(':', 1)
            k = k.strip()
            try:
                parsed[k] = float(v)
            except Exception:
                continue
        # 以 default 的鍵構建並正規化
        if not parsed:
            return dict(default_weights)
        total = sum(parsed.get(k, default_weights.get(k, 0.0)) for k in default_weights.keys())
        if total <= 0:
            return dict(default_weights)
        return {k: (parsed.get(k, default_weights.get(k, 0.0)) / total) for k in default_weights.keys()}
    except Exception:
        return dict(default_weights)


def normalize_keywords(keywords: List[str]) -> List[str]:
    """將關鍵字清單做小寫、去頭尾、去重的標準化處理。

    - 忽略非字串項
    - 保留輸入順序的第一個出現（透過 seen 集合）
    """
    normalized: List[str] = []
    seen: Set[str] = set()
    for kw in keywords or []:
        if not isinstance(kw, str):
            continue
        lowered = kw.strip().lower()
        if lowered and lowered not in seen:
            seen.add(lowered)
            normalized.append(lowered)
    return normalized


def get_iso_timestamp() -> str:
    """取得現在時間的 ISO 8601 字串。"""
    from datetime import datetime
    return datetime.now().isoformat()


# =============================================================================
# 文件選擇與合併工具（跨模組共用）
# =============================================================================

def select_documents_by_matrix(
    available_documents: Dict[str, str],
    selection_matrix: Dict[str, Any],
    min_primary: int = 2,
) -> Dict[str, str]:
    """依據 selection_matrix 從 available_documents 中挑選文件。

    規則（與各模組現行邏輯一致）：
    - 先挑選 primary 中存在的文件
    - 若選到的文件數量小於 min_primary，則依序補上 secondary 中存在且未被選過的文件
    - 忽略 excluded

    參數:
        available_documents: 可用文件名 -> 內容
        selection_matrix: 形如 {'primary': [...], 'secondary': [...], 'excluded': [...]} 的設定
        min_primary: 若主要文件不足時，最小保底的選取數量（透過 secondary 補齊）

    返回:
        已選取的文件名 -> 內容 字典
    """
    selected: Dict[str, str] = {}
    if not available_documents:
        return selected

    primary = list(selection_matrix.get('primary', []) or [])
    secondary = list(selection_matrix.get('secondary', []) or [])
    excluded: Set[str] = set(selection_matrix.get('excluded', []) or [])

    # 先選 primary
    for name in primary:
        if name in available_documents and name not in excluded:
            selected[name] = available_documents[name]

    # 不足則補 secondary
    if len(selected) < min_primary:
        for name in secondary:
            if name in available_documents and name not in selected and name not in excluded:
                selected[name] = available_documents[name]
            if len(selected) >= min_primary:
                break

    return selected


def combine_documents_by_weight(
    documents: Dict[str, str],
    weights: Optional[Dict[str, float]] = None,
    *,
    default_weight: float = 0.1,
    include_headers: bool = True,
) -> str:
    """依據權重合併多個文件為單一字串。

    - 會依照權重由大至小排序
    - 權重缺失者使用 default_weight
    - include_headers=True 時會在每段前加上標頭，包含文件名與權重
    """
    if not documents:
        return ""

    if not weights:
        # 沒有權重就直接合併
        return "\n\n".join([c for c in documents.values() if c and c.strip()])

    triples = []  # (weight, name, content)
    for name, content in documents.items():
        if not content or not content.strip():
            continue
        w = float(weights.get(name, default_weight)) if isinstance(weights, dict) else default_weight
        triples.append((w, name, content))

    # 權重由大到小
    triples.sort(key=lambda x: x[0], reverse=True)

    parts: List[str] = []
    for w, name, content in triples:
        if include_headers:
            parts.append(f"=== {name} (權重: {w:.2f}) ===\n{content}")
        else:
            parts.append(content)

    return "\n\n".join(parts)
