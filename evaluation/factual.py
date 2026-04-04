# factuality.py - 六維度故事評估系統 - 事實正確性維度
# 用途：從故事文本中以 NER 為主抽取可驗證聲明（claims），再以本地知識/維基百科/AI 驗證，輸出分數與建議。
# 重點：
# - _extract_factual_claims：逐句執行 NER，整句作為候選聲明，推斷類型與可驗證性
# - _verify_single_claim：本地知識 → 維基百科 → AI →（可選）網路搜尋 的級聯驗證
# - _calculate_factuality_scores：整合準確度/覆蓋/風險/AI 得到最終分
import logging
import re
import os
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Union
import yaml
from consistency import ComprehensiveKnowledgeGraph, AIAnalyzer
from utils import (
    SentenceSplitterMixin,
    ensure_instance,
    get_bool_env,
    get_default_model_path,
    get_env,
    get_kg_path,
    load_spacy_model,
)
from shared.ai_safety import (
    get_dimension_fallback_score,
    normalize_confidence_0_1,
    normalize_score_0_100,
)

logger = logging.getLogger(__name__)
FACTUAL_AI_FALLBACK_SCORE = get_dimension_fallback_score("factuality")
# 直接使用多知識庫系統，不再依賴維基百科API
try:
    from kb import MultiKnowledgeBase, KnowledgeResult
    MULTI_KB_AVAILABLE = True
except ImportError:
    MULTI_KB_AVAILABLE = False
    logger.warning("多知識庫系統不可用，事實檢測功能將受限")
from concurrent.futures import ThreadPoolExecutor

@dataclass
class FactualClaim:
    claim_id: str
    text: str
    claim_type: str  # 'factual', 'numerical', 'temporal', 'geographical', 'scientific'
    confidence: float
    context: str
    location: str  # 在文本中的位置
    verifiable: bool
    # 新增：NER 與三元組、實體連結（更科學、可重現）
    entities: List[Tuple[str, str]] = None  # [(text, label)]
    triples: List[Tuple[str, str, str]] = None  # [(subject, relation/verb, object)]
    links: Dict[str, Dict[str, str]] = None  # entity_text -> {title, url}

@dataclass
class FactCheckResult:
    claim: FactualClaim
    verdict: str  # 'supported', 'refuted', 'unverifiable', 'uncertain'
    evidence: List[str]
    confidence: float
    sources: List[str]
    risk_level: str  # 'low', 'medium', 'high', 'critical'

@dataclass
class FactualityScores:
    claim_accuracy: float
    verification_coverage: float
    risk_assessment: float
    final: float

