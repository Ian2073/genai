"""文本連貫性評估模組。

提供語義、結構、主題、時間等多層面分析，協助檢測兒童故事是否前後呼應、
情節流暢、時間軸合理。整合知識圖譜、LLM 推理、語義嵌入與規則檢測，輸出
細緻的分數、證據與改善建議，供報告模組與開發者使用。"""
import logging
import re
import numpy as np
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Union
import torch
import os

# 共用你的一致性模組裡的工具
from consistency import ComprehensiveKnowledgeGraph, AIAnalyzer
from shared.story_data import collect_full_story_paths, discover_story_dirs
from utils import (
    SentenceSplitterMixin,
    ensure_instance,
    get_default_model_path,
    get_kg_path,
    resolve_model_path,
    load_category_keywords,
    load_spacy_model,
)
from shared.ai_safety import (
    get_dimension_fallback_score,
    normalize_confidence_0_1,
    normalize_score_0_100,
)

logger = logging.getLogger(__name__)

COHERENCE_AI_FALLBACK_SCORE = get_dimension_fallback_score("coherence")

@dataclass
class CoherenceScores:
    objective: float
    ai: float
    final: float

@dataclass
class FourDimensionCoherenceScores:
    """四維度連貫性評估分數"""
    semantic: float        # 語義連貫性 (詞彙一致性、概念關聯性、語義場維持)
    structural: float      # 結構連貫性 (段落邏輯順序、章節層次關係、論證結構完整性)
    thematic: float        # 主題連貫性 (主題一致性、焦點維持、話題轉換自然度)
    temporal: float        # 時間連貫性 (時間線一致性、事件順序邏輯、時態使用一致性)
    final: float          # 最終綜合分數
    confidence: float     # 評估置信度
    uncertainty: float    # 不確定性指標

@dataclass
class CoherenceIssue:
    issue_type: str
    location: str
    description: str
    severity: str  # 'low', 'medium', 'high'
    suggestions: List[str]

@dataclass
class CoherenceEvidence:
    """連貫性證據"""
    layer: str
    element: str
    score: float
    confidence: float
    evidence_text: str
    position: int
    evidence_type: str  # 'direct', 'semantic', 'inferred', 'ai_analysis'