class FactualityChecker(SentenceSplitterMixin):
    # 事實正確性檢測器（六維度故事評估系統 - 事實驗證維度）
    def __init__(self, 
                 kg_path: str = get_kg_path(),
                 model_path: str = get_default_model_path("Qwen2.5-14B"),
                 use_multiple_ai_prompts: bool = False,
                 enable_web_search: bool = False,
                 enable_wikipedia: bool = True,
                 wikipedia_language: str = "zh",
                 verify_fictional_characters: bool = False,
                 ai: AIAnalyzer = None,
                 kg: ComprehensiveKnowledgeGraph = None,
                 nlp=None,
                 # 效能與啟用選項
                 enable_ai_gating: bool = False,
                 ai_gating_max_calls_per_doc: int = 50,
                 perform_wiki_linking_in_extraction: bool = False,
                 spacy_pipe_batch_size: int = None,  # 🚀 優化：動態批次大小
                 spacy_pipe_n_process: int = 1,
                 verify_max_workers: Optional[int] = None,
                 verbose: bool = False,
                 # 新增效能監控選項
                 enable_performance_logging: bool = True,
                 enable_progress_tracking: bool = True):
        # 簡單流程（事實怎麼驗）：
        # 1) 找句子 → 抽取可驗證聲明（人名/地名/數字/時間）
        # 2) 先看本地知識，再問多知識庫（Wikidata/DBpedia）
        # 3) 仍不確定才用 AI 輔助
        # 4) 合併結果，計算「準確/覆蓋/風險」三項，得最終分
        # 載入核心工具：知識圖譜 + AI分析器 + 語言處理器
        self.kg = ensure_instance(kg, ComprehensiveKnowledgeGraph, kg_path)
        self.ai = ensure_instance(ai, AIAnalyzer, model_path, use_multiple_ai_prompts)
        self.nlp = ensure_instance(nlp, load_spacy_model)
        self.logger = logging.getLogger(__name__)
        # 讀取環境變數：FACT_VERBOSE, FACT_NPROC, FACT_BATCH, FACT_VERIFY_WORKERS, FACT_SKIP_VERIFICATION
        verbose_raw = get_env('FACT_VERBOSE', '') or ''
        env_verbose = verbose_raw.lower() in {'1', 'true', 'yes', 'on'}
        self.verbose = verbose or env_verbose
        
        # 智能快速模式：保持準確性但優化性能
        self.fast_mode = get_bool_env('FACT_FAST_MODE', False)
        
        # 移除聲明數量限制，檢測所有事實聲明
        self.max_claims = 1000  # 設置一個很大的數值，實際不會達到
            
        # 移除句子數量限制，處理所有句子
        self.max_sentences = 10000  # 設置一個很大的數值，實際不會達到
        
        # 效能監控設定
        self.enable_performance_logging = enable_performance_logging
        self.enable_progress_tracking = enable_progress_tracking
        self.performance_stats = {
            'extraction_time': 0.0,
            'verification_time': 0.0,
            'ai_analysis_time': 0.0,
            'total_claims_processed': 0,
            'wikipedia_queries': 0,
            'ai_calls': 0
        }
        
        # 🚀 智能快取機制
        self._claim_cache = {}  # 聲明抽取快取
        self._verification_cache = {}  # 驗證結果快取
        self._entity_cache = {}  # 實體識別快取
        self._local_category_cache: Optional[Dict[str, List[str]]] = None
        self._local_category_config_path = os.path.join(
            os.path.dirname(__file__),
            "config",
            "local_categories.yaml",
        )
        
        # 驗證選項設定
        self.enable_web_search = enable_web_search # 是否啟用網路搜尋
        self.enable_wikipedia = enable_wikipedia # 是否啟用維基百科驗證
        self.verify_fictional_characters = verify_fictional_characters # 是否驗證虛構角色
        
        # 效能控制配置
        self.enable_ai_gating = enable_ai_gating # AI呼叫次數限制
        self.ai_gating_max_calls_per_doc = ai_gating_max_calls_per_doc
        self._ai_gating_calls_used = 0 # 已使用的AI呼叫次數
        self.perform_wiki_linking_in_extraction = perform_wiki_linking_in_extraction
        # 批次與並行（允許環境變更覆蓋）
        env_batch = get_env('FACT_BATCH')
        if env_batch and env_batch.isdigit():
            try:
                spacy_pipe_batch_size = max(1, int(env_batch))
            except Exception:
                pass
        env_nproc = get_env('FACT_NPROC')
        if env_nproc and env_nproc.isdigit():
            try:
                spacy_pipe_n_process = max(1, int(env_nproc))
            except Exception:
                pass
        # 讀取環境覆寫（FACT_BATCH, FACT_NPROC）
        # 動態批次大小優化
        env_batch = get_env('EVAL_BATCH_SIZE', get_env('FACT_BATCH', '') or '')
        if env_batch and env_batch.isdigit():
            try:
                base_batch_size = max(32, int(env_batch))
                # 快速模式下使用更大批次以提升GPU利用率
                fast_mode_enabled = get_bool_env('EVAL_FAST_MODE', False)
                if fast_mode_enabled:
                    spacy_pipe_batch_size = min(base_batch_size * 2, 2048)
                else:
                    spacy_pipe_batch_size = base_batch_size
            except Exception:
                pass
        env_nproc = get_env('FACT_NPROC', '')
        if env_nproc and env_nproc.isdigit():
            try:
                spacy_pipe_n_process = max(1, int(env_nproc))
            except Exception:
                pass

        # 避免多進程死鎖：只在明確設定時才使用多進程
        # 如果 FACT_NPROC=1 或未設定，強制使用單進程
        if spacy_pipe_n_process == 1:
            spacy_pipe_n_process = 1  # 強制單進程，避免死鎖
        self.spacy_pipe_batch_size = spacy_pipe_batch_size # 批次處理大小
        self.spacy_pipe_n_process = spacy_pipe_n_process # 並行處理數
        # 驗證階段的執行緒數
        env_vw = get_env('FACT_VERIFY_WORKERS')
        if verify_max_workers is None and env_vw and env_vw.isdigit():
            try:
                verify_max_workers = max(1, int(env_vw))
            except Exception:
                pass
        if verify_max_workers is None:
            cpu_count = os.cpu_count() or 1
            # 🚀 優化並行處理：根據GPU可用性動態調整執行緒數
            import torch
            if torch.cuda.is_available():
                # GPU加速時可以支持更多並行處理
                verify_max_workers = max(12, min(24, int(cpu_count * 2.0)))
            else:
                # CPU模式使用保守設定
                verify_max_workers = max(8, min(16, int(cpu_count * 1.0)))
        self.verify_max_workers = verify_max_workers
        
        # 初始化多知識庫事實檢查器（替代維基百科）
        if MULTI_KB_AVAILABLE:
            try:
                self.multi_kb = MultiKnowledgeBase()
                self.logger.info("✅ 多知識庫事實檢查器初始化成功 (Wikidata + DBpedia)")
                self.enable_wikipedia = True  # 啟用事實檢查功能
            except Exception as e:
                self.logger.warning("⚠️ 多知識庫事實檢查器初始化失敗: %s", e)
                self.enable_wikipedia = False
                self.multi_kb = None
        else:
            self.multi_kb = None
            self.enable_wikipedia = False
            self.logger.warning("⚠️ 多知識庫系統不可用，事實檢測功能將受限")

        # 根據文本語言動態切換維基語言（僅在英文內容時使用 en）
        self.detect_language_for_wiki = True
        
        # 🚨 高風險聲明模式（英文）
        self.high_risk_patterns_en = [
            r'\b(?:always|never|all|none|every|no)\s+(?:\w+\s+){0,3}(?:are|is|do|does|have|has|can|cannot|will|won\'t)\b',
            r'\b(?:definitely|certainly|absolutely|guaranteed|proven|fact|truth|reality)\b',
            r'\b(?:causes?|leads?\s+to|results?\s+in|prevents?|cures?|treats?)\s+(?:\w+\s+){0,2}(?:cancer|disease|illness|death)\b',
            r'\b(?:studies?\s+show|research\s+proves|scientists?\s+say|experts?\s+claim)\b'
        ]
        # 🚨 高風險聲明模式（中文）
        self.high_risk_patterns_zh = [
            r'(總是|從不|所有|沒有|每個|一定|絕對)',
            r'(證明|鐵證|事實|真相|現實|毋庸置疑)',
            r'(導致|造成|引發|導向|預防|治療|治癒).{0,6}(癌|疾病|死亡)',
            r'(研究顯示|研究證明|科學家表示|專家稱|專家表示)'
        ]
        # 預設使用英文模式（會在檢測時依語言切換）
        self.high_risk_patterns = self.high_risk_patterns_en
        

        # 📄 事實正確性評估文檔選擇矩陣
        self.document_selection_matrix = {
            'primary': ['full_story.txt'],
            'secondary': [],
            'conditional': [],
            'excluded': [],
            'weights': {
                'full_story.txt': 1.0
            }
        }
        
    def _log(self, message: str) -> None:
        """在 verbose 模式下輸出進度訊息"""
        if getattr(self, 'verbose', False):
            self.logger.info("[Factuality] %s", message)
    
    def _log_performance(self, operation: str, duration: float, details: str = "") -> None:
        """記錄效能統計"""
        if self.enable_performance_logging:
            self.logger.info("[Performance] %s: %.2fs %s", operation, duration, details)
    
    def _update_progress(self, current: int, total: int, operation: str) -> None:
        """更新進度顯示"""
        if self.enable_progress_tracking and total > 0:
            percentage = (current / total) * 100
            self.logger.info("[Progress] %s: %d/%d (%.1f%%)", operation, current, total, percentage)

    def _truncate(self, text: str, max_len: int = 120) -> str:
        if text is None:
            return ""
        t = text.replace("\n", " ").strip()
        return t if len(t) <= max_len else t[:max_len - 3] + "..."

    def _is_purely_fictional_content(self, story_text: str, story_title: str) -> bool:
        """🚀 快速檢測是否為純虛構內容，避免無效的事實檢查"""
        # 智能檢測標題是否為純虛構內容（不包含可驗證事實）
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                判斷以下標題是否為純虛構故事（不包含任何可驗證的事實內容）：
                
                標題：{story_title}
                
                注意：
                - 即使標題包含"story"、"adventure"等詞，如果內容包含真實事實，仍應判斷為"包含事實"
                - 只有完全虛構、不包含任何真實人物、地點、事件的純故事才判斷為"純虛構"
                
                只回答：純虛構 或 包含事實
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "純虛構" in ai_response or "pure fictional" in ai_response:
                    return True
        except Exception:
            pass
        
        # 快速文本採樣檢查（只檢查前500字符以提高速度）
        sample_text = story_text[:500].lower()
        
        # 虛構內容特徵
        fictional_patterns = [
            r'\b(?:once upon a time|long ago|in a land far away)\b',
            r'\b(?:fairy|wizard|magic|spell|enchanted|mystical)\b',
            r'\b(?:dragon|unicorn|phoenix|griffin)\b',
            r'\b(?:kingdom|castle|palace|dungeon)\b',
            r'\b(?:princess|prince|king|queen|knight)\b'
        ]
        
        fictional_score = sum(1 for pattern in fictional_patterns if re.search(pattern, sample_text))
        
        # 如果發現3個以上虛構特徵，認定為純虛構內容
        return fictional_score >= 3

    def _estimate_content_signals(self, story_text: str, story_title: str) -> Tuple[float, float]:
        """智能評估文本中的『可驗證訊號』與『虛構訊號』
        - 可驗證訊號：年份、具單位的數值、地名/人名（NER）、SVO結構數量
        - 虛構訊號：童話開場語、魔法詞、奇幻生物、童話地名
        回傳：factual_score, fictional_score
        """
        import math
        text = (story_text or "").strip()
        title = (story_title or "").strip()
        lower = text.lower()

        # 1) 可驗證訊號
        year_hits = len(re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", text))
        unit_hits = len(re.findall(r"\b\d+(?:[\.,]\d+)?\s*(?:km|kilometer|meter|m|kg|ton|tons|mph|km/h|kph|percent|%)\b", lower))
        number_hits = len(re.findall(r"\b\d{2,}\b", text))

        # NER: 若有可用 nlp 就抓實體數；否則以 0 計
        ner_entities = 0
        try:
            if hasattr(self.nlp, "pipe"):
                sample = " ".join(text.split()[:5000])
                doc = self.nlp(sample)
                ner_entities = len([ent for ent in getattr(doc, "ents", []) if ent.label_ in {"PERSON","ORG","GPE","LOC","DATE","QUANTITY"}])
        except Exception:
            ner_entities = 0

        factual_score = (
            4.0 * min(year_hits, 20) +
            3.0 * min(unit_hits, 30) +
            1.0 * min(number_hits, 50) +
            0.8 * min(ner_entities, 50)
        )

        # 2) 虛構訊號
        fairy_openers = [
            r"\bonce upon a time\b", r"\blong ago\b", r"\bin a land far away\b"
        ]
        magic_words = [
            r"\bmagic\b", r"\bwizard\b", r"\bspell\b", r"\benchanted\b", r"\bmystical\b",
            r"\bdragon\b", r"\bunicorn\b", r"\bphoenix\b", r"\bgriffin\b"
        ]
        place_words = [r"\bkingdom\b", r"\bcastle\b", r"\bpalace\b", r"\bdungeon\b"]

        fairy_hits = sum(1 for p in fairy_openers if re.search(p, lower))
        magic_hits = sum(1 for p in magic_words if re.search(p, lower))
        place_hits = sum(1 for p in place_words if re.search(p, lower))

        # 標題的奇幻指標（弱權重）
        title_lower = title.lower()
        title_hits = sum(1 for kw in ["odyssey","fairy","tale","story","magic","enchanted","mystical"] if kw in title_lower)

        fictional_score = 10.0 * fairy_hits + 4.0 * magic_hits + 2.5 * place_hits + 1.0 * title_hits

        return float(factual_score), float(fictional_score)

    def _has_hard_verifiable_signals(self, story_text: str, story_title: str) -> bool:
        """檢測高可信可驗證訊號，避免將可驗證文本誤判為純虛構。"""
        text = (story_text or "")
        title = (story_title or "")
        sample = f"{title}\n{text[:4000]}"

        hard_patterns = [
            r"\b(1[5-9]\d{2}|20\d{2})\b",  # 年份
            r"\b\d+(?:[\.,]\d+)?\s*(?:km|kilometer|meter|m|kg|ton|tons|mph|km/h|kph|percent|%)\b",  # 單位
            r"\b(?:https?://|www\.)\S+\b",  # URL
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",  # 英文月份
            r"\b(?:UN|NASA|WHO|EU|USA|UK|GDP|AI)\b",  # 常見縮寫
            r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # 專名（兩個首字大寫詞）
        ]

        hits = 0
        for pattern in hard_patterns:
            if re.search(pattern, sample):
                hits += 1
        return hits >= 2
    
    def _create_fictional_content_result(
        self,
        story_title: str,
        processing_time: float,
        story_text: str = "",
        factual_signal: Optional[float] = None,
        fictional_signal: Optional[float] = None,
    ) -> Dict:
        """為純虛構內容創建快速結果（以啟發式分數避免常數分數）。"""
        heuristic_score = self._heuristic_factuality_without_claims(
            story_text,
            story_title,
            factual_signal=factual_signal,
            fictional_signal=fictional_signal,
        )
        # 虛構文本仍應保留中性偏低區間，避免與高可驗證文本等價。
        fictional_score = max(42.0, min(68.0, heuristic_score))
        try:
            risk_score = self._estimate_risk_from_text(story_text)
        except Exception:
            risk_score = 65.0

        return {
            "factuality": {
                "scores": {
                    "claim_accuracy": round(fictional_score, 1),
                    "verification_coverage": 0.0,
                    "risk_assessment": round(risk_score, 1),
                    "final": round(fictional_score, 1)
                },
                "claims": [],
                "verification_results": [],
                "risk_assessment": {
                    "overall_risk": "none",
                    "risk_distribution": {},
                    "high_risk_claims": [],
                    "risk_factors": []
                },
                "suggestions": [
                    "故事為虛構內容，已採用虛構情境評分模式。",
                    "若需提高事實性可解釋度，可加入可驗證錨點（時間、地點、客觀事件）。",
                ]
            },
            "meta": {
                "story_title": story_title,
                "total_claims": 0,
                "verifiable_claims": 0,
                "verified_claims": 0,
                "fictional_content_detected": True,
                "performance_stats": {
                    "total_time": processing_time,
                    "extraction_time": 0.0,
                    "verification_time": 0.0,
                    "ai_analysis_time": 0.0,
                    "wikipedia_queries": 0
                }
            }
        }
    
    def _select_priority_claims(self, claims: List[FactualClaim], max_claims: int) -> List[FactualClaim]:
        """智能選擇最重要的聲明進行驗證"""
        # 按重要性排序：可驗證性 > 置信度 > 聲明類型
        def claim_priority(claim):
            # 可驗證的聲明優先
            verifiable_score = 100 if claim.verifiable else 0
            
            # 高置信度優先
            confidence_score = claim.confidence * 50
            
            # 特定類型優先（temporal, numerical, scientific 更容易驗證）
            type_scores = {
                'temporal': 30,
                'numerical': 25,
                'scientific': 20,
                'geographical': 15,
                'factual': 10,
                'biographical': 5
            }
            type_score = type_scores.get(claim.claim_type, 0)
            
            # 有實體的聲明優先
            entity_score = min(len(claim.entities or []) * 5, 20)
            
            return verifiable_score + confidence_score + type_score + entity_score
        
        # 排序並選擇前 N 個
        sorted_claims = sorted(claims, key=claim_priority, reverse=True)
        selected_claims = sorted_claims[:max_claims]
        
        self._log(f"選擇了 {len(selected_claims)} 條高優先級聲明進行驗證")
        return selected_claims
    
    def get_documents_for_factuality(self, available_documents: Dict[str, str]) -> Dict[str, str]:
        # 挑選適合做事實驗證的文檔（故事主文 > 旁白 > 大綱）
        selected_docs = {}
        
        # 優先選擇主要文檔
        for doc_name in self.document_selection_matrix['primary']:
            if doc_name in available_documents:
                selected_docs[doc_name] = available_documents[doc_name]
        
        # 如果主要文檔不足，添加次要文檔
        if len(selected_docs) < 2:
            for doc_name in self.document_selection_matrix['secondary']:
                if doc_name in available_documents and doc_name not in selected_docs:
                    selected_docs[doc_name] = available_documents[doc_name]
        
        # 添加條件性文檔（如果存在）
        for doc_name in self.document_selection_matrix['conditional']:
            if doc_name in available_documents and doc_name not in selected_docs:
                selected_docs[doc_name] = available_documents[doc_name]
        
        return selected_docs
    
    def get_document_weights_for_factuality(self) -> Dict[str, float]:
        """獲取事實正確性評估的文檔權重"""
        return self.document_selection_matrix['weights']
    
    def check(self, story_text: str, story_title: str = "Story",
              outline_text: str = None, narration_text: str = None) -> Dict:
        """主要檢測接口"""
        import time
        start_time = time.time()
        
        self._log(f"開始檢測：{story_title}")
        self._log(f"spaCy 設定 batch_size={self.spacy_pipe_batch_size}, n_process={self.spacy_pipe_n_process}")
        self._log(f"驗證執行緒數 verify_max_workers={self.verify_max_workers}")
        
        # 🚦 智能啟動判斷：根據『可驗證訊號』vs『虛構訊號』動態決定是否執行事實檢查
        try:
            factual_score, fictional_score = self._estimate_content_signals(story_text, story_title)
            has_hard_facts = self._has_hard_verifiable_signals(story_text, story_title)
            self._log(f"[啟動判斷] factual_signal={factual_score:.1f}, fictional_signal={fictional_score:.1f}")
            # 放寬虛構檢測門檻：讓更多童話/寓言故事被識別為虛構內容
            skip_threshold = 20 if self.fast_mode else 12  # 提高門檻
            fictional_threshold = 10 if self.fast_mode else 15  # 降低門檻
            diff_threshold = 5 if self.fast_mode else 8  # 降低差異要求
            
            if factual_score < skip_threshold and fictional_score > fictional_threshold and (fictional_score - factual_score) >= diff_threshold and not has_hard_facts:
                self._log("⚡ 內容高度偏虛構且缺乏可驗證訊號 → 跳過事實檢查，給予虛構內容啟發式分數")
                return self._create_fictional_content_result(
                    story_title,
                    time.time() - start_time,
                    story_text=story_text,
                    factual_signal=factual_score,
                    fictional_signal=fictional_score,
                )
            if has_hard_facts:
                self._log("🛡️ 偵測到硬事實訊號，強制執行事實檢查流程")
        except Exception:
            # 若評估出錯，保守起見照常檢查
            pass
        
        # 移除文本長度限制，處理所有文本
        
        # 重置效能統計
        self.performance_stats = {k: 0.0 if 'time' in k else 0 for k, v in self.performance_stats.items()}
        
        self._log("步驟1/6 抽取事實聲明（NER）…")
        # 🔍 1) 事實聲明抽取
        extraction_start = time.time()
        claims = self._extract_factual_claims(story_text, outline_text, narration_text)
        extraction_time = time.time() - extraction_start
        self.performance_stats['extraction_time'] = extraction_time
        self.performance_stats['total_claims_processed'] = len(claims)
        
        self._log_performance("聲明抽取", extraction_time, f"共 {len(claims)} 條聲明")
        self._log(f"抽取完成，候選聲明共 {len(claims)} 條，其中可驗證 {len([c for c in claims if c.verifiable])} 條")
        
        if not claims:
            self._log("未發現可用聲明，輸出空報告")
            return self._generate_no_claims_report(story_title, story_text)
        
        # ✅ 2) 事實驗證
        self._log("步驟2/6 驗證聲明（Wikipedia / AI / Web）…")
        verification_start = time.time()
        
        # 智能快速模式：優先驗證最重要的聲明
        if self.fast_mode and len(claims) > self.max_claims:
            self._log(f"快速模式：從 {len(claims)} 條聲明中選擇最重要的 {self.max_claims} 條進行驗證")
            claims = self._select_priority_claims(claims, self.max_claims)
        
        verification_results = self._verify_claims(claims)
        verification_time = time.time() - verification_start
        self.performance_stats['verification_time'] = verification_time
        self._log_performance("聲明驗證", verification_time, f"驗證 {len(verification_results)} 條結果")
        self._log("聲明驗證完成")
        
        # 🚨 3) 風險評估
        self._log("步驟3/6 風險評估…")
        risk_assessment = self._assess_risk_levels(verification_results)
        self._log("風險評估完成")
        
        # 🤖 4) AI 事實檢查增強
        self._log("步驟4/6 AI 事實檢查增強…")
        ai_start = time.time()
        ai_analysis = self._advanced_ai_fact_check(story_text, claims, verification_results)
        ai_time = time.time() - ai_start
        self.performance_stats['ai_analysis_time'] = ai_time
        self._log_performance("AI 分析", ai_time)
        self._log("AI 增強完成")
        
        # 📊 5) 綜合評分
        self._log("步驟5/6 計算綜合評分…")
        scores = self._calculate_factuality_scores(verification_results, risk_assessment, ai_analysis)
        self._log(f"分數：claim_accuracy={scores.claim_accuracy:.1f}, coverage={scores.verification_coverage:.1f}, risk={scores.risk_assessment:.1f}, final={scores.final:.1f}")
        
        # 💡 6) 生成建議
        self._log("步驟6/6 生成建議…")
        suggestions = self._generate_factuality_suggestions(verification_results, risk_assessment, ai_analysis)
        
        total_time = time.time() - start_time
        self._log_performance("總檢測時間", total_time)
        self._log("建議生成完成，準備返回結果")
        
        return {
            "meta": {
                "version": "1.0_factuality_checker",
                "story_title": story_title,
                "total_claims": len(claims),
                "verifiable_claims": len([c for c in claims if c.verifiable]),
                "web_search_enabled": self.enable_web_search,
                "wikipedia_enabled": self.enable_wikipedia,
                "ai_available": self.ai.model_available,
                "processing_time": total_time,
                "performance_stats": self.performance_stats.copy()
            },
            "factuality": {
                "claims": [self._claim_to_dict(claim) for claim in claims],
                "verification_results": [self._result_to_dict(result) for result in verification_results],
                "risk_assessment": risk_assessment,
                "scores": {
                    "claim_accuracy": round(scores.claim_accuracy, 1),
                    "verification_coverage": round(scores.verification_coverage, 1),
                    "risk_assessment": round(scores.risk_assessment, 1),
                    "final": round(scores.final, 1)
                },
                "ai_analysis": ai_analysis,
                "suggestions": suggestions
            }
        }
    
    def _extract_factual_claims(self, story_text: str, outline_text: str = None, 
                               narration_text: str = None) -> List[FactualClaim]:
        """抽取事實聲明（NER 為主）
        - 合併故事、綱要、旁白文本；逐句執行 spaCy NER。
        - 若句中含具體實體或數值線索，將整句視為候選聲明。
        - 依實體類型推斷 claim_type，計算置信度並判斷是否可驗證。
        - 去重後返回標準化的 FactualClaim 列表。
        """
        self._log("[抽取] 開始合併文本並切句…")
        claims = []
        claim_id_counter = 1
        
        # 合併所有文本來源
        text_sources = [
            ("story", story_text),
            ("outline", outline_text or ""),
            ("narration", narration_text or "")
        ]
        
        for source_type, text in text_sources:
            if not text.strip():
                continue
            self._log(f"[抽取] 處理來源：{source_type}")
            
            # 移除早期退出檢查，處理所有來源
            
            sentences = self._split_sentences(text)
            if not sentences:
                continue
            
            # 處理所有句子，不限制數量
            
            # 快速預檢查：如果文本太短或明顯是虛構內容，跳過
            if len(text) < 100:
                self._log(f"[抽取] 跳過來源 {source_type}：文本太短")
                continue
            
            # 智能檢查是否包含事實性內容
            try:
                if self.ai and self.ai.model_available:
                    prompt = f"""
                    判斷以下文本是否包含可驗證的事實性內容：
                    
                    文本：{text[:200]}...
                    
                    考慮因素：
                    1. 是否包含具體的數據、日期、地點、人物
                    2. 是否包含科學事實、歷史事件、真實機構
                    3. 即使是在故事中，如果提到真實人物（如Marie Curie）或真實地點（如MIT），仍應判斷為"包含事實"
                    
                    只回答：包含事實 或 純虛構
                    """
                    
                    result = self.ai.analyze_consistency(prompt, [], {})
                    ai_response = result.get("analysis", "").strip().lower()
                    
                    has_factual_content = "包含事實" in ai_response or "factual" in ai_response
                else:
                    # AI不可用時，默認檢測所有內容
                    has_factual_content = True
            except Exception:
                # AI檢測失敗時，默認檢測所有內容
                has_factual_content = True
            
            if not has_factual_content:
                self._log(f"[抽取] 跳過來源 {source_type}：無事實性內容")
                continue
            
            # 優化：直接處理整個文本，避免逐句處理
            self._log(f"[抽取] 處理文本：{len(text)} 字符")
            doc = self.nlp(text)
            
            # 提取所有實體
            all_entities = [(ent.text, ent.label_, ent.start_char, ent.end_char) for ent in doc.ents]
            self._log(f"[抽取] 提取到 {len(all_entities)} 個實體")
            
            # 快速檢查是否有重要實體
            important_entity_types = {'PERSON', 'ORG', 'GPE', 'DATE', 'MONEY', 'QUANTITY', 'CARDINAL'}
            important_entities = [e for e in all_entities if e[1] in important_entity_types]
            
            if not important_entities:
                self._log(f"[抽取] 跳過來源 {source_type}：無重要實體")
                continue
            
            # 智能按句子分組實體（考慮實體可能跨句子邊界）
            sentence_entities = {}
            for i, sentence in enumerate(sentences):
                # 計算句子在原文中的位置
                sentence_start = sum(len(sentences[j]) + 1 for j in range(i))  # +1 for space/newline
                sentence_end = sentence_start + len(sentence)
                
                # 找到屬於這個句子的實體（允許部分重疊）
                sentence_ents = []
                for ent_text, ent_label, start_char, end_char in all_entities:
                    # 實體與句子有重疊就認為屬於該句子
                    if (start_char < sentence_end and end_char > sentence_start):
                        sentence_ents.append((ent_text, ent_label))
                
                sentence_entities[i] = sentence_ents
            
            # 逐句處理聲明抽取
            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                
                # 獲取該句子的實體
                entities = sentence_entities.get(i, [])
                
                # 檢查是否有數字（使用簡單的正則表達式，避免重複NER）
                has_number_token = bool(re.search(r'\b\d+\b', sentence))
                
                # 只處理包含重要實體類型的句子
                important_entity_types = {'PERSON', 'ORG', 'GPE', 'DATE', 'MONEY', 'QUANTITY', 'CARDINAL'}
                important_entities = [e for e in entities if e[1] in important_entity_types]
                
                # 如果沒有重要實體和數字，跳過
                if not important_entities and not has_number_token:
                    continue
                    
                # 使用過濾後的重要實體
                entities = important_entities
                
                # 推斷聲明類型
                claim_type = self._infer_claim_type_from_entities(entities, has_number_token)
                
                # 以整句作為候選聲明（避免片段式正則抽取）
                claim_text = sentence.strip()
                
                # 簡化調試輸出
                if self.verbose:
                    self._log(f"[抽取] 候選: {self._truncate(claim_text, 60)} | 實體: {len(entities)} | 類型: {claim_type}")
                
                if not self._is_meaningful_claim(claim_text, sentence):
                    if self.verbose:
                        self._log(f"[抽取] 跳過：不是有意義的聲明")
                    continue
                
                # 依存分析抽取簡單 SVO 三元組
                triples = self._extract_svo_triples(doc) if doc is not None else []

                # 實體連結延後到驗證階段（預設關閉以減少延遲）
                links = {}
                if self.perform_wiki_linking_in_extraction and self.enable_wikipedia and getattr(self, 'wikipedia_checker', None):
                    links = self._link_entities_via_wikipedia([e[0] for e in entities]) if entities else {}

                # 置信度：以 NER 訊號加權
                confidence = self._assess_claim_confidence_ner(claim_text, sentence, entities, has_number_token)
                
                # 可驗證性：基於通用規則（不調用外部）
                verifiable = self._is_verifiable_by_ner(entities, has_number_token, claim_type, links)
                
                # 調試輸出：顯示可驗證性判斷結果
                self._log(f"[抽取/調試] 聲明類型: {claim_type}")
                self._log(f"[抽取/調試] 置信度: {confidence:.2f}")
                self._log(f"[抽取/調試] 可驗證: {verifiable}")
                if verifiable:
                    self._log(f"[抽取/調試] ✅ 接受為事實聲明")
                else:
                    self._log(f"[抽取/調試] ❌ 跳過驗證")
                
                claim = FactualClaim(
                    claim_id=f"claim_{claim_id_counter:03d}",
                    text=claim_text,
                    claim_type=claim_type,
                    confidence=confidence,
                    context=sentence,
                    location=f"{source_type}_sentence_{i+1}",
                    verifiable=verifiable,
                    entities=entities,
                    triples=triples,
                    links=links
                )
                claims.append(claim)
                if len(claims) % 10 == 0:
                    self._log(f"[抽取] 已收集 {len(claims)} 條候選聲明…")
                claim_id_counter += 1
                
                # 移除早期退出，檢測所有聲明
        
        # 去重複
        unique_claims = self._deduplicate_claims(claims)
        self._log(f"[抽取] 去重後剩 {len(unique_claims)} 條")
        return unique_claims

    def _collect_page_evidence(self,
                               story_dir: Optional[str] = None,
                               page_num: Optional[int] = None,
                               story_text: Optional[str] = None,
                               outline_text: Optional[str] = None,
                               narration_text: Optional[str] = None,
                               dialogue_text: Optional[str] = None) -> Dict:
        """頁面語義證據聚合器（本模組獨立實作）
        當頁優先 → resources 補詞 → 全文回退，並輸出查詢候選。
        回傳：{'tier','sources','text','tokens','queries'}
        """
        def _read(path: str) -> str:
            try:
                if path and os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        return f.read()
            except Exception:
                return ''
            return ''

        def _tok(text: str) -> List[str]:
            t = (text or '').lower()
            parts = re.split(r"[^a-z0-9]+", t)
            stop = {"the","a","an","and","or","to","of","in","on","at","with","for","is","are"}
            return [p for p in parts if p and len(p) > 1 and p not in stop]

        sources: List[str] = []
        combined = ''
        tier = 'global'

        # 1) 當頁
        if story_dir and page_num is not None:
            base = story_dir
            en_dir = os.path.join(story_dir, 'en')
            if os.path.isdir(en_dir):
                base = en_dir
            main_t = _read(os.path.join(base, f"page_{page_num}.txt"))
            nar_t = _read(os.path.join(base, f"page_{page_num}_narration.txt"))
            dlg_t = _read(os.path.join(base, f"page_{page_num}_dialogue.txt"))
            page_parts = [t for t in [main_t, nar_t, dlg_t] if t]
            if page_parts:
                combined = "\n\n".join(page_parts)
                sources.extend([n for n,t in [(f"page_{page_num}.txt", main_t), (f"page_{page_num}_narration.txt", nar_t), (f"page_{page_num}_dialogue.txt", dlg_t)] if t])
                tier = 'page'
            if not combined:
                res_dir = os.path.join(story_dir, 'resources')
                if os.path.isdir(res_dir):
                    names = [f"page_{page_num}_prompt.txt", f"page_{page_num}_poses.txt", 'scenes.txt']
                    res_parts = []
                    for n in names:
                        p = os.path.join(res_dir, n)
                        c = _read(p)
                        if c:
                            res_parts.append(c)
                            sources.append(os.path.join('resources', n))
                    if res_parts:
                        combined = "\n\n".join(res_parts)
                        tier = 'resources'

        # 2) 全文回退
        if not combined:
            all_parts = [story_text or '', outline_text or '', narration_text or '', dialogue_text or '']
            combined = "\n\n".join([t for t in all_parts if t])
            sources.append('global_combined')
            tier = 'global'

        toks = _tok(combined)
        uniq: List[str] = []
        seen = set()
        for w in toks:
            if w not in seen:
                seen.add(w)
                uniq.append(w)
        queries = uniq[:64]
        return {
            'tier': tier,
            'sources': sources,
            'text': combined[:2000],
            'tokens': set(uniq),
            'queries': queries
        }

    def _infer_claim_type_from_entities(self, entities: List[Tuple[str, str]], has_number_token: bool) -> str:
        """根據 NER 實體類型推斷聲明類型，專注於真實世界知識分類"""
        labels = {label for _, label in entities}
        entity_texts = [text.lower() for text, _ in entities]
        
        # 智能科學內容檢測
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                分析以下實體列表，判斷是否為科學相關內容：
                
                實體：{', '.join(entity_texts[:10])}
                
                考慮因素：
                1. 是否包含科學概念、理論、定律
                2. 是否包含自然現象、物理化學過程
                3. 是否包含生物學、天文學等科學領域
                
                只回答：科學 或 非科學
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "科學" in ai_response or "scientific" in ai_response:
                    return "scientific"
        except Exception:
            pass
        
        # 時間類型（具體的歷史時間）
        if any(lbl in {"DATE", "TIME"} for lbl in labels):
            return "temporal"
        
        # 地理類型（真實地名）- 擴展地理實體識別
        if any(lbl in {"GPE", "LOC"} for lbl in labels):
            real_places = {
                # 國家
                "china", "usa", "america", "united states", "france", "japan", "england", 
                "germany", "italy", "spain", "canada", "australia", "brazil", "india",
                "russia", "korea", "mexico", "egypt", "thailand", "singapore",
                # 城市
                "london", "paris", "tokyo", "beijing", "new york", "los angeles",
                "shanghai", "mumbai", "delhi", "moscow", "berlin", "rome", "madrid",
                "toronto", "sydney", "seoul", "bangkok", "dubai", "hong kong",
                # 地理特徵
                "river", "mountain", "ocean", "sea", "lake", "desert", "forest",
                "continent", "island", "peninsula", "valley", "plateau", "coast"
            }
            if any(place in entity_texts for place in real_places):
                return "geographical"
            return "factual"  # 非真實地名降級為一般事實
        
        # 數值類型（測量、統計數據）
        if any(lbl in {"QUANTITY", "PERCENT", "MONEY"} for lbl in labels) or has_number_token:
            return "numerical"
        
        # 機構組織類型
        if any(lbl in {"ORG"} for lbl in labels):
            known_orgs = {"nasa", "who", "unesco", "microsoft", "google", "apple", "harvard", "oxford"}
            if any(org in entity_texts for org in known_orgs):
                return "institutional"
            return "factual"
        
        # 歷史事件類型
        if any(lbl in {"EVENT"} for lbl in labels):
            historical_events = {"world war", "olympics", "earthquake", "hurricane", "revolution"}
            entity_text_combined = " ".join(entity_texts)
            if any(event in entity_text_combined for event in historical_events):
                return "historical"
            return "factual"
        
        # 人物類型（但排除虛構角色）
        if any(lbl in {"PERSON"} for lbl in labels):
            fictional_names = {"emma", "alex", "sarah", "lisa", "tom", "pip", "grandpa tom"}
            if any(name in entity_texts for name in fictional_names):
                return "fictional"  # 明確標記為虛構
            return "biographical"
        
        # 通用事實模式檢測（避免漏判）
        if self._contains_factual_patterns(entity_texts, labels):
            return "factual"
            
        return "factual"

    def _contains_factual_patterns(self, entity_texts: List[str], labels: set) -> bool:
        """檢測通用事實模式，避免漏判真實世界知識"""
        
        # 數值測量模式
        numerical_patterns = [
            r'\d+\s*(miles?|kilometers?|km|meters?|feet|inches?)',  # 距離
            r'\d+\s*(degrees?|celsius|fahrenheit|°c|°f)',           # 溫度
            r'\d+\s*(years?|months?|days?|hours?|minutes?)',        # 時間
            r'\d+\s*(million|billion|thousand)',                     # 大數字
            r'\d+\s*(percent|%)',                                    # 百分比
            r'\d+\s*(population|people|inhabitants)',                # 人口
        ]
        
        combined_text = ' '.join(entity_texts).lower()
        if any(re.search(pattern, combined_text) for pattern in numerical_patterns):
            return True
        
        # 智能科學事實檢測
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                判斷以下文本是否包含科學事實：
                
                文本：{combined_text[:200]}
                
                考慮因素：
                1. 是否包含具體的測量數據
                2. 是否包含科學屬性描述
                3. 是否包含可驗證的科學聲明
                
                只回答：科學事實 或 非科學事實
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "科學事實" in ai_response or "scientific" in ai_response:
                    return True
        except Exception:
            pass
        
        # 地理關係詞
        geographical_relations = {
            'north of', 'south of', 'east of', 'west of', 'between', 'near',
            'border', 'coast', 'mountain', 'river', 'ocean', 'sea', 'lake'
        }
        
        if any(relation in combined_text for relation in geographical_relations):
            return True
        
        # 時間關係詞
        temporal_relations = {
            'built in', 'founded in', 'established in', 'created in', 'discovered in',
            'invented in', 'occurred in', 'happened in', 'took place in'
        }
        
        if any(relation in combined_text for relation in temporal_relations):
            return True
            
        return False

    def _assess_claim_confidence_ner(self, claim_text: str, sentence: str,
                                     entities: List[Tuple[str, str]], has_number_token: bool) -> float:
        """根據 NER 訊號評估置信度
        - 多個實體與時間/數值訊號提高置信度；
        - 對話與第一人稱降低置信度；
        - 輸出介於 0.1–0.9。
        """
        confidence = 0.6
        # 多個實體提高置信度
        if len(entities) >= 2:
            confidence += 0.15
        # 時間或數值線索提高置信度
        if any(lbl in {"DATE", "TIME", "QUANTITY", "PERCENT", "MONEY"} for _, lbl in entities) or has_number_token:
            confidence += 0.1
        # 對話/第一人稱等降低（沿用原有啟發式）
        sentence_lower = sentence.lower()
        if '"' in sentence or 'said' in sentence_lower:
            confidence -= 0.1
        if re.search(r'\b(?:I|we|my|our)\b', sentence, re.IGNORECASE):
            confidence -= 0.1
        return max(0.1, min(0.9, confidence))

    def _estimate_verifiability_score(self, sentence: str) -> float:
        """以通用訊號評估一句話是否值得做外部事實驗證（0~1）。
        訊號來源：
        - NER：存在 DATE/TIME/GPE/LOC/ORG/PERSON/QUANTITY…
        - 數值：包含數字或量詞
        - 句法：存在簡單 SVO 結構（主-謂-賓）
        - 語氣：避免第一人稱、強烈主觀詞；懲罰純對話
        - 長度：過短/過長均降權
        """
        try:
            doc = self.nlp(sentence) if getattr(self.nlp, "pipe_names", None) else None
        except Exception:
            doc = None

        score = 0.0

        # 1) NER 訊號
        if doc is not None:
            labels = {ent.label_ for ent in doc.ents}
            if labels:
                score += min(0.35, 0.08 * len(labels))
            if any(lbl in {"DATE", "TIME", "GPE", "LOC", "ORG", "EVENT", "QUANTITY", "PERCENT", "MONEY"} for lbl in labels):
                score += 0.2

        # 2) 數值訊號
        if any(ch.isdigit() for ch in sentence):
            score += 0.15

        # 3) SVO 簡單判斷（有動詞且有名詞）
        if doc is not None:
            has_verb = any(t.pos_ == 'VERB' for t in doc)
            has_noun = any(t.pos_ in {'NOUN', 'PROPN'} for t in doc)
            if has_verb and has_noun:
                score += 0.15

        # 4) 語氣與對話懲罰
        lower = sentence.lower()
        if '"' in sentence or '"' in sentence or '"' in sentence:
            score -= 0.15
        if re.search(r'\b(?:i|we|my|our)\b', lower):
            score -= 0.1

        # 5) 長度正則化
        length = len(sentence.split())
        if 6 <= length <= 40:
            score += 0.1
        elif length < 4 or length > 60:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _ai_is_real_world_fact(self, sentence: str) -> Optional[bool]:
        """可選：用 AI 判斷一句話是否屬於『可對外知識驗證的事實敘述』。
        - True：應納入事實檢查
        - False：不需要
        - None：AI 不可用或判斷失敗
        """
        if not self.enable_ai_gating:
            return None
        if not self.ai or not self.ai.model_available:
            return None
        # 呼叫上限控制，避免延遲暴增
        if self._ai_gating_calls_used >= max(0, int(self.ai_gating_max_calls_per_doc)):
            return None
        try:
            prompt = (
                "判斷下列句子是否包含可被外部知識驗證的客觀事實（例如時間、地點、機構、科學/生物常識、量化數據）。\n"
                "只回答 Yes 或 No。\n\n"
                f"句子：{sentence}"
            )
            self._ai_gating_calls_used += 1
            result = self.ai.analyze_consistency(sentence, [], {})
            # 簡化：如果 ai_score 偏高，視為 Yes
            score = result.get('ai_score', 50)
            return True if score >= 65 else False if score <= 35 else None
        except Exception:
            return None

    def _is_verifiable_by_ner(self, entities: List[Tuple[str, str]], has_number_token: bool, claim_type: str, links: Dict[str, Dict[str, str]]) -> bool:
        """基於 NER 的可驗證性判斷
        專注於真實世界知識的驗證，允許虛構情節但檢查科學常識
        """
        labels = {label for _, label in entities}
        entity_texts = [text.lower() for text, _ in entities]
        
        # 新增：使用 AI 智能判斷是否為需要驗證的內容
        if not self._should_verify_content(entity_texts, claim_type):
            return False
        
        # 基於聲明類型進行可驗證性判斷
        
        # 1. 科學知識 - 僅驗證基礎科學常識，排除故事中的魔法/虛構科學
        if claim_type == "scientific":
            return self._is_basic_scientific_fact(entity_texts)
        
        # 2. 生物學知識（動物習性）- 僅驗證真實動物行為
        if claim_type == "biological":
            return self._is_real_animal_behavior(entity_texts)
        
        # 3. 動物行為 - 童話中常見的動物行為常識
        if claim_type == "animal_behavior":
            return self._is_common_animal_behavior(entity_texts)
        
        # 4. 自然現象 - 物理常識和自然規律
        if claim_type == "natural_phenomena":
            return self._is_natural_phenomena_fact(entity_texts)
        
        # 5. 社會常識 - 文化規範和社會行為
        if claim_type == "social_norms":
            return self._is_social_norm_fact(entity_texts)
        
        # 6. 一般常識 - 生活經驗和基本常識
        if claim_type == "common_sense":
            return self._is_common_sense_fact(entity_texts)
        
        # 7. 地理知識 - 真實地名可驗證
        if claim_type == "geographical":
            return True
        
        # 8. 歷史知識 - 可驗證
        if claim_type == "historical":
            return True
        
        # 9. 機構組織 - 可驗證
        if claim_type == "institutional":
            return True
        
        # 10. 時間 - 具體時間可驗證
        if claim_type == "temporal":
            return True  # 簡化：所有時間聲明都嘗試驗證
        
        # 11. 數值 - 具體測量值可驗證
        if claim_type == "numerical":
            return True  # 簡化：所有數值聲明都嘗試驗證
        
        # 12. 人物傳記 - 真實人物可驗證（排除虛構角色）
        if claim_type == "biographical":
            return True  # 簡化：所有人物聲明都嘗試驗證
        
        # 13. 虛構內容 - 明確不可驗證
        if claim_type == "fictional":
            return False
        
        # 14. 默認：嘗試驗證（除非明確標記為虛構）
        return True
    
    def _should_verify_content(self, entity_texts: List[str], claim_type: str) -> bool:
        """擴展可驗證內容範圍，包含童話中的常識元素"""
        # 擴展策略：包含童話中常見的可驗證常識
        verifiable_types = [
            "geographical", "historical", "institutional", "temporal", "numerical",
            "scientific", "biological", "biographical", "factual", "common_sense",
            "animal_behavior", "natural_phenomena", "social_norms"
        ]
        return claim_type in verifiable_types
    
    def _is_cultural_fictional_content(self, entity_texts: List[str], claim_type: str) -> bool:
        """使用 AI 判斷是否為虛構故事中的文化元素（不應驗證）"""
        if not self.ai or not self.ai.model_available:
            return False
        
        # 組合實體文本進行 AI 判斷
        combined_text = " ".join(entity_texts)
        if not combined_text.strip():
            return False
        
        try:
            prompt = (
                "判斷以下內容是否為虛構故事中的文化藝術元素（如摺紙、糖骷髏、茶道等），"
                "這些在故事中通常是背景設定，不需要事實驗證。\n"
                "只回答 Yes 或 No。\n\n"
                f"內容：{combined_text}"
            )
            
            # 使用 AI 分析
            result = self.ai.analyze_consistency(combined_text, [], {})
            score = result.get('ai_score', 50)
            
            # 如果 AI 認為是文化元素，返回 True（不驗證）
            return score >= 70
            
        except Exception:
            return False
    
    def _is_story_setting_content(self, entity_texts: List[str], claim_type: str) -> bool:
        """使用 AI 判斷是否為故事設定內容（不應驗證）"""
        if not self.ai or not self.ai.model_available:
            return False
        
        combined_text = " ".join(entity_texts)
        if not combined_text.strip():
            return False
        
        try:
            prompt = (
                "判斷以下內容是否為虛構故事中的角色、地點或設定（如角色名稱、故事場景等），"
                "這些是故事創作元素，不需要事實驗證。\n"
                "只回答 Yes 或 No。\n\n"
                f"內容：{combined_text}"
            )
            
            result = self.ai.analyze_consistency(combined_text, [], {})
            score = result.get('ai_score', 50)
            
            return score >= 70
            
        except Exception:
            return False
    
    def _is_basic_scientific_fact(self, entity_texts: List[str]) -> bool:
        """簡化：所有科學內容都嘗試驗證"""
        return True  # 簡化策略：所有科學聲明都嘗試驗證
    
    def _is_real_animal_behavior(self, entity_texts: List[str]) -> bool:
        """簡化：所有生物學內容都嘗試驗證"""
        return True  # 簡化策略：所有生物學聲明都嘗試驗證

    def _local_category_match(self, category: str, text: str) -> bool:
        if not text:
            return False

        if self.multi_kb and hasattr(self.multi_kb, "is_local_category_match"):
            try:
                return self.multi_kb.is_local_category_match(category, text)
            except Exception:
                pass

        if self._local_category_cache is None:
            self._local_category_cache = self._load_local_categories_from_file()

        keywords = self._local_category_cache.get(category, [])
        if not keywords:
            return False

        lowered = text.lower()
        return any(keyword in lowered for keyword in keywords)

    def _load_local_categories_from_file(self) -> Dict[str, List[str]]:
        path = getattr(self, "_local_category_config_path", None)
        if not path or not os.path.exists(path):
            return {}

        try:
            with open(path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except Exception:
            return {}

        categories = data.get("categories", {})
        if not isinstance(categories, dict):
            return {}

        normalized: Dict[str, List[str]] = {}
        for name, keywords in categories.items():
            if not isinstance(keywords, list):
                continue

            cleaned = sorted({kw.lower().strip() for kw in keywords if isinstance(kw, str) and kw.strip()})
            if cleaned:
                normalized[name] = cleaned

        return normalized

    def _is_common_animal_behavior(self, entity_texts: List[str]) -> bool:
        """判斷是否為常見動物行為常識"""
        if not entity_texts:
            return False
        combined_text = " ".join(entity_texts)
        return self._local_category_match("animal_behavior", combined_text)

    def _is_natural_phenomena_fact(self, entity_texts: List[str]) -> bool:
        """判斷是否為自然現象常識"""
        if not entity_texts:
            return False
        combined_text = " ".join(entity_texts)
        return self._local_category_match("natural_phenomena", combined_text)

    def _is_social_norm_fact(self, entity_texts: List[str]) -> bool:
        """判斷是否為社會常識"""
        if not entity_texts:
            return False
        combined_text = " ".join(entity_texts)
        return self._local_category_match("social_norms", combined_text)

    def _is_common_sense_fact(self, entity_texts: List[str]) -> bool:
        """判斷是否為一般常識"""
        if not entity_texts:
            return False
        combined_text = " ".join(entity_texts)
        return self._local_category_match("common_sense", combined_text)
        
    def _has_concrete_temporal(self, entities: List[Tuple[str, str]]) -> bool:
        """檢查是否包含具體的時間信息（可驗證的）"""
        for text, label in entities:
            if label in {"DATE", "TIME"}:
                t = text.lower().strip()
                # 具體年份
                if re.search(r'\b\d{4}\b', t):
                    return True
                # 具體月日
                if re.search(r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d+\b', t):
                    return True
                # 歷史時期
                if any(period in t for period in ["century", "bc", "ad", "dynasty"]):
                    return True
        return False
    
    def _has_verifiable_numerical(self, entities: List[Tuple[str, str]], has_number_token: bool) -> bool:
        """檢查是否包含可驗證的數值信息"""
        if not has_number_token:
            return False
        
        # 檢查是否為有意義的測量或統計數據
        numerical_patterns = [
            r'\b\d+\s*(?:km|mile|meter|feet|celsius|fahrenheit|kg|pound|liter|gallon)\b',
            r'\b\d+\s*(?:percent|%)\b',
            r'\b\d{4}\b',  # 年份
            r'\b\d+\s*(?:million|billion|thousand)\b'
        ]
        
        for text, _ in entities:
            for pattern in numerical_patterns:
                if re.search(pattern, text.lower()):
                    return True
        
        return False

    def _has_non_vague_temporal(self, entities: List[Tuple[str, str]]) -> bool:
        """檢查是否包含非模糊的時間表述（避免 'one day' 這類）」"""
        vague_terms = {
            "one day", "some day", "someday", "today", "yesterday", "tomorrow",
            "one morning", "one evening", "one night", "once"
        }
        for text, label in entities:
            if label in {"DATE", "TIME"}:
                t = text.lower().strip()
                # 若包含數字日期或月份，視為非模糊
                if re.search(r"\b\d{4}\b", t) or re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", t):
                    return True
                if t in vague_terms:
                    continue
                # 長度較長且具體（例如 'on Monday morning'）
                if len(t.split()) >= 2 and not any(v in t for v in vague_terms):
                    return True
        return False

    def _extract_svo_triples(self, doc) -> List[Tuple[str, str, str]]:
        """使用依存關係抽取簡單 SVO 三元組（兒童文本友好）"""
        if doc is None:
            return []
        triples: List[Tuple[str, str, str]] = []
        # 對每個動詞，尋找 nsubj 與 dobj/attr/pobj
        for token in doc:
            if token.pos_ == 'VERB' or token.dep_ == 'ROOT':
                subject = None
                obj = None
                # 主語
                for child in token.children:
                    if child.dep_ in {'nsubj', 'nsubjpass'}:
                        subject = child.subtree
                        subject = ' '.join([t.text for t in subject])
                        break
                # 受詞或補語
                for child in token.children:
                    if child.dep_ in {'dobj', 'attr', 'pobj', 'dative', 'oprd'}:
                        obj = child.subtree
                        obj = ' '.join([t.text for t in obj])
                        break
                if subject and obj:
                    triples.append((subject, token.lemma_, obj))
        # 去重與截斷
        unique = []
        seen = set()
        for s, v, o in triples:
            key = (s.lower().strip(), v.lower().strip(), o.lower().strip())
            if key not in seen:
                seen.add(key)
                # 避免過長
                unique.append((s[:80], v[:40], o[:80]))
        return unique[:5]

    def _link_entities_via_wikipedia(self, entity_texts: List[str]) -> Dict[str, Dict[str, str]]:
        """以維基搜尋進行輕量實體連結，專注於真實世界知識實體"""
        links: Dict[str, Dict[str, str]] = {}
        try:
            api = getattr(self.wikipedia_checker, 'api', None)
            if not api:
                return links
            
            # 真實世界知識實體白名單（優先連結）
            real_world_entities = {
                # 動物
                "rabbit", "rabbits", "bear", "bears", "cat", "cats", "dog", "dogs",
                "bird", "birds", "fish", "elephant", "elephants", "lion", "lions",
                
                # 科學概念
                "water", "sun", "moon", "earth", "gravity", "light", "sound",
                "photosynthesis", "heart", "brain", "lungs", "dew", "starlight",
                
                # 烹飪和食物科學
                "flour", "sugar", "butter", "cookies", "baking", "oven",
                
                # 植物和自然
                "flowers", "trees", "plants", "garden", "grass", "leaves", 
                "forest", "pine", "branches",
                
                # 地理
                "china", "usa", "america", "france", "japan", "england",
                "london", "paris", "tokyo", "beijing",
                
                # 機構
                "nasa", "who", "unesco", "microsoft", "google", "apple"
            }
            
            # 虛構角色黑名單
            fictional_blacklist = {
                "alex", "emma", "sarah", "lisa", "tom", "pip", "grandpa tom", 
                "grandpa", "mom", "dad", "mother", "father", "toy", "cookie",
                "magic", "forest", "castle", "fairy", "dragon"
            }
            
            for ent in entity_texts[:3]:
                q = ent.strip()
                if not q or len(q) < 3:
                    continue
                
                q_lower = q.lower()
                
                # 跳過明顯的虛構元素
                if q_lower in fictional_blacklist:
                    continue
                
                # 跳過時間泛稱詞
                if q_lower in {"one day", "today", "yesterday", "tomorrow", "morning", "afternoon", "evening"}:
                    continue
                
                # 跳過數字和頁碼
                if re.match(r'^\d+$', q) or re.match(r'^Page \d+', q):
                    continue
                
                # 優先處理真實世界實體
                is_real_world_entity = q_lower in real_world_entities
                
                results = api.search_pages(q, limit=3)
                if results:
                    best_result = None
                    for r in results:
                        # 對真實世界實體降低閾值，對其他實體提高閾值
                        min_score = 0.6 if is_real_world_entity else 0.8
                        if getattr(r, 'relevance_score', 0.0) < min_score:
                            continue
                        
                        title_lower = r.title.lower()
                        
                        # 檢查是否為明顯錯誤的連結
                        if self._is_bad_wikipedia_link(q_lower, title_lower):
                            continue
                        
                        # 檢查標題相關性
                        if self._is_relevant_wikipedia_link(q_lower, title_lower, is_real_world_entity):
                            best_result = r
                            break
                    
                    if best_result:
                        links[q] = {"title": best_result.title, "url": best_result.url}
                        
        except Exception:
            return links
        return links
    
    def _is_bad_wikipedia_link(self, query: str, title: str) -> bool:
        """檢查是否為明顯錯誤的維基百科連結"""
        # 已知的錯誤連結模式
        bad_links = {
            ("lisa", "lisa"): True,  # Lisa -> LiSA (歌手)
            ("pip", "pip"): True,    # Pip -> PIP (程式包管理器)
            ("alex", "alex"): True,  # 常見名字的誤連
            ("emma", "emma"): True,
            ("tom", "tom"): True
        }
        
        return bad_links.get((query, title), False)
    
    def _is_relevant_wikipedia_link(self, query: str, title: str, is_real_world_entity: bool) -> bool:
        """檢查維基百科連結是否相關"""
        # 對真實世界實體採用較寬鬆的標準
        if is_real_world_entity:
            # 完全匹配或包含關係
            if query == title or query in title or title in query:
                return True
            # 檢查是否有共同的關鍵詞
            query_words = set(query.split())
            title_words = set(title.split())
            if len(query_words.intersection(title_words)) > 0:
                return True
        else:
            # 對非真實世界實體採用嚴格標準
            if query == title:
                return True
            # 只接受高度相關的連結
            if query in title and len(query) > 3:
                return True
        
        return False
    
    def _is_meaningful_claim(self, claim_text: str, sentence: str) -> bool:
        """檢查是否為有意義的事實聲明（移除領域特定正則，採用通用訊號）
        原則：
        - 使用通用可驗證性評分（NER、數值、SVO、長度、語氣）
        - 可選用 AI 分類輔助（若可用），避免硬編碼清單
        - 新增：過濾虛構故事中的文化元素和設定
        """
        # 放寬最小長度，允許數據句（例如："8,849 meters" 類型）
        tokens = claim_text.split()
        if len(tokens) < 2 and not re.search(r"\b\d+\b", claim_text):
            return False
        if re.match(r'^Page \d+:', claim_text.strip()):
            return False
        if re.match(r'^\d+:', claim_text.strip()):
            return False
        # 過濾純引號對話（但允許帶數據的陳述）
        if claim_text.strip().startswith('"') and claim_text.strip().endswith('"'):
            if not re.search(r"\d", claim_text):
                return False

        # 若包含強可驗證訊號，直接視為有意義（年份、數值+單位）
        if re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", claim_text):
            return True
        if re.search(r"\b\d+(?:[\.,]\d+)?\s*(?:km|kilometer|meter|m|kg|ton|tons|mph|km/h|kph|percent|%)\b", claim_text.lower()):
            return True

        # 先檢查句中是否包含「普遍事實語氣」的 SVO 片段（即使整句是虛構敘事也保留）
        try:
            doc = self.nlp(sentence) if getattr(self, 'nlp', None) else None
            triples = self._extract_svo_triples(doc) if doc is not None else []
            for s, v, o in triples:
                if self._looks_like_universal_fact(s, v, o, sentence):
                    return True
        except Exception:
            pass

        # 新增：過濾明顯的虛構故事內容
        if self._is_obviously_fictional_content(sentence):
            return False

        # 基於通用特徵的可驗證性評分
        score = self._estimate_verifiability_score(sentence)
        if score >= 0.35:  # 降低閾值，讓更多潛在事實通過
            return True

        # 若模型可用，使用 AI 輔助判定此句是否屬於「可對外部知識驗證的事實敘述」
        if self._ai_is_real_world_fact(sentence) is True:
            return True

        return False
    
    def _is_obviously_fictional_content(self, sentence: str) -> bool:
        """簡化：只檢測明顯的虛構內容"""
        # 簡化策略：只檢測明顯的虛構模式，避免誤判科學事實
        sentence_lower = sentence.lower()
        
        # 明顯的虛構模式
        fictional_patterns = [
            r'\b(once upon a time|long ago|in a faraway land)\b',
            r'\b(magic|spell|fairy|dragon|princess|prince)\b',
            r'\b(and they lived happily ever after)\b'
        ]
        
        for pattern in fictional_patterns:
            if re.search(pattern, sentence_lower):
                return True
        
        return False  # 默認不認為是虛構內容
    
    def _fallback_fictional_detection(self, sentence: str) -> bool:
        """備用的虛構內容檢測（當 AI 不可用時）"""
        sentence_lower = sentence.lower()
        
        # 基本的虛構內容模式
        fictional_patterns = [
            r'\b(?:once upon a time|long ago|in a magical|in the enchanted)\b',
            r'\b(?:grandpa|grandma|emma|alex|tom)\b.*\b(?:workshop|cozy|magical)\b',
            r'\b(?:twirled|sparkled|giggled|squealed|beamed)\b',
            r'\b(?:eyes twinkled|heart fluttered|magical journey)\b',
            r'\b(?:let\'s explore|what if we learn|we\'re going on)\b',
            r'^".*"$',  # 純對話
            r'\b(?:said|asked|replied|exclaimed)\b.*"[^"]*"',  # 對話標記
        ]
        
        for pattern in fictional_patterns:
            if re.search(pattern, sentence_lower):
                return True
        
        return False

    def _looks_like_universal_fact(self, subject: str, verb: str, obj: str, sentence: str) -> bool:
        """偵測是否為普遍事實語氣：
        - 一般現在式/恆常性（can/cannot, usually/often, all/most）
        - 否定/能力/量化/屬性陳述（be-動詞 + 名詞/形容詞）
        - 不依賴特定詞庫，使用模式與 AI gating 輔助
        """
        try:
            s = f"{subject} {verb} {obj}".strip().lower()
            full = sentence.lower()

            # 能力/否定/頻率/量化指示
            indicators = [
                r"\bcan(not)?\b", r"\bcannot\b", r"\bcan't\b", r"\bnever\b", r"\balways\b",
                r"\boften\b", r"\busually\b", r"\btypically\b", r"\bgenerally\b", r"\bcommonly\b",
                r"\ball\b", r"\bmost\b", r"\bsome\b", r"\bno\b",
            ]
            if any(re.search(p, full) for p in indicators):
                return True

            # be-動詞屬性敘述（X is Y 類型）
            if re.search(r"\b(is|are|am|be|being|been)\b", full):
                # 避免純對話/事件性描述
                if not re.search(r"\b(said|asked|replied|exclaimed)\b", full):
                    return True

            # AI 輔助：是否屬於可對外驗證的普遍事實
            ai_flag = self._ai_is_real_world_fact(s)
            if ai_flag is True:
                return True

        except Exception:
            pass

        return False
    
    def _assess_claim_confidence(self, claim_text: str, sentence: str) -> float:
        """評估聲明的置信度"""
        confidence = 0.5  # 基礎置信度
        
        # 檢查確定性標記
        certainty_markers = ['definitely', 'certainly', 'absolutely', 'proven', 'fact']
        uncertainty_markers = ['maybe', 'perhaps', 'possibly', 'might', 'could', 'probably']
        
        sentence_lower = sentence.lower()
        
        for marker in certainty_markers:
            if marker in sentence_lower:
                confidence += 0.2
                break
        
        for marker in uncertainty_markers:
            if marker in sentence_lower:
                confidence -= 0.2
                break
        
        # 檢查是否為對話內容（通常置信度較低）
        if '"' in sentence or 'said' in sentence_lower:
            confidence -= 0.1
        
        # 檢查是否為第一人稱敘述（可能是主觀的）
        if re.search(r'\b(?:I|we|my|our)\b', sentence, re.IGNORECASE):
            confidence -= 0.1
        
        return max(0.1, min(0.9, confidence))
    
    def _is_verifiable_claim(self, claim_text: str, claim_type: str) -> bool:
        """智能檢查聲明是否可驗證"""
        # 虛構內容明確不可驗證
        if claim_type == 'fictional':
            return False
        
        # 使用AI智能檢測虛構內容
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                判斷以下聲明是否包含虛構內容，無法通過外部知識庫驗證：
                
                聲明：{claim_text}
                
                考慮因素：
                1. 是否包含虛構人物、機構或事件
                2. 是否為敘事性描述而非客觀事實
                3. 是否可以通過公開資料驗證
                
                只回答：可驗證 或 不可驗證
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "不可驗證" in ai_response or "unverifiable" in ai_response:
                    return False
        except Exception:
            pass
        
        # 使用AI智能判斷可驗證性
        try:
            prompt = f"""
            判斷以下聲明是否可以通過外部知識庫（如維基百科、科學數據庫）進行客觀驗證：
            
            聲明：{claim_text}
            類型：{claim_type}
            
            考慮因素：
            1. 是否包含客觀事實（時間、地點、人物、數據）
            2. 是否為虛構故事元素
            3. 是否可以通過公開資料驗證
            
            只回答：可驗證 或 不可驗證
            """
            
            if self.ai and self.ai.model_available:
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "可驗證" in ai_response or "verifiable" in ai_response:
                    return True
                elif "不可驗證" in ai_response or "unverifiable" in ai_response:
                    return False
                else:
                    # AI回應不明確時使用備用邏輯
                    return self._fallback_verifiability_check(claim_type)
            else:
                return self._fallback_verifiability_check(claim_type)
                
        except Exception as e:
            # AI分析失敗時使用備用邏輯
            return self._fallback_verifiability_check(claim_type)
    
    def _fallback_verifiability_check(self, claim_type: str) -> bool:
        """備用可驗證性檢查邏輯"""
        # 可驗證的聲明類型
        verifiable_types = [
            'numerical', 'geographical', 'temporal', 'historical', 
            'scientific', 'biographical', 'institutional', 'factual'
        ]
        
        return claim_type in verifiable_types
    
    def _deduplicate_claims(self, claims: List[FactualClaim]) -> List[FactualClaim]:
        """去除重複的聲明"""
        unique_claims = []
        seen_texts = set()
        
        for claim in claims:
            # 簡化的去重邏輯
            normalized_text = re.sub(r'\s+', ' ', claim.text.lower().strip())
            
            if normalized_text not in seen_texts:
                seen_texts.add(normalized_text)
                unique_claims.append(claim)
        
        return unique_claims
    
    def _verify_claims(self, claims: List[FactualClaim]) -> List[FactCheckResult]:
        """驗證事實聲明（支援並行）"""
        total = len(claims)
        verifiable_total = len([c for c in claims if c.verifiable])
        self._log(f"[驗證] 開始驗證：共 {total} 條（可驗證 {verifiable_total}，執行緒 {self.verify_max_workers}）")
        
        # 準備結果容器，保持輸出順序穩定
        results: List[Optional[FactCheckResult]] = [None] * total
        completed_count = 0
        
        # 先處理不可驗證（不需 I/O）
        for idx, claim in enumerate(claims):
            if not claim.verifiable:
                results[idx] = FactCheckResult(
                    claim=claim,
                    verdict="unverifiable",
                    evidence=["此聲明無法通過客觀事實驗證"],
                    confidence=0.0,
                    sources=[],
                    risk_level="low"
                )
                completed_count += 1
        
        self._update_progress(completed_count, total, "聲明驗證")
        
        # 並行處理可驗證的部分
        def _task(index_claim: Tuple[int, FactualClaim]) -> Tuple[int, FactCheckResult]:
            nonlocal completed_count
            idx, claim = index_claim
            self._log(f"[驗證] ({idx+1}/{total}) {claim.claim_id} | 文：{self._truncate(claim.text, 100)}")
            result = self._verify_single_claim(claim)
            completed_count += 1
            self._update_progress(completed_count, total, "聲明驗證")
            return idx, result
            
        tasks: List[Tuple[int, FactualClaim]] = [(i, c) for i, c in enumerate(claims) if c.verifiable]
        if tasks:
            with ThreadPoolExecutor(max_workers=self.verify_max_workers) as executor:
                for idx, res in executor.map(_task, tasks):
                    results[idx] = res
        
        # 回填確保無 None
        filled = [r for r in results if r is not None]
        self._log(f"[驗證] 全部完成（成功 {len(filled)}/{total}）")
        return filled
    
    def _get_cache_key(self, text: str) -> str:
        """生成快取鍵值"""
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
    
    def _verify_single_claim(self, claim: FactualClaim) -> FactCheckResult:
        """驗證單個聲明（支援快取）"""
        # 🚀 檢查驗證快取
        cache_key = self._get_cache_key(claim.text)
        if cache_key in self._verification_cache:
            cached_result = self._verification_cache[cache_key]
            # 更新聲明ID但保留快取的驗證結果
            cached_result.claim = claim
            self._log(f"[快取] 使用快取結果：{self._truncate(claim.text, 100)}")
            return cached_result
        
        # 0. 移除列舉式快速規則，僅使用通用級聯驗證
        self._log(f"[驗證/單條] 開始 {claim.claim_id} → {self._truncate(claim.text, 100)}")
        # 1. 多知識庫事實檢查（如果啟用）
        if self.enable_wikipedia and self.multi_kb:
            self._log("[驗證/單條] 嘗試多知識庫檢查…")
            multi_kb_result = self._multi_kb_fact_check(claim)
            if multi_kb_result:
                self._log(f"[驗證/單條] 多知識庫結果：{multi_kb_result.verdict} (conf={multi_kb_result.confidence:.2f})")
                return multi_kb_result
        
        # 2. 使用AI進行初步判斷
        self._log("[驗證/單條] 嘗試 AI 檢查…")
        ai_result = self._ai_fact_check(claim)
        if ai_result:
            self._log(f"[驗證/單條] AI 結果：{ai_result.verdict} (conf={ai_result.confidence:.2f})")
            return ai_result
        
        # 3. 網路搜尋（如果啟用）
        if self.enable_web_search:
            self._log("[驗證/單條] 嘗試 Web 檢查…")
            web_result = self._web_fact_check(claim)
            if web_result:
                self._log(f"[驗證/單條] Web 結果：{web_result.verdict} (conf={web_result.confidence:.2f})")
                return web_result
        
        # 4. 默認結果
        self._log("[驗證/單條] 無法驗證 → 標記 uncertain")
        result = FactCheckResult(
            claim=claim,
            verdict="uncertain",
            evidence=["無法找到足夠的證據來驗證此聲明"],
            confidence=0.3,
            sources=[],
            risk_level=self._assess_claim_risk(claim)
        )
        
        # 🚀 儲存到快取
        self._verification_cache[cache_key] = result
        return result

    def _multi_kb_fact_check(self, claim: FactualClaim) -> Optional[FactCheckResult]:
        """使用多知識庫進行事實檢查"""
        if not self.enable_wikipedia or not self.multi_kb:
            return None
        
        try:
            # 判斷聲明類型以優化查詢
            claim_type = self._infer_claim_type(claim.text)
            self._log(f"[多知識庫] 聲明類型：{claim_type}")
            
            # 使用多知識庫驗證事實
            kb_results = self.multi_kb.verify_fact(claim.text, claim_type)
            self.performance_stats['wikipedia_queries'] += 1  # 保持統計一致性
            
            if not kb_results:
                return None
            
            # 聚合多知識庫結果
            verdict, confidence, evidence = self.multi_kb.aggregate_results(kb_results)
            self._log(f"[多知識庫] 聚合結果：{verdict} (置信度: {confidence:.2f})")
            
            # 轉換結果格式
            verdict_mapping = {
                'supported': 'supported',
                'refuted': 'refuted', 
                'uncertain': 'uncertain',
                'not_found': 'unverifiable',
                'error': 'uncertain'
            }
            
            final_verdict = verdict_mapping.get(verdict, 'uncertain')
            
            # 組合證據和來源
            final_evidence = evidence.copy()
            sources = []
            
            # 添加知識庫來源信息
            for kb_result in kb_results:
                if kb_result.source and kb_result.evidence:
                    # 添加所有證據，不只是第一個
                    for evidence_item in kb_result.evidence[:3]:  # 限制最多3個證據
                        final_evidence.append(f"[{kb_result.source}] {evidence_item}")
                    sources.append(f"{kb_result.source}知識庫")
            
            return FactCheckResult(
                claim=claim,
                verdict=final_verdict,
                evidence=final_evidence,
                confidence=confidence,
                sources=sources,
                risk_level=self._assess_claim_risk(claim)
            )
            
        except Exception as e:
            self.logger.exception("多知識庫事實檢查失敗: %s", e)
            return None
    
    def _infer_claim_type(self, claim_text: str) -> str:
        """智能推斷聲明類型 - 使用AI分析而非硬編碼關鍵詞"""
        try:
            # 使用AI智能分析聲明類型
            prompt = f"""
            分析以下聲明的類型，選擇最合適的分類：
            
            聲明：{claim_text}
            
            分類選項：
            - biographical: 人物傳記、生平事蹟
            - geographical: 地理位置、氣候、地理特徵
            - scientific: 科學發現、理論、實驗、數據
            - historical: 歷史事件、年代、歷史人物
            - numerical: 數值、統計、測量數據
            - institutional: 機構、組織、大學
            - animal_behavior: 動物行為、習性描述
            - natural_phenomena: 自然現象、物理常識
            - social_norms: 社會常識、文化規範
            - common_sense: 一般常識、生活經驗
            - fictional: 純虛構人物、故事元素
            - general: 其他一般性事實
            
            只回答分類名稱，不要其他內容。
            """
            
            if self.ai and self.ai.model_available:
                try:
                    result = self.ai.analyze_consistency(prompt, [], {})
                    ai_response = result.get("analysis", "").strip().lower()
                    
                    # 解析AI回應
                    valid_types = ["biographical", "geographical", "scientific", "historical", 
                                 "numerical", "institutional", "animal_behavior", "natural_phenomena",
                                 "social_norms", "common_sense", "fictional", "general"]
                    
                    for claim_type in valid_types:
                        if claim_type in ai_response:
                            return claim_type
                    
                    # 如果AI回應不包含有效類型，使用備用邏輯
                    return self._fallback_claim_type_inference(claim_text)
                except Exception as e:
                    # AI分析失敗時使用備用邏輯
                    return self._fallback_claim_type_inference(claim_text)
            else:
                return self._fallback_claim_type_inference(claim_text)
                
        except Exception as e:
            # AI分析失敗時使用備用邏輯
            return self._fallback_claim_type_inference(claim_text)
    
    def _fallback_claim_type_inference(self, claim_text: str) -> str:
        """備用聲明類型推斷邏輯"""
        claim_lower = claim_text.lower()
        
        # 使用AI智能檢測虛構內容
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                分析以下聲明是否包含虛構內容（虛構人物、虛構機構、虛構事件等）：
                
                聲明：{claim_text}
                
                判斷標準：
                1. 是否包含虛構人物（如故事中的角色）
                2. 是否包含虛構機構或組織
                3. 是否包含虛構的發現或事件
                4. 是否為敘事性描述而非客觀事實
                
                只回答：虛構 或 真實
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "虛構" in ai_response or "fictional" in ai_response:
                    return "fictional"
        except Exception:
            pass
        
        # 智能內容類型檢測
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                分析以下聲明的內容類型：
                
                聲明：{claim_text}
                
                分類選項：
                - scientific: 科學發現、理論、實驗、數據
                - biographical: 人物傳記、生平事蹟
                - geographical: 地理位置、氣候、地理特徵
                - historical: 歷史事件、年代、歷史人物
                - numerical: 數值、統計、測量數據
                - institutional: 機構、組織、大學
                - general: 其他一般性事實
                
                只回答分類名稱。
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                valid_types = ["scientific", "biographical", "geographical", "historical", "numerical", "institutional", "general"]
                for claim_type in valid_types:
                    if claim_type in ai_response:
                        return claim_type
        except Exception:
            pass
        
        # 默認返回一般類型
        return "general"

    def _simplify_claim_for_wikipedia(self, claim: FactualClaim) -> str:
        """將聲明簡化為適合百科檢索的客觀句式。
        策略：
        - 優先使用 SVO 三元組重組（若可用）
        - 移除引號、語氣詞與直接引述
        - 壓縮多餘空白，保留核心名詞/數字
        """
        text = (claim.text or '').strip()
        # 去掉引號
        text = text.replace('"', '"').replace('"', '"')
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        # 以三元組重建
        triples = claim.triples or []
        if triples:
            s, v, o = triples[0]
            candidate = f"{s} {v} {o}".strip()
            # 避免過短或不通順則回退
            if len(candidate.split()) >= 3:
                return candidate
        # 去掉明顯的對話與說話動詞片段
        text = re.sub(r"\b(said|asked|told|replied)\b.*$", "", text, flags=re.IGNORECASE).strip()
        # 合併多空白
        text = re.sub(r"\s+", " ", text)
        return text

    def _generate_wikipedia_queries(self, claim: FactualClaim) -> List[str]:
        """根據句子與實體自動生成若干百科查詢候選。
        策略：
        1) 使用 SVO/簡化句作為通用候選
        2) 利用實體標籤、年份、數值+單位構造目標化查詢（資源友善，避免泛化關鍵詞）
        """
        queries: List[str] = []
        simplified = self._simplify_claim_for_wikipedia(claim)
        if simplified:
            queries.append(simplified)
        if claim.text:
            queries.append(claim.text)

        # 依實體構造關鍵查詢（加強：人名+事件/年份、地標+高度/長度、作品+出版年）
        entities = claim.entities or []
        labels = {lbl for _, lbl in entities}
        ents_by_label: Dict[str, List[str]] = {}
        for text, lbl in entities:
            ents_by_label.setdefault(lbl, []).append(text)

        lower_text = (claim.text or '').lower()

        # 提取年份、數值+單位
        years = re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", claim.text or '')
        num_units = re.findall(r"\b(\d+(?:[\.,]\d+)?)\s*(km|kilometer|kilometre|meters|meter|metres|m|kg|ton|tons|km/h|kph|mph|%)\b", lower_text)

        persons = (ents_by_label.get('PERSON') or [])
        works = (ents_by_label.get('WORK_OF_ART') or [])
        places = (ents_by_label.get('GPE') or []) + (ents_by_label.get('LOC') or []) + (ents_by_label.get('FAC') or [])
        orgs = (ents_by_label.get('ORG') or [])

        # 人名 + 特定事件關鍵詞/年份
        if persons:
            for p in persons[:2]:
                if 'discover' in lower_text:
                    # e.g., "Marie Curie discovered radium 1898"
                    target = (works[:1] or orgs[:1] or places[:1] or ["discovery"])[0]
                    y = years[:1]
                    q = f"{p} discovered {target}" if not y else f"{p} discovered {target} {y[0]}"
                    queries.append(q)
                if any(k in lower_text for k in ['won', 'nobel', 'prize']):
                    # e.g., "Marie Curie Nobel Prize 1903 Physics"
                    y = years[:1]
                    queries.append(f"{p} Nobel Prize {y[0]}" if y else f"{p} Nobel Prize")
                if any(k in lower_text for k in ['ascent', 'climb', 'first successful']):
                    # e.g., "Edmund Hillary Tenzing Norgay Everest 1953"
                    mountain = places[:1] or ["Mount Everest"]
                    y = years[:1]
                    queries.append(f"{p} {mountain[0]} {y[0]}" if y else f"{p} {mountain[0]}")

        # 地標/設施 + 高度/長度/速度/面積（帶單位）
        if places or orgs:
            targets = (places or []) + (orgs or [])
            for t in targets[:3]:
                if any(k in lower_text for k in ['height','tall','elevation','meters','metres','m']):
                    queries.append(f"{t} height")
                if any(k in lower_text for k in ['length','long','km','kilometer','kilometre']):
                    queries.append(f"{t} length")
                if any(k in lower_text for k in ['speed','km/h','kph','mph']):
                    queries.append(f"{t} speed")
                if any(k in lower_text for k in ['area','square kilometers','km^2','km²']):
                    queries.append(f"{t} area")

        # 物理常數/學科通用精確查詢
        if any(k in lower_text for k in ['speed of light','299,792,458','299792458']):
            queries.append('speed of light exact value')
            queries.append('speed of light metres per second')
        if 'boil' in lower_text and 'water' in lower_text:
            queries.append('water boiling point at sea level')

        # 期刊/出版年（作品）
        if works:
            for w in works[:2]:
                if years:
                    queries.append(f"{w} {years[0]}")
                queries.append(w)

        # 科學/健康：通用關鍵詞
        science_keys = [
            ('boil' in lower_text or 'freeze' in lower_text, 'water boiling point sea level'),
            ('body temperature' in lower_text or 'normal body temperature' in lower_text, 'normal human body temperature'),
            ('chicken' in lower_text and ('cook' in lower_text or 'cooked' in lower_text), 'safe minimum cooking temperature chicken'),
            ('antibiotic' in lower_text and ('virus' in lower_text or 'viral' in lower_text), 'antibiotics effectiveness against viruses'),
            ('vaccine' in lower_text and ('immune' in lower_text or 'immunity' in lower_text), 'how vaccines work immune system')
        ]
        for cond, q in science_keys:
            if cond:
                queries.append(q)

        # 去重，保持順序
        seen: Set[str] = set()
        unique: List[str] = []
        for q in queries:
            qq = q.strip()
            if not qq or qq.lower() in seen:
                continue
            seen.add(qq.lower())
            unique.append(qq)
        return unique[:8]
    
    # （移除 _check_local_knowledge 與 _texts_similar，統一走外部驗證）
    
    def _ai_fact_check(self, claim: FactualClaim) -> Optional[FactCheckResult]:
        """使用AI進行事實檢查"""
        if not self.ai or not self.ai.model_available:
            return None
        
        prompt = f"""
        請評估以下聲明的事實正確性：
        
        聲明：{claim.text}
        上下文：{claim.context}
        類型：{claim.claim_type}
        
        請回答：
        1. 這個聲明是否正確？(正確/錯誤/不確定)
        2. 你的置信度如何？(0-1)
        3. 簡要說明理由
        
        格式：VERDICT: [正確/錯誤/不確定], CONFIDENCE: [0-1], REASON: [理由]
        """
        
        try:
            # 使用現有的AI分析介面
            ai_result = self.ai.analyze_consistency(claim.context, [], {})
            
            # 簡化的結果解析
            ai_score = ai_result.get("ai_score", 50)
            
            if ai_score >= 70:
                verdict = "supported"
                confidence = 0.7
            elif ai_score <= 30:
                verdict = "refuted"
                confidence = 0.7
            else:
                verdict = "uncertain"
                confidence = 0.5
            
            return FactCheckResult(
                claim=claim,
                verdict=verdict,
                evidence=[f"AI分析: {ai_result.get('analysis', '無詳細分析')}"],
                confidence=confidence,
                sources=["ai_analysis"],
                risk_level=self._assess_claim_risk(claim)
            )
            
        except Exception as e:
            return None
    
    def _web_fact_check(self, claim: FactualClaim) -> Optional[FactCheckResult]:
        """網路事實檢查（簡化版本）"""
        if not self.enable_web_search:
            return None
        
        # 這裡可以實現真實的網路搜尋
        # 目前返回模擬結果
        return FactCheckResult(
            claim=claim,
            verdict="uncertain",
            evidence=["網路搜尋功能暫未完全實現"],
            confidence=0.3,
            sources=["web_search_placeholder"],
            risk_level=self._assess_claim_risk(claim)
        )
    
    def _assess_claim_risk(self, claim: FactualClaim) -> str:
        """評估聲明的風險等級，專注於真實世界知識的準確性"""
        claim_text_lower = claim.text.lower()
        
        # 檢查高風險模式（絕對性聲明、醫療聲明等）
        for pattern in self.high_risk_patterns:
            if re.search(pattern, claim_text_lower):
                return "high"
        
        # 智能風險評估
        try:
            if self.ai and self.ai.model_available:
                prompt = f"""
                評估以下聲明的風險等級：
                
                聲明：{claim.text}
                
                風險等級：
                - high: 可能誤導、有害、錯誤的聲明
                - medium: 需要謹慎對待的聲明
                - low: 一般性、低風險的聲明
                
                只回答風險等級。
                """
                
                result = self.ai.analyze_consistency(prompt, [], {})
                ai_response = result.get("analysis", "").strip().lower()
                
                if "high" in ai_response:
                    return "high"
                elif "medium" in ai_response:
                    return "medium"
        except Exception:
            pass
        
        # 基於新的聲明類型系統評估風險
        risk_levels = {
            'scientific': 'medium',     # 科學事實錯誤可能誤導
            'biological': 'medium',     # 動物習性錯誤影響教育
            'historical': 'medium',     # 歷史事實錯誤需要糾正
            'geographical': 'low',      # 地理錯誤相對影響較小
            'institutional': 'low',     # 機構信息錯誤影響較小
            'numerical': 'low',         # 數值錯誤通常影響有限
            'temporal': 'low',          # 時間錯誤影響較小
            'biographical': 'low',      # 人物信息在虛構語境下風險較低
            'fictional': 'none',        # 虛構內容無事實風險
            'factual': 'low'           # 一般事實風險較低
        }
        
        return risk_levels.get(claim.claim_type, 'low')
    
    def _assess_risk_levels(self, results: List[FactCheckResult]) -> Dict:
        """評估整體風險等級"""
        risk_counts = Counter(result.risk_level for result in results)
        verdict_counts = Counter(result.verdict for result in results)
        
        # 計算高風險聲明
        high_risk_claims = [r for r in results if r.risk_level == "high"]
        refuted_claims = [r for r in results if r.verdict == "refuted"]
        uncertain_claims = [r for r in results if r.verdict == "uncertain"]
        
        # 評估整體風險
        if len(high_risk_claims) > 0 or len(refuted_claims) > 2:
            overall_risk = "high"
        elif len(refuted_claims) > 0 or len(uncertain_claims) > 3:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        return {
            "overall_risk": overall_risk,
            "risk_distribution": dict(risk_counts),
            "verdict_distribution": dict(verdict_counts),
            "high_risk_claims": len(high_risk_claims),
            "refuted_claims": len(refuted_claims),
            "uncertain_claims": len(uncertain_claims),
            "supported_claims": len([r for r in results if r.verdict == "supported"])
        }
    
    def _advanced_ai_fact_check(self, story_text: str, claims: List[FactualClaim], 
                               results: List[FactCheckResult]) -> Dict:
        """AI 深度事實檢查分析"""
        if not self.ai or not self.ai.model_available:
            return {"score": FACTUAL_AI_FALLBACK_SCORE, "analysis": "AI模型不可用，使用基礎評分"}
        
        # 統計摘要
        total_claims = len(claims)
        verifiable_claims = len([c for c in claims if c.verifiable])
        supported_claims = len([r for r in results if r.verdict == "supported"])
        
        prompt = f"""
        請分析以下故事的事實正確性：
        
        故事摘要：{story_text[:800]}...
        
        事實聲明統計：
        - 總聲明數：{total_claims}
        - 可驗證聲明：{verifiable_claims}  
        - 支持的聲明：{supported_claims}
        
        請評估整體事實可信度（0-100分）並說明主要風險。
        """
        
        try:
            # 使用整理過的提示詞，避免把原文直接丟進通用一致性入口造成上下文失焦
            ai_result = self.ai.analyze_consistency(prompt, [], {})
            ai_score = normalize_score_0_100(
                ai_result.get("ai_score", FACTUAL_AI_FALLBACK_SCORE),
                FACTUAL_AI_FALLBACK_SCORE,
            )
            ai_confidence = normalize_confidence_0_1(ai_result.get("confidence", 0.6), 0.6)
            
            return {
                "score": ai_score,
                "analysis": ai_result.get("analysis", "AI事實檢查分析完成"),
                "confidence": ai_confidence,
                "recommendations": self._generate_ai_recommendations(results)
            }
        except Exception as e:
            return {"score": FACTUAL_AI_FALLBACK_SCORE, "analysis": f"AI分析失敗: {str(e)}"}
    
    def _generate_ai_recommendations(self, results: List[FactCheckResult]) -> List[str]:
        """生成AI建議"""
        recommendations = []
        
        refuted_count = len([r for r in results if r.verdict == "refuted"])
        uncertain_count = len([r for r in results if r.verdict == "uncertain"])
        high_risk_count = len([r for r in results if r.risk_level == "high"])
        
        if refuted_count > 0:
            recommendations.append(f"發現 {refuted_count} 個可能錯誤的事實聲明，建議核實")
        
        if uncertain_count > 2:
            recommendations.append(f"有 {uncertain_count} 個不確定的聲明，建議提供更多證據")
        
        if high_risk_count > 0:
            recommendations.append(f"發現 {high_risk_count} 個高風險聲明，需要特別注意")
        
        return recommendations
    
    def _calculate_factuality_scores(self, results: List[FactCheckResult], 
                                   risk_assessment: Dict, ai_analysis: Dict) -> FactualityScores:
        """計算事實正確性分數"""
        if not results:
            # 當未偵測到可驗證聲明時，給較保守且具區分度的分數，以免整體分佈過度集中
            # 調整為較低的基準，並避免覆蓋度默認為高分
            return FactualityScores(55.0, 50.0, 65.0, 58.0)
        
        # 1. 聲明準確度分數 - 修復版：包含所有驗證結果
        supported_count = len([r for r in results if r.verdict == "supported"])
        refuted_count = len([r for r in results if r.verdict == "refuted"])
        uncertain_count = len([r for r in results if r.verdict == "uncertain"])
        unverifiable_count = len([r for r in results if r.verdict == "unverifiable"])
        
        # 計算總驗證結果數（排除unverifiable，因為這些無法驗證）
        total_verified = supported_count + refuted_count + uncertain_count
        
        if total_verified > 0:
            # 支持率：支持數 / 總驗證數
            support_ratio = supported_count / total_verified
            # 錯誤率：反駁數 / 總驗證數
            error_ratio = refuted_count / total_verified
            # 不確定率：不確定數 / 總驗證數
            uncertainty_ratio = uncertain_count / total_verified
            
            # 基礎分數：支持率 * 100
            base_score = support_ratio * 100
            # 錯誤懲罰：每個錯誤聲明扣15分
            error_penalty = error_ratio * 15
            # 不確定懲罰：每個不確定聲明扣5分
            uncertainty_penalty = uncertainty_ratio * 5
            
            claim_accuracy = max(0, base_score - error_penalty - uncertainty_penalty)
        else:
            # 若沒有可驗證的聲明，降低準確度基準，擴大量尺
            claim_accuracy = 55.0
        
        # 2. 驗證覆蓋度分數 - 修復版：基於實際驗證結果
        total_claims = len(results)
        verified_claims = supported_count + refuted_count + uncertain_count  # 實際驗證的聲明數
        
        if total_claims > 0:
            coverage_ratio = verified_claims / total_claims
            verification_coverage = coverage_ratio * 100
        else:
            # 無結果時不給滿分，避免分佈被拉高且喪失區分度
            verification_coverage = 50.0
        
        # 3. 風險評估分數
        risk_level = risk_assessment.get("overall_risk", "low")
        risk_scores = {"low": 90, "medium": 70, "high": 40, "critical": 20}
        risk_score = risk_scores.get(risk_level, 70)
        
        # 高風險聲明額外扣分
        high_risk_count = risk_assessment.get("high_risk_claims", 0)
        # 提高高風險扣分以放大量尺
        risk_penalty = high_risk_count * 22
        risk_assessment_score = max(0, risk_score - risk_penalty)
        
        # 4. 綜合分數
        ai_score = ai_analysis.get("score", 65)
        
        # 🎯 對於高度不可驗證的故事（大部分童話/虛構），擴大分數範圍
        unverifiable_ratio = 1.0 - (verification_coverage / 100.0) if total_claims > 0 else 1.0
        if unverifiable_ratio > 0.7:  # 超過 70% 不可驗證
            # 高度虛構故事：根據風險和 AI 分析調整基礎分數範圍
            if risk_level == "low" and ai_score >= 60:
                # 低風險且 AI 認為合理：給予 60-65 範圍
                base_unverifiable = 62.0 + min(3.0, (ai_score - 60) * 0.6)
            elif risk_level == "medium" or ai_score < 60:
                # 中等風險或 AI 評分較低：55-60 範圍
                base_unverifiable = 57.0 + min(3.0, (ai_score - 55) * 0.6)
            else:
                # 高風險：降低到 50-55
                base_unverifiable = 52.0 + min(3.0, (ai_score - 50) * 0.6)
            
            # 使用調整後的基礎分數，但仍考慮驗證覆蓋度（權重降低）
            claim_accuracy = base_unverifiable
        
        # 權重：準確度與風險為主，覆蓋度次之，AI 輔助提升（從 0.1 提升到 0.15）
        weights = [0.45, 0.2, 0.2, 0.15]  # 調整權重分配
        components = [claim_accuracy, verification_coverage, risk_assessment_score, ai_score]
        final_score = sum(c * w for c, w in zip(components, weights))
        
        # 🎯 對高度不可核故事設上限（避免虛構故事分數過高）
        if unverifiable_ratio > 0.75 and risk_level == "low":
            final_score = min(65.0, final_score)  # 最高不超過 65
        
        return FactualityScores(
            claim_accuracy=claim_accuracy,
            verification_coverage=verification_coverage,
            risk_assessment=risk_assessment_score,
            final=min(100.0, max(0.0, final_score))
        )
    
    def _generate_factuality_suggestions(self, results: List[FactCheckResult], 
                                       risk_assessment: Dict, ai_analysis: Dict) -> List[str]:
        """生成事實正確性建議"""
        suggestions = []
        
        # 基於驗證結果的建議
        refuted_claims = [r for r in results if r.verdict == "refuted"]
        uncertain_claims = [r for r in results if r.verdict == "uncertain"]
        high_risk_claims = [r for r in results if r.risk_level == "high"]
        
        if refuted_claims:
            suggestions.append(f"發現 {len(refuted_claims)} 個可能錯誤的事實，建議核實並修正")
            
            # 提供具體例子
            for result in refuted_claims[:2]:
                suggestions.append(f"  錯誤聲明: '{result.claim.text}' - {result.evidence[0] if result.evidence else '需要驗證'}")
        
        if uncertain_claims:
            suggestions.append(f"有 {len(uncertain_claims)} 個不確定的聲明，建議提供更多證據或標註為虛構")
        
        if high_risk_claims:
            suggestions.append(f"發現 {len(high_risk_claims)} 個高風險聲明，可能誤導讀者")
        
        # 基於風險評估的建議
        overall_risk = risk_assessment.get("overall_risk", "low")
        if overall_risk in ["high", "critical"]:
            suggestions.append("整體事實風險較高，建議全面檢查事實聲明")
        elif overall_risk == "medium":
            suggestions.append("存在中等程度的事實風險，建議重點檢查不確定的聲明")
        
        # AI 建議
        ai_recommendations = ai_analysis.get("recommendations", [])
        suggestions.extend(ai_recommendations)
        
        # 一般性建議
        if not suggestions:
            suggestions.append("事實檢查通過，未發現明顯錯誤")
        else:
            suggestions.append("建議在發布前進行專業的事實核查")
        
        return suggestions
    
    def _generate_no_claims_report(self, story_title: str, story_text: str = "") -> Dict:
        """生成無事實聲明的報告，並基於故事內容進行智能評分"""
        # 先用無模型啟發式評分，避免固定常數分數。
        intelligent_score = self._heuristic_factuality_without_claims(story_text, story_title)
        try:
            assessor = getattr(self, '_assess_story_factuality_intelligence', None)
            if callable(assessor):
                ai_guided_score = assessor(story_text, story_title)
                # 融合無模型啟發與 AI 分析，降低單一路徑波動。
                intelligent_score = round(0.45 * intelligent_score + 0.55 * ai_guided_score, 1)
        except Exception:
            pass
        
        # 風險評估：改為與總分解耦，依文本關鍵詞做啟發式估計
        try:
            risk_score = self._estimate_risk_from_text(story_text)
        except Exception:
            risk_score = 70.0
        
        return {
            "meta": {
                "version": "1.0_factuality_checker",
                "story_title": story_title,
                "total_claims": 0,
                "verifiable_claims": 0,
                "web_search_enabled": self.enable_web_search,
                "ai_available": self.ai.model_available
            },
            "factuality": {
                "claims": [],
                "verification_results": [],
                "risk_assessment": {
                    "overall_risk": "none",
                    "risk_distribution": {},
                    "verdict_distribution": {},
                    "high_risk_claims": 0,
                    "refuted_claims": 0,
                    "uncertain_claims": 0,
                    "supported_claims": 0
                },
                "scores": {
                    # 使用智能評分作為內容事實性得分，風險分獨立估計
                    "claim_accuracy": intelligent_score,
                    "verification_coverage": 0.0,
                    "risk_assessment": risk_score,
                    "final": intelligent_score
                },
                "ai_analysis": {
                    "score": intelligent_score,
                    "analysis": f"未抽取到可驗證聲明，基於故事內容智能評估事實性表現（風險分獨立估計），得分：{intelligent_score}/100。",
                    "confidence": 0.55 if self.ai and self.ai.model_available else 0.45
                },
                "suggestions": [
                    "未抽取到可驗證聲明：本故事可能為虛構或缺乏可驗證事實。",
                    "若需進行事實檢查，請在文本中加入具體可驗證資訊（人物、地點、時間、事件）。"
                ]
            }
        }

    def _heuristic_factuality_without_claims(
        self,
        story_text: str,
        story_title: str = "",
        factual_signal: Optional[float] = None,
        fictional_signal: Optional[float] = None,
    ) -> float:
        """在無聲明場景下給出可變且可解釋的事實性代理分數。"""
        text = story_text or ""
        if not text.strip():
            return 55.0

        try:
            if factual_signal is None or fictional_signal is None:
                factual_signal, fictional_signal = self._estimate_content_signals(text, story_title or "")
        except Exception:
            factual_signal, fictional_signal = 0.0, 0.0

        try:
            has_hard_facts = self._has_hard_verifiable_signals(text, story_title or "")
        except Exception:
            has_hard_facts = False

        try:
            signals = self._extract_anchor_signals(text)
        except Exception:
            signals = {"anchors": 0, "connectives": 0, "contradictions": 0, "length": 1}

        base = 52.0
        base += min(18.0, max(0.0, float(factual_signal)) * 0.16)
        # 虛構訊號僅做輕度抑制，避免童話被過度懲罰。
        base -= min(10.0, max(0.0, float(fictional_signal)) * 0.12)

        if has_hard_facts:
            base += 6.0

        base += min(8.0, max(0, int(signals.get("anchors", 0))) * 0.35)
        base += min(4.0, max(0, int(signals.get("connectives", 0))) * 0.25)
        base -= min(10.0, max(0, int(signals.get("contradictions", 0))) * 2.0)

        # 內容過短時降低可信度上限。
        if len(text) < 280:
            base = min(base, 62.0)

        return float(max(35.0, min(82.0, round(base, 1))))

    def _estimate_risk_from_text(self, story_text: str) -> float:
        """在無聲明情境下，使用直觀關鍵詞與錨點訊號對內容風險做啟發式估計（與總分解耦）。"""
        if not story_text:
            return 70.0
        text = story_text.lower()
        base = 65.0  # 童話預設中低風險
        
        # 明示虛構/童話語境 → 風險降低
        low_risk_markers = [
            "once upon a time", "fairy tale", "folktale", "legend", "story", "bedtime story"
        ]
        if any(k in text for k in low_risk_markers):
            base -= 10.0
        
        # 絕對化/誤導性醫療與保證用語 → 風險升高
        high_risk_markers = [
            "cure", "heals", "miracle", "medicine", "medical", "guaranteed", "100%", "always", "never",
            "proven", "scientifically proven", "study shows", "research shows", "detox", "anti-vax", "flat earth",
            "impossible", "cannot be", "makes no sense", "nonsense"
        ]
        hits = sum(1 for k in high_risk_markers if k in text)
        if hits:
            base += min(15.0, 4.0 * hits)
        
        # 錨點訊號：更多錨點/連接詞 → 風險略降；矛盾增多 → 風險升
        signals = self._extract_anchor_signals(story_text)
        base -= min(6.0, 0.2 * max(0, signals.get("anchors", 0) - 3))
        base -= min(4.0, 0.3 * max(0, signals.get("connectives", 0) - 2))
        base += min(8.0, 2.0 * signals.get("contradictions", 0))
        
        # 範圍裁剪
        return max(40.0, min(90.0, round(base, 1)))
    
    def _claim_to_dict(self, claim: FactualClaim) -> Dict:
        """將FactualClaim轉換為字典"""
        return {
            "claim_id": claim.claim_id,
            "text": claim.text,
            "claim_type": claim.claim_type,
            "confidence": round(claim.confidence, 2),
            "context": claim.context,
            "location": claim.location,
            "verifiable": claim.verifiable,
            "entities": claim.entities or [],
            "triples": claim.triples or [],
            "links": claim.links or {}
        }
    
    def _result_to_dict(self, result: FactCheckResult) -> Dict:
        """將FactCheckResult轉換為字典"""
        return {
            "claim_id": result.claim.claim_id,
            "verdict": result.verdict,
            "evidence": result.evidence,
            "confidence": round(result.confidence, 2),
            "sources": result.sources,
            "risk_level": result.risk_level
        }

    def _assess_story_factuality_intelligence(self, story_text: str, story_title: str) -> float:
        """基於故事內容進行智能事實性評分（不依賴文字解析，使用模型回傳的結構化分數）"""
        if not story_text:
            return self._heuristic_factuality_without_claims(story_text, story_title)

        if not self.ai or not self.ai.model_available:
            return self._heuristic_factuality_without_claims(story_text, story_title)
        
        try:
            # 直接對故事正文做一致性分析，取其客觀/主觀作為事實性的代理訊號
            result = self.ai.analyze_consistency(story_text, [], {})
            ai_score = float(result.get("ai_score", 70.0))
            objective_score = float(result.get("objective_score", 70.0))
            
            # 分數壓縮映射，避免極端值：
            # - AI 主觀分數：壓到 40~90 區間
            # - 客觀分數：壓到 50~90 區間
            norm_ai = max(40.0, min(90.0, 40.0 + (ai_score - 40.0) * 0.6))
            norm_obj = max(50.0, min(90.0, 50.0 + (objective_score - 50.0) * 0.4))
            
            # 合成：偏向客觀一點（更保守），避免因文風導致的主觀飄移
            base = 0.45 * norm_ai + 0.55 * norm_obj
            
            # 錨點訊號微調
            signals = self._extract_anchor_signals(story_text)
            anchors = signals["anchors"]
            connectives = signals["connectives"]
            contradictions = signals["contradictions"]
            length = signals["length"]
            
            # 多錨點 + 因果連接詞 → 更像可驗證/合理敘事
            if anchors >= 5:
                base += min(3.0, 0.2 * anchors)  # 最多 +3
            if connectives >= 3:
                base += min(2.0, 0.3 * connectives)  # 最多 +2
            
            # 明顯矛盾 → 降分
            if contradictions:
                base -= min(6.0, 2.0 + 1.0 * contradictions)
            
            # 短文過度穩定抬分避免：極短內容上限略收緊
            if length < 8:
                base = min(base, 70.0)
            
            # 輕量常識詞微調
            text_lower = story_text.lower()
            if any(k in text_lower for k in ["forest", "castle", "king", "queen", "sun", "moon", "village", "river", "mountain"]):
                base += 0.5
            
            # 分佈拉伸：讓好文上揚、差文下探（以 60 為中心輕拉伸）
            delta = base - 60.0
            base += 0.25 * delta
            
            # 範圍裁剪
            return float(max(30.0, min(90.0, round(base, 1))))
        except Exception:
            return self._heuristic_factuality_without_claims(story_text, story_title)

    def _extract_anchor_signals(self, story_text: str) -> Dict[str, int]:
        """抽取可作為常識/可驗證傾向的錨點訊號（僅用於加減分，不作硬判定）。
        返回：{"anchors": int, "connectives": int, "contradictions": int, "length": int}
        anchors: NER錨點數（GPE/DATE/TIME/CARDINAL/QUANTITY/ORDINAL/PERSON）
        connectives: 因果/時間連接詞命中數
        contradictions: 矛盾/不可能標記命中數
        length: 句子數粗略長度
        """
        text = story_text or ""
        anchors = 0
        connectives = 0
        contradictions = 0
        length = 0
        
        try:
            doc = self.nlp(text) if self.nlp else None
            if doc is not None:
                # 句子數
                length = max(1, len(list(doc.sents)))
                # NER 錨點
                ner_types = {"GPE", "DATE", "TIME", "CARDINAL", "QUANTITY", "ORDINAL", "PERSON"}
                anchors = sum(1 for ent in doc.ents if ent.label_ in ner_types)
            else:
                # 簡易句子統計
                length = max(1, text.count(".") + text.count("!") + text.count("?"))
        except Exception:
            length = max(1, text.count(".") + text.count("!") + text.count("?"))
        
        tl = text.lower()
        # 因果/時間連接詞（中文/英文）
        connective_markers = [
            "because", "so that", "therefore", "so, ", "thus", "hence", "after", "before", "then", "when", "while",
            "因為", "所以", "因此", "於是", "然後", "之後", "當", "同時"
        ]
        connectives = sum(tl.count(k) for k in connective_markers)
        
        # 矛盾/不可能標記
        contradiction_markers = [
            "impossible", "cannot be", "can't be", "makes no sense", "nonsense", "paradox",
            "不可能", "矛盾", "沒有道理", "荒謬"
        ]
        contradictions = sum(tl.count(k) for k in contradiction_markers)
        
        return {"anchors": anchors, "connectives": connectives, "contradictions": contradictions, "length": length}


# ==================== 獨立運行測試 ====================
if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    def is_story_directory(path: str) -> bool:
        if not os.path.isdir(path):
            return False
        en_dir = os.path.join(path, 'en')
        base_dir = en_dir if os.path.exists(en_dir) else path
        return os.path.exists(os.path.join(base_dir, 'full_story.txt'))
    
    def find_story_directories(root: str) -> list:
        if is_story_directory(root):
            return [root]
        story_dirs = []
        if not os.path.isdir(root):
            return story_dirs
        for name in os.listdir(root):
            p = os.path.join(root, name)
            if is_story_directory(p):
                story_dirs.append(p)
        return story_dirs
    
    root = 'output'
    story_dirs = find_story_directories(root)
    if not story_dirs:
        logger.error("❌ 未找到故事資料夾：%s", root)
        raise SystemExit(1)
    
    try:
        checker = FactualityChecker(enable_web_search=False, enable_wikipedia=True)
        logger.info("開始事實正確性評估")
    except Exception as e:
        logger.exception("❌ 初始化失敗: %s", e)
        raise SystemExit(1)
    
    logger.info("🔎 事實性檢測 | 自動掃描模式")
    logger.info("=" * 60)
    logger.info("📁 掃描 output，找到 %d 個故事資料夾", len(story_dirs))
    for story_dir in story_dirs:
        en_dir = os.path.join(story_dir, 'en')
        base_dir = en_dir if os.path.exists(en_dir) else story_dir
        text = None
        p = os.path.join(base_dir, 'full_story.txt')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                text = f.read()
        if not text:
            logger.warning("- 略過：%s (無 full_story.txt)", os.path.basename(story_dir))
            continue
        try:
            result = checker.check(text, os.path.basename(story_dir))
            data = result['factuality']
            scores = data['scores']
            vr = data['verification_results']
            claims = data.get('claims', [])
            supported = len([v for v in vr if v['verdict'] == 'supported'])
            refuted = len([v for v in vr if v['verdict'] == 'refuted'])
            uncertain = len([v for v in vr if v['verdict'] == 'uncertain'])
            logger.info("")
            logger.info("=" * 60)
            logger.info("📖 檢測: %s", os.path.basename(story_dir))
            logger.info("📊 詳細分數:")
            logger.info("  🎯 總分: %.1f/100", scores['final'])
            logger.info("  🔍 聲明準確度: %.1f/100", scores['claim_accuracy'])
            logger.info("  📚 驗證覆蓋度: %.1f/100", scores['verification_coverage'])
            logger.info("  🚨 風險評估: %.1f/100", scores['risk_assessment'])
            logger.info("📑 檢查結果: 支持 %d | 反駁 %d | 不確定 %d", supported, refuted, uncertain)

            # 顯示抽取到的聲明（僅展示可驗證前10筆，兒童故事友善展示）
            if claims:
                logger.info("")
                logger.info("🧩 抽取到的聲明 (僅顯示可驗證，最多前10筆)：")
                verifiable_claims = [c for c in claims if c.get('verifiable')]
                for c in verifiable_claims[:10]:
                    logger.info("  - %s | 類型:%s | 置信度:%.2f", c['claim_id'], c['claim_type'], c['confidence'])
                    logger.info("    句子: %s", c['context'])
                    if c.get('entities'):
                        ents = ', '.join([f"{e[0]}:{e[1]}" for e in c['entities'][:6]])
                        logger.info("    實體: %s", ents)
                    if c.get('triples'):
                        for s,v,o in c['triples'][:3]:
                            logger.info("    三元組: (%s) -%s-> (%s)", s, v, o)
                    if c.get('links'):
                        # 只列出最多3個連結
                        shown = 0
                        for ent, info in c['links'].items():
                            logger.info("    連結: %s -> %s | %s", ent, info.get('title', ''), info.get('url', ''))
                            shown += 1
                            if shown >= 3:
                                break

            # 顯示驗證細節
            if vr:
                logger.info("")
                logger.info("🔎 驗證細節 (前10筆)：")
                id_to_claim = {c['claim_id']: c for c in claims}
                for r in vr[:10]:
                    cid = r['claim_id']
                    c = id_to_claim.get(cid, {})
                    text_preview = (c.get('text') or c.get('context') or '')[:160]
                    logger.info("  - %s | verdict:%s | conf:%.2f | risk:%s", cid, r['verdict'], r['confidence'], r['risk_level'])
                    if text_preview:
                        logger.info("    內容: %s", text_preview)
                    if r['evidence']:
                        logger.info("    證據: %s", r['evidence'][0])
                    if r['sources']:
                        logger.info("    來源: %s", r['sources'][0])
            sugg = data.get('suggestions', [])
            if sugg:
                logger.info("")
                logger.info("💡 建議 (最多3項):")
                for s in sugg[:3]:
                    logger.info("  └─ %s", s)
            logger.info("=" * 60)
        except Exception as e:
            logger.exception("❌ 失敗 %s: %s", os.path.basename(story_dir), e)