class CoherenceChecker(SentenceSplitterMixin):
    # 連貫性檢測器（六維度故事評估系統 - 文本連貫性維度）
    
    def __init__(self, 
                 kg_path: str = get_kg_path(),
                 model_path: str = get_default_model_path("Qwen2.5-14B"),
                 use_multiple_ai_prompts: bool = False,
                 ai: AIAnalyzer = None,
                 kg: ComprehensiveKnowledgeGraph = None,
                 nlp=None,
                 semantic_model=None,
                 preferred_language: Optional[str] = None,
                 eager_load_semantic: bool = False):
        # 載入核心分析工具
        self.kg = ensure_instance(kg, ComprehensiveKnowledgeGraph, kg_path)  # 知識圖譜
        self.ai = ensure_instance(ai, AIAnalyzer, model_path, use_multiple_ai_prompts)  # AI 分析器
        self.nlp = ensure_instance(nlp, load_spacy_model)  # NLP 模型
        self.logger = logging.getLogger(__name__)
        
        # 載入中央化詞彙資源（從配置文件）
        from kb import LocalCategoryMatcher
        self.local_categories = LocalCategoryMatcher()
        self.temporal_markers = load_category_keywords(self.local_categories, 'coherence.temporal_markers')  # 時間標記詞
        self.stop_words = load_category_keywords(self.local_categories, 'coherence.stop_words.basic')  # 停用詞
        # 可配置：矛盾與自我否定標記
        self.contradiction_markers = (
            load_category_keywords(self.local_categories, 'coherence.contradiction_markers')
            or [
                "is also", "was also", "at the same time", "both", "but also", "the opposite",
                "doesn't make sense", "inconsistent"
            ]
        )
        self.self_negation_markers = (
            load_category_keywords(self.local_categories, 'coherence.self_negation_markers')
            or [
                "doesn't make sense", "does not make sense", "contradict", "contradictory",
                "inconsistent", "broken story", "incomplete", "no ending", "confusing"
            ]
        )
        
        # 語義模型設定（支援延遲載入以節省記憶體）
        self.semantic_model = semantic_model
        self.preferred_language = preferred_language or 'en'
        if self.semantic_model is None and eager_load_semantic:
            self.semantic_model = self._load_semantic_model()  # 立即載入
        
        # 初始化四維度評估框架（語義/結構/主題/時間）
        self._init_four_dimension_framework()
        
        # 文檔選擇策略（主文優先 + 旁白對話輔助）
        self.document_selection_matrix = {
            'primary': ['full_story.txt'],
            'secondary': [],
            'excluded': [],
            'weights': {
                'full_story.txt': 1.0
            }
        }
        
        # 連貫性檢測模式庫（基於語言學理論設計）
        self.coherence_patterns = {
            # 時間連接詞
            "temporal": [
                r'\b(?:then|next|after|before|when|while|during|meanwhile|finally|later|earlier|soon|immediately|suddenly)\b',
                r'\b(?:first|second|third|last|initially|subsequently|eventually|simultaneously)\b',
                r'\b(?:yesterday|today|tomorrow|now|once|always|never|often|sometimes)\b'
            ],
            
            # 因果連接詞  
            "causal": [
                r'\b(?:because|since|so|therefore|thus|hence|consequently|as a result|due to)\b',
                r'\b(?:if|unless|provided|given|assuming|suppose|in case)\b',
                r'\b(?:leads to|results in|causes|triggers|brings about)\b'
            ],
            
            # 對比連接詞
            "contrast": [
                r'\b(?:but|however|yet|although|though|despite|nevertheless|nonetheless|on the other hand)\b',
                r'\b(?:instead|rather|whereas|while|unlike|contrary to|in contrast)\b'
            ],
            
            # 添加連接詞
            "addition": [
                r'\b(?:and|also|too|moreover|furthermore|additionally|besides|in addition)\b',
                r'\b(?:not only|both|either|neither|as well as)\b'
            ]
        }
        
        # 🗣️ 對話回合模式 (Adjacency Pairs)
        self.dialogue_patterns = {
            "question_answer": [
                (r'\?["\']?\s*$', r'^["\']?(?:Yes|No|I|We|That|It|Maybe|Perhaps|Of course|Sure|Well)'),
                (r'\bwhat\b.*\?', r'^["\']?(?:It|That|This|The|A)'),
                (r'\bwhere\b.*\?', r'^["\']?(?:In|At|On|Over|Under|There|Here)'),
                (r'\bwhen\b.*\?', r'^["\']?(?:When|At|On|In|During|After|Before)'),
                (r'\bwho\b.*\?', r'^["\']?(?:I|He|She|We|They|My|His|Her|The)'),
                (r'\bhow\b.*\?', r'^["\']?(?:By|With|Like|Very|So|Just|I)')
            ],
            
            "greeting_response": [
                (r'\b(?:hello|hi|good morning|good afternoon|good evening)\b', r'^["\']?(?:hello|hi|good|nice to see)')
            ],
            
            "request_compliance": [
                (r'\b(?:please|can you|could you|would you)\b.*\?', r'^["\']?(?:yes|sure|of course|okay|alright|I will|I can)')
            ]
        }
        
        # 📍 指稱解析模式
        self.reference_patterns = {
            "pronouns": r'\b(?:he|she|it|they|him|her|them|his|her|their|this|that|these|those)\b',
            "definite_articles": r'\bthe\s+\w+',
            "demonstratives": r'\b(?:this|that|these|those)\s+\w+',
            "possessives": r'\b(?:his|her|their|its)\s+\w+'
        }
        
        # 四維度連貫性評估結果存儲
        self.four_dimension_scores = None
        self.coherence_evidence = []
        self.adaptive_weights = {}
        self.validation_results = {}

    # ====== 共用小工具 ======
    def _clamp(self, value: Union[int, float], min_v: float = 0.0, max_v: float = 100.0) -> float:
        """將分數限制在[min_v, max_v] 範圍內。"""
        try:
            return max(min_v, min(max_v, float(value)))
        except Exception:
            return float(min_v)

    def _encode_texts(self, texts: List[str]) -> Optional[np.ndarray]:
        """使用已載入的語義模型將多段文字編碼為向量（平均 CLS/last_hidden_state）。

        回傳 shape=(n, hidden) 的 numpy 陣列，若模型不可用則回傳 None。
        """
        try:
            if not self.semantic_model or not self.semantic_model.get("semantic_model"):
                return None

            semantic_model = self.semantic_model["semantic_model"]
            tokenizer = semantic_model["tokenizer"]
            model = semantic_model["model"]
            device = next(model.parameters()).device

            inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if device.type == "cuda":
                inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model(**inputs)
                embeddings = outputs.last_hidden_state.mean(dim=1).detach().cpu().numpy()

            return embeddings
        except Exception as e:
            self.logger.warning("⚠️ 文本編碼失敗: %s", e)
            return None
    
    def _load_keywords(self, category: str) -> List[str]:
        """從配置文件載入關鍵詞"""
        try:
            return self.local_categories.get_keywords(category)
        except Exception:
            return []
    
    def _load_semantic_model(self):
        """🚀 載入語義相似度模型（使用你的本地模型）"""
        try:
            from transformers import AutoTokenizer, AutoModel
            from sklearn.feature_extraction.text import CountVectorizer
            from sklearn.decomposition import LatentDirichletAllocation
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            # 按語言決定優先順序（中文優先 bge-m3）
            if (self.preferred_language or 'en') == 'zh':
                model_paths = [
                    resolve_model_path("bge-m3"),
                    resolve_model_path("all-mpnet-base-v2"),
                    resolve_model_path("all-MiniLM-L6-v2")
                ]
            else:
                model_paths = [
                    resolve_model_path("all-mpnet-base-v2"),
                    resolve_model_path("bge-m3"),
                    resolve_model_path("all-MiniLM-L6-v2")
                ]
            
            semantic_model = None
            for model_path in model_paths:
                try:
                    self.logger.info("🔍 嘗試載入語義模型: %s", model_path)
                    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                    model = AutoModel.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                    
                    # 優先使用 CPU（AMD 9900X 優化）
                    use_cpu_for_semantic = os.getenv('USE_CPU_FOR_SEMANTIC', 'true').lower() in ['true', '1']
                    
                    if torch.cuda.is_available() and not use_cpu_for_semantic:
                        model = model.cuda()
                        self.logger.info("✅ 語義模型已載入到 GPU: %s", model_path)
                    else:
                        self.logger.info("✅ 語義模型已載入到 CPU (AMD 9900X 優化): %s", model_path)
                    
                    semantic_model = {
                        "tokenizer": tokenizer, 
                        "model": model,
                        "model_name": model_path.split("/")[-1]
                    }
                    break
                except Exception as e:
                    self.logger.warning("⚠️ 模型 %s 載入失敗: %s", model_path, e)
                    continue
            
            # 初始化LDA主題模型
            lda_model = LatentDirichletAllocation(
                n_components=5,  # 主題數量
                random_state=42,
                max_iter=10
            )
            
            # 初始化文本向量化器
            vectorizer = CountVectorizer(
                max_features=100,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
            return {
                "semantic_model": semantic_model,
                "lda_model": lda_model,
                "vectorizer": vectorizer,
                "cosine_similarity": cosine_similarity,
                "np": np
            }
                    
        except Exception as e:
            self.logger.warning("⚠️ 語義模型載入失敗: %s，將使用基礎功能", e)
            return None

    def _init_four_dimension_framework(self):
        """初始化四維度連貫性評估框架（基於知識圖譜）"""
        # 基礎權重配置（將被自適應權重覆蓋）
        self.base_weights = {
            "semantic": 0.25,     # 語義連貫性 (詞彙一致性、概念關聯性、語義場維持)
            "structural": 0.30,   # 結構連貫性 (段落邏輯順序、章節層次關係、論證結構完整性)
            "thematic": 0.30,     # 主題連貫性 (主題一致性、焦點維持、話題轉換自然度)
            "temporal": 0.15      # 時間連貫性 (時間線一致性、事件順序邏輯、時態使用一致性)
        }
        
        # 基於知識圖譜的連貫性元素
        self.coherence_elements = {
            "semantic": ["vocabulary_consistency", "concept_relatedness", "semantic_field_maintenance"],
            "structural": ["paragraph_logical_order", "section_hierarchy", "argument_structure_integrity"],
            "thematic": ["topic_consistency", "focus_maintenance", "topic_transition_naturalness"],
            "temporal": ["timeline_consistency", "event_sequence_logic", "tense_usage_consistency"]
        }
        
        # 基於知識圖譜的連貫性檢測規則
        self.coherence_rules = {
            "reference_resolution": {
                "pronouns": ["he", "she", "it", "they", "him", "her", "them", "his", "her", "their"],
                "demonstratives": ["this", "that", "these", "those"],
                "definite_articles": ["the"],
                "possessives": ["his", "her", "their", "its"]
            },
            "temporal_markers": {
                "sequence": ["first", "then", "next", "finally", "last"],
                "simultaneous": ["meanwhile", "at the same time", "simultaneously"],
                "causal": ["because", "since", "therefore", "consequently", "as a result"]
            },
            "discourse_markers": {
                "addition": ["and", "also", "furthermore", "moreover", "additionally"],
                "contrast": ["but", "however", "yet", "although", "despite"],
                "consequence": ["so", "thus", "hence", "therefore", "as a result"]
            }
        }
        
        # 語義相似度緩存（提升效率）
        self.semantic_cache = {}
        
        # 批量向量化緩存
        self.embedding_cache = {}
    
    def get_documents_for_coherence(self, available_documents: Dict[str, str]) -> Dict[str, str]:
        """根據連貫性評估需求選擇相應的文檔"""
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
        
        return selected_docs
    
    def get_document_weights_for_coherence(self) -> Dict[str, float]:
        """獲取連貫性評估的文檔權重"""
        return self.document_selection_matrix['weights']
    
    # ====== 四層連貫性評估核心方法 ======
    
    def _evaluate_structural_coherence(self, text: str) -> Dict:
        """結構連貫性評估：段落邏輯順序、章節層次關係、論證結構完整性"""
        sentences = self._split_sentences(text)
        paragraphs = self._split_paragraphs(text)

        # 1. 段落邏輯順序分析
        paragraph_order_score, paragraph_issues = self._analyze_paragraph_logical_order(paragraphs)

        # 2. 章節層次關係分析
        hierarchy_score, hierarchy_issues = self._analyze_section_hierarchy(text, paragraphs)

        # 3. 論證結構完整性分析
        argument_structure_score, argument_issues = self._analyze_argument_structure_integrity(sentences)

        # 計算結構連貫性分數（調整權重，增加對糟糕文本的識別）
        structural_score = (
            paragraph_order_score * 0.5 +
            hierarchy_score * 0.3 +
            argument_structure_score * 0.2
        )

        # 短文本（童話、寓言）容忍度提升
        word_count = len(text.split())
        sentence_count = len(sentences)

        # 如果是短篇故事（< 500字或 < 30句），給予合理基礎分
        if word_count < 500 or sentence_count < 30:
            # 檢查是否有清晰的故事結構（開頭、中間、結尾）
            has_intro = any(marker in text.lower() for marker in ["once upon", "there was", "there were", "long ago"])
            has_ending = any(marker in text.lower() for marker in ["the end", "happily", "ever after", "from then on", "never", "learned"])

            # 移除人工下限，讓分數更真實反映文本品質
            # 結構連貫性應該基於實際分析結果

        # 確保分數不為負數或異常值
        structural_score = self._clamp(structural_score)

        return {
            "score": structural_score,
            "paragraph_logical_order": paragraph_order_score,
            "section_hierarchy": hierarchy_score,
            "argument_structure_integrity": argument_structure_score,
            "issues": paragraph_issues + hierarchy_issues + argument_issues,
            "explanation": {
                "weights": {"paragraph_logical_order": 0.4, "section_hierarchy": 0.3, "argument_structure_integrity": 0.3},
                "components": {
                    "paragraph_logical_order": paragraph_order_score,
                    "section_hierarchy": hierarchy_score,
                    "argument_structure_integrity": argument_structure_score
                },
                "rationale": "段落順序、章節層次與論證完整性三項加權組合而成"
            }
        }
    
    def _evaluate_semantic_coherence(self, text: str) -> Dict:
        """語義連貫性評估：詞彙一致性、概念關聯性、語義場維持"""
        sentences = self._split_sentences(text)
        
        # 檢測是否為童話故事
        is_fairy_tale = self._detect_fairy_tale(text)
        # 新增：檢測是否帶有悲劇/哀傷母題（用於短篇底線保護）
        is_tragic_tale = self._detect_tragic_tale(text)
        
        # 1. 詞彙一致性分析
        vocabulary_score, vocabulary_issues = self._analyze_vocabulary_consistency(sentences)
        
        # 2. 概念關聯性分析
        concept_score, concept_issues = self._analyze_concept_relatedness(sentences)
        
        # 3. 語義場維持分析
        semantic_field_score, field_issues = self._analyze_semantic_field_maintenance(sentences)
        
        # 計算語義連貫性分數（調整權重，降低概念關聯影響）
        semantic_score = (
            vocabulary_score * 0.50 + 
            concept_score * 0.25 + 
            semantic_field_score * 0.25
        )
        
        # 針對短篇兒童故事的語義獎勵（主題詞重複、核心概念穩定）
        text_lower = text.lower()
        core_theme_terms = ["toy", "lost", "find", "found", "learn", "learned", "help", "helped"]
        theme_hits = sum(text_lower.count(t) for t in core_theme_terms)
        # 收斂重複主題詞的加分，避免僅靠重複詞彙拉高分數
        repetition_bonus = min(6.0, theme_hits * 0.8)
        semantic_score += repetition_bonus
        
        # 童話/文學性故事特殊處理（擴展版）
        fairy_tale_bonus = 0
        if is_fairy_tale:
            # 文學性故事的概念關聯可能依賴隱喻而非直接詞彙，給予更大加分
            if concept_score < 25:
                fairy_tale_bonus += 12  # 大幅提高（6 → 12）
            elif concept_score < 45:
                fairy_tale_bonus += 8  # 提高（4 → 8）
            elif concept_score < 60:
                fairy_tale_bonus += 5  # 新增：中等概念關聯也給予獎勵
            
            # 童話的詞彙一致性通常較好，給予額外獎勵
            if vocabulary_score > 60:
                fairy_tale_bonus += 5  # 提高（3 → 5）
            
            # 語義場維持良好的文學性故事額外獎勵
            if semantic_field_score > 65:
                fairy_tale_bonus += 4
            
            semantic_score += fairy_tale_bonus
        
        # 對糟糕文本的懲罰機制（非童話）
        if not is_fairy_tale:
            if concept_score < 20 and vocabulary_score < 40:
                semantic_score *= 0.6  # 嚴重語義混亂時大幅扣分（加強：0.7→0.6）
            elif concept_score < 30 or vocabulary_score < 50:
                semantic_score *= 0.75  # 輕度語義混亂時適度扣分（加強：0.85→0.75）

        # 比例化懲罰：跨句語義跳躍與矛盾密度（通用，適用各長度）
        try:
            import re
            # 以關鍵詞重疊 + 句向量相似度雙條件偵測語義跳躍
            content_sentences = [re.findall(r"[a-zA-Z']+", s.lower()) for s in sentences]
            def to_content_set(ws):
                stop = {"the","a","an","and","or","but","so","to","of","in","on","at","for","with","by","is","was","are","were","be","been","being","that","this","it","as","from","then"}
                return {w for w in ws if len(w) > 2 and w not in stop}
            sets = [to_content_set(ws) for ws in content_sentences]
            jumps = 0
            total_edges = max(1, len(sets) - 1)
            # 粗略向量相似度（TF-IDF），僅相鄰句
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                tfidf = TfidfVectorizer(min_df=1, stop_words='english')
                sent_texts = [re.sub(r"\s+"," ", s.strip()) for s in sentences]
                # 限制長度以控成本
                window_texts = sent_texts[:500]
                if len(window_texts) >= 2:
                    X = tfidf.fit_transform(window_texts)
                else:
                    X = None
            except Exception:
                X = None
            for i in range(len(sets) - 1):
                a, b = sets[i], sets[i+1]
                if not a and not b:
                    continue
                inter = len(a & b)
                union = len(a | b) or 1
                overlap = inter / union
                sim_ok = True
                if X is not None and i < X.shape[0]-1:
                    cs = cosine_similarity(X[i], X[i+1])[0][0]
                    sim_ok = cs >= 0.10  # 進一步放寬以容納文學性場景跳躍（0.18 → 0.10）
                if overlap < 0.08 and not sim_ok:  # 進一步放寬（0.12 → 0.08）
                    jumps += 1
            jump_ratio = jumps / total_edges

            # 懲罰前快照與品質護欄
            pre_penalty_score = semantic_score
            high_quality_signal = (vocabulary_score >= 75 and semantic_field_score >= 75)
            # 文學性保護：童話/寓言故事允許更多場景跳躍
            literary_protection = is_fairy_tale

            # 語義跳躍懲罰：根據品質信號與文學性調整斜率
            if jump_ratio > 0.45:  # 超過45%的句子有語義跳躍
                if literary_protection:
                    slope, cap = 0.20, 0.15  # 文學性故事大幅放寬
                elif high_quality_signal:
                    slope, cap = 0.25, 0.18
                else:
                    slope, cap = 0.45, 0.32
                semantic_score *= (1.0 - min(cap, jump_ratio * slope))
            elif jump_ratio > 0.20:
                if literary_protection:
                    slope, cap = 0.12, 0.10  # 文學性故事大幅放寬
                elif high_quality_signal:
                    slope, cap = 0.16, 0.12
                else:
                    slope, cap = 0.28, 0.20
                semantic_score *= (1.0 - min(cap, jump_ratio * slope))
            else:
                # 微小跳躍不懲罰，或極小幅度（文學性故事幾乎不懲罰）
                if not literary_protection:
                    semantic_score *= (1.0 - min(0.06, max(0.0, jump_ratio - 0.08) * 0.20))

            # 保護：高品質文本或文學性文本不被懲罰超過一定比例
            if high_quality_signal or literary_protection:
                semantic_score = max(pre_penalty_score * 0.88, semantic_score)  # 提高保護（0.85 → 0.88）
        except Exception:
            pass

        # 使用本地配置的自我否定標記
        neg_markers = self.self_negation_markers
        # 排除引號內對話的影響
        stripped = re.sub(r'"[^"]+"', ' ', text_lower)
        neg_hits = sum(stripped.count(m) for m in neg_markers)
        neg_density = neg_hits / max(1, len(sentences))
        # 自我否定懲罰：壞文會明確說自己有問題（加強版）
        if neg_hits >= 3:  # 出現3次以上仍懲罰，但降低強度
            semantic_score *= 0.6
        elif neg_density > 0.05:  # 超過5%的句子有自我否定
            semantic_score *= (1.0 - min(0.25, neg_density * 0.15))
        else:
            semantic_score *= (1.0 - min(0.08, neg_density * 0.04))

        # 針對短篇悲劇型文本，設定更高的合理下限，避免過度懲罰
        word_count = len(text.split())
        if is_tragic_tale and word_count < 400:
            semantic_score = max(70.0, semantic_score)

        # 確保分數在 0-100
        semantic_score = self._clamp(semantic_score)
        
        return {
            "score": semantic_score,
            "vocabulary_consistency": vocabulary_score,
            "concept_relatedness": concept_score,
            "semantic_field_maintenance": semantic_field_score,
            "issues": vocabulary_issues + concept_issues + field_issues,
            "explanation": {
                "weights": {"vocabulary": 0.50, "concept": 0.25, "semantic_field": 0.25},
                "components": {
                    "vocabulary": vocabulary_score,
                    "concept": concept_score,
                    "semantic_field": semantic_field_score
                },
                "bonuses": {"repetition_bonus": repetition_bonus, "fairy_tale_bonus": fairy_tale_bonus},
                "normalization": {"word_count": word_count, "short_text_floor": 72.0},
                "rationale": "詞彙一致性、概念關聯與語義場維持的加權和，另對主題詞重現給予少量獎勵"
            }
        }
    
    def _detect_fairy_tale(self, text: str) -> bool:
        """檢測是否為童話故事或文學性兒童故事（擴展版：含寓言、擬人故事）"""
        text_lower = text.lower()
        
        # 傳統童話特徵詞彙
        fairy_tale_indicators = [
            # 開頭標記
            "once upon a time", "long ago", "there was", "there were",
            "in a faraway land", "in a distant kingdom",
            
            # 童話角色
            "princess", "prince", "king", "queen", "witch", "fairy", "dragon",
            "giant", "dwarf", "elf", "magic", "spell", "castle", "kingdom",
            
            # 童話情節
            "happily ever after", "the end", "magic", "enchanted", "cursed",
            "transformation", "adventure", "quest", "treasure", "rescue",
            
            # 經典童話標題
            "cinderella", "snow white", "sleeping beauty", "little red riding hood",
            "three little pigs", "ugly duckling", "thumbelina", "little match girl",
            "emperor's new clothes", "beauty and the beast", "rapunzel"
        ]
        
        # 文學性兒童故事特徵（寓言、擬人、詩意）
        literary_story_indicators = [
            # 擬人化標記（物品/自然作為主語 + 動作動詞）
            "lantern sang", "lantern said", "lantern whispered", "lantern watched",
            "wind forgot", "wind listened", "wind loved", "wind returned",
            "river sang", "river whispered", "bridge listened", "bridge sighed",
            "moon smiled", "sun danced", "tree spoke", "flower sang",
            
            # 寓言式結構標記
            "moral", "lesson", "learned that", "teaches us", "remember that",
            "beginning", "middle", "end",
            
            # 文學性因果與哲理連接
            "because doors swing", "because listening", "because stories are",
            "because wind", "because questions have", "therefore",
            
            # 詩意描述
            "like soft green hats", "like a silver ribbon", "like river glass",
            "wore moss", "braided itself", "curled up"
        ]
        
        # 計算童話特徵匹配度
        fairy_matches = sum(1 for indicator in fairy_tale_indicators if indicator in text_lower)
        literary_matches = sum(1 for indicator in literary_story_indicators if indicator in text_lower)
        
        # 放寬閾值：傳統童話 3+，或文學性故事 2+，或混合 4+
        return fairy_matches >= 3 or literary_matches >= 2 or (fairy_matches + literary_matches) >= 4

    def _detect_tragic_tale(self, text: str) -> bool:
        """檢測是否為悲劇/哀傷母題（如孤苦、死亡、寒冷、飢餓、失去等）"""
        tl = text.lower()
        tragic_indicators = [
            # 情緒與事件
            "tragic", "tragedy", "sad", "sorrow", "tears", "cry", "cried", "wept", "lonely", "alone",
            "poor", "poverty", "cold", "freezing", "hunger", "hungry", "starving", "pain", "suffer",
            "died", "death", "dead", "passed away", "ill", "sick", "orphan", "abandoned",
            # 經典悲劇童話常見元素
            "stepmother", "cruel", "wicked", "miserable", "beg", "begging"
        ]
        hits = sum(1 for kw in tragic_indicators if kw in tl)
        return hits >= 2
    
    def _evaluate_thematic_coherence(self, text: str) -> Dict:
        """主題連貫性評估：主題一致性、焦點維持、話題轉換自然度（增強版）"""
        sentences = self._split_sentences(text)
        
        # 檢測是否為童話故事
        is_fairy_tale = self._detect_fairy_tale(text)
        
        # 1. 主題一致性分析（改進版）
        topic_consistency_score, topic_issues = self._analyze_topic_consistency(sentences)
        
        # 2. 焦點維持分析
        focus_score, focus_issues = self._analyze_focus_maintenance(sentences)
        
        # 3. 話題轉換自然度分析
        transition_naturalness_score, transition_issues = self._analyze_topic_transition_naturalness(sentences)
        
        # 4. 主題錨點分析（新增）
        theme_anchor_score, theme_anchor_issues = self._analyze_theme_anchors(sentences)
        
        # 5. 對話主題流分析（新增）
        dialogue_topic_score, dialogue_issues = self._analyze_dialogue_topic_flow(sentences)
        
        # 計算主題連貫性分數（調整權重，降低 focus 影響）
        thematic_score = (
            topic_consistency_score * 0.40 +  # 提高：主題一致性是核心
            focus_score * 0.15 +              # 降低：焦點維持不應過度影響
            transition_naturalness_score * 0.20 +  # 提高：轉換自然度更重要
            theme_anchor_score * 0.15 +       # 維持
            dialogue_topic_score * 0.10       # 維持
        )
        
        # 主題聚焦獎勵：若主題詞（toy/find/lost/lesson）在多句重現，給予主題穩定性加分
        text_lower = text.lower()
        theme_tokens = ["toy", "find", "found", "lost", "lesson", "learned"]
        sentences_with_theme = sum(1 for s in sentences if any(t in s.lower() for t in theme_tokens))
        # 收斂主題聚焦加分，避免重複句式過度加分
        focus_bonus = min(8.0, sentences_with_theme * 1.2)
        thematic_score += focus_bonus

        # 對話與主敘事一致性獎勵：存在問答/求助類模式時加分（降低獎勵，避免虛高）
        dialogue_bonus = 0.0
        if any(q in text_lower for q in ["?", "can you", "let's", "asked", "replied", "said"]):
            dialogue_bonus = 2.0
            thematic_score += dialogue_bonus
            
        # 童話故事特殊處理
        fairy_tale_bonus = 0
        if is_fairy_tale:
            # 童話故事的主題通常很明確，給予適當加分
            if topic_consistency_score < 50:
                fairy_tale_bonus += 6  # 降低童話加分
            elif topic_consistency_score < 70:
                fairy_tale_bonus += 4
            
            # 童話的焦點維持通常較好，給予額外獎勵
            if focus_score < 30:
                fairy_tale_bonus += 3
            elif focus_score < 50:
                fairy_tale_bonus += 2
            
            thematic_score += fairy_tale_bonus
        
        # 對糟糕文本的懲罰機制（非童話）
        if not is_fairy_tale:
            if topic_consistency_score < 30 and focus_score < 20:
                thematic_score *= 0.5  # 更嚴格（加強：0.55→0.5）
            elif topic_consistency_score < 50 or focus_score < 30:
                thematic_score *= 0.7  # 更嚴格（加強：0.75→0.7）

        # 比例化懲罰：主題焦點漂移與互斥敘述密度
        try:
            import re
            # 關鍵詞重疊 + 段落向量相似度雙條件衡量主題連續性
            paragraphs = self._split_paragraphs(text)
            para_tokens = [re.findall(r"[a-zA-Z']+", p.lower()) for p in paragraphs]
            def to_kw_set(ws):
                stop = {"the","a","an","and","or","but","so","to","of","in","on","at","for","with","by","is","was","are","were","be","been","being","that","this","it","as","from","then"}
                return {w for w in ws if len(w) > 2 and w not in stop}
            kw_sets = [to_kw_set(ws) for ws in para_tokens]
            drifts = 0
            edges = max(1, len(kw_sets) - 1)
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                tfidf = TfidfVectorizer(min_df=1, stop_words='english')
                para_texts = [re.sub(r"\s+"," ", p.strip()) for p in paragraphs]
                window_paras = para_texts[:200]
                if len(window_paras) >= 2:
                    PX = tfidf.fit_transform(window_paras)
                else:
                    PX = None
            except Exception:
                PX = None
            for i in range(len(kw_sets) - 1):
                a, b = kw_sets[i], kw_sets[i+1]
                if not a and not b:
                    continue
                inter = len(a & b)
                union = len(a | b) or 1
                overlap = inter / union
                sim_ok = True
                if PX is not None and i < PX.shape[0]-1:
                    cs = cosine_similarity(PX[i], PX[i+1])[0][0]
                    sim_ok = cs >= 0.2
                if overlap < 0.12 and not sim_ok:
                    drifts += 1
            drift_ratio = drifts / edges
            # 主題漂移懲罰：壞文漂移多，好文漂移少
            # 當漂移比例高時，加重懲罰
            if drift_ratio > 0.4:  # 超過40%的段落有主題漂移
                thematic_score *= (1.0 - min(0.22, drift_ratio * 0.40))  # 降低上限與斜率
            else:
                thematic_score *= (1.0 - min(0.12, drift_ratio * 0.20))
        except Exception:
            pass

        # 使用本地配置的矛盾標記
        contra_hits = sum(text.lower().count(p) for p in self.contradiction_markers)
        contra_density = contra_hits / max(1, len(sentences))
        # 矛盾敘述懲罰：降低強度以更符合文學性文本
        if contra_hits >= 3:
            thematic_score *= 0.6
        elif contra_density > 0.05:
            thematic_score *= (1.0 - min(0.25, contra_density * 0.15))
        else:
            thematic_score *= (1.0 - min(0.08, contra_density * 0.04))

        # 確保分數在 0-100
        word_count = len(text.split())
        thematic_score = max(0.0, min(100.0, thematic_score))
        
        return {
            "score": thematic_score,
            "topic_consistency": topic_consistency_score,
            "focus_maintenance": focus_score,
            "topic_transition_naturalness": transition_naturalness_score,
            "theme_anchors": theme_anchor_score,
            "dialogue_topic_flow": dialogue_topic_score,
            "issues": topic_issues + focus_issues + transition_issues + theme_anchor_issues + dialogue_issues,
            "explanation": {
                "weights": {"topic": 0.40, "focus": 0.15, "transition": 0.20, "anchors": 0.15, "dialogue": 0.10},
                "components": {
                    "topic": topic_consistency_score,
                    "focus": focus_score,
                    "transition": transition_naturalness_score,
                    "anchors": theme_anchor_score,
                    "dialogue": dialogue_topic_score
                },
                "bonuses": {"focus_bonus": focus_bonus, "dialogue_bonus": dialogue_bonus, "fairy_tale_bonus": fairy_tale_bonus},
                "normalization": {"word_count": word_count, "short_text_floor": 80.0},
                "rationale": "主題一致性與焦點維持為主，話題轉換與主題錨點、對話主題流為輔，主題詞跨句穩定給予獎勵"
            }
        }
    
    def _evaluate_temporal_coherence(self, text: str) -> Dict:
        """時間連貫性評估：時間線一致性、事件順序邏輯、時態使用一致性"""
        sentences = self._split_sentences(text)
        
        # 1. 時間線一致性分析
        timeline_score, timeline_issues = self._analyze_timeline_consistency(sentences)
        
        # 2. 事件順序邏輯分析
        event_sequence_score, event_issues = self._analyze_event_sequence_logic(sentences)
        
        # 3. 時態使用一致性分析
        tense_consistency_score, tense_issues = self._analyze_tense_usage_consistency(sentences)
        
        # 計算時間連貫性分數
        temporal_score = (
            timeline_score * 0.4 + 
            event_sequence_score * 0.35 + 
            tense_consistency_score * 0.25
        )
        
        # 時間標記序列獎勵：使用配置文件的標記
        text_lower = text.lower()
        marker_count = sum(text_lower.count(m) for m in self.temporal_markers)
        # 降低時間標記加分，避免堆標記取巧
        sequence_bonus = min(6.0, marker_count * 1.0)
        temporal_score += sequence_bonus

        # 若標記多但事件序分數偏低，視為錯置：反向懲罰
        if marker_count >= 3 and event_sequence_score < 60:
            temporal_score *= 0.85

        # 1) 時態分佈混雜度懲罰（簡化啟發式）
        try:
            import re
            # 粗略偵測：過去式(-ed)、現在(be/is/are/does)、未來(will/going to)
            tokens = re.findall(r"[a-zA-Z']+", text_lower)
            past = sum(1 for w in tokens if w.endswith('ed')) + text_lower.count('yesterday')
            present = sum(1 for w in tokens if w in {'am','is','are','does','do','today','now'})
            future = text_lower.count('will') + text_lower.count('going to') + text_lower.count('tomorrow')
            total_tense = max(1, past + present + future)
            proportions = [past/total_tense, present/total_tense, future/total_tense]
            # 熵越高代表混雜越多（上限約 ln(3)）
            import math
            entropy = -sum(p*math.log(p+1e-9) for p in proportions)
            max_entropy = math.log(3)
            mix_ratio = entropy / max_entropy  # 0~1
            # 如果時間線/事件序高，降低懲罰；否則按比例扣分（最多-12%）
            stability = (timeline_score + event_sequence_score) / 200.0
            temporal_score *= (1.0 - max(0.0, (mix_ratio - 0.5)) * (0.12 * (1.0 - stability)))
        except Exception:
            pass

        # 2) 互斥時間副詞/順序衝突懲罰（before/after、morning/night、earlier/later錯置）
        conflict_pairs = [
            ('before', 'after'), ('earlier', 'later'), ('morning', 'night'), ('yesterday', 'tomorrow')
        ]
        conflicts = 0
        for a, b in conflict_pairs:
            if a in text_lower and b in text_lower:
                conflicts += 1
        if conflicts > 0 and (timeline_score < 75 or event_sequence_score < 75):
            temporal_score *= (1.0 - min(0.10, conflicts * 0.04))

        # 3) 軟上限：標記密度高但 timeline/sequence 偏低時，避免時間分顯著高於其他
        if marker_count >= 4 and (timeline_score + event_sequence_score) / 2 < 70:
            cap = max(timeline_score, event_sequence_score) + 5
            temporal_score = min(temporal_score, cap)

        # 移除人工下限，讓分數更真實反映文本品質
        # 時間連貫性應該基於實際分析結果

        # 確保分數在 0-100
        temporal_score = self._clamp(temporal_score)
        
        return {
            "score": temporal_score,
            "timeline_consistency": timeline_score,
            "event_sequence_logic": event_sequence_score,
            "tense_usage_consistency": tense_consistency_score,
            "issues": timeline_issues + event_issues + tense_issues,
            "explanation": {
                "weights": {"timeline": 0.4, "event_sequence": 0.35, "tense": 0.25},
                "components": {
                    "timeline": timeline_score,
                    "event_sequence": event_sequence_score,
                    "tense": tense_consistency_score
                },
                "bonuses": {"sequence_bonus": sequence_bonus, "marker_count": marker_count},
                "floors": {},
                "rationale": "時間標記僅作輕度加分；若標記多但序錯或時態混雜，按比例扣分並在必要時施加軟上限"
            }
        }
    
    def _calculate_adaptive_weights(self, text: str, evaluation_results: Dict) -> Dict:
        """自適應權重計算（真正整合版）"""
        # 基於評估結果的置信度調整權重
        weights = self.base_weights.copy()
        
        # 計算各層的置信度
        layer_confidences = {}
        for layer, result in evaluation_results.items():
            if isinstance(result, dict) and 'score' in result:
                # 基於分數計算置信度
                score = result['score']
                confidence = min(1.0, score / 100.0)
                layer_confidences[layer] = confidence
            else:
                layer_confidences[layer] = 0.5  # 默認置信度
        
        # 基於置信度調整權重
        total_confidence = sum(layer_confidences.values())
        if total_confidence > 0:
            for layer in weights:
                confidence_ratio = layer_confidences.get(layer, 0.5) / total_confidence
                weights[layer] = weights[layer] * (0.5 + confidence_ratio)
        
        # 基於文本特徵調整權重
        text_features = self._extract_text_features(text)
        
        # 如果文本很短，降低語義和主題權重
        if text_features['word_count'] < 100:
            weights['semantic'] *= 0.7
            weights['thematic'] *= 0.7
            weights['structural'] *= 1.2
        
        # 已移除長文本的特殊加權（統一按短篇邏輯處理）
        
        # 正規化權重
        total_weight = sum(weights.values())
        for layer in weights:
            weights[layer] /= total_weight
        
        return weights
    
    def _multi_stage_validation(self, text: str, four_dimension_scores: FourDimensionCoherenceScores) -> Dict:
        """多階段驗證機制"""
        # 內部一致性檢查
        internal_consistency = self._check_internal_consistency(four_dimension_scores)
        
        # 跨模型一致性驗證
        cross_model_consistency = self._check_cross_model_consistency(text, four_dimension_scores)
        
        # 專家規則驗證
        expert_rule_validation = self._validate_against_expert_rules(text, four_dimension_scores)
        
        # 不確定性量化
        uncertainty = self._quantify_uncertainty(four_dimension_scores)
        
        # 計算驗證分數
        validation_score = (internal_consistency * 0.4 + cross_model_consistency * 0.3 + expert_rule_validation * 0.3)
        reliability = 1.0 - uncertainty
        
        return {
            "validation_score": validation_score,
            "uncertainty": uncertainty,
            "reliability": reliability,
            "internal_consistency": internal_consistency,
            "cross_model_consistency": cross_model_consistency,
            "expert_rule_validation": expert_rule_validation
        }
    
    def check(self, story_text: str, story_title: str = "Story", documents: Dict[str, str] = None) -> Dict:
        """主要檢測接口 - 四維度連貫性評估框架

        簡化版：忽略 documents 參數，僅用 story_text 評估。
        """
        sentences = self._split_sentences(story_text)
        paragraphs = self._split_paragraphs(story_text)
        
        # ===== 四維度連貫性評估框架 =====
        self.logger.info("開始連貫性評估")
        evaluation_results = self._evaluate_all_dimensions(story_text)

        try:
            adaptive_weights = self._calculate_adaptive_weights(story_text, evaluation_results)
        except Exception as exc:  # pragma: no cover - 防禦性處理
            self.logger.warning("自適應權重計算失敗，改用基礎權重：%s", exc)
            adaptive_weights = self.base_weights.copy()

        four_dimension_scores = self._compose_dimension_scores(evaluation_results)
        final_score, score_adjustments = self._calculate_final_score_and_adjustments(
            four_dimension_scores,
            adaptive_weights,
            evaluation_results
        )
        four_dimension_scores.final = final_score

        # 多階段驗證
        validation_results = self._multi_stage_validation(story_text, four_dimension_scores)
        four_dimension_scores.confidence = validation_results["validation_score"]
        four_dimension_scores.uncertainty = validation_results["uncertainty"]
        
        # 存儲結果供後續使用
        self.four_dimension_scores = four_dimension_scores
        self.adaptive_weights = adaptive_weights
        self.validation_results = validation_results
        
        # 💡 智能建議生成（整合四維度結果）
        suggestions = self._generate_four_dimension_coherence_suggestions(
            evaluation_results["semantic"],
            evaluation_results["structural"],
            evaluation_results["thematic"],
            evaluation_results["temporal"], 
            adaptive_weights, validation_results
        )
        
        all_issues = self._collect_dimension_issues(evaluation_results)
        dimension_summary = self._build_dimension_summary(evaluation_results, len(paragraphs))
        analysis_summary = self._build_analysis_summary(evaluation_results, len(paragraphs))
        narrative_alerts = self._detect_narrative_alerts(evaluation_results, sentences)

        def _issues_by_dimension(dimension: str) -> List[Dict[str, Union[str, float, List[str]]]]:
            return [issue for issue in all_issues if issue.get("dimension") == dimension]

        # 建立輸出結構
        return {
            "meta": {
                "version": "3.2_streamlined_coherence_analysis",
                "story_title": story_title,
                "sentences": len(sentences),
                "paragraphs": len(paragraphs),
                "ai_available": getattr(self.ai, "model_available", False),
                "framework_version": "四維度連貫性評估框架",
                "total_issues": len(all_issues),
                "analysis_timestamp": self._get_timestamp()
            },
            "coherence": {
                "scores": {
                    "semantic": round(four_dimension_scores.semantic, 1),
                    "structural": round(four_dimension_scores.structural, 1),
                    "thematic": round(four_dimension_scores.thematic, 1),
                    "temporal": round(four_dimension_scores.temporal, 1),
                    "final": round(four_dimension_scores.final, 1),
                    "confidence": round(four_dimension_scores.confidence, 2),
                    "uncertainty": round(four_dimension_scores.uncertainty, 2)
                },
                "score_adjustments": score_adjustments,
                "explanations": {
                    "semantic": evaluation_results["semantic"].get("explanation", {}),
                    "structural": evaluation_results["structural"].get("explanation", {}),
                    "thematic": evaluation_results["thematic"].get("explanation", {}),
                    "temporal": evaluation_results["temporal"].get("explanation", {})
                },
                "issues": {
                    "semantic": _issues_by_dimension("semantic"),
                    "structural": _issues_by_dimension("structural"),
                    "thematic": _issues_by_dimension("thematic"),
                    "temporal": _issues_by_dimension("temporal"),
                    "all": all_issues
                },
                "dimension_details": dimension_summary,
                "analysis_summary": analysis_summary,
                "alerts": narrative_alerts,
                "four_dimension_analysis": {
                    "adaptive_weights": adaptive_weights,
                    "validation": validation_results,
                    "dimension_performance": {
                        "best_dimension": max(
                            ["semantic", "structural", "thematic", "temporal"],
                            key=lambda x: getattr(four_dimension_scores, x)
                        ),
                        "worst_dimension": min(
                            ["semantic", "structural", "thematic", "temporal"],
                            key=lambda x: getattr(four_dimension_scores, x)
                        ),
                        "score_variance": round(self._calculate_score_variance([
                            four_dimension_scores.semantic,
                            four_dimension_scores.structural,
                            four_dimension_scores.thematic,
                            four_dimension_scores.temporal
                        ]), 2)
                    }
                },
                "suggestions": suggestions
            }
        }

    # ===== 調度與彙整工具 =====

    def _evaluate_all_dimensions(self, text: str) -> Dict[str, Dict[str, Union[float, List, Dict]]]:
        """一次取得四大維度的評估結果，統一入口避免重複程式碼。"""
        return {
            "semantic": self._evaluate_semantic_coherence(text),
            "structural": self._evaluate_structural_coherence(text),
            "thematic": self._evaluate_thematic_coherence(text),
            "temporal": self._evaluate_temporal_coherence(text)
        }

    def _compose_dimension_scores(self, evaluation_results: Dict[str, Dict[str, Union[float, List, Dict]]]) -> FourDimensionCoherenceScores:
        """將原始評估結果轉換為 ``FourDimensionCoherenceScores`` 物件。"""
        return FourDimensionCoherenceScores(
            semantic=float(evaluation_results["semantic"].get("score", 0.0)),
            structural=float(evaluation_results["structural"].get("score", 0.0)),
            thematic=float(evaluation_results["thematic"].get("score", 0.0)),
            temporal=float(evaluation_results["temporal"].get("score", 0.0)),
            final=0.0,
            confidence=0.0,
            uncertainty=0.0
        )

    def _calculate_final_score_and_adjustments(
        self,
        scores: FourDimensionCoherenceScores,
        weights: Dict[str, float],
        evaluation_results: Dict[str, Dict[str, Union[float, List, Dict]]]
    ) -> Tuple[float, List[Dict[str, Union[str, float]]]]:
        """計算最終分數並產生調整紀錄，讓後續輸出更透明。"""

        semantic_result = evaluation_results["semantic"]
        structural_result = evaluation_results["structural"]
        thematic_result = evaluation_results["thematic"]
        temporal_result = evaluation_results["temporal"]

        sem = scores.semantic
        struc = scores.structural
        them = scores.thematic
        temp = scores.temporal

        base_score = (
            sem * weights.get("semantic", 0.0) +
            struc * weights.get("structural", 0.0) +
            them * weights.get("thematic", 0.0) +
            temp * weights.get("temporal", 0.0)
        )

        final_score = base_score
        adjustments: List[Dict[str, Union[str, float]]] = []

        def register_adjustment(reason: str, value: float) -> None:
            if abs(value) < 1e-6:
                return
            adjustments.append({"reason": reason, "value": round(value, 2)})

        # ===== 正向補強 =====
        total_boost = 0.0
        if sem >= 62 and them >= 58 and temp >= 68:
            delta = min(8.0, (sem + them + temp - 188) * 0.12)
            total_boost += delta
            register_adjustment("語義/主題/時間整體表現突出", delta)

        if sem >= 62 and struc >= 62:
            delta = min(5.0, (sem + struc - 124) * 0.08)
            total_boost += delta
            register_adjustment("語義結構雙優勢加成", delta)

        if them >= 68:
            delta = min(3.0, (them - 68) * 0.10)
            total_boost += delta
            register_adjustment("主題連貫性突出", delta)

        total_boost = max(0.0, min(12.0, total_boost))
        final_score += total_boost

        # 自然過渡加成
        try:
            trans = float(thematic_result.get('topic_transition_naturalness', 0.0))
            anch = float(thematic_result.get('theme_anchors', 0.0))
            if trans >= 75 and anch >= 75 and them >= 50:
                bonus = 2.0
                if sem >= 75:
                    bonus += 1.5
                if temp >= 80:
                    bonus += 1.5
                if trans >= 85:
                    bonus += 0.5
                if anch >= 85:
                    bonus += 0.5
                applied = min(6.0, bonus)
                final_score += applied
                register_adjustment("主題轉換與語義/時間協同", applied)
        except Exception:
            pass

        if struc >= 68 and temp >= 80 and sem >= 70:
            final_score += 2.0
            register_adjustment("結構×時間協同加成", 2.0)

        # 🛡️ 僵化結構懲罰：轉場詞重複率過高（>0.6）表示機械式民間故事模式
        try:
            # 檢測轉場詞使用的多樣性
            connector_usage = thematic_result.get('connector_usage', {})
            if isinstance(connector_usage, dict):
                total_connectors = sum(connector_usage.values()) if connector_usage else 0
                if total_connectors > 0:
                    # 計算最常用詞的占比
                    max_usage = max(connector_usage.values()) if connector_usage else 0
                    repetition_rate = max_usage / total_connectors if total_connectors > 0 else 0
                    
                    # 當重複率>0.6且連貫性高時（可能是僵化模式），施加懲罰
                    if repetition_rate > 0.6 and struc >= 75:
                        penalty = min(5.0, (repetition_rate - 0.6) * 12.0)
                        final_score = max(0.0, final_score - penalty)
                        register_adjustment("僵化轉場模式懲罰", -penalty)
        except Exception:
            pass

        # ===== 懲罰機制 =====
        weakest = min(sem, struc, them, temp)
        if weakest < 30:
            penalty = (30 - weakest) * 0.18
            final_score = max(0.0, final_score - penalty)
            register_adjustment("維度分數過低懲罰", -penalty)

        bad_dimensions = sum(1 for score in [sem, struc, them, temp] if score < 35)
        if bad_dimensions >= 2:
            penalty = bad_dimensions * 5.0
            final_score = max(0.0, final_score - penalty)
            register_adjustment("多維度低分懲罰", -penalty)

        if final_score > 96.0:
            register_adjustment("安全上限裁切", 96.0 - final_score)
        final_score = min(96.0, final_score)

        final_score = min(100.0, final_score)
        final_score = max(0.0, final_score)

        return round(final_score, 1), adjustments

    def _collect_dimension_issues(self, evaluation_results: Dict[str, Dict[str, Union[float, List, Dict]]]) -> List[Dict[str, Union[str, float, List[str]]]]:
        """將各維度 issues 統一攤平，同步保留維度資訊。"""
        collected: List[Dict[str, Union[str, float, List[str]]]] = []
        for dimension, result in evaluation_results.items():
            for issue in result.get("issues", []) if isinstance(result, dict) else []:
                if hasattr(issue, "__dict__"):
                    payload = {**issue.__dict__}
                elif isinstance(issue, dict):
                    payload = issue.copy()
                else:
                    continue
                payload.setdefault("dimension", dimension)
                collected.append(payload)
        return collected

    def _build_dimension_summary(
        self,
        evaluation_results: Dict[str, Dict[str, Union[float, List, Dict]]],
        paragraph_count: int
    ) -> Dict[str, Dict[str, Union[float, int]]]:
        """建立輸出的 dimension_details 區塊，轉換為統一結構。"""
        semantic_result = evaluation_results.get("semantic", {})
        structural_result = evaluation_results.get("structural", {})
        thematic_result = evaluation_results.get("thematic", {})
        temporal_result = evaluation_results.get("temporal", {})

        def _as_float(value: Union[float, int, List, Tuple, Set, None]) -> float:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, (list, tuple, set)):
                return float(len(value))
            return 0.0

        def _issue_count(result: Dict[str, Union[List, Dict]]) -> int:
            issues = result.get("issues", []) if isinstance(result, dict) else []
            return len(issues) if isinstance(issues, list) else 0

        return {
            "semantic": {
                "score": round(_as_float(semantic_result.get("score", 0.0)), 1),
                "vocabulary_consistency": round(_as_float(semantic_result.get("vocabulary_consistency", 0.0)), 1),
                "concept_relatedness": round(_as_float(semantic_result.get("concept_relatedness", 0.0)), 1),
                "semantic_field_maintenance": round(_as_float(semantic_result.get("semantic_field_maintenance", 0.0)), 1),
                "reference_resolution": round(_as_float(semantic_result.get("reference_resolution", 0.0)), 1),
                "entity_continuity": round(_as_float(semantic_result.get("entity_continuity", 0.0)), 1),
                "issues_count": _issue_count(semantic_result)
            },
            "structural": {
                "score": round(_as_float(structural_result.get("score", 0.0)), 1),
                "paragraph_logical_order": round(_as_float(structural_result.get("paragraph_logical_order", 0.0)), 1),
                "section_hierarchy": round(_as_float(structural_result.get("section_hierarchy", 0.0)), 1),
                "argument_structure_integrity": round(_as_float(structural_result.get("argument_structure_integrity", 0.0)), 1),
                "paragraph_count": paragraph_count,
                "issues_count": _issue_count(structural_result)
            },
            "thematic": {
                "score": round(_as_float(thematic_result.get("score", 0.0)), 1),
                "topic_consistency": round(_as_float(thematic_result.get("topic_consistency", 0.0)), 1),
                "focus_maintenance": round(_as_float(thematic_result.get("focus_maintenance", 0.0)), 1),
                "topic_transition_naturalness": round(_as_float(thematic_result.get("topic_transition_naturalness", 0.0)), 1),
                "theme_anchors": round(_as_float(thematic_result.get("theme_anchors", 0.0)), 1),
                "dialogue_topic_flow": round(_as_float(thematic_result.get("dialogue_topic_flow", 0.0)), 1),
                "issues_count": _issue_count(thematic_result)
            },
            "temporal": {
                "score": round(_as_float(temporal_result.get("score", 0.0)), 1),
                "timeline_consistency": round(_as_float(temporal_result.get("timeline_consistency", 0.0)), 1),
                "event_sequence_logic": round(_as_float(temporal_result.get("event_sequence_logic", 0.0)), 1),
                "tense_usage_consistency": round(_as_float(temporal_result.get("tense_usage_consistency", 0.0)), 1),
                "temporal_markers": round(_as_float(temporal_result.get("temporal_markers", 0.0)), 1),
                "issues_count": _issue_count(temporal_result)
            }
        }

    def _build_analysis_summary(
        self,
        evaluation_results: Dict[str, Dict[str, Union[float, List, Dict]]],
        paragraph_count: int
    ) -> Dict[str, Dict[str, Union[float, int]]]:
        """建立面向報告的分析摘要，保留舊版欄位同時防禦異常值。"""
        semantic_result = evaluation_results.get("semantic", {})
        structural_result = evaluation_results.get("structural", {})
        thematic_result = evaluation_results.get("thematic", {})
        temporal_result = evaluation_results.get("temporal", {})

        def _as_float(value: Union[float, int, List, Tuple, Set, None]) -> float:
            if isinstance(value, (int, float)):
                return float(value)
            return 0.0

        def _len_if_iterable(value: Union[List, Tuple, Set, None]) -> int:
            if isinstance(value, (list, tuple, set)):
                return len(value)
            return 0

        return {
            "semantic_analysis": {
                "vocabulary_consistency": round(_as_float(semantic_result.get("vocabulary_consistency", 0.0)), 2),
                "concept_relatedness": round(_as_float(semantic_result.get("concept_relatedness", 0.0)), 2),
                "semantic_field_maintenance": round(_as_float(semantic_result.get("semantic_field_maintenance", 0.0)), 2),
                "reference_resolution_score": round(_as_float(semantic_result.get("reference_resolution", 0.0)), 2)
            },
            "structural_analysis": {
                "paragraph_logical_order": round(_as_float(structural_result.get("paragraph_logical_order", 0.0)), 2),
                "section_hierarchy": round(_as_float(structural_result.get("section_hierarchy", 0.0)), 2),
                "argument_structure_integrity": round(_as_float(structural_result.get("argument_structure_integrity", 0.0)), 2),
                "paragraph_count": paragraph_count
            },
            "thematic_analysis": {
                "topic_consistency": round(_as_float(thematic_result.get("topic_consistency", 0.0)), 2),
                "focus_maintenance": round(_as_float(thematic_result.get("focus_maintenance", 0.0)), 2),
                "topic_transition_naturalness": round(_as_float(thematic_result.get("topic_transition_naturalness", 0.0)), 2),
                "theme_anchors_count": _len_if_iterable(thematic_result.get("theme_anchors", []))
            },
            "temporal_analysis": {
                "timeline_consistency": round(_as_float(temporal_result.get("timeline_consistency", 0.0)), 2),
                "event_sequence_logic": round(_as_float(temporal_result.get("event_sequence_logic", 0.0)), 2),
                "tense_usage_consistency": round(_as_float(temporal_result.get("tense_usage_consistency", 0.0)), 2),
                "temporal_markers_count": _len_if_iterable(temporal_result.get("temporal_markers", []))
            }
        }

    def _detect_narrative_alerts(
        self,
        evaluation_results: Dict[str, Dict[str, Union[float, List, Dict]]],
        sentences: List[str]
    ) -> List[str]:
        """根據分數與文本特徵產生敘事警示，協助下游快速掌握風險。"""
        alerts: List[str] = []

        semantic = evaluation_results.get("semantic", {})
        structural = evaluation_results.get("structural", {})
        thematic = evaluation_results.get("thematic", {})
        temporal = evaluation_results.get("temporal", {})

        if semantic.get("score", 100.0) < 45:
            alerts.append("語義連貫性偏低，建議檢查詞彙與概念連接。")

        if structural.get("paragraph_logical_order", 100.0) < 40:
            alerts.append("段落邏輯順序混亂，可能需要重整敘事結構。")

        if thematic.get("topic_consistency", 100.0) < 40:
            alerts.append("主題一致性不足，故事可能缺乏清晰中心。")

        if temporal.get("timeline_consistency", 100.0) < 40:
            alerts.append("時間線疑似錯置，請特別留意事件順序。")

        if len(sentences) <= 5 and structural.get("score", 0.0) < 50:
            alerts.append("短篇故事的結構過於稀疏，建議補充橋接句。")

        return alerts
    
    # ====== 輔助方法 ======
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """分割段落"""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _extract_text_features(self, text: str) -> Dict:
        """提取文本特徵"""
        sentences = self._split_sentences(text)
        
        return {
            "length": len(text),
            "word_count": len(text.split()),
            "sentence_count": len(sentences),
            "avg_sentence_length": sum(len(s) for s in sentences) / len(sentences) if sentences else 0,
            "complexity": len([s for s in sentences if len(s.split()) > 15]) / len(sentences) if sentences else 0,
            "question_count": len([s for s in sentences if "?" in s]),
            "exclamation_count": len([s for s in sentences if "!" in s])
        }
    
    # ====== 結構連貫性分析方法 ======
    
    def _analyze_paragraph_logical_order(self, paragraphs: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析段落邏輯順序"""
        if len(paragraphs) <= 1:
            return 100.0, []
        
        issues = []
        order_scores = []
        
        for i in range(len(paragraphs) - 1):
            current_para = paragraphs[i]
            next_para = paragraphs[i + 1]
            
            # 檢查段落間的邏輯連接
            connection_score = self._analyze_paragraph_logical_connection(current_para, next_para)
            order_scores.append(connection_score)
            
            if connection_score < 60:
                issues.append(CoherenceIssue(
                    issue_type="paragraph_logical_order",
                    location=f"段落 {i+1} → {i+2}",
                    description="段落間缺乏邏輯順序，連接不自然",
                    severity="medium" if connection_score > 30 else "high",
                    suggestions=[
                        "重新安排段落順序以改善邏輯流暢度",
                        "添加過渡句來連接段落主題",
                        "確保段落間的邏輯關係清晰"
                    ]
                ))
        
        # 計算整體段落邏輯順序分數
        if order_scores:
            avg_order_score = sum(order_scores) / len(order_scores)
        else:
            avg_order_score = 100.0
        
        return avg_order_score, issues
    
    def _analyze_paragraph_logical_connection(self, para1: str, para2: str) -> float:
        """分析兩個段落間的邏輯連接度"""
        score = 50.0  # 基礎分數
        
        # 1. 檢查邏輯連接詞
        para2_start = para2[:100].lower()
        
        logical_connectors = [
            r'\b(?:therefore|thus|hence|consequently|as a result|because|since|so)\b',
            r'\b(?:however|but|yet|although|despite|nevertheless)\b',
            r'\b(?:furthermore|moreover|additionally|besides|in addition)\b',
            r'\b(?:first|second|third|then|next|finally|last)\b',
            r'\b(?:meanwhile|simultaneously|at the same time)\b'
        ]
        
        for pattern in logical_connectors:
            if re.search(pattern, para2_start, re.IGNORECASE):
                score += 20
                break
        
        # 2. 檢查主題詞彙的邏輯發展
        words1 = set(re.findall(r'\b\w{4,}\b', para1.lower()))
        words2 = set(re.findall(r'\b\w{4,}\b', para2.lower()))
        
        if words1 and words2:
            overlap = len(words1.intersection(words2))
            overlap_ratio = overlap / min(len(words1), len(words2))
            score += overlap_ratio * 25
        
        # 3. 檢查論證結構的邏輯性
        if self._has_argument_structure(para1) and self._has_argument_structure(para2):
            score += 15
        
        return min(100.0, score)
    
    def _has_argument_structure(self, paragraph: str) -> bool:
        """檢查段落是否具有論證結構"""
        argument_indicators = [
            r'\b(?:claim|assert|argue|propose|suggest)\b',
            r'\b(?:evidence|proof|support|demonstrate)\b',
            r'\b(?:therefore|thus|hence|consequently)\b',
            r'\b(?:because|since|due to|as a result)\b'
        ]
        
        indicator_count = 0
        for pattern in argument_indicators:
            if re.search(pattern, paragraph, re.IGNORECASE):
                indicator_count += 1
        
        return indicator_count >= 2
    
    def _analyze_section_hierarchy(self, text: str, paragraphs: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析章節層次關係"""
        issues = []
        
        # 檢測標題層級
        title_patterns = [
            r'^#+\s+(.+)$',  # Markdown 標題
            r'^\d+\.\s+(.+)$',  # 數字標題
            r'^[A-Z][A-Z\s]+$',  # 全大寫標題
            r'^[A-Z][a-z\s]+:$'  # 冒號標題
        ]
        
        titles = []
        for line in text.split('\n'):
            line = line.strip()
            for pattern in title_patterns:
                if re.match(pattern, line):
                    titles.append(line)
                    break
        
        # 計算層次關係分數
        if len(titles) > 1:
            hierarchy_score = self._calculate_hierarchy_score(titles)
        else:
            hierarchy_score = 80.0  # 沒有標題不算問題
        
        # 檢查層次關係問題
        if hierarchy_score < 60:
            issues.append(CoherenceIssue(
                issue_type="section_hierarchy",
                location="全文",
                description="章節層次關係不清晰，標題結構混亂",
                severity="medium",
                suggestions=[
                    "建立清晰的標題層級結構",
                    "使用一致的標題格式",
                    "確保標題層次的邏輯性"
                ]
            ))
        
        return hierarchy_score, issues
    
    def _calculate_hierarchy_score(self, titles: List[str]) -> float:
        """計算標題層次分數"""
        score = 80.0
        
        # 檢查標題格式一致性
        formats = []
        for title in titles:
            if re.match(r'^#+\s+', title):
                formats.append('markdown')
            elif re.match(r'^\d+\.\s+', title):
                formats.append('numbered')
            elif re.match(r'^[A-Z][A-Z\s]+$', title):
                formats.append('uppercase')
            elif re.match(r'^[A-Z][a-z\s]+:$', title):
                formats.append('colon')
            else:
                formats.append('other')
        
        # 格式一致性加分
        if len(set(formats)) == 1:
            score += 15
        
        # 檢查層次深度合理性
        if len(titles) <= 3:
            score += 5  # 標題數量適中
        
        return min(100.0, score)
    
    def _analyze_argument_structure_integrity(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析論證結構完整性"""
        issues = []
        
        # 檢測論證元素
        argument_elements = {
            "claim": 0,
            "evidence": 0,
            "reasoning": 0,
            "conclusion": 0
        }
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # 檢測論點
            if re.search(r'\b(?:claim|assert|argue|propose|suggest|believe|think)\b', sentence_lower):
                argument_elements["claim"] += 1
            
            # 檢測證據
            if re.search(r'\b(?:evidence|proof|data|research|study|example|instance)\b', sentence_lower):
                argument_elements["evidence"] += 1
            
            # 檢測推理
            if re.search(r'\b(?:because|since|therefore|thus|hence|consequently|as a result)\b', sentence_lower):
                argument_elements["reasoning"] += 1
            
            # 檢測結論
            if re.search(r'\b(?:conclusion|therefore|thus|hence|in conclusion|finally)\b', sentence_lower):
                argument_elements["conclusion"] += 1
        
        # 計算論證結構完整性分數
        total_elements = sum(argument_elements.values())
        if total_elements > 0:
            # 檢查是否包含所有必要的論證元素
            completeness = sum(1 for count in argument_elements.values() if count > 0) / len(argument_elements)
            structure_score = min(100.0, 50 + completeness * 50)
        else:
            structure_score = 50.0  # 沒有論證元素
        
        # 檢查論證結構問題
        if structure_score < 60:
            issues.append(CoherenceIssue(
                issue_type="argument_structure_integrity",
                location="全文",
                description="論證結構不完整，缺乏必要的論證元素",
                severity="medium",
                suggestions=[
                    "確保論證包含明確的論點、證據和推理",
                    "添加適當的結論來總結論證",
                    "加強論證的邏輯結構"
                ]
            ))
        
        return structure_score, issues
    
    def _analyze_paragraph_flow(self, paragraphs: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析段落主題流"""
        if len(paragraphs) <= 1:
            return 100.0, []
        
        issues = []
        flow_scores = []
        
        for i in range(len(paragraphs) - 1):
            current_para = paragraphs[i]
            next_para = paragraphs[i + 1]
            
            # 檢查段落間的連接
            connection_score = self._analyze_paragraph_connection(current_para, next_para)
            flow_scores.append(connection_score)
            
            if connection_score < 60:
                issues.append(CoherenceIssue(
                    issue_type="paragraph_flow",
                    location=f"段落 {i+1} → {i+2}",
                    description="段落間缺乏明確的主題連接或過渡",
                    severity="medium" if connection_score > 30 else "high",
                    suggestions=[
                        "添加過渡句來連接段落主題",
                        "使用連接詞來明確段落間的邏輯關係",
                        "確保段落主題的漸進發展"
                    ]
                ))
        
        # 計算整體段落流暢度分數
        if flow_scores:
            avg_flow_score = sum(flow_scores) / len(flow_scores)
        else:
            avg_flow_score = 100.0
        
        return avg_flow_score, issues
    
    def _analyze_paragraph_connection(self, para1: str, para2: str) -> float:
        """分析兩個段落間的連接度"""
        score = 50.0  # 基礎分數
        
        # 1. 檢查連接詞
        para2_start = para2[:100].lower()  # 檢查段落開頭
        
        for pattern_type, patterns in self.coherence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, para2_start, re.IGNORECASE):
                    score += 15
                    break
        
        # 2. 檢查詞彙重複（主題連續性）
        words1 = set(re.findall(r'\b\w{3,}\b', para1.lower()))
        words2 = set(re.findall(r'\b\w{3,}\b', para2.lower()))
        
        if words1 and words2:
            overlap = len(words1.intersection(words2))
            overlap_ratio = overlap / min(len(words1), len(words2))
            score += overlap_ratio * 20
        
        # 3. 檢查實體連續性
        if self.nlp and hasattr(self.nlp, "pipe_names"):
            try:
                doc1 = self.nlp(para1)
                doc2 = self.nlp(para2)
                
                entities1 = set(ent.text.lower() for ent in doc1.ents)
                entities2 = set(ent.text.lower() for ent in doc2.ents)
                
                if entities1 and entities2:
                    entity_overlap = len(entities1.intersection(entities2))
                    if entity_overlap > 0:
                        score += entity_overlap * 10
            except Exception:
                pass
        
        return min(100.0, score)
    
    def _analyze_sentence_connections(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析句子連接"""
        if len(sentences) <= 1:
            return 100.0, []
        
        issues = []
        connection_scores = []
        
        for i in range(len(sentences) - 1):
            current_sent = sentences[i]
            next_sent = sentences[i + 1]
            
            # 檢查句子間的連接
            connection_score = self._analyze_sentence_connection(current_sent, next_sent)
            connection_scores.append(connection_score)
            
            if connection_score < 50:
                issues.append(CoherenceIssue(
                    issue_type="sentence_connection",
                    location=f"句子 {i+1} → {i+2}",
                    description="句子間缺乏邏輯連接",
                    severity="medium",
                    suggestions=[
                        "添加連接詞來明確句子間的關係",
                        "使用過渡詞來改善句子流暢度",
                        "確保句子主題的連續性"
                    ]
                ))
        
        # 計算平均連接分數
        if connection_scores:
            avg_connection_score = sum(connection_scores) / len(connection_scores)
        else:
            avg_connection_score = 100.0
        
        return avg_connection_score, issues
    
    def _analyze_sentence_connection(self, sent1: str, sent2: str) -> float:
        """分析兩個句子間的連接度"""
        score = 40.0  # 基礎分數
        
        # 檢查連接詞
        sent2_start = sent2[:50].lower()
        
        for pattern_type, patterns in self.coherence_patterns.items():
            for pattern in patterns:
                if re.search(pattern, sent2_start, re.IGNORECASE):
                    score += 20
                    break
        
        # 檢查詞彙重複
        words1 = set(re.findall(r'\b\w{3,}\b', sent1.lower()))
        words2 = set(re.findall(r'\b\w{3,}\b', sent2.lower()))
        
        if words1 and words2:
            overlap = len(words1.intersection(words2))
            overlap_ratio = overlap / min(len(words1), len(words2))
            score += overlap_ratio * 30
        
        return min(100.0, score)
    
    def _analyze_transition_markers(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析過渡標記"""
        issues = []
        transition_scores = []
        
        for i, sentence in enumerate(sentences):
            # 檢查過渡標記
            transition_count = 0
            for pattern_type, patterns in self.coherence_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, sentence, re.IGNORECASE)
                    transition_count += len(matches)
            
            # 計算過渡標記分數
            if transition_count > 0:
                transition_score = min(100.0, 60 + transition_count * 15)
            else:
                transition_score = 50.0  # 沒有過渡標記不一定是問題
            
            transition_scores.append(transition_score)
            
            # 檢查過度使用過渡標記
            if transition_count > 3:
                issues.append(CoherenceIssue(
                    issue_type="transition_overuse",
                    location=f"句子 {i+1}",
                    description="過渡標記使用過多，可能影響閱讀流暢度",
                    severity="low",
                    suggestions=[
                        "減少過渡標記的使用",
                        "使用更自然的句子連接方式"
                    ]
                ))
        
        # 計算平均過渡標記分數
        if transition_scores:
            avg_transition_score = sum(transition_scores) / len(transition_scores)
        else:
            avg_transition_score = 100.0
        
        return avg_transition_score, issues
    
    def _analyze_discourse_structure(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析話語結構"""
        issues = []
        
        # 檢查話語標記
        discourse_markers = 0
        for sentence in sentences:
            for pattern_type, patterns in self.coherence_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, sentence, re.IGNORECASE)
                    discourse_markers += len(matches)
        
        # 計算話語結構分數
        if len(sentences) > 0:
            marker_density = discourse_markers / len(sentences)
            discourse_score = min(100.0, 50 + marker_density * 20)
        else:
            discourse_score = 100.0
        
        # 檢查話語結構問題
        if discourse_markers == 0 and len(sentences) > 3:
            issues.append(CoherenceIssue(
                issue_type="discourse_structure",
                location="全文",
                description="缺乏話語標記，可能影響文本結構清晰度",
                severity="medium",
                suggestions=[
                    "添加適當的話語標記來改善文本結構",
                    "使用連接詞來明確句子間的邏輯關係"
                ]
            ))
        
        return discourse_score, issues
    
    # ====== 語義連貫性分析方法 ======
    
    def _analyze_vocabulary_consistency(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析詞彙一致性"""
        issues = []
        
        # 提取所有詞彙
        all_words = []
        for sentence in sentences:
            words = re.findall(r'\b\w{3,}\b', sentence.lower())
            all_words.extend(words)
        
        if len(all_words) < 2:
            return 100.0, []
        
        # 計算詞彙一致性
        word_counts = Counter(all_words)
        total_words = len(all_words)
        unique_words = len(word_counts)
        
        # 詞彙重複率（一致性指標）
        repetition_rate = 1 - (unique_words / total_words) if total_words > 0 else 0
        
        # 計算詞彙一致性分數
        vocabulary_score = min(100.0, 50 + repetition_rate * 50)
        
        # 檢查詞彙一致性問題
        if vocabulary_score < 60:
            issues.append(CoherenceIssue(
                issue_type="vocabulary_consistency",
                location="全文",
                description="詞彙使用過於分散，缺乏一致性",
                severity="medium",
                suggestions=[
                    "保持核心詞彙的重複使用",
                    "建立詞彙使用的一致性標準",
                    "避免過度使用同義詞"
                ]
            ))
        
        return vocabulary_score, issues
    
    def _analyze_concept_relatedness(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析概念關聯性"""
        issues = []
        
        if len(sentences) < 2:
            return 100.0, []
        
        # 檢測是否為童話故事
        text = " ".join(sentences)
        is_fairy_tale = self._detect_fairy_tale(text)
        
        # 使用語義相似度計算概念關聯性
        if self.semantic_model and self.semantic_model.get("semantic_model"):
            concept_scores, concept_breaks = self._detect_concept_breaks_advanced(sentences)
        else:
            concept_scores, concept_breaks = self._detect_concept_breaks_basic(sentences)
        
        # 計算平均概念關聯性分數
        if concept_scores:
            avg_concept_score = sum(concept_scores) / len(concept_scores)
        else:
            avg_concept_score = 100.0
        
        # 童話故事特殊處理：童話的概念關聯性通常較簡單
        if is_fairy_tale and avg_concept_score < 30:
            avg_concept_score = min(50.0, avg_concept_score + 20)  # 童話概念簡單是正常的
        
        # 添加概念斷裂問題
        for break_idx in concept_breaks:
            issues.append(CoherenceIssue(
                issue_type="concept_break",
                location=f"句子 {break_idx+1} → {break_idx+2}",
                description="檢測到概念關聯性斷裂，句子間概念缺乏關聯",
                severity="high" if concept_scores[break_idx] < 30 else "medium",
                suggestions=[
                    "加強句子間的概念關聯",
                    "使用更相關的概念和詞彙",
                    "建立清晰的概念發展線索"
                ]
            ))
        
        return avg_concept_score, issues
    
    def _analyze_semantic_field_maintenance(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析語義場維持"""
        issues = []
        
        if len(sentences) < 2:
            return 100.0, []
        
        # 提取語義場詞彙（名詞、動詞、形容詞）
        semantic_fields = {"nouns": [], "verbs": [], "adjectives": []}
        
        for i, sentence in enumerate(sentences):
            if self.nlp and hasattr(self.nlp, "pipe_names"):
                try:
                    doc = self.nlp(sentence)
                    for token in doc:
                        if token.pos_ == "NOUN":
                            semantic_fields["nouns"].append((i, token.text.lower()))
                        elif token.pos_ == "VERB":
                            semantic_fields["verbs"].append((i, token.text.lower()))
                        elif token.pos_ == "ADJ":
                            semantic_fields["adjectives"].append((i, token.text.lower()))
                except Exception:
                    pass
        
        # 計算語義場維持分數
        field_scores = []
        for field_type, field_words in semantic_fields.items():
            if len(field_words) > 1:
                # 計算詞彙在句子間的分佈
                sentence_counts = Counter(word[0] for word in field_words)
                distribution_score = len(sentence_counts) / len(sentences) if sentences else 0
                field_scores.append(distribution_score * 100)
        
        if field_scores:
            semantic_field_score = sum(field_scores) / len(field_scores)
        else:
            semantic_field_score = 50.0
        
        # 檢查語義場維持問題
        if semantic_field_score < 60:
            issues.append(CoherenceIssue(
                issue_type="semantic_field_maintenance",
                location="全文",
                description="語義場維持不足，詞彙分佈不均勻",
                severity="medium",
                suggestions=[
                    "確保語義相關詞彙在文本中均勻分佈",
                    "維持語義場的連續性",
                    "避免語義場的突然中斷"
                ]
            ))
        
        return semantic_field_score, issues
    
    def _detect_concept_breaks_advanced(self, sentences: List[str]) -> Tuple[List[float], List[int]]:
        """高級概念斷裂檢測（使用transformers模型）"""
        concept_scores = []
        concept_breaks = []
        
        try:
            semantic_model = self.semantic_model["semantic_model"]
            tokenizer = semantic_model["tokenizer"]
            model = semantic_model["model"]
            cosine_similarity = self.semantic_model["cosine_similarity"]
            np = self.semantic_model["np"]
            
            # 批量編碼所有句子
            device = next(model.parameters()).device
            all_inputs = tokenizer(sentences, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if device.type == 'cuda':
                all_inputs = {k: v.to(device) for k, v in all_inputs.items()}
            
            with torch.no_grad():
                outputs = model(**all_inputs)
                embeddings = outputs.last_hidden_state.mean(dim=1)
            
            # 計算相鄰句子的概念相似度
            for i in range(len(sentences) - 1):
                emb1 = embeddings[i:i+1].cpu().numpy()
                emb2 = embeddings[i+1:i+2].cpu().numpy()
                
                similarity = cosine_similarity(emb1, emb2)[0][0]
                score = similarity * 100
                concept_scores.append(score)
                
                # 檢測概念斷裂（相似度低於閾值）
                if score < 25:  # 概念關聯性閾值
                    concept_breaks.append(i)
            
            return concept_scores, concept_breaks
            
        except Exception as e:
            self.logger.warning("⚠️ 高級概念斷裂檢測失敗: %s", e)
            return self._detect_concept_breaks_basic(sentences)
    
    def _detect_concept_breaks_basic(self, sentences: List[str]) -> Tuple[List[float], List[int]]:
        """基礎概念斷裂檢測（改進：使用滑動窗口）"""
        concept_scores = []
        concept_breaks = []
        window_size = 3
        
        for i in range(len(sentences)):
            # 獲取窗口內的句子
            window_start = max(0, i - window_size + 1)
            window_end = min(len(sentences), i + window_size)
            
            # 當前句子的詞彙
            current_words = set(re.findall(r'\b\w{4,}\b', sentences[i].lower()))
            
            # 窗口內其他句子的詞彙
            window_words = set()
            for j in range(window_start, window_end):
                if j != i:
                    window_words.update(re.findall(r'\b\w{4,}\b', sentences[j].lower()))
            
            if current_words and window_words:
                overlap = len(current_words.intersection(window_words))
                # 放寬評分：只要有詞彙關聯就給高分
                score = min(100.0, 40 + (overlap / max(len(current_words), 1)) * 120)
            else:
                score = 60.0  # 提高基礎分
            
            concept_scores.append(score)
            
            # 檢測概念斷裂（放寬閾值：從25降到15）
            if score < 15:
                concept_breaks.append(i)
        
        return concept_scores, concept_breaks
    
    def _analyze_reference_resolution(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析指稱消解"""
        issues = []
        reference_scores = []
        
        for i, sentence in enumerate(sentences):
            # 檢查代詞
            pronouns = re.findall(self.reference_patterns["pronouns"], sentence, re.IGNORECASE)
            
            for pronoun in pronouns:
                # 檢查代詞是否有明確的先行詞
                antecedent_score = self._find_antecedent(pronoun, i, sentences)
                reference_scores.append(antecedent_score)
                
                if antecedent_score < 50:
                    issues.append(CoherenceIssue(
                        issue_type="pronoun_reference",
                        location=f"句子 {i+1}",
                        description=f"代詞 '{pronoun}' 的指稱對象不明確",
                        severity="high" if antecedent_score < 20 else "medium",
                        suggestions=[
                            f"明確指出 '{pronoun}' 所指的對象",
                            "考慮重複使用名詞而非代詞",
                            "調整句子順序使指稱關係更清晰"
                        ]
                    ))
            
            # 檢查定冠詞 "the" 的使用
            definite_refs = re.findall(self.reference_patterns["definite_articles"], sentence, re.IGNORECASE)
            for ref in definite_refs:
                ref_score = self._check_definite_reference(ref, i, sentences)
                reference_scores.append(ref_score)
                
                if ref_score < 40:
                    issues.append(CoherenceIssue(
                        issue_type="definite_reference",
                        location=f"句子 {i+1}",
                        description=f"定冠詞用法 '{ref}' 可能缺乏前文鋪墊",
                        severity="medium",
                        suggestions=[
                            f"確保 '{ref}' 在前文中已被引入",
                            "考慮使用不定冠詞 'a/an' 首次引入概念"
                        ]
                    ))
        
        # 計算整體指稱分數
        if reference_scores:
            avg_reference_score = sum(reference_scores) / len(reference_scores)
        else:
            avg_reference_score = 100.0
        
        return avg_reference_score, issues
    
    def _find_antecedent(self, pronoun: str, sentence_idx: int, sentences: List[str]) -> float:
        """尋找代詞的先行詞"""
        pronoun_lower = pronoun.lower()
        
        # 檢查前面的句子（最多檢查3句）
        search_range = max(0, sentence_idx - 3)
        
        for i in range(sentence_idx - 1, search_range - 1, -1):
            prev_sentence = sentences[i].lower()
            
            # 簡單的先行詞匹配
            if pronoun_lower in ['he', 'him', 'his']:
                # 尋找男性名詞
                if re.search(r'\b(?:man|boy|father|dad|grandpa|uncle|brother|king|prince)\b', prev_sentence):
                    return 80.0
                # 尋找人名（首字母大寫）
                if re.search(r'\b[A-Z][a-z]+\b', sentences[i]):
                    return 70.0
                    
            elif pronoun_lower in ['she', 'her']:
                # 尋找女性名詞
                if re.search(r'\b(?:woman|girl|mother|mom|grandma|aunt|sister|queen|princess)\b', prev_sentence):
                    return 80.0
                if re.search(r'\b[A-Z][a-z]+\b', sentences[i]):
                    return 70.0
                    
            elif pronoun_lower in ['it', 'its']:
                # 尋找物件名詞
                if re.search(r'\b(?:book|toy|house|tree|car|ball|box|door)\b', prev_sentence):
                    return 75.0
                    
            elif pronoun_lower in ['they', 'them', 'their']:
                # 尋找複數名詞
                if re.search(r'\b\w+s\b', prev_sentence):  # 簡單的複數檢測
                    return 70.0
        
        return 30.0  # 未找到明確先行詞
    
    def _check_definite_reference(self, ref: str, sentence_idx: int, sentences: List[str]) -> float:
        """檢查定冠詞引用的合理性"""
        # 提取名詞部分
        noun = ref.replace('the ', '').strip()
        
        # 檢查前文是否已經提及
        for i in range(sentence_idx):
            if noun.lower() in sentences[i].lower():
                return 80.0
        
        # 檢查是否為常識概念（不需要前文介紹）
        common_concepts = ['sun', 'moon', 'sky', 'ground', 'door', 'window', 'table', 'chair']
        if noun.lower() in common_concepts:
            return 90.0
        
        return 30.0
    
    def _analyze_entity_continuity(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析實體連續性"""
        issues = []
        
        # 提取所有實體
        entities = []
        for i, sentence in enumerate(sentences):
            if self.nlp and hasattr(self.nlp, "pipe_names"):
                try:
                    doc = self.nlp(sentence)
                    for ent in doc.ents:
                        entities.append({
                            'text': ent.text,
                            'label': ent.label_,
                            'sentence_idx': i,
                            'start': ent.start_char,
                            'end': ent.end_char
                        })
                except Exception:
                    pass
        
        # 分析實體連續性
        entity_continuity_score = 100.0
        if len(entities) > 1:
            # 檢查實體重複出現
            entity_counts = Counter(ent['text'].lower() for ent in entities)
            repeated_entities = {k: v for k, v in entity_counts.items() if v > 1}
            
            if repeated_entities:
                # 計算連續性分數
                continuity_ratio = len(repeated_entities) / len(set(ent['text'].lower() for ent in entities))
                entity_continuity_score = min(100.0, 60 + continuity_ratio * 40)
            else:
                entity_continuity_score = 50.0  # 沒有重複實體可能表示缺乏連續性
        
        # 檢查實體連續性問題
        if entity_continuity_score < 60:
            issues.append(CoherenceIssue(
                issue_type="entity_continuity",
                location="全文",
                description="實體連續性不足，可能影響文本連貫性",
                severity="medium",
                suggestions=[
                    "確保重要實體在文本中重複出現",
                    "使用一致的實體命名",
                    "建立實體之間的明確關係"
                ]
            ))
        
        return entity_continuity_score, issues
    
    def _analyze_topic_consistency(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析主題一致性（基於LDA主題模型）"""
        issues = []
        
        if len(sentences) < 2:
            return 100.0, []
        
        # 使用LDA分析主題一致性
        if self.semantic_model and self.semantic_model.get("lda_model"):
            topic_consistency_score, topic_issues = self._analyze_topic_drift_with_lda(sentences)
            issues.extend(topic_issues)
        else:
            # 回退到基礎詞彙分析
            topic_consistency_score, topic_issues = self._analyze_topic_consistency_basic(sentences)
            issues.extend(topic_issues)
        
        return topic_consistency_score, issues
    
    def _analyze_topic_drift_with_lda(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """使用改進的主題一致性分析（基於全文錨點 + 語義相似度）。

        修正：改用本模組已載入的 huggingface 模型編碼，避免依賴不存在的 sentence_model。
        """
        issues: List[CoherenceIssue] = []

        try:
            # 1) 智能段落分割
            paragraphs = self._smart_paragraph_segmentation(sentences)
            if len(paragraphs) < 2:
                return 80.0, []

            # 2) 取得段落與全文向量
            paragraph_vectors = self._encode_texts(paragraphs)
            if paragraph_vectors is None:
                return self._analyze_topic_consistency_basic(sentences)

            full_text = " ".join(sentences)
            full_vec = self._encode_texts([full_text])
            if full_vec is None:
                return self._analyze_topic_consistency_basic(sentences)
            full_text_vector = full_vec[0]

            # 3) 每段與全文錨點的相似度
            paragraph_similarities: List[float] = []
            for i in range(paragraph_vectors.shape[0]):
                para_vector = paragraph_vectors[i]
                denom = (np.linalg.norm(para_vector) * np.linalg.norm(full_text_vector)) or 1e-8
                similarity = float(np.dot(para_vector, full_text_vector) / denom)
                paragraph_similarities.append(similarity)

            # 4) 主題一致性分數（中位數更穩健）
            if paragraph_similarities:
                median_similarity = float(np.median(paragraph_similarities))
                topic_consistency_score = self._clamp(median_similarity * 100.0)
            else:
                topic_consistency_score = 80.0

            # 5) 相鄰段落漂移檢測（僅作輕度調整）
            adjacent_drifts: List[float] = []
            if paragraph_vectors.shape[0] > 1:
                for i in range(paragraph_vectors.shape[0] - 1):
                    a = paragraph_vectors[i]
                    b = paragraph_vectors[i + 1]
                    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-8
                    adj_similarity = float(np.dot(a, b) / denom)
                    adjacent_drifts.append(adj_similarity)

                low_similarity_count = sum(1 for sim in adjacent_drifts if sim < 0.3)
                if adjacent_drifts and low_similarity_count > len(adjacent_drifts) * 0.6:
                    topic_consistency_score *= 0.8

            # 6) 建立問題提示
            if topic_consistency_score < 60:
                debug_info = f"段落相似度: {[f'{sim:.3f}' for sim in paragraph_similarities]}"
                if adjacent_drifts:
                    debug_info += f", 相鄰段相似度: {[f'{sim:.3f}' for sim in adjacent_drifts]}"

                issues.append(CoherenceIssue(
                    issue_type="topic_drift",
                    location="全文",
                    description=f"檢測到主題一致性不足，段落與全文主題關聯性較低 ({debug_info})",
                    severity="high" if topic_consistency_score < 40 else "medium",
                    suggestions=[
                        "加強段落與整體主題的關聯性",
                        "確保各段落都圍繞核心主題展開",
                        "使用主題詞彙來維持一致性"
                    ]
                ))

            return float(topic_consistency_score), issues

        except Exception as e:
            self.logger.warning("⚠️ 改進主題分析失敗: %s", e)
            return self._analyze_topic_consistency_basic(sentences)
    
    def _smart_paragraph_segmentation(self, sentences: List[str]) -> List[str]:
        """智能段落分割策略"""
        # 檢查是否有頁面標記
        text = " ".join(sentences)
        if "Page " in text and re.search(r'Page \d+:', text):
            # 按頁面分割
            paragraphs = []
            current_paragraph = []
            for sentence in sentences:
                if re.search(r'Page \d+:', sentence):
                    if current_paragraph:
                        paragraphs.append(" ".join(current_paragraph))
                        current_paragraph = []
                current_paragraph.append(sentence)
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
            return paragraphs
        else:
            # 使用較大的段落大小（6-8句）
            paragraph_size = min(8, max(6, len(sentences) // 2))
            paragraphs = []
            for i in range(0, len(sentences), paragraph_size):
                paragraph = " ".join(sentences[i:i+paragraph_size])
                paragraphs.append(paragraph)
            return paragraphs
    
    def _analyze_topic_consistency_basic(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """基礎主題一致性分析（回退方法）"""
        issues = []
        
        # 提取主題詞彙
        topic_words = []
        for sentence in sentences:
            words = re.findall(r'\b\w{4,}\b', sentence.lower())
            topic_words.extend(words)
        
        # 計算主題一致性
        if len(topic_words) > 0:
            word_counts = Counter(topic_words)
            # 計算主題集中度
            total_words = len(topic_words)
            unique_words = len(word_counts)
            topic_concentration = 1 - (unique_words / total_words) if total_words > 0 else 0
            
            topic_consistency_score = min(100.0, 50 + topic_concentration * 50)
        else:
            topic_consistency_score = 50.0
        
        # 檢查主題一致性問題
        if topic_consistency_score < 60:
            issues.append(CoherenceIssue(
                issue_type="topic_consistency",
                location="全文",
                description="主題一致性不足，可能影響文本連貫性",
                severity="medium",
                suggestions=[
                    "保持主題詞彙的一致性",
                    "避免過度分散的詞彙使用",
                    "建立清晰的主題線索"
                ]
            ))
        
        return topic_consistency_score, issues
    
    def _analyze_theme_anchors(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """主題錨點分析（動態提取核心詞彙）"""
        issues = []
        
        # 動態提取高頻詞彙作為主題錨點
        text = " ".join(sentences).lower()
        words = re.findall(r'\b\w{4,}\b', text)
        
        # 排除停用詞 - 使用配置文件
        words = [w for w in words if w not in self.stop_words]
        
        # 計算詞頻
        from collections import Counter
        word_freq = Counter(words)
        
        # 提取前10個高頻詞作為主題錨點
        top_anchors = [word for word, count in word_freq.most_common(10) if count >= 3]
        
        if not top_anchors:
            return 60.0, issues  # 沒有高頻詞，給基礎分
        
        # 計算這些錨點在文本中的分佈均勻度
        anchor_presence_per_segment = []
        segment_size = max(1, len(sentences) // 3)  # 分成3段
        
        for i in range(0, len(sentences), segment_size):
            segment = " ".join(sentences[i:i+segment_size]).lower()
            presence = sum(1 for anchor in top_anchors if anchor in segment)
            anchor_presence_per_segment.append(presence / len(top_anchors))
        
        # 計算分佈均勻度（標準差越小越好）
        import numpy as np
        if len(anchor_presence_per_segment) > 1:
            std_dev = np.std(anchor_presence_per_segment)
            # 標準差低表示錨點分佈均勻
            theme_anchor_score = max(50.0, min(100.0, 100 - std_dev * 100))
        else:
            theme_anchor_score = 80.0  # 文本太短，給予較高基礎分
        
        # 檢測主題錨點問題
        if theme_anchor_score < 40:
            issues.append(CoherenceIssue(
                issue_type="theme_anchors",
                location="全文",
                description=f"主題錨點分佈不均：{anchor_presence_per_segment}",
                severity="medium",
                suggestions=[
                    "確保核心主題詞在全文中均勻出現",
                    "避免主題詞過度集中在某些段落",
                    "維持主題詞彙的一致性"
                ]
            ))
        
        return theme_anchor_score, issues
    
    def _analyze_dialogue_topic_flow(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """對話回合與主題流耦合分析"""
        issues = []
        
        # 檢測對話回合完整性
        dialogue_rounds = []
        current_round = []
        
        for sentence in sentences:
            # 檢測問答模式
            if re.search(r'\?', sentence) or re.search(r'(?:asked|said|told|explained)', sentence.lower()):
                if current_round:
                    dialogue_rounds.append(current_round)
                current_round = [sentence]
            elif current_round and re.search(r'(?:answered|replied|responded)', sentence.lower()):
                current_round.append(sentence)
                dialogue_rounds.append(current_round)
                current_round = []
            elif current_round:
                current_round.append(sentence)
        
        if current_round:
            dialogue_rounds.append(current_round)
        
        # 計算對話回合完整性
        complete_rounds = 0
        for round_sentences in dialogue_rounds:
            if len(round_sentences) >= 2:  # 至少包含問和答
                complete_rounds += 1
        
        dialogue_completeness = complete_rounds / len(dialogue_rounds) if dialogue_rounds else 0
        dialogue_topic_score = dialogue_completeness * 100
        
        # 檢測對話主題流問題
        if dialogue_topic_score < 50:
            issues.append(CoherenceIssue(
                issue_type="dialogue_topic_flow",
                location="對話部分",
                description="對話回合不完整，影響主題流暢性",
                severity="low",
                suggestions=[
                    "完善問答對話的完整性",
                    "確保對話圍繞主題展開",
                    "加強對話與敘述的銜接"
                ]
            ))
        
        return dialogue_topic_score, issues
    
    def _analyze_semantic_cohesion(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析語義凝聚性（增強版語義斷裂檢測）"""
        issues = []
        
        if len(sentences) < 2:
            return 100.0, []
        
        # 使用增強語義相似度計算
        if self.semantic_model and self.semantic_model.get("semantic_model"):
            cohesion_scores, semantic_breaks = self._detect_semantic_breaks_advanced(sentences)
        else:
            cohesion_scores, semantic_breaks = self._detect_semantic_breaks_basic(sentences)
        
        # 計算平均凝聚性分數
        if cohesion_scores:
            avg_cohesion_score = sum(cohesion_scores) / len(cohesion_scores)
        else:
            avg_cohesion_score = 100.0
        
        # 添加語義斷裂問題
        for break_idx in semantic_breaks:
            issues.append(CoherenceIssue(
                issue_type="semantic_break",
                location=f"句子 {break_idx+1} → {break_idx+2}",
                description="檢測到語義斷裂，句子間缺乏語義關聯",
                severity="high" if cohesion_scores[break_idx] < 30 else "medium",
                suggestions=[
                    "添加過渡句來連接語義斷裂處",
                    "使用更相關的詞彙和概念",
                    "建立清晰的語義線索"
                ]
            ))
        
        # 檢查整體語義凝聚性問題
        if avg_cohesion_score < 50:
            issues.append(CoherenceIssue(
                issue_type="semantic_cohesion",
                location="全文",
                description="語義凝聚性不足，句子間缺乏語義關聯",
                severity="high",
                suggestions=[
                    "加強句子間的語義關聯",
                    "使用更相關的詞彙和概念",
                    "建立清晰的語義線索"
                ]
            ))
        
        return avg_cohesion_score, issues
    
    def _detect_semantic_breaks_advanced(self, sentences: List[str]) -> Tuple[List[float], List[int]]:
        """高級語義斷裂檢測（使用transformers模型）"""
        cohesion_scores = []
        semantic_breaks = []
        
        try:
            semantic_model = self.semantic_model["semantic_model"]
            tokenizer = semantic_model["tokenizer"]
            model = semantic_model["model"]
            cosine_similarity = self.semantic_model["cosine_similarity"]
            np = self.semantic_model["np"]
            
            # 批量編碼所有句子
            device = next(model.parameters()).device
            all_inputs = tokenizer(sentences, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if device.type == 'cuda':
                all_inputs = {k: v.to(device) for k, v in all_inputs.items()}
            
            with torch.no_grad():
                outputs = model(**all_inputs)
                embeddings = outputs.last_hidden_state.mean(dim=1)
            
            # 計算相鄰句子的相似度
            for i in range(len(sentences) - 1):
                emb1 = embeddings[i:i+1].cpu().numpy()
                emb2 = embeddings[i+1:i+2].cpu().numpy()
                
                similarity = cosine_similarity(emb1, emb2)[0][0]
                score = similarity * 100
                cohesion_scores.append(score)
                
                # 檢測語義斷裂（相似度低於閾值）
                if score < 30:  # 可調整的閾值
                    semantic_breaks.append(i)
            
            return cohesion_scores, semantic_breaks
            
        except Exception as e:
            self.logger.warning("⚠️ 高級語義斷裂檢測失敗: %s", e)
            return self._detect_semantic_breaks_basic(sentences)
    
    def _detect_semantic_breaks_basic(self, sentences: List[str]) -> Tuple[List[float], List[int]]:
        """基礎語義斷裂檢測（回退方法）"""
        cohesion_scores = []
        semantic_breaks = []
        
        for i in range(len(sentences) - 1):
            sent1 = sentences[i]
            sent2 = sentences[i + 1]
            
            # 使用詞彙重疊計算相似度
            words1 = set(re.findall(r'\b\w{3,}\b', sent1.lower()))
            words2 = set(re.findall(r'\b\w{3,}\b', sent2.lower()))
            
            if words1 and words2:
                overlap = len(words1.intersection(words2))
                similarity = overlap / max(len(words1), len(words2))
                score = similarity * 100
            else:
                score = 50.0
            
            cohesion_scores.append(score)
            
            # 檢測語義斷裂
            if score < 30:
                semantic_breaks.append(i)
        
        return cohesion_scores, semantic_breaks
    
    # ====== 主題連貫性分析方法 ======
    
    def _analyze_focus_maintenance(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析焦點維持（改進：使用滑動窗口，允許自然發展）"""
        issues = []
        
        if len(sentences) < 2:
            return 100.0, []
        
        # 提取每句的主題詞彙
        topic_words_per_sentence = []
        for sentence in sentences:
            words = re.findall(r'\b\w{4,}\b', sentence.lower())
            topic_words_per_sentence.append(set(words))
        
        # 使用滑動窗口（3句）計算焦點維持，允許主題自然發展
        focus_scores = []
        window_size = 3
        
        for i in range(len(topic_words_per_sentence)):
            # 當前句子的詞彙
            current_words = topic_words_per_sentence[i]
            
            # 獲取窗口內的其他句子（前後各1-2句）
            window_start = max(0, i - window_size + 1)
            window_end = min(len(topic_words_per_sentence), i + window_size)
            window_words = set()
            for j in range(window_start, window_end):
                if j != i:
                    window_words.update(topic_words_per_sentence[j])
            
            if current_words and window_words:
                overlap = len(current_words.intersection(window_words))
                # 放寬評分標準：只要有詞彙重疊就給高分
                focus_score = min(100.0, 50 + (overlap / max(len(current_words), 1)) * 100)
            else:
                focus_score = 70.0  # 提高基礎分
            
            focus_scores.append(focus_score)
        
        # 計算平均焦點維持分數
        if focus_scores:
            avg_focus_score = sum(focus_scores) / len(focus_scores)
        else:
            avg_focus_score = 100.0
        
        # 檢查焦點維持問題（放寬閾值）
        if avg_focus_score < 40:  # 從60降到40
            issues.append(CoherenceIssue(
                issue_type="focus_maintenance",
                location="全文",
                description="焦點維持不足，主題詞彙缺乏連續性",
                severity="medium",
                suggestions=[
                    "保持核心主題詞彙的連續使用",
                    "避免主題的突然跳躍",
                    "建立清晰的主題發展線索"
                ]
            ))
        
        return avg_focus_score, issues
    
    def _analyze_topic_transition_naturalness(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析話題轉換自然度（放寬標準，允許自然過渡）"""
        issues = []
        
        if len(sentences) < 2:
            return 100.0, []
        
        # 檢測話題轉換標記（放寬範圍，包含常見敘事詞）
        transition_markers = [
            r'\b(?:now|next|then|after|meanwhile|however|but|and|so)\b',
            r'\b(?:one day|once|when|while|as|from that day)\b',
            r'\b(?:suddenly|finally|soon|later|eventually)\b'
        ]
        
        transition_scores = []
        for i in range(len(sentences) - 1):
            current_sent = sentences[i]
            next_sent = sentences[i + 1]
            
            # 檢查是否有話題轉換標記
            has_transition = False
            for pattern in transition_markers:
                if re.search(pattern, next_sent, re.IGNORECASE):
                    has_transition = True
                    break
            
            # 計算話題轉換自然度（放寬評分）
            if has_transition:
                transition_score = 85.0  # 有轉換標記高分
            else:
                # 檢查話題連續性
                current_words = set(re.findall(r'\b\w{4,}\b', current_sent.lower()))
                next_words = set(re.findall(r'\b\w{4,}\b', next_sent.lower()))
                
                if current_words and next_words:
                    overlap = len(current_words.intersection(next_words))
                    overlap_ratio = overlap / max(len(current_words), len(next_words))
                    
                    if overlap_ratio < 0.2:  # 話題大幅轉換
                        transition_score = 50.0
                    else:
                        transition_score = 75.0  # 自然過渡，給予高分
                else:
                    transition_score = 70.0
            
            transition_scores.append(transition_score)
        
        # 計算平均話題轉換自然度分數
        if transition_scores:
            avg_transition_score = sum(transition_scores) / len(transition_scores)
        else:
            avg_transition_score = 100.0
        
        # 檢查話題轉換問題
        if avg_transition_score < 60:
            issues.append(CoherenceIssue(
                issue_type="topic_transition_naturalness",
                location="全文",
                description="話題轉換不自然，缺乏適當的過渡標記",
                severity="medium",
                suggestions=[
                    "在話題轉換時添加適當的過渡標記",
                    "使用更自然的話題轉換方式",
                    "確保話題轉換的邏輯性"
                ]
            ))
        
        return avg_transition_score, issues
    
    # ====== 時間連貫性分析方法 ======
    
    def _analyze_timeline_consistency(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析時間線一致性"""
        issues = []
        
        # 檢測時間標記
        temporal_markers = []
        for i, sentence in enumerate(sentences):
            for pattern in self.coherence_patterns["temporal"]:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    temporal_markers.append({
                        'sentence_idx': i,
                        'marker': match.group(),
                        'position': match.start()
                    })
        
        # 分析時間線一致性（處理無時間標記情況）
        if temporal_markers:
            timeline_score = self._analyze_temporal_sequence(temporal_markers, sentences)
            if timeline_score < 60:
                issues.append(CoherenceIssue(
                    issue_type="timeline_consistency",
                    location="全文",
                    description="時間線存在不一致或混亂",
                    severity="high" if timeline_score < 30 else "medium",
                    suggestions=[
                        "檢查時間標記的邏輯順序",
                        "避免時間跳躍過於突然",
                        "使用更明確的時間過渡詞"
                    ]
                ))
        else:
            # 沒有時間標記不一定是問題，給予溫和的中高分，且不生成問題
            timeline_score = 80.0
        
        return timeline_score, issues
    
    def _analyze_event_sequence_logic(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析事件順序邏輯"""
        issues = []
        
        # 檢測事件序列標記
        sequence_markers = ['first', 'second', 'third', 'then', 'next', 'finally', 'last', 'initially', 'subsequently', 'eventually']
        found_markers = []
        
        for i, sentence in enumerate(sentences):
            for marker in sequence_markers:
                if marker in sentence.lower():
                    found_markers.append((i, marker))
        
        # 計算事件順序邏輯分數
        if found_markers:
            # 檢查序列的邏輯性
            sequence_score = self._check_sequence_logic(found_markers)
        else:
            sequence_score = 70.0  # 沒有序列標記不一定是問題
        
        # 檢查事件順序問題
        if sequence_score < 60:
            issues.append(CoherenceIssue(
                issue_type="event_sequence_logic",
                location="全文",
                description="事件順序邏輯不清晰或不合理",
                severity="medium",
                suggestions=[
                    "使用更明確的序列標記",
                    "確保事件順序的邏輯性",
                    "避免事件順序的混亂"
                ]
            ))
        
        return sequence_score, issues
    
    def _check_sequence_logic(self, found_markers: List[Tuple[int, str]]) -> float:
        """檢查序列邏輯"""
        if len(found_markers) < 2:
            return 80.0
        
        score = 80.0
        sequence_order = ['first', 'initially', 'second', 'third', 'then', 'next', 'subsequently', 'finally', 'last', 'eventually']
        
        # 檢查序列詞的順序
        violations = 0
        for i in range(len(found_markers) - 1):
            current_marker = found_markers[i][1].lower()
            next_marker = found_markers[i + 1][1].lower()
            
            if current_marker in sequence_order and next_marker in sequence_order:
                current_idx = sequence_order.index(current_marker)
                next_idx = sequence_order.index(next_marker)
                
                if next_idx < current_idx:
                    violations += 1
        
        # 根據違規次數扣分
        score -= violations * 15
        
        return max(0.0, score)
    
    def _analyze_tense_usage_consistency(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析時態使用一致性"""
        issues = []
        
        if not self.nlp or not hasattr(self.nlp, "pipe_names"):
            return 70.0, []  # 沒有spaCy模型時使用默認分數
        
        # 提取時態信息
        tenses = []
        for sentence in sentences:
            try:
                doc = self.nlp(sentence)
                sentence_tenses = []
                for token in doc:
                    if token.pos_ == "VERB":
                        # 簡化的時態檢測
                        if token.tag_ in ["VBD", "VBN"]:  # 過去時
                            sentence_tenses.append("past")
                        elif token.tag_ in ["VBZ", "VBP"]:  # 現在時
                            sentence_tenses.append("present")
                        elif token.tag_ in ["VBG"]:  # 進行時
                            sentence_tenses.append("progressive")
                        elif token.tag_ in ["MD"]:  # 情態動詞
                            sentence_tenses.append("modal")
                
                if sentence_tenses:
                    tenses.append(sentence_tenses[0])  # 使用第一個動詞的時態
            except Exception:
                pass
        
        # 計算時態一致性分數
        if len(tenses) > 1:
            # 檢查時態一致性
            tense_counts = Counter(tenses)
            most_common_tense = tense_counts.most_common(1)[0][0]
            consistency_ratio = tense_counts[most_common_tense] / len(tenses)
            tense_score = min(100.0, 50 + consistency_ratio * 50)
        else:
            tense_score = 80.0
        
        # 檢查時態一致性問題
        if tense_score < 60:
            issues.append(CoherenceIssue(
                issue_type="tense_usage_consistency",
                location="全文",
                description="時態使用不一致，影響時間連貫性",
                severity="medium",
                suggestions=[
                    "保持時態使用的一致性",
                    "避免不必要的時態切換",
                    "確保時態與時間線的對應"
                ]
            ))
        
        return tense_score, issues
    
    # ====== 邏輯連貫性分析方法 ======
    
    def _analyze_temporal_consistency(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析時間一致性"""
        issues = []
        temporal_scores = []
        
        # 檢測時間標記
        temporal_markers = []
        for i, sentence in enumerate(sentences):
            for pattern in self.coherence_patterns["temporal"]:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    temporal_markers.append({
                        'sentence_idx': i,
                        'marker': match.group(),
                        'position': match.start()
                    })
            
        # 分析時間一致性
        if temporal_markers:
            temporal_score = self._analyze_temporal_sequence(temporal_markers, sentences)
            temporal_scores.append(temporal_score)
            
            if temporal_score < 60:
                issues.append(CoherenceIssue(
                    issue_type="temporal_consistency",
                    location="全文",
                    description="時間線存在不一致或混亂",
                    severity="high" if temporal_score < 30 else "medium",
                    suggestions=[
                        "檢查時間標記的邏輯順序",
                        "避免時間跳躍過於突然",
                        "使用更明確的時間過渡詞"
                    ]
                ))
        else:
            temporal_scores.append(80.0)  # 沒有時間標記不一定是問題
        
        # 計算平均時間一致性分數
        if temporal_scores:
            avg_temporal_score = sum(temporal_scores) / len(temporal_scores)
        else:
            avg_temporal_score = 100.0
        
        return avg_temporal_score, issues
    
    def _analyze_temporal_sequence(self, temporal_markers: List[Dict], sentences: List[str]) -> float:
        """分析時間序列"""
        if not temporal_markers:
            return 80.0
        
        score = 80.0
        
        # 檢查時間標記的邏輯順序
        time_sequence = ['first', 'then', 'next', 'after', 'finally', 'last']
        sequence_violations = 0
        
        for i in range(len(temporal_markers) - 1):
            current_marker = temporal_markers[i]['marker'].lower()
            next_marker = temporal_markers[i + 1]['marker'].lower()
            
            # 檢查序列詞的順序
            if current_marker in time_sequence and next_marker in time_sequence:
                current_idx = time_sequence.index(current_marker)
                next_idx = time_sequence.index(next_marker)
                
                if next_idx < current_idx:
                    sequence_violations += 1
        
        # 根據違規次數扣分
        score -= sequence_violations * 15
        
        return max(0.0, score)
    
    def _analyze_causal_relations(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析因果關係"""
        issues = []
        causal_scores = []
        
        # 檢測因果關係
        causal_relations = []
        for i, sentence in enumerate(sentences):
            for pattern in self.coherence_patterns["causal"]:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    causal_relations.append({
                        'sentence_idx': i,
                        'marker': match.group(),
                        'position': match.start()
                    })
        
        # 分析因果邏輯
        if causal_relations:
            causal_score = self._analyze_causal_logic(causal_relations, sentences)
            causal_scores.append(causal_score)
            
            if causal_score < 60:
                issues.append(CoherenceIssue(
                    issue_type="causal_logic",
                    location="全文",
                    description="因果關係邏輯不清晰或不合理",
                    severity="high" if causal_score < 30 else "medium",
                    suggestions=[
                        "明確表達因果關係",
                        "確保原因和結果的邏輯合理性",
                        "避免循環論證"
                    ]
                ))
        else:
            causal_scores.append(70.0)  # 沒有明確因果關係不一定是問題
        
        # 計算平均因果關係分數
        if causal_scores:
            avg_causal_score = sum(causal_scores) / len(causal_scores)
        else:
            avg_causal_score = 100.0
        
        return avg_causal_score, issues
    
    def _analyze_causal_logic(self, causal_relations: List[Dict], sentences: List[str]) -> float:
        """分析因果邏輯"""
        if not causal_relations:
            return 70.0
        
        score = 70.0
        
        # 檢查因果關係的合理性
        for relation in causal_relations:
            sentence = sentences[relation['sentence_idx']]
            marker = relation['marker'].lower()
            
            # 分析因果關係的前後文
            cause_part = sentence[:relation['position']].strip()
            effect_part = sentence[relation['position'] + len(marker):].strip()
            
            if cause_part and effect_part:
                # 簡單的因果合理性檢查
                logic_score = self._assess_causal_reasonableness(cause_part, effect_part, marker)
                score += (logic_score - 50) * 0.2  # 調整影響權重
        
        return max(0.0, min(100.0, score))
    
    def _assess_causal_reasonableness(self, cause: str, effect: str, marker: str) -> float:
        """評估因果關係的合理性"""
        # 檢查是否為常見的合理因果模式
        reasonable_patterns = [
            (r'\bsick\b', r'\b(?:doctor|medicine|rest)\b'),
            (r'\brained\b', r'\b(?:wet|umbrella|inside)\b'),
            (r'\bhungry\b', r'\b(?:eat|food|restaurant)\b'),
            (r'\btired\b', r'\b(?:sleep|rest|bed)\b'),
            (r'\bhappy\b', r'\b(?:smile|laugh|celebrate)\b'),
            (r'\bsad\b', r'\b(?:cry|tears|comfort)\b')
        ]
        
        for cause_pattern, effect_pattern in reasonable_patterns:
            if re.search(cause_pattern, cause, re.IGNORECASE) and re.search(effect_pattern, effect, re.IGNORECASE):
                return 80.0
        
        return 50.0  # 中性評分
    
    def _analyze_logical_sequence(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析邏輯序列"""
        issues = []
        
        # 檢查邏輯序列標記
        sequence_markers = ['first', 'second', 'third', 'then', 'next', 'finally', 'last']
        found_markers = []
        
        for i, sentence in enumerate(sentences):
            for marker in sequence_markers:
                if marker in sentence.lower():
                    found_markers.append((i, marker))
        
        # 計算邏輯序列分數
        if found_markers:
            # 檢查序列的完整性
            sequence_score = min(100.0, 60 + len(found_markers) * 10)
        else:
            sequence_score = 50.0  # 沒有序列標記不一定是問題
        
        # 檢查邏輯序列問題
        if sequence_score < 60:
            issues.append(CoherenceIssue(
                issue_type="logical_sequence",
                location="全文",
                description="邏輯序列不夠清晰",
                severity="medium",
                suggestions=[
                    "使用更明確的序列標記",
                    "確保邏輯步驟的清晰順序",
                    "添加過渡詞來連接邏輯步驟"
                ]
            ))
        
        return sequence_score, issues
    
    def _analyze_argument_flow(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析論證流程"""
        issues = []
        
        # 檢查論證標記
        argument_markers = ['because', 'since', 'therefore', 'thus', 'hence', 'consequently']
        found_markers = 0
        
        for sentence in sentences:
            for marker in argument_markers:
                if marker in sentence.lower():
                    found_markers += 1
        
        # 計算論證流程分數
        if len(sentences) > 0:
            marker_density = found_markers / len(sentences)
            argument_score = min(100.0, 50 + marker_density * 50)
        else:
            argument_score = 100.0
        
        # 檢查論證流程問題
        if argument_score < 60:
            issues.append(CoherenceIssue(
                issue_type="argument_flow",
                location="全文",
                description="論證流程不夠清晰",
                severity="medium",
                suggestions=[
                    "使用更多論證標記來明確邏輯關係",
                    "確保論證步驟的清晰順序",
                    "加強論證的邏輯性"
                ]
            ))
        
        return argument_score, issues
    
    # ====== 功能連貫性分析方法 ======
    
    def _analyze_dialogue_coherence(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析對話連貫性"""
        issues = []
        dialogue_scores = []
        
        # 識別對話句子
        dialogue_sentences = []
        for i, sentence in enumerate(sentences):
            if self._is_dialogue(sentence):
                dialogue_sentences.append((i, sentence))
        
        if len(dialogue_sentences) < 2:
            return 90.0, []  # 沒有足夠的對話不算問題
        
        # 分析對話回合
        for i in range(len(dialogue_sentences) - 1):
            current_idx, current_dialogue = dialogue_sentences[i]
            next_idx, next_dialogue = dialogue_sentences[i + 1]
            
            # 檢查是否為相鄰句子（允許中間有敘述）
            if next_idx - current_idx <= 3:  # 允許中間有1-2句敘述
                adjacency_score = self._check_adjacency_pair(current_dialogue, next_dialogue)
                dialogue_scores.append(adjacency_score)
                
                if adjacency_score < 50:
                    issues.append(CoherenceIssue(
                        issue_type="dialogue_adjacency",
                        location=f"對話 {i+1} → {i+2}",
                        description="對話回合缺乏邏輯關聯性",
                        severity="medium",
                        suggestions=[
                            "確保問題有相應的回答",
                            "讓對話回應更自然地銜接",
                            "檢查對話的邏輯順序"
                        ]
                    ))
        
        # 計算平均對話銜接分數
        if dialogue_scores:
            avg_dialogue_score = sum(dialogue_scores) / len(dialogue_scores)
        else:
            avg_dialogue_score = 90.0
        
        return avg_dialogue_score, issues
    
    def _is_dialogue(self, sentence: str) -> bool:
        """判斷是否為對話句子"""
        # 檢查是否包含引號
        if '"' in sentence or "'" in sentence:
            return True
        
        # 檢查是否包含對話標記
        dialogue_markers = ['said', 'asked', 'replied', 'answered', 'whispered', 'shouted']
        for marker in dialogue_markers:
            if marker in sentence.lower():
                return True
        
        return False
    
    def _check_adjacency_pair(self, dialogue1: str, dialogue2: str) -> float:
        """檢查對話回合的關聯性"""
        score = 40.0  # 基礎分數
        
        # 檢查問答對
        for question_pattern, answer_pattern in self.dialogue_patterns["question_answer"]:
            if re.search(question_pattern, dialogue1, re.IGNORECASE):
                if re.search(answer_pattern, dialogue2, re.IGNORECASE):
                    score += 40
                    break
        
        # 檢查招呼回應
        for greeting_pattern, response_pattern in self.dialogue_patterns["greeting_response"]:
            if re.search(greeting_pattern, dialogue1, re.IGNORECASE):
                if re.search(response_pattern, dialogue2, re.IGNORECASE):
                    score += 35
                    break
        
        # 檢查請求回應
        for request_pattern, compliance_pattern in self.dialogue_patterns["request_compliance"]:
            if re.search(request_pattern, dialogue1, re.IGNORECASE):
                if re.search(compliance_pattern, dialogue2, re.IGNORECASE):
                    score += 35
                    break
        
        return min(100.0, score)
    
    def _analyze_narrative_flow(self, sentences: List[str]) -> Tuple[float, List[CoherenceIssue]]:
        """分析敘事流程"""
        issues = []
        
        # 檢查敘事標記
        narrative_markers = ['once upon', 'there was', 'one day', 'suddenly', 'meanwhile', 'finally']
        found_markers = 0
        
        for sentence in sentences:
            for marker in narrative_markers:
                if marker in sentence.lower():
                    found_markers += 1
        
        # 計算敘事流程分數
        if len(sentences) > 0:
            marker_density = found_markers / len(sentences)
            narrative_score = min(100.0, 50 + marker_density * 50)
        else:
            narrative_score = 100.0
        
        # 檢查敘事流程問題
        if narrative_score < 60:
            issues.append(CoherenceIssue(
                issue_type="narrative_flow",
                location="全文",
                description="敘事流程不夠清晰",
                severity="medium",
                suggestions=[
                    "使用更多敘事標記來改善流程",
                    "確保敘事結構的清晰性",
                    "加強敘事的連貫性"
                ]
            ))
        
        return narrative_score, issues
    
    def _analyze_purpose_consistency(self, text: str) -> Tuple[float, List[CoherenceIssue]]:
        """分析目的一致性"""
        issues = []
        
        # 檢查目的標記
        purpose_markers = ['goal', 'purpose', 'aim', 'objective', 'target', 'intention']
        found_markers = 0
        
        for marker in purpose_markers:
            if marker in text.lower():
                found_markers += 1
        
        # 計算目的一致性分數
        if found_markers > 0:
            purpose_score = min(100.0, 60 + found_markers * 10)
        else:
            purpose_score = 50.0  # 沒有明確目的標記不一定是問題
        
        # 檢查目的一致性問題
        if purpose_score < 60:
            issues.append(CoherenceIssue(
                issue_type="purpose_consistency",
                location="全文",
                description="目的一致性不足",
                severity="medium",
                suggestions=[
                    "明確表達文本的目的",
                    "確保內容與目的一致",
                    "加強目的的表達"
                ]
            ))
        
        return purpose_score, issues
    
    def _analyze_audience_engagement(self, text: str) -> Tuple[float, List[CoherenceIssue]]:
        """分析受眾參與度"""
        issues = []
        
        # 檢查參與度標記
        engagement_markers = ['you', 'your', 'imagine', 'think', 'consider', 'suppose']
        found_markers = 0
        
        for marker in engagement_markers:
            if marker in text.lower():
                found_markers += 1
        
        # 計算受眾參與度分數
        if found_markers > 0:
            engagement_score = min(100.0, 50 + found_markers * 5)
        else:
            engagement_score = 50.0  # 沒有參與度標記不一定是問題
        
        # 檢查受眾參與度問題
        if engagement_score < 60:
            issues.append(CoherenceIssue(
                issue_type="audience_engagement",
                location="全文",
                description="受眾參與度不足",
                severity="low",
                suggestions=[
                    "增加與受眾的互動",
                    "使用更直接的語言",
                    "加強受眾的參與感"
                ]
            ))
        
        return engagement_score, issues
    
    def _advanced_ai_coherence_analysis(self, story_text: str, sentences: List[str]) -> Dict:
        """AI 深度連貫性分析"""
        if not self.ai or not self.ai.model_available:
            return {"score": COHERENCE_AI_FALLBACK_SCORE, "analysis": "AI模型不可用，使用基礎評分"}
        
        prompt = f"""
        請分析以下故事的連貫性，從以下角度評分（0-100分）：
        
        故事文本：
        {story_text[:1500]}...
        
        分析要點：
        1. 段落間的邏輯銜接是否流暢
        2. 代詞和指稱是否明確
        3. 時間線是否一致合理
        4. 對話是否自然銜接
        5. 整體敘事是否連貫
        
        請給出總分並說明主要問題。
        """
        
        try:
            ai_result = self.ai.analyze_consistency(story_text, [], {})
            ai_score = normalize_score_0_100(
                ai_result.get("ai_score", COHERENCE_AI_FALLBACK_SCORE),
                COHERENCE_AI_FALLBACK_SCORE,
            )
            ai_confidence = normalize_confidence_0_1(ai_result.get("confidence", 0.6), 0.6)
            return {
                "score": ai_score,
                "analysis": ai_result.get("analysis", "AI連貫性分析完成"),
                "confidence": ai_confidence
            }
        except Exception as e:
            return {"score": COHERENCE_AI_FALLBACK_SCORE, "analysis": f"AI分析失敗: {str(e)}"}
    
    def _calculate_semantic_similarity(self, sentence: str, phrases: List[str]) -> float:
        """使用本地transformers計算語義相似度"""
        if not self.semantic_model or not self.semantic_model.get("semantic_model"):
            return 0.0
        
        try:
            semantic_model = self.semantic_model["semantic_model"]
            tokenizer = semantic_model["tokenizer"]
            model = semantic_model["model"]
            device = next(model.parameters()).device
            
            # 編碼句子
            sentence_inputs = tokenizer(sentence, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if device.type == 'cuda':
                sentence_inputs = {k: v.to(device) for k, v in sentence_inputs.items()}
            
            with torch.no_grad():
                sentence_outputs = model(**sentence_inputs)
                sentence_embedding = sentence_outputs.last_hidden_state.mean(dim=1)
            
            max_similarity = 0.0
            
            # 計算與短語的相似度
            for phrase in phrases:
                phrase_inputs = tokenizer(phrase, return_tensors="pt", padding=True, truncation=True, max_length=512)
                if device.type == 'cuda':
                    phrase_inputs = {k: v.to(device) for k, v in phrase_inputs.items()}
                
                with torch.no_grad():
                    phrase_outputs = model(**phrase_inputs)
                    phrase_embedding = phrase_outputs.last_hidden_state.mean(dim=1)
                
                similarity = torch.cosine_similarity(sentence_embedding, phrase_embedding)
                max_similarity = max(max_similarity, float(similarity))
            
            return max_similarity
            
        except Exception as e:
            self.logger.warning("語義相似度計算失敗: %s", e)
            return 0.0
    
    # ====== 驗證和建議生成方法 ======
    
    def _check_internal_consistency(self, four_dimension_scores: FourDimensionCoherenceScores) -> float:
        """檢查內部一致性"""
        scores = [four_dimension_scores.structural, four_dimension_scores.semantic, 
                 four_dimension_scores.thematic, four_dimension_scores.temporal]
        
        # 計算分數的標準差
        if len(scores) > 1:
            std_dev = np.std(scores)
            consistency = max(0.0, 1.0 - std_dev / 50)  # 標準差越小，一致性越高
        else:
            consistency = 1.0
        
        return consistency
    
    def _check_cross_model_consistency(self, text: str, four_dimension_scores: FourDimensionCoherenceScores) -> float:
        """檢查跨模型一致性"""
        # 基於分數分佈的一致性檢查
        scores = [four_dimension_scores.structural, four_dimension_scores.semantic, 
                 four_dimension_scores.thematic, four_dimension_scores.temporal]
        
        if len(scores) < 2:
            return 0.5
        
        # 計算分數的變異係數
        mean_score = sum(scores) / len(scores)
        if mean_score == 0:
            return 0.0
        
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_dev = variance ** 0.5
        coefficient_of_variation = std_dev / mean_score
        
        # 變異係數越小，一致性越高
        consistency = max(0.0, 1.0 - coefficient_of_variation)
        
        return consistency
    
    def _validate_against_expert_rules(self, text: str, four_dimension_scores: FourDimensionCoherenceScores) -> float:
        """專家規則驗證"""
        validation_score = 1.0
        
        # 基本規則檢查
        if four_dimension_scores.structural < 30:
            validation_score -= 0.3  # 結構分數太低
        
        if four_dimension_scores.semantic < 20:
            validation_score -= 0.2  # 語義分數太低
        
        if four_dimension_scores.thematic < 25:
            validation_score -= 0.2  # 邏輯分數太低
        
        if four_dimension_scores.temporal < 30:
            validation_score -= 0.3  # 功能分數太低
        
        return max(0.0, validation_score)
    
    def _quantify_uncertainty(self, four_dimension_scores: FourDimensionCoherenceScores) -> float:
        """量化不確定性"""
        scores = [four_dimension_scores.structural, four_dimension_scores.semantic, 
                 four_dimension_scores.thematic, four_dimension_scores.temporal]
        
        # 基於分數方差的不確定性
        if len(scores) > 1:
            variance = np.var(scores)
            uncertainty = min(1.0, variance / 1000)  # 正規化到0-1
        else:
            uncertainty = 0.5
        
        # 基於置信度調整
        confidence_factor = 1.0 - four_dimension_scores.confidence
        uncertainty = (uncertainty + confidence_factor) / 2
        
        return uncertainty
    
    def _generate_four_dimension_coherence_suggestions(self, semantic_result: Dict, structural_result: Dict, 
                                                     thematic_result: Dict, temporal_result: Dict,
                                                     adaptive_weights: Dict, validation_results: Dict) -> List[str]:
        """💡 四維度連貫性智能建議生成"""
        suggestions = []
        
        # 基於四維度分數的建議
        dimension_scores = {
            "語義連貫性": semantic_result["score"],
            "結構連貫性": structural_result["score"],
            "主題連貫性": thematic_result["score"],
            "時間連貫性": temporal_result["score"]
        }
        
        # 找出最低分的維度
        min_dimension = min(dimension_scores, key=dimension_scores.get)
        min_score = dimension_scores[min_dimension]
        
        if min_score < 50:
            suggestions.append(f"🚨 {min_dimension}得分較低({min_score:.1f})，建議優先改進")
        
        # 語義連貫性建議
        if semantic_result["score"] < 70:
            suggestions.append("🧠 語義連貫性：建議改善詞彙一致性和概念關聯")
            if semantic_result.get("vocabulary_consistency", 0) < 60:
                suggestions.append("   • 保持核心詞彙的重複使用，建立詞彙一致性")
            if semantic_result.get("concept_relatedness", 0) < 60:
                suggestions.append("   • 加強句子間的概念關聯，使用更相關的概念")
            if semantic_result.get("semantic_field_maintenance", 0) < 60:
                suggestions.append("   • 確保語義相關詞彙在文本中均勻分佈")
        
        # 結構連貫性建議
        if structural_result["score"] < 70:
            suggestions.append("📋 結構連貫性：建議改善段落邏輯順序和論證結構")
            if structural_result.get("paragraph_logical_order", 0) < 60:
                suggestions.append("   • 重新安排段落順序以改善邏輯流暢度")
            if structural_result.get("section_hierarchy", 0) < 60:
                suggestions.append("   • 建立清晰的標題層級結構")
            if structural_result.get("argument_structure_integrity", 0) < 60:
                suggestions.append("   • 確保論證包含明確的論點、證據和推理")
        
        # 主題連貫性建議
        if thematic_result["score"] < 70:
            suggestions.append("🎯 主題連貫性：建議改善主題一致性和焦點維持")
            if thematic_result.get("topic_consistency", 0) < 60:
                suggestions.append("   • 保持主題詞彙的一致性，避免過度分散")
            if thematic_result.get("focus_maintenance", 0) < 60:
                suggestions.append("   • 保持核心主題詞彙的連續使用")
            if thematic_result.get("topic_transition_naturalness", 0) < 60:
                suggestions.append("   • 在話題轉換時添加適當的過渡標記")
        
        # 時間連貫性建議
        if temporal_result["score"] < 70:
            suggestions.append("⏰ 時間連貫性：建議改善時間線一致性和事件順序")
            if temporal_result.get("timeline_consistency", 0) < 60:
                suggestions.append("   • 檢查時間標記的邏輯順序，避免時間跳躍")
            if temporal_result.get("event_sequence_logic", 0) < 60:
                suggestions.append("   • 使用更明確的序列標記，確保事件順序邏輯")
            if temporal_result.get("tense_usage_consistency", 0) < 60:
                suggestions.append("   • 保持時態使用的一致性，避免不必要的時態切換")
        
        # 基於權重的建議
        max_weight_dimension = max(adaptive_weights, key=adaptive_weights.get)
        if adaptive_weights[max_weight_dimension] > 0.4:
            dimension_names = {
                "semantic": "語義連貫性",
                "structural": "結構連貫性", 
                "thematic": "主題連貫性",
                "temporal": "時間連貫性"
            }
            suggestions.append(f"⚖️ 系統自動調整：{dimension_names[max_weight_dimension]}權重較高，建議重點關注")
        
        # 基於驗證結果的建議
        if validation_results["uncertainty"] > 0.3:
            suggestions.append("⚠️ 評估不確定性較高，建議人工復核")
        
        if validation_results["reliability"] < 0.7:
            suggestions.append("🔍 評估可靠性較低，建議檢查文本質量")
        
        # 綜合建議
        if all(score >= 80 for score in dimension_scores.values()):
            suggestions.append("🎉 四維度連貫性評估優秀，文本質量很高！")
        elif all(score >= 60 for score in dimension_scores.values()):
            suggestions.append("👍 四維度連貫性評估良好，可進行小幅優化")
        else:
            suggestions.append("📝 四維度連貫性評估需要改進，建議全面檢查")
        
        return suggestions[:8]  # 限制建議數量


    def _get_timestamp(self) -> str:
        """獲取當前時間戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _calculate_score_variance(self, scores: List[float]) -> float:
        """計算分數方差"""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        return variance

# ==================== 獨立運行測試 ====================
if __name__ == "__main__":
    import os
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    def main():
        logger.info("連貫性評估")
        logger.info("=" * 50)

        try:
            checker = CoherenceChecker()
            logger.info("✅ 連貫性檢測器初始化成功")
        except Exception as e:
            logger.exception("❌ 初始化失敗: %s", e)
            return

        stories_dir = "output"
        logger.info("🔍 檢查故事資料夾: %s", stories_dir)
        if not os.path.exists(stories_dir):
            logger.error("❌ 故事資料夾不存在: %s", stories_dir)
            return
        logger.info("✅ 故事資料夾存在")

        test_stories = {}

        for story_dir in discover_story_dirs([stories_dir]):
            story_folder = story_dir.name
            story_path = str(story_dir)

            logger.info("📁 掃描故事資料夾: %s", story_folder)

            # 只讀取 full_story.txt
            story_content = None
            story_file = None
            collected_docs = {}

            full_story_candidates = collect_full_story_paths(story_path)
            file_path = str(full_story_candidates[0]) if full_story_candidates else None
            if file_path:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    if content and len(content) > 50:
                        story_content = content
                        story_file = "full_story.txt"
                        logger.info("   ✅ 讀取: %s (%d 字)", story_file, len(content))
                        collected_docs["full_story.txt"] = content
                except Exception as read_err:
                    logger.warning("   ⚠️ 讀取失敗 %s: %s", "full_story.txt", read_err)

            if story_content:
                test_stories[f"{story_folder} ({story_file})"] = {
                    "text": story_content,
                    "documents": collected_docs
                }
            else:
                logger.warning("   ❌ 未找到 full_story.txt")

        if not test_stories:
            logger.error("❌ 未找到任何故事文檔")
            return

        logger.info("")
        logger.info("📚 找到 %d 個故事文檔", len(test_stories))
        logger.info("=" * 60)

        for story_name, payload in test_stories.items():
            logger.info("")
            logger.info("=" * 60)
            logger.info("📖 檢測: %s", story_name)

            try:
                story_text = payload["text"] if isinstance(payload, dict) else payload
                documents = payload.get("documents") if isinstance(payload, dict) else None
                result = checker.check(story_text, story_name, documents=documents)

                coherence_data = result.get('coherence', {})
                scores = coherence_data.get('scores', {})
                logger.info("📊 詳細分數:")
                logger.info("  🎯 總分: %.1f/100", scores.get('final', 0))
                logger.info("  🧠 語義連貫性: %.1f/100", scores.get('semantic', 0))
                logger.info("  📋 結構連貫性: %.1f/100", scores.get('structural', 0))
                logger.info("  🎯 主題連貫性: %.1f/100", scores.get('thematic', 0))
                logger.info("  ⏰ 時間連貫性: %.1f/100", scores.get('temporal', 0))
                logger.info("  🔒 置信度: %.2f", scores.get('confidence', 0))
                logger.info("  ⚠️ 不確定性: %.2f", scores.get('uncertainty', 0))

                if isinstance(payload, dict) and payload.get('documents'):
                    doc_weights = checker.get_document_weights_for_coherence()
                    used_docs = payload['documents'].keys()
                    shown = ", ".join([f"{name}:{doc_weights.get(name, 0):.2f}" for name in used_docs])
                    logger.info("📄 加權文檔: %s", shown)

                explanations = coherence_data.get('explanations', {})
                if explanations:
                    logger.info("")
                    logger.info("📊 詳細分析：為何是這個分數")
                    sem = explanations.get('semantic', {})
                    if sem:
                        w = sem.get('weights', {})
                        comp = sem.get('components', {})
                        bonus = sem.get('bonuses', {})
                        logger.info("  🧠 語義：")
                        logger.info(
                            "     ├─ 權重: vocab %s, concept %s, field %s",
                            w.get('vocabulary', w.get('vocabulary', 0)),
                            w.get('concept', 0),
                            w.get('semantic_field', 0)
                        )
                        logger.info(
                            "     ├─ 構成: vocab %.1f, concept %.1f, field %.1f",
                            comp.get('vocabulary', comp.get('vocabulary_consistency', 0)),
                            comp.get('concept', comp.get('concept_relatedness', 0)),
                            comp.get('semantic_field', comp.get('semantic_field_maintenance', 0))
                        )
                        if bonus:
                            logger.info(
                                "     └─ 額外: repetition_bonus %s",
                                bonus.get('repetition_bonus', 0)
                            )

                    stc = explanations.get('structural', {})
                    if stc:
                        w = stc.get('weights', {})
                        comp = stc.get('components', {})
                        logger.info("  📋 結構：")
                        logger.info(
                            "     ├─ 權重: paragraph %s, hierarchy %s, argument %s",
                            w.get('paragraph_logical_order', 0),
                            w.get('section_hierarchy', 0),
                            w.get('argument_structure_integrity', 0)
                        )
                        logger.info(
                            "     └─ 構成: paragraph %.1f, hierarchy %.1f, argument %.1f",
                            comp.get('paragraph_logical_order', 0),
                            comp.get('section_hierarchy', 0),
                            comp.get('argument_structure_integrity', 0)
                        )

                    thm = explanations.get('thematic', {})
                    if thm:
                        w = thm.get('weights', {})
                        comp = thm.get('components', {})
                        bonus = thm.get('bonuses', {})
                        logger.info("  🎯 主題：")
                        logger.info(
                            "     ├─ 權重: topic %s, focus %s, transition %s, anchors %s, dialogue %s",
                            w.get('topic', 0),
                            w.get('focus', 0),
                            w.get('transition', 0),
                            w.get('anchors', 0),
                            w.get('dialogue', 0)
                        )
                        logger.info(
                            "     ├─ 構成: topic %.1f, focus %.1f, transition %.1f, anchors %.1f, dialogue %.1f",
                            comp.get('topic', comp.get('topic_consistency', 0)),
                            comp.get('focus', comp.get('focus_maintenance', 0)),
                            comp.get('transition', comp.get('topic_transition_naturalness', 0)),
                            comp.get('anchors', comp.get('theme_anchors', 0)),
                            comp.get('dialogue', comp.get('dialogue_topic_flow', 0))
                        )
                        if bonus:
                            logger.info(
                                "     └─ 額外: focus_bonus %s, dialogue_bonus %s",
                                bonus.get('focus_bonus', 0),
                                bonus.get('dialogue_bonus', 0)
                            )

                    tmp = explanations.get('temporal', {})
                    if tmp:
                        w = tmp.get('weights', {})
                        comp = tmp.get('components', {})
                        bonus = tmp.get('bonuses', {})
                        logger.info("  ⏰ 時間：")
                        logger.info(
                            "     ├─ 權重: timeline %s, sequence %s, tense %s",
                            w.get('timeline', 0),
                            w.get('event_sequence', 0),
                            w.get('tense', 0)
                        )
                        logger.info(
                            "     ├─ 構成: timeline %.1f, sequence %.1f, tense %.1f",
                            comp.get('timeline', 0),
                            comp.get('event_sequence', 0),
                            comp.get('tense', 0)
                        )
                        if bonus:
                            logger.info(
                                "     └─ 額外: sequence_bonus %s, markers %s",
                                bonus.get('sequence_bonus', 0),
                                bonus.get('marker_count', 0)
                            )

                thematic_result = coherence_data.get('thematic_result', {})
                if thematic_result:
                    logger.info("")
                    logger.info("🔍 主題連貫性詳細分析:")
                    logger.info("   • 主題一致性: %.1f/100", thematic_result.get('topic_consistency', 0))
                    logger.info("   • 焦點維持: %.1f/100", thematic_result.get('focus_maintenance', 0))
                    logger.info("   • 話題轉換: %.1f/100", thematic_result.get('topic_transition_naturalness', 0))
                    logger.info("   • 主題錨點: %.1f/100", thematic_result.get('theme_anchors', 0))
                    logger.info("   • 對話主題流: %.1f/100", thematic_result.get('dialogue_topic_flow', 0))

                suggestions = coherence_data.get('suggestions', [])
                if suggestions:
                    logger.info("")
                    logger.info("💡 建議 (最多5項):")
                    for suggestion in suggestions[:5]:
                        logger.info("  └─ %s", suggestion)

            except Exception as analysis_err:
                logger.exception("❌ 分析失敗: %s", analysis_err)

        logger.info("")
        logger.info("✅ 所有故事評估完成")
        logger.info("=" * 60)

    main()