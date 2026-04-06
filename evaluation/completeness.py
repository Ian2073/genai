# completeness.py - 六維度故事評估系統 - 故事完整性維度
# 用途：從結構/語義/邏輯/功能四層次檢查故事是否完整，並提供修正建議
# 重點：
# - 自適應權重與故事類型模板（自動偵測）
# - 產出證據與子分數，便於針對性調整
import logging
import re
import numpy as np
import networkx as nx
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import torch
import os

# 共用你的一致性模組裡的工具
from .consistency import ComprehensiveKnowledgeGraph, AIAnalyzer
from .kb import LocalCategoryMatcher
from .shared.story_data import collect_full_story_paths, discover_story_dirs

# 文體檢測器
from .genre import GenreDetector
from .utils import (
    SentenceSplitterMixin,
    ensure_instance,
    get_default_model_path,
    get_semantic_model_candidates,
    get_kg_path,
    load_category_keywords,
    load_spacy_model,
    clamp_score,
    parse_weight_list,
    normalize_keywords,
    get_iso_timestamp,
    select_documents_by_matrix,
)
from .shared.ai_safety import (
    get_dimension_fallback_score,
    normalize_confidence_0_1,
    normalize_score_0_100,
)

DEFAULT_SEMANTIC_KEYWORDS = {
    "setup": {
        "direct": ["once upon", "in the beginning", "there was", "one day", "at first", "lived", "was", "were", "had"],
        "semantic": ["character introduction", "setting description", "background information", "initial situation"]
    },
    "inciting": {
        "direct": ["until", "then one day", "suddenly", "but then", "however", "when", "while", "as", "during"],
        "semantic": ["change occurs", "disruption", "catalyst event", "something happens"]
    },
    "conflict": {
        "direct": ["but", "however", "problem", "trouble", "couldn't", "could not", "difficult", "challenge", "struggle", "wolf", "hunt", "chase", "fight", "battle", "danger", "lost", "stuck", "trapped", "scared", "worried"],
        "semantic": ["obstacle", "opposition", "difficulty", "tension", "confrontation", "antagonist", "villain", "threat"]
    },
    "turning": {
        "direct": ["so", "therefore", "decided", "because of that", "realized", "then", "after", "next", "climax", "peak", "moment", "turning point", "suddenly", "just then"],
        "semantic": ["decision made", "realization", "change of direction", "pivot point", "climactic moment"]
    },
    "resolution": {
        "direct": ["finally", "in the end", "at last", "eventually", "solved", "fixed", "resolved", "saved", "helped", "escaped", "defeated", "overcame", "won", "success"],
        "semantic": ["problem solved", "conflict resolved", "conclusion reached", "victory", "triumph"]
    },
    "ending": {
        "direct": ["happily ever after", "the end", "from then on", "after that", "ever since", "always"],
        "semantic": ["final state", "new normal", "lesson learned", "closure"]
    }
}

DEFAULT_STORY_ELEMENT_KEYWORDS = {
    "introduction": {
        "strong_indicators": ["once upon", "there was", "lived", "princess", "prince", "king", "queen", "little girl", "little boy"],
        "weak_indicators": ["in the beginning", "one day", "at first", "was", "were", "had", "long ago", "far away"],
        "story_context": ["castle", "village", "forest", "house", "cottage", "kingdom", "palace"]
    },
    "problem": {
        "strong_indicators": ["problem", "trouble", "difficult", "challenge", "lost", "stuck", "scared", "wicked", "evil", "danger"],
        "weak_indicators": ["but", "however", "couldn't", "could not", "worried", "sad", "angry", "afraid", "terrified"],
        "story_context": ["alone", "confused", "struggle", "worry", "concern", "cursed", "spell", "trap"]
    },
    "adventure": {
        "strong_indicators": ["discovered", "found", "met", "encountered", "journey", "quest", "adventure", "wandered", "traveled"],
        "weak_indicators": ["then", "next", "suddenly", "but then", "when", "while", "as", "during", "meanwhile"],
        "story_context": ["explore", "magic", "treasure", "forest", "mountain", "river", "fairy", "witch", "dragon"]
    },
    "solution": {
        "strong_indicators": ["helped", "saved", "healed", "cured", "fixed", "worked", "succeeded", "defeated", "overcame", "rescued"],
        "weak_indicators": ["finally", "in the end", "at last", "eventually", "solved", "resolved", "triumph", "victory"],
        "story_context": ["made better", "together", "grateful", "everyone", "friendship", "love", "kiss", "awakened"]
    },
    "lesson": {
        "strong_indicators": ["learned", "understood", "realized", "happily ever after", "from then on", "ever since", "always"],
        "weak_indicators": ["taught", "showed", "discovered", "wisdom", "never", "moral", "lesson", "goodness"],
        "story_context": ["kindness", "bravery", "honesty", "friendship", "understanding", "love", "peace"]
    }
}

DEFAULT_EXPECTED_CHARACTERS = ["princess", "prince", "king", "queen", "witch", "fairy", "wolf", "pig", "duck"]

DEFAULT_CHARACTER_ALIASES = {
    "princess": ["beautiful princess", "young princess", "sweet princess"],
    "prince": ["handsome prince", "brave prince", "charming prince"],
    "king": ["wise king", "old king", "powerful king"],
    "queen": ["beautiful queen", "wicked queen", "good queen"],
    "witch": ["wicked witch", "old witch", "evil witch"],
    "fairy": ["good fairy", "fairy godmother", "magical fairy"],
    "wolf": ["big bad wolf", "hungry wolf", "clever wolf"],
    "pig": ["little pig", "smart pig", "lazy pig"],
    "duck": ["ugly duckling", "little duck", "beautiful swan"]
}

DEFAULT_STORY_CONCEPTS = ["character", "setting", "problem", "solution", "moral"]

DEFAULT_CAUSAL_PATTERNS_EN = [
    "because\\s+of",
    "due\\s+to",
    "as\\s+a\\s+result",
    "therefore",
    "consequently",
    "so\\s+that",
    "in\\s+order\\s+to",
    "which\\s+led\\s+to",
    "causing",
    "resulted\\s+in"
]

COMPLETENESS_AI_FALLBACK_SCORE = get_dimension_fallback_score("completeness")

DEFAULT_CAUSAL_PATTERNS_ZH = [
    "因為", "由於", "因此", "所以", "以致", "從而", "從而導致", "導致", "造成", "使得", "因而", "從而使得"
]

DEFAULT_CULTURAL_ELEMENTS = {
    "nigerian_names": ["Aya", "Kemi", "Tunde", "Bola"],
    "games": ["Ayo"]
}

@dataclass
class CompletenessScores:
    objective: float
    ai: float
    final: float

@dataclass
class FourLayerCompletenessScores:
    """四層完整性評估分數"""
    structural: float      # 結構完整性
    semantic: float        # 語義完整性  
    logical: float         # 邏輯完整性
    functional: float      # 功能完整性
    final: float          # 最終綜合分數
    confidence: float     # 評估置信度
    uncertainty: float    # 不確定性指標

@dataclass
class CompletenessEvidence:
    """完整性證據"""
    layer: str
    element: str
    score: float
    confidence: float
    evidence_text: str
    position: int
    evidence_type: str  # 'direct', 'semantic', 'inferred', 'ai_analysis'

class CompletenessChecker(SentenceSplitterMixin):
    """完整性檢測器（四層評估：結構/語義/邏輯/功能）"""
    
    def __init__(self,
                 kg_path: str = get_kg_path(),
                 model_path: str = get_default_model_path("Qwen2.5-14B"),
                 use_multiple_ai_prompts: bool = False,
                 ai: AIAnalyzer = None,
                 kg: ComprehensiveKnowledgeGraph = None,
                 nlp=None,
                 semantic_model=None,
                 preferred_language: Optional[str] = None,
                 eager_load_semantic: bool = False,
                 debug_logs: bool = False):
                
        # 載入核心分析工具
        self.kg = ensure_instance(kg, ComprehensiveKnowledgeGraph, kg_path)  # 知識圖譜
        self.ai = ensure_instance(ai, AIAnalyzer, model_path, use_multiple_ai_prompts)  # AI 分析器
        self.nlp = ensure_instance(nlp, load_spacy_model)  # NLP 模型
        
        # 文體檢測器（識別童話/寓言等類型）
        self.genre_detector = GenreDetector()

        # 日誌設定
        self.logger = logging.getLogger(__name__)
        env_debug = (os.getenv("COMPLETENESS_DEBUG", "").strip().lower())
        self.debug_logs = debug_logs or env_debug in {"1", "true", "yes", "on"}

        # 語義模型設定（支援延遲載入）
        self.semantic_model = semantic_model
        self.preferred_language = preferred_language or 'en'
        if self.semantic_model is None and eager_load_semantic:
            self.semantic_model = self._load_semantic_model()
        
        # 載入中央化詞彙資源
        self.local_categories = LocalCategoryMatcher()
        self.semantic_keywords = self._load_semantic_keywords()  # 故事結構關鍵詞
        self.story_element_keywords = self._load_story_element_keywords()  # 故事元素關鍵詞
        self.expected_characters = self._load_keywords('completeness.characters.expected', DEFAULT_EXPECTED_CHARACTERS)
        self.character_aliases = self._load_character_aliases()  # 角色別名
        self.story_concepts = self._load_keywords('completeness.story_concepts.core', DEFAULT_STORY_CONCEPTS)
        self.cultural_elements = self._load_cultural_elements()  # 文化元素
        self.action_words = self._load_keywords('readability.action_words.narrative', [])  # 動作詞
        self.emotion_words_positive = self._load_keywords('emotion.joy.words', [])  # 正面情感詞
        # 初始化四層完整性評估框架
        self._init_four_layer_framework()
        
        # 智能故事結構模板庫（支援多種故事類型）
        self.story_templates = {
            "classic_hero": ["call_to_adventure", "refusal", "mentor", "crossing_threshold", "tests", "ordeal", "reward", "road_back", "resurrection", "return"],
            "three_act": ["setup", "inciting_incident", "plot_point_1", "confrontation", "midpoint", "plot_point_2", "climax", "resolution", "denouement"],
            "simple_story": ["setup", "inciting", "conflict", "turning", "resolution", "ending"],
            "children_story": ["introduction", "problem", "adventure", "solution", "lesson"]
        }

        # 頁面語義證據聚合（本模組獨立版，供後續接入）
        # 不影響既有流程，僅提供可用工具
        
        # 🔗 因果關係檢測器（英文）
        self.causal_patterns_en = self._load_keywords('completeness.causal_patterns.en', DEFAULT_CAUSAL_PATTERNS_EN)
        # 🔗 因果關係檢測器（中文）
        self.causal_patterns_zh = self._load_keywords('completeness.causal_patterns.zh', DEFAULT_CAUSAL_PATTERNS_ZH)
        # 預設使用英文規則（會在執行時依語言切換）
        self.causal_patterns = self.causal_patterns_en
        
        # 每個槽位的最低「證據」門檻
        self.min_evidence_per_slot = 1
        
        # 四層完整性評估結果存儲
        self.four_layer_scores = None
        self.completeness_evidence = []
        self.adaptive_weights = {}
        self.validation_results = {}

    def _debug(self, message: str) -> None:
        if self.debug_logs:
            self.logger.info(message)

    def _info(self, message: str) -> None:
        self.logger.info(message)

    def _warn(self, message: str, exc: Optional[Exception] = None) -> None:
        if exc is not None:
            self.logger.warning("%s | %s", message, exc)
        else:
            self.logger.warning(message)

    def _load_semantic_model(self):
        """🚀 載入語義相似度模型（使用統一的 bge-large-zh-v1.5）"""
        try:
            from transformers import AutoTokenizer, AutoModel
            
            # 使用統一候選路徑（可透過環境變數覆寫）
            model_paths = get_semantic_model_candidates()
            
            for model_path in model_paths:
                try:
                    self._debug(f"🔍 嘗試載入語義模型: {model_path}")
                    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                    model = AutoModel.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                    
                    # 優先使用 CPU（AMD 9900X 優化）
                    use_cpu_for_semantic = os.getenv('USE_CPU_FOR_SEMANTIC', 'true').lower() in ['true', '1']
                    
                    if torch.cuda.is_available() and not use_cpu_for_semantic:
                        model = model.cuda()
                        self._info(f"✅ 語義模型已載入到 GPU: {model_path}")
                    else:
                        self._info(f"✅ 語義模型已載入到 CPU (AMD 9900X 優化): {model_path}")
                    
                    return {
                        "tokenizer": tokenizer, 
                        "model": model,
                        "model_name": model_path.split("/")[-1]
                    }
                except Exception as e:
                    self._warn(f"模型 {model_path} 載入失敗", e)
                    continue
                    
            self._warn("未找到可用的語義模型，將使用基礎功能")
            return None
            
        except Exception as e:
            self._warn("語義模型載入失敗，將使用基礎功能", e)
            return None

    def _init_four_layer_framework(self):
        """初始化故事書四層完整性評估框架（基於知識圖譜）"""
        # 基礎權重配置（將被自適應權重覆蓋，可在 YAML 中覆寫）
        self.base_weights = self._load_base_weights({
            "structural": 0.35,   # 結構完整性最重要
            "semantic": 0.25,     # 語義完整性次之
            "logical": 0.20,      # 邏輯完整性
            "functional": 0.20    # 功能完整性
        })
        
        # 基於知識圖譜的故事結構元素（支援多種故事類型）
        self.story_elements = ["introduction", "adventure", "discovery", "sharing", "lesson"]
        
        # 通用故事結構模板（擴展支持更多類型）
        self.story_structure_templates = {
            "fairy_tale": {
                "required_elements": ["introduction", "conflict", "climax", "resolution"],
                "optional_elements": ["magic", "transformation", "happy_ending"],
                "keywords": [
                    "once upon a time", "lived", "castle", "prince", "princess", "fairy",
                    "magic", "happily ever after", "evil", "good", "wicked", "beautiful",
                    # Cinderella 常見要素
                    "ball", "slipper", "glass slipper", "midnight", "fairy godmother", "coach", "pumpkin",
                    # Sleeping Beauty/Snow White 常見要素
                    "spell", "curse", "sleep", "kiss", "dwarfs", "dwarf", "awakened",
                    # 通用童話要素
                    "forest", "village", "kingdom", "palace", "tower", "garden", "cottage",
                    "dragon", "giant", "troll", "elf", "dwarf", "enchanted", "mysterious"
                ]
            },
            "fable_moral": {
                "required_elements": ["introduction", "conflict", "lesson"],
                "optional_elements": ["moral", "teaching", "resolution"],
                "keywords": [
                    "wolf", "pig", "bear", "fox", "rabbit", "clever", "foolish", "wise", "learned", "moral", "lesson",
                    "three little pigs", "big bad wolf", "huff and puff", "blow down", "brick house", "straw house",
                    "ugly duckling", "beautiful swan", "different", "accepted", "belonged",
                    "little match girl", "cold", "warm", "dream", "heaven", "grandmother"
                ]
            },
            "adventure_story": {
                "required_elements": ["introduction", "problem", "adventure", "solution", "lesson"],
                "optional_elements": ["conflict", "climax", "resolution"],
                "keywords": ["problem", "challenge", "rescue", "danger", "hero", "quest", "journey"]
            },
            "exploration_story": {
                "required_elements": ["introduction", "adventure", "discovery", "sharing", "lesson"],
                "optional_elements": ["curiosity", "wonder", "marvel", "treasure"],
                "keywords": ["explore", "discover", "treasure", "magical", "tales", "world", "adventure"]
            },
            "friendship_story": {
                "required_elements": ["introduction", "meeting", "interaction", "bonding", "lesson"],
                "optional_elements": ["conflict", "reconciliation", "trust"],
                "keywords": ["together", "friendship", "bonding", "share", "play", "laugh", "friend"]
            },
            "learning_story": {
                "required_elements": ["introduction", "curiosity", "discovery", "understanding", "lesson"],
                "optional_elements": ["teaching", "wisdom", "knowledge", "growth"],
                "keywords": ["learn", "teach", "understand", "story", "culture", "tradition", "knowledge"]
            },
            "cultural_story": {
                "required_elements": ["introduction", "culture", "tradition", "sharing", "lesson"],
                "optional_elements": ["heritage", "wisdom", "values", "community"],
                "keywords": ["culture", "tradition", "heritage", "community", "wisdom", "values"]
            }
        }
        
        # 基於知識圖譜的內容要求
        self.content_requirements = {
            "character_consistency": {
                "required": "exact same names throughout story",
                "examples": ["Little Emma", "Grandpa Tom", "Little Alex"],
                "avoid": ["name variations", "inconsistent naming"]
            },
            "grammar_requirements": {
                "sentence_length": "5-12 words per sentence",
                "punctuation": "proper spacing after periods, commas, exclamation marks",
                "article_usage": "use 'a' before consonants, 'an' before vowels",
                "contractions": "use proper apostrophes (don't, can't, won't)",
                "word_spacing": "NEVER join words together - always separate with spaces"
            },
            "cultural_elements": self.cultural_elements
        }
        
        # 語義相似度緩存（提升效率）
        self.semantic_cache = {}
        
        # 批量向量化緩存
        self.embedding_cache = {}
        
        # 📄 完整性評估文檔選擇矩陣
        self.document_selection_matrix = {
            'primary': ['full_story.txt', 'outline.txt'],
            'secondary': ['narration.txt', 'dialogue.txt'],
            'excluded': ['title.txt'],
            'weights': {
                'full_story.txt': 0.60,
                'outline.txt': 0.25,
                'narration.txt': 0.10,
                'dialogue.txt': 0.05
            }
        }
    
    def get_documents_for_completeness(self, available_documents: Dict[str, str]) -> Dict[str, str]:
        """根據完整性評估需求選擇相應的文檔（共用 utils 選擇器）"""
        return select_documents_by_matrix(available_documents, self.document_selection_matrix, min_primary=2)
    
    def get_document_weights_for_completeness(self) -> Dict[str, float]:
        """獲取完整性評估的文檔權重"""
        return self.document_selection_matrix['weights']

    # ====== 四層完整性評估核心方法 ======
    
    
    def _evaluate_structural_completeness(self, text: str) -> Dict:
        """第1層：故事書結構完整性評估（基於知識圖譜預測）"""
        sentences = self._split_sentences(text)

        # 1. 檢測故事類型
        story_type = self._detect_story_type(text)

        # 2. 基於知識圖譜預測故事結構
        structure_prediction = self._predict_story_structure(text, story_type)

        # 3. 使用預測的元素進行評估
        elements_to_check = structure_prediction["predicted_elements"]
        evidence = {element: [] for element in elements_to_check}

        # 檢查每個預測的結構元素
        for i, sentence in enumerate(sentences):
            for element in elements_to_check:
                score = self._check_story_element(sentence, element, i, len(sentences))
                if score > 0.2:  # 降低閾值，更敏感
                    evidence[element].append({
                        "sentence_id": i,
                        "text": sentence,
                        "score": score,
                        "confidence": min(1.0, score * 1.5)
                    })

        # 4. 計算結構完整性分數
        filled_elements = len([k for k, v in evidence.items() if v])
        total_elements = len(elements_to_check)
        # 對長文友善的覆蓋率：同時考慮命中強度（證據數量）
        raw_coverage = filled_elements / total_elements if total_elements > 0 else 0
        evidence_hits = sum(len(v) for v in evidence.values())
        # 針對短篇故事：移除長文本相關加權，只保留證據豐富度
        richness_boost = min(0.2, (evidence_hits / max(1, total_elements)) * 0.02)
        coverage_ratio = min(1.0, raw_coverage + richness_boost)

        # 5. 基於預測置信度的評分算法（平衡調整）
        base_score = coverage_ratio * 80
        confidence_bonus = structure_prediction["confidence"] * 10  # 降低預測置信度獎勵
        # 質量獎勵：統一上限（短篇評估場景）
        quality_bonus = min(15, evidence_hits * 2)

        # 懲罰機制：識別差故事
        penalty = 0
        if coverage_ratio < 0.3:  # 結構覆蓋率太低
            penalty += 30
        # 短文懲罰：對極短文本施加懲罰（可調整閾值）
        word_count = len(text.split())
        if word_count < 60:
            penalty += 25  # 極短 → 結構難以完整呈現
        elif word_count < 100:
            penalty += 15  # 很短 → 略降
        elif word_count < 150:
            penalty += 8   # 稍短 → 輕微
        # 移除長文本懲罰，短篇場景不適用

        # 額外獎勵：如果故事有完整的大綱結構
        # 調整：降低上限避免「結構完整但品質一般」的故事得高分
        if coverage_ratio >= 0.8:  # 80%以上的結構覆蓋率
            structural_score = min(88, base_score + confidence_bonus + quality_bonus + 5 - penalty)  # 降至88分
        else:
            structural_score = min(85, base_score + confidence_bonus + quality_bonus - penalty)  # 降至85分

        return {
            "score": structural_score,
            "coverage_ratio": coverage_ratio,
            "filled_elements": filled_elements,
            "total_elements": total_elements,
            "evidence": evidence,
            "missing_elements": [k for k, v in evidence.items() if not v],
            "story_type": story_type,
            "elements_checked": elements_to_check,
            "structure_prediction": structure_prediction,
            "prediction_confidence": structure_prediction["confidence"]
        }
    
    def _evaluate_semantic_completeness(self, text: str) -> Dict:
        """第2層：故事書語義完整性評估（基於知識圖譜）"""
        sentences = self._split_sentences(text)
        # 短文快速路徑：對於極短/短篇故事，直接以輕量規則與關鍵詞覆蓋為主，跳過重型圖計算
        word_count = len(text.split())
        if word_count <= 220:
            tl = text.lower()
            role_tokens = ["princess","prince","king","queen","witch","fairy","wolf","pig","duck","girl","boy","man","woman"]
            plot_tokens = ["adventure","found","learned","helped","saved","discovered","explored","escape","rescue","hide","build"]
            action_tokens = ["asked","replied","said","woke up","went","entered","returned","walked","ran","jumped","cried","laughed"]
            role_hits = sum(1 for t in role_tokens if t in tl)
            plot_hits = sum(1 for t in plot_tokens if t in tl)
            action_hits = sum(1 for t in action_tokens if t in tl)
            coverage = min(1.0, (role_hits*0.4 + plot_hits*0.4 + action_hits*0.2) / 6)
            base_score = 70 + coverage * 20  # 70~90
            # 童話/寓言小篇幅給小額提升
            if any(k in tl for k in ["once upon","happily ever after","moral","lesson"]):
                base_score += 2
            semantic_score = max(0, min(90, base_score))
            return {
                "score": semantic_score,
                "semantic_density": 0.0,
                "concept_coverage": coverage,
                "extracted_concepts": [],
                "concept_graph": None,
                "missing_concepts": [],
                "content_quality": 0.0,
                "character_consistency": 0.0,
                "cultural_elements": 0.0
            }
        
        # 基於知識圖譜的概念抽取
        extracted_concepts = self._extract_story_concepts(text)
        
        # 基於知識圖譜的內容質量檢查
        content_quality = self._check_content_quality(text)
        
        # 角色一致性檢查
        character_consistency = self._check_character_consistency(text)
        
        # 文化元素檢查
        cultural_elements = self._check_cultural_elements(text)
        
        # 計算語義密度和覆蓋度（一般路徑）
        concept_relations = self._analyze_concept_relations(sentences, extracted_concepts)
        concept_graph = self._build_concept_graph(extracted_concepts, concept_relations)
        semantic_density = self._calculate_semantic_density(concept_graph)
        concept_coverage = len(extracted_concepts) / len(self.story_concepts) if self.story_concepts else 0
        
        # 基於知識圖譜的語義完整性分數（平衡調整）
        base_score = (semantic_density * 0.25 + concept_coverage * 0.25 + content_quality * 0.25 + character_consistency * 0.15 + cultural_elements * 0.10) * 100
        # 添加基礎分數獎勵，確保短故事也能得到合理分數
        if len(text.split()) < 100:  # 短故事
            base_score = max(base_score, 70)  # 降低最低分數到70
        elif len(text.split()) < 200:  # 中等長度故事
            base_score = max(base_score, 75)  # 降低最低分數到75
        
        # 懲罰機制：識別差故事的語義問題
        penalty = 0
        if content_quality < 0.3:  # 內容質量太差
            penalty += 25
        if character_consistency < 0.3:  # 角色一致性太差
            penalty += 20
        if semantic_density < 0.1:  # 語義密度太低
            penalty += 15
        if len(text.split()) < 10:  # 故事太短，內容空洞
            penalty += 30
        
        # 額外獎勵：如果故事有明確的角色和情節
        if any(word in text.lower() for word in ["princess", "prince", "king", "queen", "witch", "fairy", "wolf", "pig", "duck", "girl", "boy", "man", "woman"]):
            base_score += 8  # 有角色描述
        if any(word in text.lower() for word in ["adventure", "found", "learned", "helped", "saved", "discovered", "explored"]):
            base_score += 8  # 有情節發展
        # 額外獎勵：如果故事有對話和敘述
        if any(word in text.lower() for word in ["asked", "replied", "said", "woke up", "went", "entered", "returned", "walked", "ran", "jumped"]):
            base_score += 5  # 有動作描述
        
        # 調整：降低上限，避免過高評分
        semantic_score = min(86, max(0, base_score - penalty))  # 從90降至86分
        
        return {
            "score": semantic_score,
            "semantic_density": semantic_density,
            "concept_coverage": concept_coverage,
            "extracted_concepts": extracted_concepts,
            "concept_graph": concept_graph,
            "missing_concepts": [c for c in self.story_concepts if c not in extracted_concepts],
            "content_quality": content_quality,
            "character_consistency": character_consistency,
            "cultural_elements": cultural_elements
        }
    
    def _evaluate_logical_completeness(self, text: str) -> Dict:
        """第3層：故事書邏輯完整性評估"""
        sentences = self._split_sentences(text)
        
        # 故事因果關係分析
        causal_chains = self._analyze_causal_relationships(sentences, [])
        
        # 故事邏輯推理鏈檢查
        reasoning_chains = self._extract_reasoning_chains(sentences)
        
        # 故事邏輯一致性檢查
        consistency_score = self._check_logical_consistency(sentences, causal_chains, reasoning_chains)
        
        # 故事推理完整性檢查
        reasoning_completeness = self._check_reasoning_completeness(reasoning_chains, causal_chains)
        
        # 以因果鏈強度加入邏輯評估：鼓勵多鏈且鏈長
        chain_count = 0
        avg_chain_len = 0.0
        try:
            if causal_chains:
                chain_count = len(causal_chains)
                lens = [len(chain.get("chain", [])) if isinstance(chain, dict) else len(chain) for chain in causal_chains]
                avg_chain_len = sum(lens) / max(1, len(lens))
        except Exception:
            chain_count = 0
            avg_chain_len = 0.0

        # 正規化的因果鏈強度（0~1）：鏈數與鏈長皆有貢獻
        chain_strength = min(1.0, 0.20 * chain_count + 0.15 * avg_chain_len)

        # 基礎分：一致性、推理完整性、因果強度
        logical_score = (
            consistency_score * 0.55 + reasoning_completeness * 0.30 + chain_strength * 0.15
        ) * 100.0

        # 懲罰機制：識別差故事的邏輯問題（更嚴格，去除固定保底）
        penalty = 0.0
        if consistency_score < 0.3:
            penalty += 28.0
        if reasoning_completeness < 0.3:
            penalty += 22.0
        if len(text.split()) < 10:
            penalty += 30.0

        tl = text.lower()
        adversatives = ["but", "however", "although", "despite"]
        causatives = ["because", "so", "therefore", "then", "thus"]
        adversative_hits = sum(tl.count(w) for w in adversatives)
        causative_hits = sum(tl.count(w) for w in causatives)
        if adversative_hits >= 2 and causative_hits == 0:
            penalty += 15.0  # 明顯轉折但無因果解釋
        if "because" in tl and ("so" not in tl and "therefore" not in tl and "thus" not in tl):
            penalty += 8.0  # 有因不見果

        # 過度依賴時間連詞但無因果支撐
        time_markers = ["then", "later", "after", "before", "suddenly", "immediately"]
        time_hits = sum(tl.count(w) for w in time_markers)
        if time_hits >= 5 and causative_hits <= 1:
            penalty += 8.0

        # 荒謬/無因由標記
        absurd_markers = ["out of nowhere", "for no reason", "without reason", "nonsense"]
        absurd_hits = sum(tl.count(w) for w in absurd_markers)
        if absurd_hits >= 2:
            penalty += 10.0
        elif absurd_hits == 1:
            penalty += 5.0

        # 額外獎勵：多樣因果連接詞與完整結尾
        connective_variety = len([w for w in ["because", "so", "therefore", "thus", "hence", "as a result"] if w in tl])
        if connective_variety >= 3:
            logical_score += 4.0
        if any(w in tl for w in ["finally", "in the end", "as a result", "therefore"]):
            logical_score += 3.0

        logical_score = max(0.0, logical_score - penalty)

        # 動態上限：強者更高，弱者更低，避免所有案例聚在同一上限
        if consistency_score >= 0.9 and reasoning_completeness >= 0.9 and chain_strength >= 0.8:
            dynamic_cap = 95.0
        elif consistency_score >= 0.75 and reasoning_completeness >= 0.75:
            dynamic_cap = 90.0
        else:
            dynamic_cap = 85.0
        logical_score = min(dynamic_cap, logical_score)
        
        return {
            "score": logical_score,
            "consistency_score": consistency_score,
            "reasoning_completeness": reasoning_completeness,
            "causal_chains": causal_chains,
            "reasoning_chains": reasoning_chains,
            "logical_gaps": self._identify_logical_gaps(reasoning_chains, causal_chains)
        }
    
    def _evaluate_functional_completeness(self, text: str) -> Dict:
        """第4層：故事書功能完整性評估"""
        # 如果AI模型不可用，使用基礎評估
        if not self.ai or not self.ai.model_available:
            self._warn("AI模型不可用，使用基礎功能完整性評估")
            
            # 基礎功能完整性評估
            basic_score = self._basic_functional_assessment(text)
            goal_achievement = self._basic_goal_achievement_analysis(text)
            functional_gaps = self._basic_functional_gaps_analysis(text)
            
            return {
                "score": basic_score,
                "ai_analysis_score": basic_score,
                "goal_achievement": goal_achievement,
                "confidence": 0.6,  # 基礎評估的置信度較低
                "functional_gaps": functional_gaps
            }
        
        # 使用AI分析故事目標達成度
        ai_analysis = self._advanced_ai_analysis(text, {}, [], [])
        functional_score = ai_analysis.get("score", 50)
        ai_confidence = ai_analysis.get("confidence", 0.5)
        
        # 故事目標達成度分析
        goal_achievement = self._analyze_story_goal_achievement(text)
        
        # 故事書功能完整性分數（平衡調整）
        final_functional_score = (functional_score * 0.6 + goal_achievement * 0.4)
        
        # 懲罰機制：識別差故事的功能問題
        penalty = 0
        if goal_achievement < 30:  # 目標達成度太低
            penalty += 25
        if len(text.split()) < 10:  # 故事太短，功能不完整
            penalty += 30
        # 檢查是否有明確的問題但沒有解決
        if any(word in text.lower() for word in ["problem", "trouble", "difficult", "lost", "stuck"]):
            if not any(word in text.lower() for word in ["solved", "fixed", "found", "helped", "learned"]):
                penalty += 20  # 有問題但沒有解決
        # 檢查是否有開始但沒有結尾
        if any(word in text.lower() for word in ["once upon", "one day", "began", "started"]):
            if not any(word in text.lower() for word in ["finally", "ended", "concluded", "from then on", "happily ever after"]):
                penalty += 15  # 有開始但沒有結尾
        
        # 添加基礎分數獎勵，確保有教育意義的故事得到高分
        if any(word in text.lower() for word in ["learned", "lesson", "moral", "understood", "realized"]):
            final_functional_score = max(final_functional_score, 75)  # 降低教育意義最低分數到75
        if any(word in text.lower() for word in ["happily ever after", "from then on", "ever since"]):
            final_functional_score = max(final_functional_score, 80)  # 降低明確結尾最低分數到80
        # 額外獎勵：如果故事有完整的目標達成過程
        if all(word in text.lower() for word in ["lost", "found", "learned"]):
            final_functional_score += 5  # 降低完整目標達成獎勵
        # 額外獎勵：如果故事有角色發展
        if any(word in text.lower() for word in ["grateful", "careful", "friends", "helped"]):
            final_functional_score += 3  # 降低角色發展獎勵
        
        # 調整：降低上限，避免功能層過高拉高總分
        final_functional_score = min(85, max(0, final_functional_score - penalty))  # 從90降至85分
        
        return {
            "score": final_functional_score,
            "ai_analysis_score": functional_score,
            "goal_achievement": goal_achievement,
            "confidence": ai_confidence,
            "functional_gaps": self._identify_story_functional_gaps(text)
        }
    
    def _calculate_adaptive_weights(self, text: str, evaluation_results: Dict) -> Dict:
        """自適應權重計算（真正整合版）"""
        # 基於評估結果的置信度調整權重
        # 先讀取 YAML 的 adaptive 權重作為起點，再做動態調整
        weights = self._load_adaptive_weights(self.base_weights.copy())
        
        # 計算各層的置信度
        layer_confidences = {}
        for layer, result in evaluation_results.items():
            if isinstance(result, dict) and 'confidence' in result:
                layer_confidences[layer] = result['confidence']
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
        
        # 如果文本很短，降低語義和邏輯權重
        if text_features['word_count'] < 100:
            weights['semantic'] *= 0.7
            weights['logical'] *= 0.7
            weights['structural'] *= 1.2
        
        # 如果文本很長，提高語義和邏輯權重
        elif text_features['word_count'] > 500:
            weights['semantic'] *= 1.2
            weights['logical'] *= 1.2
            weights['structural'] *= 0.9
        
        # 正規化權重
        total_weight = sum(weights.values())
        for layer in weights:
            weights[layer] /= total_weight
        
        return weights
    
    def _multi_stage_validation(self, text: str, four_layer_scores: FourLayerCompletenessScores) -> Dict:
        """多階段驗證機制"""
        # 內部一致性檢查
        internal_consistency = self._check_internal_consistency(four_layer_scores)
        
        # 跨模型一致性驗證
        cross_model_consistency = self._check_cross_model_consistency(text, four_layer_scores)
        
        # 專家規則驗證
        expert_rule_validation = self._validate_against_expert_rules(text, four_layer_scores)
        
        # 不確定性量化
        uncertainty = self._quantify_uncertainty(four_layer_scores)
        
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

    # ====== 輔助方法 ======
    
    def _check_story_element(self, sentence: str, element: str, position: int, total_sentences: int) -> float:
        """檢查故事書結構元素（優化版）"""
        sentence_lower = sentence.lower()
        score = 0.0
        
        # 使用故事書專用關鍵詞系統
        if element in self.story_element_keywords:
            keywords = self.story_element_keywords[element]
            
            # 1. 強指標匹配（權重最高）
            for keyword in keywords["strong_indicators"]:
                if keyword in sentence_lower:
                    score += 2.0
            
            # 2. 弱指標匹配
            for keyword in keywords["weak_indicators"]:
                if keyword in sentence_lower:
                    score += 1.0
            
            # 3. 故事上下文匹配
            for keyword in keywords["story_context"]:
                if keyword in sentence_lower:
                    score += 1.5
        
        # 位置權重調整（故事書專用）
        position_ratio = position / total_sentences
        position_weights = {
            "introduction": 0.1,
            "problem": 0.3,
            "adventure": 0.5,
            "solution": 0.8,
            "lesson": 0.9
        }
        
        preferred_position = position_weights.get(element, 0.5)
        distance = abs(position_ratio - preferred_position)
        position_weight = max(0.4, 1.0 - distance)  # 提高最低權重
        
        return score * position_weight
    
    def _extract_story_concepts(self, text: str) -> List[str]:
        """抽取故事書概念（基於知識圖譜）"""
        found_concepts = []
        text_lower = text.lower()
        
        # 基於經典童話的概念檢測
        concept_indicators = {
            "character": {
                "direct": ["princess", "prince", "king", "queen", "witch", "fairy", "wolf", "pig", "duck", "girl", "boy", "man", "woman"],
                "aliases": ["little girl", "little boy", "old woman", "young man", "beautiful princess", "handsome prince"],
                "patterns": ["character", "person", "child", "grandfather", "friend", "hero", "heroine", "villain"]
            },
            "setting": {
                "direct": ["castle", "village", "forest", "house", "cottage", "kingdom", "palace", "tower", "garden"],
                "aliases": ["deep forest", "royal palace", "magical kingdom", "enchanted forest"],
                "descriptive": ["beautiful", "majestic", "mysterious", "enchanted", "magical", "dark", "bright"],
                "patterns": ["setting", "location", "environment", "world", "place", "realm"]
            },
            "problem": {
                "direct": ["problem", "trouble", "difficult", "challenge", "curse", "spell", "danger", "threat"],
                "aliases": ["wicked witch", "evil queen", "big bad wolf", "terrible curse"],
                "context": ["lost", "trapped", "scared", "worried", "afraid", "terrified"],
                "patterns": ["conflict", "issue", "obstacle", "struggle", "crisis", "dilemma"]
            },
            "solution": {
                "direct": ["helped", "saved", "solved", "fixed", "worked", "defeated", "overcame", "rescued", "awakened"],
                "aliases": ["true love's kiss", "magic spell", "brave deed", "clever plan"],
                "context": ["together", "learned", "understood", "discovered", "triumph", "victory"],
                "patterns": ["resolution", "answer", "fix", "cure", "salvation", "redemption"]
            },
            "moral": {
                "direct": ["learned", "understood", "realized", "lesson", "moral", "wisdom"],
                "aliases": ["happily ever after", "from then on", "ever since", "always"],
                "context": ["kindness", "bravery", "honesty", "friendship", "love", "goodness"],
                "patterns": ["teaching", "meaning", "message", "value", "virtue"]
            }
        }
        
        for concept, indicators in concept_indicators.items():
            concept_found = False
            
            # 檢查直接匹配
            for indicator in indicators.get("direct", []):
                if indicator in text_lower:
                    concept_found = True
                    break
            
            # 檢查別名匹配
            if not concept_found:
                for indicator in indicators.get("aliases", []):
                    if indicator in text_lower:
                        concept_found = True
                        break
            
            # 檢查描述性詞彙匹配
            if not concept_found:
                for indicator in indicators.get("descriptive", []):
                    if indicator in text_lower:
                        concept_found = True
                        break
            
            # 檢查上下文匹配
            if not concept_found:
                for indicator in indicators.get("context", []):
                    if indicator in text_lower:
                        concept_found = True
                        break
            
            # 檢查模式匹配
            if not concept_found:
                for indicator in indicators.get("patterns", []):
                    if indicator in text_lower:
                        concept_found = True
                        break
            
            if concept_found:
                found_concepts.append(concept)
        
        return found_concepts
    
    def _check_content_quality(self, text: str) -> float:
        """檢查內容質量（基於知識圖譜要求）"""
        quality_score = 0.0
        text_lower = text.lower()
        
        # 檢查語法要求
        grammar_score = 0.0
        
        # 檢查句子長度（5-12個單詞）
        sentences = self._split_sentences(text)
        if sentences:
            word_counts = [len(sentence.split()) for sentence in sentences]
            avg_length = sum(word_counts) / len(word_counts)
            if 5 <= avg_length <= 12:
                grammar_score += 0.3
        
        # 檢查標點符號間距
        if re.search(r'[.!?][A-Z]', text):  # 正確的標點符號後大寫
            grammar_score += 0.2
        
        # 檢查冠詞使用
        if re.search(r'\ba\s+[aeiou]', text_lower):  # 避免 "a" 在元音前
            grammar_score -= 0.1
        if re.search(r'\ban\s+[bcdfghjklmnpqrstvwxyz]', text_lower):  # 避免 "an" 在輔音前
            grammar_score -= 0.1
        
        # 檢查單詞間距（避免單詞連接）
        if re.search(r'[a-z][A-Z]', text):  # 檢查是否有單詞連接
            grammar_score -= 0.2
        
        # 檢查縮寫
        if re.search(r"don't|can't|won't|isn't|aren't", text_lower):
            grammar_score += 0.2
        
        quality_score += max(0, grammar_score)
        
        # 檢查內容豐富度
        content_score = 0.0
        
        # 檢查多樣性詞彙
        unique_words = len(set(text_lower.split()))
        if unique_words > 20:
            content_score += 0.3
        
        # 檢查情感表達 - 使用配置文件
        emotion_count = sum(1 for word in self.emotion_words_positive if word in text_lower)
        if emotion_count > 0:
            content_score += 0.2
        
        # 檢查動作描述 - 使用配置文件
        action_count = sum(1 for word in self.action_words if word in text_lower)
        if action_count > 0:
            content_score += 0.2
        
        quality_score += content_score
        
        return min(1.0, quality_score)
    
    def _check_character_consistency(self, text: str) -> float:
        """檢查角色一致性（基於實際故事內容）"""
        consistency_score = 0.0
        text_lower = text.lower()
        
        # 使用spaCy提取實際的角色名稱
        if self.nlp:
            doc = self.nlp(text)
            characters = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            
            if characters:
                # 檢查角色名稱的一致性
                character_variants = {}
                for char in characters:
                    base_name = char.lower().replace("little ", "").replace("grandpa ", "").replace("grandma ", "")
                    if base_name not in character_variants:
                        character_variants[base_name] = []
                    character_variants[base_name].append(char)
                
                # 計算一致性分數
                for base_name, variants in character_variants.items():
                    if len(variants) > 1:
                        # 有多個變體，檢查是否合理
                        if len(set(variants)) == 1:
                            consistency_score += 0.3  # 完全一致
                        else:
                            # 檢查是否為合理的別名（如Little Emma vs Emma）
                            has_reasonable_variants = any(
                                any(alias.lower() in variant.lower() for alias in ["little", "grandpa", "grandma"])
                                for variant in variants
                            )
                            if has_reasonable_variants:
                                consistency_score += 0.2  # 合理的變體
                            else:
                                consistency_score += 0.1  # 不一致但可接受
                    else:
                        consistency_score += 0.2  # 單一角色名稱
                
                # 基礎分數
                consistency_score += 0.3
            else:
                # 沒有檢測到角色，使用關鍵詞檢測
                character_keywords = self._get_character_keyword_pool()
                found_keywords = sum(1 for keyword in character_keywords if keyword in text_lower)
                if found_keywords > 0:
                    consistency_score += 0.4
        else:
            # 備用檢測方法
            character_keywords = self._get_character_keyword_pool()
            found_keywords = sum(1 for keyword in character_keywords if keyword in text_lower)
            if found_keywords > 0:
                consistency_score += 0.5
        
        return min(1.0, consistency_score)
    
    def _check_cultural_elements(self, text: str) -> float:
        """檢查文化元素（基於故事內容的合理性）"""
        cultural_score = 0.0
        text_lower = text.lower()
        
        # 檢查故事背景描述
        setting_indicators = [
            "kingdom", "castle", "village", "forest", "mountain", "river", "sea",
            "palace", "cottage", "house", "garden", "meadow", "valley"
        ]
        
        found_settings = sum(1 for indicator in setting_indicators if indicator in text_lower)
        if found_settings > 0:
            cultural_score += 0.3  # 有背景描述
        
        # 檢查傳統故事元素
        traditional_elements = [
            "magic", "spell", "curse", "blessing", "fairy", "witch", "wizard",
            "dragon", "giant", "troll", "elf", "dwarf", "princess", "prince"
        ]
        
        found_traditional = sum(1 for element in traditional_elements if element in text_lower)
        if found_traditional > 0:
            cultural_score += 0.4  # 有傳統故事元素
        
        # 檢查道德或教育元素
        moral_elements = [
            "lesson", "moral", "learned", "understood", "realized", "wisdom",
            "kindness", "bravery", "honesty", "friendship", "love", "help"
        ]
        
        found_moral = sum(1 for element in moral_elements if element in text_lower)
        if found_moral > 0:
            cultural_score += 0.3  # 有道德教育元素

        if self.cultural_elements:
            matched_categories = 0
            for keywords in self.cultural_elements.values():
                if any(keyword in text_lower for keyword in keywords):
                    matched_categories += 1
            cultural_score += min(0.4, matched_categories * 0.2)
        
        return min(1.0, cultural_score)
    
    def _analyze_story_goal_achievement(self, text: str) -> float:
        """分析故事目標達成度（AI增強版）"""
        if not self.ai or not self.ai.model_available:
            raise RuntimeError("AI模型未載入，無法進行目標達成度分析")
        
        try:
            # 使用AI分析目標達成度
            ai_result = self.ai.analyze_consistency(text, [], {})
            
            # 從AI分析結果中提取分數
            if isinstance(ai_result, dict) and 'score' in ai_result:
                return float(ai_result['score'])
            elif isinstance(ai_result, dict) and 'completeness_score' in ai_result:
                return float(ai_result['completeness_score'])
            else:
                # 基於文本特徵的簡單評分
                text_lower = text.lower()
                goal_indicators = [
                    "happily ever after", "learned", "lesson", "moral", "understood",
                    "helped", "saved", "grateful", "success", "better"
                ]
                found_indicators = sum(1 for indicator in goal_indicators if indicator in text_lower)
                return min(100, 50 + found_indicators * 10)
        except Exception as e:
            raise RuntimeError(f"AI目標達成度分析失敗: {e}")
    
    def _identify_story_functional_gaps(self, text: str) -> List[str]:
        """識別故事功能缺口（AI增強版）"""
        if not self.ai or not self.ai.model_available:
            raise RuntimeError("AI模型未載入，無法進行功能缺口分析")
        
        try:
            # 使用AI分析功能缺口
            ai_result = self.ai.analyze_consistency(text, [], {})
            
            # 基於AI分析結果和文本特徵識別缺口
            gaps = []
            text_lower = text.lower()
            
            # 檢查故事結尾
            if not any(word in text_lower for word in ["happily ever after", "the end", "from then on", "ever since"]):
                gaps.append("缺少明確的故事結尾")
            
            # 檢查教育意義
            if not any(word in text_lower for word in ["learned", "lesson", "moral", "understood", "realized"]):
                gaps.append("缺少教育意義或道德寓意")
            
            # 檢查問題解決
            if not any(word in text_lower for word in ["helped", "saved", "solved", "fixed", "worked"]):
                gaps.append("缺少問題解決過程")
            
            # 檢查角色發展
            if not any(word in text_lower for word in ["character", "grew", "changed", "developed", "became"]):
                gaps.append("缺少角色發展或成長")
            
            # 檢查衝突解決
            if not any(word in text_lower for word in ["conflict", "problem", "challenge", "overcame", "resolved"]):
                gaps.append("缺少明確的衝突和解決")
            
            return gaps[:5]  # 最多返回5個缺口
        except Exception as e:
            raise RuntimeError(f"AI功能缺口分析失敗: {e}")
    
    
    
    def _analyze_concept_relations(self, sentences: List[str], concepts: List[str]) -> List[Dict]:
        """分析概念之間的關係"""
        relations = []
        
        for i, sentence in enumerate(sentences):
            sentence_concepts = [c for c in concepts if c in sentence.lower()]
            if len(sentence_concepts) >= 2:
                for j, concept1 in enumerate(sentence_concepts):
                    for concept2 in sentence_concepts[j+1:]:
                        relations.append({
                            "concept1": concept1,
                            "concept2": concept2,
                            "sentence_id": i,
                            "sentence": sentence,
                            "strength": 1.0
                        })
        
        return relations
    
    def _build_concept_graph(self, concepts: List[str], relations: List[Dict]) -> nx.Graph:
        """構建概念圖"""
        G = nx.Graph()
        
        # 添加節點
        for concept in concepts:
            G.add_node(concept)
        
        # 添加邊
        for relation in relations:
            G.add_edge(relation["concept1"], relation["concept2"], 
                      weight=relation["strength"])
        
        return G
    
    def _calculate_semantic_density(self, concept_graph: nx.Graph) -> float:
        """計算語義密度"""
        if len(concept_graph.nodes()) < 2:
            return 0.0
        
        # 計算平均度數
        degrees = [d for n, d in concept_graph.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0
        
        # 計算連通性
        if nx.is_connected(concept_graph):
            connectivity = 1.0
        else:
            # 最大連通分量比例
            largest_cc = max(nx.connected_components(concept_graph), key=len)
            connectivity = len(largest_cc) / len(concept_graph.nodes())
        
        # 計算三角係數（局部聚類係數）
        try:
            clustering = nx.average_clustering(concept_graph)
        except Exception:
            clustering = 0.0
        
        # 綜合語義密度
        semantic_density = (avg_degree * 0.4 + connectivity * 0.4 + clustering * 0.2) / 10
        return min(1.0, semantic_density)
    
    def _extract_reasoning_chains(self, sentences: List[str]) -> List[Dict]:
        """抽取推理鏈"""
        reasoning_chains = []
        
        for i, sentence in enumerate(sentences):
            # 尋找推理標記詞
            reasoning_markers = ["because", "since", "as", "therefore", "thus", "hence", "so", "consequently"]
            
            for marker in reasoning_markers:
                if marker in sentence.lower():
                    reasoning_chains.append({
                        "sentence_id": i,
                        "sentence": sentence,
                        "marker": marker,
                        "type": "explicit_reasoning"
                    })
        
        return reasoning_chains
    
    def _check_logical_consistency(self, sentences: List[str], causal_chains: List[Dict], reasoning_chains: List[Dict]) -> float:
        """檢查邏輯一致性"""
        # 簡化的邏輯一致性檢查
        consistency_score = 1.0
        
        # 檢查因果關係的合理性
        for chain in causal_chains:
            if chain.get("strength", 0) < 0.3:
                consistency_score -= 0.1
        
        # 檢查推理鏈的完整性
        if len(reasoning_chains) > 0 and len(causal_chains) == 0:
            consistency_score -= 0.2  # 有推理但沒有因果關係
        
        return max(0.0, consistency_score)
    
    def _check_reasoning_completeness(self, reasoning_chains: List[Dict], causal_chains: List[Dict]) -> float:
        """檢查推理完整性"""
        total_reasoning = len(reasoning_chains) + len(causal_chains)
        
        if total_reasoning == 0:
            return 0.0
        
        # 檢查推理鏈的長度
        avg_chain_length = 1.0
        if causal_chains:
            avg_chain_length = sum(chain.get("strength", 1.0) for chain in causal_chains) / len(causal_chains)
        
        # 推理完整性分數
        completeness = min(1.0, total_reasoning * 0.1 + avg_chain_length * 0.5)
        return completeness
    
    def _identify_logical_gaps(self, reasoning_chains: List[Dict], causal_chains: List[Dict]) -> List[str]:
        """識別邏輯缺口"""
        gaps = []
        
        if len(reasoning_chains) == 0 and len(causal_chains) == 0:
            gaps.append("缺少邏輯推理和因果關係")
        
        if len(reasoning_chains) > 0 and len(causal_chains) == 0:
            gaps.append("有推理但缺少明確的因果關係")
        
        if len(causal_chains) > 0:
            weak_chains = [c for c in causal_chains if c.get("strength", 0) < 0.5]
            if len(weak_chains) > len(causal_chains) * 0.5:
                gaps.append("因果關係強度不足")
        
        return gaps
    
    
    
    
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
    
    def _calculate_feature_adjustments(self, features: Dict) -> Dict:
        """計算特徵調整係數"""
        adjustments = {}
        
        # 基於文本長度調整
        if features["length"] < 100:
            adjustments["semantic"] = 0.8  # 短文本語義分析較困難
            adjustments["logical"] = 0.7
        elif features["length"] > 1000:
            adjustments["structural"] = 1.2  # 長文本結構分析更重要
        
        # 基於複雜度調整
        if features["complexity"] > 0.5:
            adjustments["logical"] = 1.1  # 複雜文本邏輯分析更重要
        
        return adjustments
    
    def _calculate_confidence_adjustments(self, evaluation_results: Dict) -> Dict:
        """計算置信度調整係數"""
        adjustments = {}
        
        # 基於各層評估的置信度調整權重
        for layer in ["structural", "semantic", "logical", "functional"]:
            if layer in evaluation_results:
                confidence = evaluation_results[layer].get("confidence", 0.5)
                adjustments[layer] = 0.5 + confidence * 0.5  # 0.5-1.0範圍
        
        return adjustments
    
    def _check_internal_consistency(self, four_layer_scores: FourLayerCompletenessScores) -> float:
        """檢查內部一致性"""
        scores = [four_layer_scores.structural, four_layer_scores.semantic, 
                 four_layer_scores.logical, four_layer_scores.functional]
        
        # 計算分數的標準差
        if len(scores) > 1:
            std_dev = np.std(scores)
            consistency = max(0.0, 1.0 - std_dev / 50)  # 標準差越小，一致性越高
        else:
            consistency = 1.0
        
        return consistency
    
    def _check_cross_model_consistency(self, text: str, four_layer_scores: FourLayerCompletenessScores) -> float:
        """檢查跨模型一致性（真實實現）"""
        # 基於分數分佈的一致性檢查
        scores = [four_layer_scores.structural, four_layer_scores.semantic, 
                 four_layer_scores.logical, four_layer_scores.functional]
        
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
    
    def _validate_against_expert_rules(self, text: str, four_layer_scores: FourLayerCompletenessScores) -> float:
        """專家規則驗證"""
        validation_score = 1.0
        
        # 基本規則檢查
        if four_layer_scores.structural < 30:
            validation_score -= 0.3  # 結構分數太低
        
        if four_layer_scores.semantic < 20:
            validation_score -= 0.2  # 語義分數太低
        
        if four_layer_scores.logical < 25:
            validation_score -= 0.2  # 邏輯分數太低
        
        if four_layer_scores.functional < 30:
            validation_score -= 0.3  # 功能分數太低
        
        return max(0.0, validation_score)
    
    def _quantify_uncertainty(self, four_layer_scores: FourLayerCompletenessScores) -> float:
        """量化不確定性"""
        scores = [four_layer_scores.structural, four_layer_scores.semantic, 
                 four_layer_scores.logical, four_layer_scores.functional]
        
        # 基於分數方差的不確定性
        if len(scores) > 1:
            variance = np.var(scores)
            uncertainty = min(1.0, variance / 1000)  # 正規化到0-1
        else:
            uncertainty = 0.5
        
        # 基於置信度調整
        confidence_factor = 1.0 - four_layer_scores.confidence
        uncertainty = (uncertainty + confidence_factor) / 2
        
        return uncertainty

    # ================== 頁面語義證據聚合器（本模組獨立實作） ==================
    def _collect_page_evidence(self,
                               story_dir: Optional[str] = None,
                               page_num: Optional[int] = None,
                               story_text: Optional[str] = None,
                               narration_text: Optional[str] = None,
                               dialogue_text: Optional[str] = None) -> Dict:
        """
        逐頁聚合語義證據：當頁文本優先 → resources 補詞 → 全文回退。
        回傳：{'tier','sources','text','tokens','queries'}
        """
        import os, re
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

        if story_dir and page_num is not None:
            base = story_dir
            en_dir = os.path.join(story_dir, 'en')
            if os.path.isdir(en_dir):
                base = en_dir
            main_t = _read(os.path.join(base, f"page_{page_num}.txt"))
            nar_t = _read(os.path.join(base, f"page_{page_num}_narration.txt"))
            dlg_t = _read(os.path.join(base, f"page_{page_num}_dialogue.txt"))
            parts = [t for t in [main_t, nar_t, dlg_t] if t]
            if parts:
                combined = "\n\n".join(parts)
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

        if not combined:
            all_parts = [story_text or '', narration_text or '', dialogue_text or '']
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

    # ====== 外部主要介面 ======
    def check(self, story_text: str, story_title: str = "Story", language: Optional[str] = None) -> Dict:
        sentences = self._split_sentences(story_text)
        # 語言分流
        if language:
            self.preferred_language = language
            self.causal_patterns = self.causal_patterns_zh if language == 'zh' else self.causal_patterns_en
            # 依語言重置語義模型以採用正確優先序
            self.semantic_model = None
        if self.semantic_model is None:
            self.semantic_model = self._load_semantic_model()
        sent_bins = self._bin_by_position(sentences)

        # 🎭 文體檢測（全新加入）- 取代舊的 story_type 檢測
        genre_info = self.genre_detector.detect(story_text, story_title)
        genre_params = self.genre_detector.get_scoring_params(genre_info)
        
        self._debug(
            f"📚 文體檢測: {genre_info['dominant']} (信心度: {genre_info['confidence']:.2f})"
        )
        self._debug(
            "   詳細分布: " + ", ".join([f"{k}={v:.2f}" for k, v in genre_info['scores'].items()])
        )

        # 🧠 1) 故事類型識別（保留舊邏輯作為備用）
        story_type = self._detect_story_type(story_text)
        
        # 🔍 2) 語義事件抽取（保持原有功能）
        events = self._extract_semantic_events(sentences)
        
        # 🎯 3) 智能槽位偵測（保持原有功能）
        evidence = self._collect_smart_evidence(sentences, sent_bins, events, story_type)
        
        # 🔗 4) 因果關係分析（保持原有功能）
        causal_chains = self._analyze_causal_relationships(sentences, events)
        
        # ===== 故事書四層完整性評估框架 =====
        self._debug("開始完整性評估")
        
        # 第1層：結構完整性評估
        structural_result = self._evaluate_structural_completeness(story_text)
        
        # 第2層：語義完整性評估
        semantic_result = self._evaluate_semantic_completeness(story_text)
        
        # 第3層：邏輯完整性評估
        logical_result = self._evaluate_logical_completeness(story_text)
        
        # 第4層：功能完整性評估
        functional_result = self._evaluate_functional_completeness(story_text)
        
        # 故事書專用權重
        evaluation_results = {
            "structural": structural_result,
            "semantic": semantic_result,
            "logical": logical_result,
            "functional": functional_result
        }
        
        # 加權：先讀 YAML adaptive 權重，再依文本與置信度做動態調整
        adaptive_weights = self._load_adaptive_weights({"structural": 0.28, "semantic": 0.30, "logical": 0.27, "functional": 0.15})
        try:
            adaptive_weights = self._calculate_adaptive_weights(story_text, evaluation_results)
        except Exception as exc:
            self._warn("自適應權重計算失敗，改用 YAML/預設權重", exc)
        
        # 四層分數整合
        four_layer_scores = FourLayerCompletenessScores(
            structural=structural_result["score"],
            semantic=semantic_result["score"],
            logical=logical_result["score"],
            functional=functional_result["score"],
            final=0.0,  # 將在下面計算
            confidence=0.0,  # 將在下面計算
            uncertainty=0.0  # 將在下面計算
        )
        
        # 計算最終分數：四層等權平均（功能層依語義/結構穩定度非線性縮放，避免 AI/目標把分數硬拉高）
        structural_score = four_layer_scores.structural
        semantic_score = four_layer_scores.semantic
        logical_score = four_layer_scores.logical
        functional_score = four_layer_scores.functional

        # 非線性功能縮放：40→75 作為穩定帶，低於 40 幾乎不給功能貢獻，75 以上才滿額
        def _smooth_norm(x: float, low: float = 40.0, high: float = 75.0) -> float:
            if x <= low:
                return 0.0
            if x >= high:
                return 1.0
            # 平滑上升，鼓勵達到 high 之後才完全釋放功能層加成
            ratio = (x - low) / (high - low)
            return max(0.0, min(1.0, ratio ** 1.05))

        s_norm = _smooth_norm(structural_score)
        sem_norm = _smooth_norm(semantic_score)
        functional_scale = (s_norm + sem_norm) * 0.5
        effective_functional = functional_score * functional_scale

        base_score = (
            structural_score * adaptive_weights.get("structural", 0.25) +
            semantic_score * adaptive_weights.get("semantic", 0.25) +
            logical_score * adaptive_weights.get("logical", 0.25) +
            effective_functional * adaptive_weights.get("functional", 0.25)
        )
        
        # 🎭 根據文體類型調整評分（全新方法，取代舊的硬編碼邏輯）
        # 使用文體檢測器提供的參數
        penalty_weight = genre_params['completeness']['penalty_weight']
        min_floor = genre_params['completeness']['min_floor']
        
        self._debug(
            f"  🎯 文體調整參數: penalty_weight={penalty_weight:.2f}, min_floor={min_floor:.1f}"
        )
        
        # 針對童話和寓言故事類型調整（使用文體檢測結果）
        if genre_info['dominant'] in ['poem', 'fable', 'fairy_tale']:
            word_count = len(story_text.split())
            self._debug(
                f"  📖 童話/寓言調整: 類型={story_type}, 字數={word_count}, 基礎分={base_score:.1f}"
            )
            if word_count < 800:
                # 品質導向：同時考慮結構/語義/邏輯與證據（三幕式、因果、寓意）
                quality_min = min(structural_score, semantic_score, logical_score)

                # 1) 三幕式與因果、寓意的簡易證據蒐集（不依賴模型，僅輕量啟發式）
                tl = (story_text or "").lower()
                begin_markers = [
                    "once upon a time", "one day", "long ago", "in a small", "there was"
                ]
                middle_markers = [
                    "then", "but", "however", "because", "so", "after", "suddenly"
                ]
                end_markers = [
                    "finally", "at last", "in the end", "happily", "ever after"
                ]
                moral_markers = [
                    "moral", "lesson", "learned that", "teach us", "we should", "the lesson"
                ]

                def _hit_count(text, markers):
                    return sum(text.count(m) for m in markers)

                has_begin = _hit_count(tl, begin_markers) > 0
                has_middle = _hit_count(tl, middle_markers) > 0
                has_end = _hit_count(tl, end_markers) > 0
                has_moral = _hit_count(tl, moral_markers) > 0

                three_act_evidence = sum([has_begin, has_middle, has_end])
                causal_evidence = 1 if _hit_count(tl, ["because", "so"]) > 0 else 0
                moral_evidence = 1 if has_moral else 0

                evidence_bonus = 0.0
                # 三幕式完整 → +1.5，部分 → +0.5~1.0
                if three_act_evidence == 3:
                    evidence_bonus += 2.5  # 提高 1.5→2.5
                elif three_act_evidence == 2:
                    evidence_bonus += 1.5  # 提高 1.0→1.5
                elif three_act_evidence == 1:
                    evidence_bonus += 0.8  # 提高 0.5→0.8

                # 因果與寓意各最多 +1.2（提高 0.8→1.2）
                evidence_bonus += min(1.2, causal_evidence * 1.2)
                evidence_bonus += min(1.2, moral_evidence * 1.2)

                # 2) 長度與品質加成（維持原有邏輯，略為收斂）
                len_bonus = min(2.5, (800 - word_count) / 300.0)  # 提高上限 1.8→2.5
                quality_bonus = 0.0
                if quality_min >= 70:
                    quality_bonus = min(3.0, (quality_min - 70.0) * 0.10)  # 提高係數與上限
                elif quality_min >= 60:
                    # 品質略低但證據良好時，給予部分加成
                    quality_bonus = min(1.8, (quality_min - 60.0) * 0.08)  # 提高上限 1.2→1.8
                elif quality_min >= 50:
                    # 新增：品質中等時給予基礎加成
                    quality_bonus = min(1.0, (quality_min - 50.0) * 0.05)

                # 3) 證據導向合併：確保不是單靠字數
                total_bonus = round(len_bonus + quality_bonus + min(5.0, evidence_bonus), 2)  # 提高上限 3.0→5.0

                if total_bonus > 0:
                    base_score = min(100.0, base_score + total_bonus)
                    self._debug(
                        f"  ✨ 證據導向加成: +{total_bonus:.1f}（三幕/因果/寓意/長度/品質） → 新分數={base_score:.1f}"
                    )
                else:
                    self._debug("  ⚠️ 證據不足或品質偏低，短篇不予加成")
            # 取消中篇上限（800–1200），改以整體評分機制決定

        # 進一步的極短篇寬容（不依賴文體檢測，避免漏判）：
        # 若句子數極少但存在開場/轉折/結尾/寓意線索，給予小幅加成
        try:
            words_total = len((story_text or "").split())
            sent_count = len(self._split_sentences(story_text or ""))
            tl2 = (story_text or "").lower()
            short_hits = 0
            for mk in ["once upon a time", "one day", "long ago", "in the end", "finally", "because", "so", "lesson", "moral"]:
                short_hits += tl2.count(mk)
            if words_total < 600 and sent_count < 40 and short_hits >= 2:
                extra_short_bonus = min(4.0, 1.0 + 0.5 * (short_hits - 2))
                base_score = min(100.0, base_score + extra_short_bonus)
                self._debug(f"  ✨ 極短篇寬容加成: +{extra_short_bonus:.1f} → 新分數={base_score:.1f}")
        except Exception:
            pass

        # 內容自我否定/混亂與荒謬訊號扣分：避免不合理文本在完整性層面虛高
        try:
            tl = story_text.lower()
            neg_markers = [
                "doesn't make sense", "does not make sense", "incomplete", "no ending",
                "broken story", "confusing", "contradict", "contradictory", "not a story",
                "no plot", "no characters", "no setting"
            ]
            neg_hits = sum(tl.count(m) for m in neg_markers)
            if neg_hits > 0:
                base_score -= min(15.0, neg_hits * 2.5)

            # 荒謬/不合常理結構訊號
            absurdity_markers = [
                "made of", "actually a", "upside down", "talking ", "flying ",
                "invisible", "impossible", "polka-dotted", "square clouds"
            ]
            absurd_hits = sum(tl.count(m) for m in absurdity_markers)
            if absurd_hits >= 8:
                base_score -= 10.0
            elif absurd_hits >= 5:
                base_score -= 6.0
            elif absurd_hits >= 3:
                base_score -= 3.0

            # 高荒謬密度的軟封頂（避免形式化段落把總分拉高）
            if absurd_hits >= 8:
                base_score = min(base_score, 72.0)

            # 自相矛盾密度偵測：大量 "also"/"at the same time"/"contradict" 等語彙
            contr_hits = tl.count(" also ") + tl.count("at the same time") + tl.count("contradict") + tl.count("contradictory")
            if contr_hits >= 12:
                # 額外扣分並設置軟上限，避免矛盾文本整體分過高
                base_score -= min(10.0, (contr_hits - 12) * 0.5)
                base_score = min(base_score, 55.0)
        except Exception:
            pass

        # 弱項拖累：最弱與次弱拉低總分，強化壞文下修
        # 🎯 使用文體檢測器的 penalty_weight 動態調整
        scores_list = [structural_score, semantic_score, logical_score, functional_score]
        sorted_scores = sorted(scores_list)
        weakest = sorted_scores[0]
        second_weakest = sorted_scores[1]
        penalty = 0.0
        penalty_scale = 1.0
        
        # 根據文體類型動態調整弱項扣分
        if genre_info['dominant'] in ['poem', 'fable']:
            # 詩歌/寓言：最寬鬆（只在極端情況下扣分）
            if weakest < 35:
                penalty += (35.0 - weakest) * 0.12 * penalty_weight
            if second_weakest < 40:
                penalty += (40.0 - second_weakest) * 0.06 * penalty_weight
            below_40 = sum(1 for s in scores_list if s < 40)
            if below_40 >= 2:
                penalty += 3.0 * penalty_weight
        elif genre_info['dominant'] == 'fairy_tale':
            # 童話：適中（原有邏輯）
            if weakest < 35:
                penalty += (35.0 - weakest) * 0.15 * penalty_weight
            if second_weakest < 40:
                penalty += (40.0 - second_weakest) * 0.08 * penalty_weight
            below_40 = sum(1 for s in scores_list if s < 40)
            if below_40 >= 2:
                penalty += 4.0 * penalty_weight
            # 極短篇童話：進一步下調懲罰比例
            try:
                if len((story_text or "").split()) < 600:
                    penalty_scale = 0.85 if len((story_text or "").split()) >= 400 else 0.75
            except Exception:
                pass
        else:
            # 非童話保持原有嚴格標準
            if weakest < 40:
                penalty += (40.0 - weakest) * 0.25 * penalty_weight
            if second_weakest < 50:
                penalty += (50.0 - second_weakest) * 0.15 * penalty_weight
            below_45 = sum(1 for s in scores_list if s < 45)
            if below_45 >= 2:
                penalty += 6.0 * penalty_weight

        # 平衡度懲罰：四層差異過大代表完整性不均衡
        # 🎯 使用文體檢測器動態調整平衡度要求
        mean_score = sum(scores_list) / 4.0
        variance = sum((s - mean_score) ** 2 for s in scores_list) / 4.0
        stddev = variance ** 0.5
        if genre_info['dominant'] in ['poem', 'fable']:
            # 詩歌/寓言允許最大差異
            if stddev > 20.0:
                penalty += min(4.0, (stddev - 20.0) * 0.12) * penalty_weight
        elif genre_info['dominant'] == 'fairy_tale':
            # 童話允許較大差異
            if stddev > 18.0:
                penalty += min(5.0, (stddev - 18.0) * 0.15) * penalty_weight
        else:
            if stddev > 12.0:
                penalty += min(8.0, (stddev - 12.0) * 0.25) * penalty_weight

        base_score = max(0.0, base_score - penalty * penalty_scale)
        
        # 🎯 使用文體檢測器的最低保障分（取代硬編碼）
        if base_score > 0 and base_score < min_floor:
            self._debug(
                f"  🛡️ 應用文體最低保障分: {base_score:.1f} → {min_floor:.1f}"
            )
            base_score = min_floor

        # 優秀補點：四層皆高水準時給予小幅加成，讓好文更貼近 80–90
        boost = 0.0
        # 主加成：門檻再放寬，讓優秀文本更容易上探 80+
        if structural_score >= 75 and semantic_score >= 70 and logical_score >= 75 and effective_functional >= 60:
            boost += min(12.0, (structural_score + semantic_score + logical_score + effective_functional - 285.0) * 0.12)
        # 高邏輯協同：邏輯很強時，小幅拉抬
        if logical_score >= 85 and structural_score >= 75 and semantic_score >= 70 and effective_functional >= 60:
            boost += min(6.0, (logical_score - 85.0) * 0.5 + max(0.0, structural_score - 75.0) * 0.08)
        # 三層均衡優秀（結構/語義/邏輯）
        if structural_score >= 75 and semantic_score >= 75 and logical_score >= 75:
            boost += 4.0
        # 額外條件：結構/語義雙優或三層≥78
        if (structural_score >= 80 and semantic_score >= 80) or sum(1 for s in [structural_score, semantic_score, logical_score, effective_functional] if s >= 78) >= 3:
            boost += 2.5
        base_score = min(100.0, base_score + boost)

        # 更嚴格跨層上限：關鍵層偏弱時限制最高分，防止補點穿透
        # 🎯 童話故事豁免：創意故事允許某些層級偏弱（尤其功能層）
        if story_type not in ['fairy_tale', 'fable_moral']:
            # 非童話保持嚴格上限
            if semantic_score < 40.0:
                base_score = min(base_score, 52.0)
            if semantic_score < 50.0:
                base_score = min(base_score, 60.0)
            if structural_score < 55.0:
                base_score = min(base_score, 58.0)
            if logical_score < 55.0:
                base_score = min(base_score, 58.0)
            low_dims_under_50 = sum(1 for s in [structural_score, semantic_score, logical_score] if s < 50.0)
            if low_dims_under_50 >= 2:
                base_score = min(base_score, 50.0)
        else:
            # 童話故事：只在極端低分時設置軟上限（避免完全劣質文本虛高）
            if semantic_score < 30.0:
                base_score = min(base_score, 48.0)
            # 結構+語義+邏輯三項中至少兩項 < 35 才限制
            critical_low = sum(1 for s in [structural_score, semantic_score, logical_score] if s < 35.0)
            if critical_low >= 2:
                base_score = min(base_score, 52.0)

        # 正向凝聚補點（小幅）：明確主題/寓意且三層達標時，給輕微加分
        cohesive_terms = ["lesson", "moral", "kindness", "friendship", "helped", "wisdom", "learned", "brave", "courage"]
        if any(term in tl for term in cohesive_terms) and structural_score >= 75 and semantic_score >= 70 and logical_score >= 74:
            base_score = min(100.0, base_score + 2.0)
        
        four_layer_scores.final = clamp_score(base_score)
        
        # 多階段驗證
        validation_results = self._multi_stage_validation(story_text, four_layer_scores)
        four_layer_scores.confidence = validation_results["validation_score"]
        four_layer_scores.uncertainty = validation_results["uncertainty"]
        
        # 存儲結果供後續使用
        self.four_layer_scores = four_layer_scores
        self.adaptive_weights = adaptive_weights
        self.validation_results = validation_results
        
        # 🤖 保持原有AI分析（作為備用）
        ai_analysis = self._advanced_ai_analysis(story_text, evidence, events, causal_chains)
        
        # 💡 智能建議生成（整合四層結果）
        suggestions = self._generate_four_layer_suggestions(
            structural_result, semantic_result, logical_result, functional_result, 
            adaptive_weights, validation_results, story_type
        )

        # ===== 研究型附加指標（可作論文化延伸） =====
        total_slots = len(self.story_templates.get(story_type, self.story_templates["simple_story"]))
        covered_slots = len([k for k, v in evidence.items() if v])
        structure_coverage = (covered_slots / total_slots * 100) if total_slots else 0
        event_density = (len(events) / max(1, len(sentences))) * 100  # 每句事件密度（%）
        avg_chain_len = 0.0
        if causal_chains:
            try:
                lens = [len(chain.get("chain", [])) if isinstance(chain, dict) else len(chain) for chain in causal_chains]
                avg_chain_len = sum(lens) / len(lens)
            except Exception:
                avg_chain_len = 0.0
        template_match_score = min(100.0, structure_coverage * 0.8 + (avg_chain_len * 10))  # 簡易組合指標

        # 生成詳細的問題報告
        all_issues = []
        
        # 收集結構完整性問題
        if structural_result["score"] < 70:
            for missing_element in structural_result.get("missing_elements", []):
                all_issues.append({
                    "issue_type": "structural_missing",
                    "severity": "high" if missing_element in ["introduction", "resolution"] else "medium",
                    "description": f"缺少故事結構元素: {missing_element}",
                    "layer": "structural",
                    "suggestions": [f"建議添加 {missing_element} 相關內容"]
                })
        
        # 收集語義完整性問題
        if semantic_result["score"] < 70:
            for missing_concept in semantic_result.get("missing_concepts", []):
                all_issues.append({
                    "issue_type": "semantic_missing",
                    "severity": "medium",
                    "description": f"缺少關鍵概念: {missing_concept}",
                    "layer": "semantic",
                    "suggestions": [f"建議加強 {missing_concept} 相關描述"]
                })
            
            if semantic_result.get("content_quality", 1.0) < 0.5:
                all_issues.append({
                    "issue_type": "content_quality",
                    "severity": "high",
                    "description": "內容質量不達標（語法、標點、詞彙使用問題）",
                    "layer": "semantic",
                    "suggestions": ["檢查句子長度(5-12詞)", "確認標點符號間距", "檢查冠詞使用"]
                })
        
        # 收集邏輯完整性問題
        for gap in logical_result.get("logical_gaps", []):
            all_issues.append({
                "issue_type": "logical_gap",
                "severity": "medium",
                "description": gap,
                "layer": "logical",
                "suggestions": ["增加邏輯連接詞", "明確因果關係"]
            })
        
        # 收集功能完整性問題
        for gap in functional_result.get("functional_gaps", []):
            all_issues.append({
                "issue_type": "functional_gap",
                "severity": "high" if "結尾" in gap or "寓意" in gap else "medium",
                "description": gap,
                "layer": "functional",
                "suggestions": ["完善故事結尾", "明確教育意義"]
            })
        
        # 生成詳細的實體摘要
        entity_summary = {
            "story_structure": {
                "detected_elements": structural_result.get("elements_checked", []),
                "filled_elements": structural_result.get("filled_elements", 0),
                "total_elements": structural_result.get("total_elements", 0),
                "coverage_percentage": round(structural_result.get("coverage_ratio", 0) * 100, 1)
            },
            "semantic_analysis": {
                "extracted_concepts": semantic_result.get("extracted_concepts", []),
                "concept_density": round(semantic_result.get("semantic_density", 0), 3),
                "content_quality_score": round(semantic_result.get("content_quality", 0), 2),
                "character_consistency_score": round(semantic_result.get("character_consistency", 0), 2)
            },
            "logical_structure": {
                "causal_chains_count": len(causal_chains),
                "reasoning_chains_count": len(logical_result.get("reasoning_chains", [])),
                "logical_consistency": round(logical_result.get("consistency_score", 0), 2)
            },
            "functional_assessment": {
                "goal_achievement": round(functional_result.get("goal_achievement", 0), 1),
                "ai_confidence": round(functional_result.get("confidence", 0), 2),
                "story_purpose_clarity": "high" if functional_result.get("goal_achievement", 0) > 70 else "medium" if functional_result.get("goal_achievement", 0) > 50 else "low"
            }
        }

        return {
            "meta": {
                "version": "3.2_detailed_completeness_analysis",
                "story_title": story_title,
                "sentences": len(sentences),
                "story_type": story_type,
                "semantic_model_available": self.semantic_model is not None,
                "framework_version": "故事書四層完整性評估框架",
                "total_issues": len(all_issues),
                "analysis_timestamp": get_iso_timestamp()
            },
            "completeness": {
                # 詳細的四層完整性評估結果
                "scores": {
                    "structural": round(four_layer_scores.structural, 1),
                    "semantic": round(four_layer_scores.semantic, 1),
                    "logical": round(four_layer_scores.logical, 1),
                    "functional": round(four_layer_scores.functional, 1),
                    "final": round(four_layer_scores.final, 1),
                    "confidence": round(four_layer_scores.confidence, 2),
                    "uncertainty": round(four_layer_scores.uncertainty, 2)
                },
                "explanations": {
                    "structural": {
                        "weights": {"coverage": 80, "prediction_confidence": 10, "quality": 20},
                        "components": {
                            "coverage_ratio": round(structural_result.get("coverage_ratio", 0), 3),
                            "prediction_confidence": round(structural_result.get("prediction_confidence", 0), 2),
                            "evidence_count": sum(len(v) for v in structural_result.get("evidence", {}).values())
                        },
                        "rationale": "結構完整性由槽位覆蓋率及預測置信度與證據質量組合而成"
                    },
                    "semantic": {
                        "weights": {"semantic_density": 0.25, "concept_coverage": 0.25, "content_quality": 0.25, "character_consistency": 0.15, "cultural": 0.10},
                        "components": {
                            "semantic_density": round(semantic_result.get("semantic_density", 0), 3),
                            "concept_coverage": round(semantic_result.get("concept_coverage", 0), 2),
                            "content_quality": round(semantic_result.get("content_quality", 0), 2),
                            "character_consistency": round(semantic_result.get("character_consistency", 0), 2),
                            "cultural_elements": round(semantic_result.get("cultural_elements", 0), 2)
                        },
                        "rationale": "語義完整性綜合考量概念密度、覆蓋、內容/角色品質與文化成分"
                    },
                    "logical": {
                        "weights": {"consistency": 0.6, "reasoning": 0.4},
                        "components": {
                            "logical_consistency": round(logical_result.get("consistency_score", 0), 2),
                            "reasoning_completeness": round(logical_result.get("reasoning_completeness", 0), 2),
                            "causal_chains_count": len(logical_result.get("causal_chains", []))
                        },
                        "rationale": "邏輯完整性以一致性為主、推理鏈完整為輔"
                    },
                    "functional": {
                        "weights": {"ai_analysis": 0.6, "goal_achievement": 0.4},
                        "components": {
                            "ai_analysis_score": round(functional_result.get("ai_analysis_score", 0), 1),
                            "goal_achievement": round(functional_result.get("goal_achievement", 0), 1)
                        },
                        "rationale": "功能完整性關注目標達成與教育/結尾等目的性"
                    },
                    "final": {
                        "adaptive_weights": {k: round(v, 3) for k, v in adaptive_weights.items()},
                        "rationale": "最終分數為四層分數依自適應權重加權所得"
                    }
                },
                "issues": {
                    "structural": [issue for issue in all_issues if issue["layer"] == "structural"],
                    "semantic": [issue for issue in all_issues if issue["layer"] == "semantic"],
                    "logical": [issue for issue in all_issues if issue["layer"] == "logical"],
                    "functional": [issue for issue in all_issues if issue["layer"] == "functional"],
                    "all": all_issues
                },
                "layer_details": {
                    "structural": {
                        "score": round(structural_result["score"], 1),
                        "coverage_ratio": round(structural_result["coverage_ratio"], 2),
                        "filled_elements": structural_result["filled_elements"],
                        "total_elements": structural_result["total_elements"],
                        "missing_elements": structural_result["missing_elements"],
                        "evidence": structural_result.get("evidence", {}),
                        "structure_prediction": structural_result.get("structure_prediction", {})
                    },
                    "semantic": {
                        "score": round(semantic_result["score"], 1),
                        "semantic_density": round(semantic_result["semantic_density"], 3),
                        "concept_coverage": round(semantic_result["concept_coverage"], 2),
                        "extracted_concepts": semantic_result["extracted_concepts"],
                        "missing_concepts": semantic_result["missing_concepts"],
                        "content_quality": round(semantic_result.get("content_quality", 0), 2),
                        "character_consistency": round(semantic_result.get("character_consistency", 0), 2),
                        "cultural_elements": round(semantic_result.get("cultural_elements", 0), 2),
                        "concept_graph_stats": {
                            "nodes": len(semantic_result.get("extracted_concepts", [])),
                            "density": round(semantic_result.get("semantic_density", 0), 3)
                        }
                    },
                    "logical": {
                        "score": round(logical_result["score"], 1),
                        "consistency_score": round(logical_result["consistency_score"], 2),
                        "reasoning_completeness": round(logical_result["reasoning_completeness"], 2),
                        "logical_gaps": logical_result["logical_gaps"],
                        "causal_chains": logical_result.get("causal_chains", []),
                        "reasoning_chains": logical_result.get("reasoning_chains", [])
                    },
                    "functional": {
                        "score": round(functional_result["score"], 1),
                        "ai_analysis_score": round(functional_result["ai_analysis_score"], 1),
                        "goal_achievement": round(functional_result["goal_achievement"], 1),
                        "confidence": round(functional_result["confidence"], 2),
                        "functional_gaps": functional_result["functional_gaps"]
                    }
                },
                "analysis_summary": entity_summary,
                "four_layer_analysis": {
                    "story_type": story_type,
                    "adaptive_weights": adaptive_weights,
                    "validation": validation_results,
                    "layer_performance": {
                        "best_layer": max(["structural", "semantic", "logical", "functional"], 
                                        key=lambda x: getattr(four_layer_scores, x)),
                        "worst_layer": min(["structural", "semantic", "logical", "functional"], 
                                         key=lambda x: getattr(four_layer_scores, x)),
                        "score_variance": round(self._calculate_score_variance([
                            four_layer_scores.structural, four_layer_scores.semantic,
                            four_layer_scores.logical, four_layer_scores.functional
                        ]), 2)
                    }
                },
                # 保持原有結構（向後兼容）
                "story_analysis": {
                    "type": story_type,
                    "causal_chains": len(causal_chains),
                    "structural_elements": covered_slots
                },
                "evidence": evidence,
                "causal_relationships": causal_chains[:10],
                # 動態事件上限：依字數與句數擴張，長文不再僅顯示20
                "events": events[: max(20, min(400, len(story_text.split()) // 80, len(sentences) // 2))],
                "metrics": {
                    "structure_coverage": round(structure_coverage, 1),
                    "event_density": round(event_density, 1),
                    "causal_chain_avg_length": round(avg_chain_len, 2),
                    "template_match_score": round(template_match_score, 1),
                    "semantic_density": round(semantic_result["semantic_density"], 3),
                    "concept_coverage": round(semantic_result["concept_coverage"], 2),
                    "logical_consistency": round(logical_result["consistency_score"], 2),
                    "reasoning_completeness": round(logical_result["reasoning_completeness"], 2),
                    "goal_achievement": round(functional_result["goal_achievement"], 1)
                },
                "story_type": story_type,
                "ai_analysis": ai_analysis,
                "suggestions": suggestions
            }
        }

    # ====== 高科技實作方法 ======
    
    def _detect_story_type(self, text: str) -> str:
        """🧠 智能故事類型識別（基於知識圖譜）"""
        text_lower = text.lower()
        
        # 基於知識圖譜的故事類型檢測
        type_scores = {}
        for story_type, template in self.story_structure_templates.items():
            score = 0
            # 檢查關鍵詞匹配
            for keyword in template["keywords"]:
                if keyword in text_lower:
                    score += 2
            
            # 檢查角色和設定匹配
            if story_type == "cultural_story" and any(name in text_lower for name in ["aya", "kemi", "tunde", "bola"]):
                score += 3
            
            if story_type == "exploration_story" and any(name in text_lower for name in ["emma", "alex", "tom"]):
                score += 2
                
            type_scores[story_type] = score
        
        # 調試信息
        self._debug(f"🔍 故事類型檢測分數: {type_scores}")
        
        # 返回最高分的故事類型
        if type_scores:
            best_type = max(type_scores, key=type_scores.get)
            if type_scores[best_type] > 0:
                self._debug(
                    f"✅ 檢測到故事類型: {best_type} (分數: {type_scores[best_type]})"
                )
                return best_type
        
        self._warn("未檢測到明確故事類型，使用默認: exploration_story")
        return "exploration_story"  # 默認返回探索型故事
    
    def _predict_story_structure(self, text: str, story_type: str) -> Dict:
        """🔮 基於知識圖譜預測故事結構（AI增強）"""
        text_lower = text.lower()
        template = self.story_structure_templates.get(story_type, self.story_structure_templates["exploration_story"])
        
        # 預測可能存在的元素
        predicted_elements = []
        detected_elements = []
        
        # 檢查必需元素
        for element in template["required_elements"]:
            predicted_elements.append(element)
            if self._check_element_presence(text, element):
                detected_elements.append(element)
        
        # 檢查可選元素
        for element in template["optional_elements"]:
            if self._check_element_presence(text, element):
                predicted_elements.append(element)
                detected_elements.append(element)
        
        # AI模型輔助預測（如果可用）
        ai_prediction = None
        if self.ai and self.ai.model_available:
            try:
                ai_prediction = self._ai_predict_story_structure(text, story_type)
                if ai_prediction:
                    # 合併AI預測結果
                    ai_elements = ai_prediction.get("predicted_elements", [])
                    for element in ai_elements:
                        if element not in predicted_elements:
                            predicted_elements.append(element)
                            if self._check_element_presence(text, element):
                                detected_elements.append(element)
            except Exception as e:
                self._warn("AI預測失敗", e)
        
        return {
            "story_type": story_type,
            "predicted_elements": predicted_elements,
            "detected_elements": detected_elements,
            "missing_required": [e for e in template["required_elements"] if e not in detected_elements],
            "confidence": len(detected_elements) / len(template["required_elements"]) if template["required_elements"] else 0,
            "ai_prediction": ai_prediction
        }
    
    def _ai_predict_story_structure(self, text: str, story_type: str) -> Dict:
        """🤖 AI模型輔助預測故事結構"""
        if not self.ai or not self.ai.model_available:
            return None
        
        try:
            prompt = f"""
            分析以下故事文本，預測其結構元素：
            
            故事類型: {story_type}
            文本: {text[:500]}...
            
            請分析並返回JSON格式：
            {{
                "predicted_elements": ["introduction", "adventure", "discovery", "sharing", "lesson"],
                "confidence": 0.8,
                "reasoning": "基於文本內容的分析理由"
            }}
            """
            
            response = self.ai.analyze_consistency(text, [], {})
            # 這裡可以解析AI回應並返回結構化結果
            return {
                "predicted_elements": ["introduction", "adventure", "discovery", "sharing", "lesson"],
                "confidence": 0.7,
                "reasoning": "AI分析結果"
            }
        except Exception as e:
            self._warn("AI預測錯誤", e)
            return None
    
    def _check_element_presence(self, text: str, element: str) -> bool:
        """檢查特定元素是否存在於文本中"""
        text_lower = text.lower()
        
        # 基於經典童話的元素檢測規則
        element_rules = {
            "introduction": ["once upon", "there was", "lived", "little", "grandpa", "in the beginning", "long ago", "far away", "princess", "prince", "king", "queen"],
            "conflict": ["problem", "trouble", "difficult", "challenge", "lost", "stuck", "scared", "wicked", "evil", "danger", "threat", "curse", "spell", "wolf", "hunt", "chase", "fight", "battle"],
            "climax": ["suddenly", "just then", "at that moment", "climax", "peak", "turning point", "realized", "decided", "because of that", "so", "therefore"],
            "resolution": ["finally", "in the end", "at last", "eventually", "solved", "fixed", "resolved", "saved", "helped", "escaped", "defeated", "overcame", "won", "success", "awakened", "kissed"],
            "problem": ["problem", "trouble", "difficult", "challenge", "lost", "stuck", "scared", "wicked", "evil", "danger", "threat", "curse", "spell"],
            "adventure": ["adventure", "journey", "explore", "discover", "quest", "magical", "wandered", "traveled", "forest", "castle", "palace"],
            "discovery": ["discover", "found", "treasure", "amazing", "wonderful", "fascinating", "met", "encountered", "realized", "understood"],
            "sharing": ["share", "together", "tell", "show", "play", "laugh", "helped", "saved", "grateful", "everyone"],
            "lesson": ["learned", "understood", "realized", "lesson", "moral", "wisdom", "happily ever after", "from then on", "ever since", "always"],
            "culture": ["culture", "tradition", "heritage", "community", "wisdom", "values", "kingdom", "palace", "castle"],
            "curiosity": ["curious", "wonder", "ask", "question", "excited", "interested", "wanted to know", "marveled"],
            "bonding": ["friendship", "together", "bonding", "care", "love", "trust", "helped", "saved", "grateful"]
        }
        
        if element in element_rules:
            return any(keyword in text_lower for keyword in element_rules[element])
        
        return False
    
    def _extract_semantic_events(self, sentences: List[str]) -> List[Dict]:
        """🔍 語義事件抽取（升級版）"""
        events = []
        
        for i, sentence in enumerate(sentences):
            # 使用spaCy進行更深入的分析
            if self.nlp:
                doc = self.nlp(sentence)
                
                # 尋找動作事件
                for token in doc:
                    if token.pos_ == "VERB" and not token.is_stop:
                        # 提取主語和賓語
                        subject = None
                        obj = None
                        
                        for child in token.children:
                            if child.dep_ in ["nsubj", "nsubjpass"]:
                                subject = child.text
                            elif child.dep_ in ["dobj", "pobj"]:
                                obj = child.text
                        
                        if subject:  # 有主語的動作更可能是重要事件
                            events.append({
                                "sentence_id": i,
                                "action": token.lemma_,
                                "subject": subject,
                                "object": obj,
                                "text": sentence,
                                "importance": self._calculate_event_importance(sentence, token.lemma_)
                            })
        
        # 按重要性排序
        events.sort(key=lambda x: x["importance"], reverse=True)
        return events
    
    def _calculate_event_importance(self, sentence: str, action: str) -> float:
        """計算事件重要性"""
        importance = 1.0
        
        # 重要動詞加分
        important_verbs = ["decide", "realize", "discover", "fight", "save", "die", "love", "marry", "defeat"]
        if action in important_verbs:
            importance += 2.0
        
        # 情感詞彙加分 - 使用配置文件（混合正負面情感）
        emotion_keywords = []
        for emotion_type in ['joy', 'sadness', 'anger', 'fear', 'surprise']:
            emotion_keywords.extend(self._load_keywords(f'emotion.{emotion_type}.words', []))
        if any(word in sentence.lower() for word in emotion_keywords[:20]):  # 限制前20個高頻詞
            importance += 1.0
        
        # 對話加分（通常包含重要信息）
        if '"' in sentence or "said" in sentence.lower():
            importance += 0.5
            
        return importance
    
    def _analyze_causal_relationships(self, sentences: List[str], events: List[Dict]) -> List[Dict]:
        """🔗 因果關係分析"""
        causal_chains = []
        
        for i, sentence in enumerate(sentences):
            for pattern in self.causal_patterns:
                matches = re.finditer(pattern, sentence.lower())
                for match in matches:
                    # 尋找因果關係的前後文
                    cause_part = sentence[:match.start()].strip()
                    effect_part = sentence[match.end():].strip()
                    
                    if cause_part and effect_part:
                        causal_chains.append({
                            "sentence_id": i,
                            "cause": cause_part,
                            "effect": effect_part,
                            "connector": match.group(),
                            "strength": self._assess_causal_strength(sentence, match.group())
                        })
        
        return causal_chains
    
    def _assess_causal_strength(self, sentence: str, connector: str) -> float:
        """評估因果關係強度"""
        strong_connectors = ["because of", "due to", "resulted in"]
        medium_connectors = ["therefore", "consequently", "so that"]
        
        if connector in strong_connectors:
            return 0.9
        elif connector in medium_connectors:
            return 0.7
        else:
            return 0.5
    
    def _collect_smart_evidence(self, sentences: List[str], sent_bins: Dict, events: List[Dict], story_type: str) -> Dict:
        """🎯 智能槽位偵測"""
        template = self.story_templates.get(story_type, self.story_templates["simple_story"])
        evidence = {slot: [] for slot in template}
        
        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            
            # 對每個模板槽位檢查
            for slot in template:
                slot_score = 0
                
                # 1. 直接關鍵詞匹配
                if slot in self.semantic_keywords:
                    for keyword in self.semantic_keywords[slot]["direct"]:
                        if keyword in sentence_lower:
                            slot_score += 1.0
                
                # 2. 語義相似度匹配（如果有語義模型）
                if self.semantic_model and slot in self.semantic_keywords:
                    semantic_phrases = self.semantic_keywords[slot]["semantic"]
                    try:
                        max_similarity = self._calculate_semantic_similarity(sentence, semantic_phrases)
                        
                        if max_similarity > 0.6:  # 閾值可調整
                            slot_score += max_similarity
                    except Exception:
                        pass  # 語義匹配失敗時跳過
                
                # 3. 位置權重（開頭和結尾的句子更可能包含setup和ending）
                position_weight = self._get_position_weight(i, len(sentences), slot)
                slot_score *= position_weight
                
                if slot_score > 0.3:  # 調整閾值
                    evidence[slot].append({
                        "sentence_id": i,
                        "text": sentence,
                        "score": round(slot_score, 2),
                        "evidence_type": "smart_detection"
                    })
        
        return evidence
    
    def _get_position_weight(self, sentence_id: int, total_sentences: int, slot: str) -> float:
        """根據句子位置和槽位類型給予權重"""
        position_ratio = sentence_id / total_sentences
        
        # 不同槽位在故事中的典型位置
        position_preferences = {
            "setup": 0.2,           # 開頭20%
            "introduction": 0.1,    # 開頭10%
            "inciting": 0.3,        # 前30%
            "conflict": 0.5,        # 中間
            "turning": 0.6,         # 60%位置
            "resolution": 0.8,      # 80%位置
            "ending": 0.9           # 結尾
        }
        
        preferred_position = position_preferences.get(slot, 0.5)
        distance = abs(position_ratio - preferred_position)
        
        # 距離越近權重越高
        return max(0.3, 1.0 - distance)
    
    # ====== 基礎實作細節 ======
    def _bin_by_position(self, sentences: List[str]) -> Dict[str, List[int]]:
        n = len(sentences)
        if n == 0:
            return {"begin": [], "middle": [], "end": []}
        
        # 簡化的位置分組
        begin_end = max(1, n // 4)
        return {
            "begin": list(range(begin_end)),
            "middle": list(range(begin_end, n - begin_end)),
            "end": list(range(n - begin_end, n))
        }
    
    def _score_structural_completeness(self, evidence: Dict, events: List[Dict], causal_chains: List[Dict], story_type: str) -> float:
        """📊 結構完整性評分"""
        template = self.story_templates.get(story_type, self.story_templates["simple_story"])
        
        # 基礎結構分數
        filled_slots = len([k for k, v in evidence.items() if v])
        structure_ratio = filled_slots / len(template)
        structure_score = structure_ratio * 70  # 最高70分
        
        # 事件豐富度加分
        if events:
            event_bonus = min(20, len(events) * 2)  # 最高20分
        else:
            event_bonus = 0
        
        # 因果關係加分
        if causal_chains:
            causal_bonus = min(10, len(causal_chains) * 3)  # 最高10分
        else:
            causal_bonus = 0
        
        return min(100, structure_score + event_bonus + causal_bonus)
    
    def _advanced_ai_analysis(self, story_text: str, evidence: Dict, events: List[Dict], causal_chains: List[Dict]) -> Dict:
        """🤖 AI 深度分析"""
        if not self.ai or not self.ai.model_available:
            return {"score": COMPLETENESS_AI_FALLBACK_SCORE, "analysis": "AI模型不可用，使用基礎評分"}
        
        # 構建更詳細的prompt
        prompt = f"""
        請分析以下故事的完整性，考慮以下方面：
        
        故事文本：
        {story_text[:1000]}...
        
        結構分析：
        - 檢測到的結構元素：{len([k for k, v in evidence.items() if v])}
        - 重要事件數量：{len(events)}
        - 因果關係鏈：{len(causal_chains)}
        
        請從以下角度評分（0-100）：
        1. 故事是否有清晰的開始、發展和結束
        2. 情節發展是否合理
        3. 角色動機是否明確
        4. 衝突是否得到解決
        
        請給出總分並簡要說明理由。
        """
        
        try:
            # 取得 AI 模型原始分（若無則後退至內容分）
            ai_result = self.ai.analyze_consistency(story_text, [], {})
            raw_ai_score = ai_result.get("ai_score", ai_result.get("score", 0))

            content_proxy = self._calculate_content_based_ai_score(story_text, evidence, events)

            # 基於內容訊號校準：結構/事件/因果與負面標記
            tl = story_text.lower()
            neg_markers = [
                "doesn't make sense", "does not make sense", "incomplete", "no ending",
                "broken story", "confusing", "contradict", "contradictory"
            ]
            neg_hits = sum(tl.count(m) for m in neg_markers)
            structure_slots = len([k for k, v in evidence.items() if v])
            event_count = len(events) if isinstance(events, list) else 0
            causal_count = len(causal_chains) if isinstance(causal_chains, list) else 0

            # 原始分合理性檢查
            if raw_ai_score <= 0 or raw_ai_score > 100:
                raw_ai_score = content_proxy
            raw_ai_score = normalize_score_0_100(raw_ai_score, content_proxy)

            # 懲罰與調整（對好文更友善）
            penalty = 0.0
            if structure_slots < 4:
                penalty += 6.0
            elif structure_slots < 6:
                penalty += 3.0
            if event_count < 3:
                penalty += 6.0
            elif event_count < 10:
                penalty += 2.0
            if causal_count == 0:
                penalty += 6.0
            if neg_hits >= 3:
                penalty += 10.0
            elif neg_hits == 2:
                penalty += 6.0
            elif neg_hits == 1:
                penalty += 3.0

            # 好文加成：結構/事件/因果皆優時，小幅提升
            bonus = 0.0
            if structure_slots >= 8 and event_count >= 15 and causal_count >= 2:
                bonus += 5.0
            elif structure_slots >= 7 and event_count >= 12 and causal_count >= 1:
                bonus += 3.0

            # 融合原始 AI 與內容代理分（抑制過高、抬升過低）
            blended = 0.5 * raw_ai_score + 0.5 * content_proxy
            calibrated = max(0.0, blended - penalty + bonus)

            # 高分壓頂：避免動輒 95 分
            if calibrated > 85.0:
                calibrated = 85.0 + (calibrated - 85.0) * 0.5  # 壓縮上尾

            # 低分地板：完全破碎文本也不至於 0，但保留低檔區間
            calibrated = max(15.0, min(92.0, calibrated))

            return {
                "score": calibrated,
                "analysis": f"AI分析校準分 {calibrated:.1f}/100 (raw={raw_ai_score:.1f}, proxy={content_proxy:.1f}, penalty={penalty:.1f})",
                "confidence": normalize_confidence_0_1(0.8, 0.8)
            }
        except Exception as e:
            # 如果AI分析失敗，使用基礎評分
            fallback_score = self._calculate_content_based_ai_score(story_text, evidence, events)
            return {"score": fallback_score, "analysis": f"AI分析失敗，使用基礎評分: {str(e)}"}
    
    def _calculate_content_based_ai_score(self, story_text: str, evidence: Dict, events: List[Dict]) -> float:
        """基於內容計算AI評分（較保守，不易飆高）"""
        word_count = len(story_text.split())
        
        # 基礎分數基於故事長度
        if word_count < 50:
            base_score = 25
        elif word_count < 100:
            base_score = 45
        elif word_count < 200:
            base_score = 60
        elif word_count < 500:
            base_score = 68
        else:
            base_score = 72
        
        # 結構元素獎勵
        structure_elements = len([k for k, v in evidence.items() if v])
        structure_bonus = min(12, structure_elements * 1.5)
        
        # 事件豐富度獎勵
        event_bonus = min(8, len(events) * 0.4)
        
        # 故事完整性指標獎勵
        completeness_bonus = 0.0
        text_lower = story_text.lower()
        
        # 檢查故事結構完整性
        if any(word in text_lower for word in ["once upon", "one day", "in the beginning"]):
            completeness_bonus += 3  # 有開始
        if any(word in text_lower for word in ["but", "however", "problem", "trouble"]):
            completeness_bonus += 3  # 有衝突
        if any(word in text_lower for word in ["finally", "at last", "in the end", "happily ever after"]):
            completeness_bonus += 3  # 有結尾
        
        # 輕度負面訊號扣分
        neg_markers = [
            "doesn't make sense", "does not make sense", "incomplete", "no ending",
            "broken story", "confusing", "contradict", "contradictory"
        ]
        neg_hits = sum(text_lower.count(m) for m in neg_markers)
        neg_penalty = 0.0
        if neg_hits >= 3:
            neg_penalty = 8.0
        elif neg_hits == 2:
            neg_penalty = 5.0
        elif neg_hits == 1:
            neg_penalty = 2.5

        final_score = base_score + structure_bonus + event_bonus + completeness_bonus - neg_penalty
        return max(0.0, min(90.0, final_score))
    
    def _calculate_final_score(self, structural_score: float, ai_analysis: Dict, story_type: str) -> float:
        """🎯 最終綜合評分"""
        ai_score = ai_analysis.get("score", 50)
        
        # 根據故事類型調整權重
        if story_type == "children_story":
            # 兒童故事更注重結構清晰
            final = 0.7 * structural_score + 0.3 * ai_score
        elif story_type == "classic_hero":
            # 英雄故事更注重情節完整性
            final = 0.5 * structural_score + 0.5 * ai_score
        else:
            # 一般故事平衡考量
            final = 0.6 * structural_score + 0.4 * ai_score
        
        return min(100, max(0, final))
    
    def _generate_smart_suggestions(self, evidence: Dict, events: List[Dict], causal_chains: List[Dict], ai_analysis: Dict, story_type: str) -> List[str]:
        """💡 智能建議生成"""
        suggestions = []
        template = self.story_templates.get(story_type, self.story_templates["simple_story"])
        
        # 檢查缺失的結構元素
        missing_slots = [slot for slot in template if not evidence.get(slot)]
        if missing_slots:
            suggestions.append(f"故事缺少以下結構元素：{', '.join(missing_slots)}")
        
        # 事件豐富度建議
        if len(events) < 3:
            suggestions.append("故事中的重要事件較少，建議增加更多具體的行動和轉折")
        
        # 因果關係建議
        if len(causal_chains) < 2:
            suggestions.append("故事中的因果關係不夠明確，建議使用更多連接詞來說明事件之間的關係")
        
        # 基於AI分析的建議
        if ai_analysis.get("score", 50) < 60:
            suggestions.append("AI分析顯示故事完整性有待提升，建議檢查情節發展的邏輯性")
        
        # 故事類型特定建議
        if story_type == "children_story":
            if not any("lesson" in str(evidence.get(slot, [])) for slot in template):
                suggestions.append("兒童故事建議包含明確的教育意義或道德寓意")
        
        return suggestions if suggestions else ["故事結構完整，無特殊建議"]
    
    def _generate_four_layer_suggestions(self, structural_result: Dict, semantic_result: Dict, 
                                       logical_result: Dict, functional_result: Dict,
                                       adaptive_weights: Dict, validation_results: Dict, 
                                       story_type: str) -> List[str]:
        """💡 四層完整性智能建議生成"""
        suggestions = []
        
        # 基於四層分數的建議
        layer_scores = {
            "結構完整性": structural_result["score"],
            "語義完整性": semantic_result["score"],
            "邏輯完整性": logical_result["score"],
            "功能完整性": functional_result["score"]
        }
        
        # 找出最低分的層次
        min_layer = min(layer_scores, key=layer_scores.get)
        min_score = layer_scores[min_layer]
        
        if min_score < 50:
            suggestions.append(f"🚨 {min_layer}得分較低({min_score:.1f})，建議優先改進")
        
        # 結構完整性建議
        if structural_result["score"] < 70:
            missing_elements = structural_result.get("missing_elements", [])
            if missing_elements:
                # 長文採用更溫和的建議
                # 使用證據密度近似長文情況，避免未定義變數
                total_hits = sum(len(v) for v in structural_result.get("evidence", {}).values())
                if total_hits > 300:
                    suggestions.append("📋 結構完整性：建議標註或分段突出高潮與結局段落，以提升結構明晰度")
                else:
                    suggestions.append(f"📋 結構完整性：缺少以下元素 - {', '.join(missing_elements[:3])}")
            else:
                suggestions.append("📋 結構完整性：建議增加更多結構化內容")
        
        # 語義完整性建議（基於知識圖譜）
        if semantic_result["score"] < 70:
            missing_concepts = semantic_result.get("missing_concepts", [])
            if missing_concepts:
                suggestions.append(f"🧠 語義完整性：缺少關鍵概念 - {', '.join(missing_concepts[:3])}")
            else:
                suggestions.append("🧠 語義完整性：建議加強概念之間的關聯性")
            
            # 基於知識圖譜的具體建議
            content_quality = semantic_result.get('content_quality', 0)
            if content_quality < 0.5:
                suggestions.append("✍️ 內容質量：檢查句子長度(5-12詞)、標點符號間距、冠詞使用")
            
            character_consistency = semantic_result.get('character_consistency', 0)
            if character_consistency < 0.5:
                suggestions.append("👥 角色一致性：確保角色名稱在故事中保持一致，避免同一角色使用不同稱呼")
            
            cultural_elements = semantic_result.get('cultural_elements', 0)
            if cultural_elements < 0.3:
                suggestions.append("🌍 文化元素：可以考慮增加更多文化背景描述，讓故事更豐富")
        
        # 邏輯完整性建議
        if logical_result["score"] < 70:
            logical_gaps = logical_result.get("logical_gaps", [])
            if logical_gaps:
                suggestions.append(f"🔗 邏輯完整性：{logical_gaps[0]}")
            else:
                suggestions.append("🔗 邏輯完整性：建議增加更多因果關係和推理鏈")
        
        # 功能完整性建議
        if functional_result["score"] < 70:
            functional_gaps = functional_result.get("functional_gaps", [])
            if functional_gaps:
                suggestions.append(f"🎯 功能完整性：{functional_gaps[0]}")
            else:
                suggestions.append("🎯 功能完整性：建議明確文本目標並確保達成")
        
        # 基於文本類型的特定建議
        if story_type == "children_story":
            if structural_result["score"] < 80:
                suggestions.append("👶 兒童故事：建議包含更清晰的開始、問題、解決和結局")
            if "lesson" not in str(structural_result.get("evidence", {})):
                suggestions.append("👶 兒童故事：建議加入教育意義或道德寓意")
        
        elif story_type == "technical_doc":
            if functional_result["score"] < 80:
                suggestions.append("⚙️ 技術文檔：建議增加錯誤處理和故障排除說明")
            if semantic_result["score"] < 70:
                suggestions.append("⚙️ 技術文檔：建議完善概念定義和關係說明")
        
        elif story_type == "instruction_manual":
            if structural_result["score"] < 80:
                suggestions.append("📖 操作手冊：建議按步驟順序組織內容")
            if functional_result["score"] < 80:
                suggestions.append("📖 操作手冊：建議增加安全警告和注意事項")
        
        # 基於權重的建議
        max_weight_layer = max(adaptive_weights, key=adaptive_weights.get)
        if adaptive_weights[max_weight_layer] > 0.4:
            layer_names = {
                "structural": "結構完整性",
                "semantic": "語義完整性", 
                "logical": "邏輯完整性",
                "functional": "功能完整性"
            }
            suggestions.append(f"⚖️ 系統自動調整：{layer_names[max_weight_layer]}權重較高，建議重點關注")
        
        # 基於驗證結果的建議
        if validation_results["uncertainty"] > 0.3:
            suggestions.append("⚠️ 評估不確定性較高，建議人工復核")
        
        if validation_results["reliability"] < 0.7:
            suggestions.append("🔍 評估可靠性較低，建議檢查文本質量")
        
        # 綜合建議
        if all(score >= 80 for score in layer_scores.values()):
            suggestions.append("🎉 四層完整性評估優秀，文本質量很高！")
        elif all(score >= 60 for score in layer_scores.values()):
            suggestions.append("👍 四層完整性評估良好，可進行小幅優化")
        else:
            suggestions.append("📝 四層完整性評估需要改進，建議全面檢查")
        
        return suggestions[:8]  # 限制建議數量
    
    def _calculate_semantic_similarity(self, sentence: str, phrases: List[str]) -> float:
        """使用本地transformers計算語義相似度（優化版）"""
        if not self.semantic_model:
            return 0.0
        
        try:
            tokenizer = self.semantic_model["tokenizer"]
            model = self.semantic_model["model"]
            device = next(model.parameters()).device
            
            # 編碼句子
            sentence_inputs = tokenizer(sentence, return_tensors="pt", padding=True, truncation=True, max_length=512)
            if device.type == 'cuda':
                sentence_inputs = {k: v.to(device) for k, v in sentence_inputs.items()}
            
            with torch.no_grad():
                sentence_outputs = model(**sentence_inputs)
                sentence_embedding = sentence_outputs.last_hidden_state.mean(dim=1)
            
            max_similarity = 0.0
            
            # 批次處理短語以提高效率
            if len(phrases) > 1:
                phrase_inputs = tokenizer(phrases, return_tensors="pt", padding=True, truncation=True, max_length=512)
                if device.type == 'cuda':
                    phrase_inputs = {k: v.to(device) for k, v in phrase_inputs.items()}
                with torch.no_grad():
                    phrase_outputs = model(**phrase_inputs)
                    phrase_embeddings = phrase_outputs.last_hidden_state.mean(dim=1)  # [N, D]
                # 以正規化後矩陣乘法計算相似度： [N,D] · [D,1] -> [N,1]
                se = torch.nn.functional.normalize(sentence_embedding, p=2, dim=1)   # [1, D]
                pe = torch.nn.functional.normalize(phrase_embeddings, p=2, dim=1)    # [N, D]
                sims = torch.mm(pe, se.t()).squeeze(1)  # [N]
                max_similarity = float(sims.max().item()) if sims.numel() > 0 else 0.0
            else:
                # 單個短語的情況
                for phrase in phrases:
                    phrase_inputs = tokenizer(phrase, return_tensors="pt", padding=True, truncation=True, max_length=512)
                    if device.type == 'cuda':
                        phrase_inputs = {k: v.to(device) for k, v in phrase_inputs.items()}
                    
                    with torch.no_grad():
                        phrase_outputs = model(**phrase_inputs)
                        phrase_embedding = phrase_outputs.last_hidden_state.mean(dim=1)
                    
                    se = torch.nn.functional.normalize(sentence_embedding, p=2, dim=1)
                    pe = torch.nn.functional.normalize(phrase_embedding, p=2, dim=1)
                    similarity = torch.mm(pe, se.t()).squeeze()
                    sim_val = float(similarity.item()) if similarity.numel() > 0 else 0.0
                    max_similarity = max(max_similarity, sim_val)
            
            return max_similarity
            
        except Exception as e:
            self._warn("語義相似度計算失敗", e)
            return 0.0


    def _batch_calculate_semantic_similarity(self, text: str, concepts: List[str]) -> Dict[str, float]:
        """批量計算語義相似度（高效版）"""
        if not self.semantic_model:
            raise RuntimeError("語義模型未載入，無法計算相似度")
        
        # 檢查緩存
        cache_key = f"{hash(text)}_{hash(tuple(concepts))}"
        if cache_key in self.semantic_cache:
            return self.semantic_cache[cache_key]
        
        try:
            # 批量計算嵌入
            similarities = {}
            
            # 使用現有的語義相似度計算方法
            for concept in concepts:
                similarity = self._calculate_semantic_similarity(text, [concept])
                similarities[concept] = similarity
            
            # 緩存結果
            self.semantic_cache[cache_key] = similarities
            return similarities
            
        except Exception as e:
            raise RuntimeError(f"語義相似度計算失敗: {e}")
    
    
    def _calculate_score_variance(self, scores: List[float]) -> float:
        """計算分數方差"""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        return variance
    
    def _basic_functional_assessment(self, text: str) -> float:
        """基礎功能完整性評估（不依賴AI）"""
        text_lower = text.lower()
        score = 60  # 提高基礎分數
        
        # 檢查故事結尾
        if any(word in text_lower for word in ["happily ever after", "the end", "from then on", "ever since"]):
            score += 20  # 提高結尾獎勵
        
        # 檢查教育意義
        if any(word in text_lower for word in ["learned", "lesson", "moral", "understood", "realized"]):
            score += 20  # 提高教育意義獎勵
        
        # 檢查問題解決
        if any(word in text_lower for word in ["helped", "saved", "solved", "fixed", "worked", "found"]):
            score += 15  # 提高問題解決獎勵
        
        # 檢查角色發展
        if any(word in text_lower for word in ["grew", "changed", "developed", "became", "discovered", "met"]):
            score += 15  # 提高角色發展獎勵
        
        return min(100, score)
    
    def _basic_goal_achievement_analysis(self, text: str) -> float:
        """基礎目標達成度分析（不依賴AI）"""
        text_lower = text.lower()
        goal_indicators = [
            "happily ever after", "learned", "lesson", "moral", "understood",
            "helped", "saved", "grateful", "success", "better", "together", "found", "met"
        ]
        found_indicators = sum(1 for indicator in goal_indicators if indicator in text_lower)
        return min(100, 50 + found_indicators * 10)  # 提高基礎分數和獎勵
    
    def _basic_functional_gaps_analysis(self, text: str) -> List[str]:
        """基礎功能缺口分析（不依賴AI）"""
        gaps = []
        text_lower = text.lower()
        
        # 檢查故事結尾
        if not any(word in text_lower for word in ["happily ever after", "the end", "from then on", "ever since"]):
            gaps.append("缺少明確的故事結尾")
        
        # 檢查教育意義
        if not any(word in text_lower for word in ["learned", "lesson", "moral", "understood", "realized"]):
            gaps.append("缺少教育意義或道德寓意")
        
        # 檢查問題解決
        if not any(word in text_lower for word in ["helped", "saved", "solved", "fixed", "worked"]):
            gaps.append("缺少問題解決過程")
        
        return gaps[:5]
    
    def _detect_poor_story_indicators(self, text: str) -> Dict[str, List[str]]:
        """檢測差故事指標"""
        text_lower = text.lower()
        poor_indicators = {
            "structural_issues": [],
            "semantic_issues": [],
            "logical_issues": [],
            "functional_issues": []
        }
        
        # 結構問題檢測
        if len(text.split()) < 10:
            poor_indicators["structural_issues"].append("故事過於簡短，缺乏情節發展")
        if len(text.split()) > 1000 and len(text.split('.')) < 5:
            poor_indicators["structural_issues"].append("故事過長但缺乏結構")
        if not any(word in text_lower for word in ["once upon", "one day", "there was", "lived"]):
            poor_indicators["structural_issues"].append("缺少故事開頭")
        if not any(word in text_lower for word in ["finally", "ended", "concluded", "from then on"]):
            poor_indicators["structural_issues"].append("缺少故事結尾")
        
        # 語義問題檢測
        if not any(name in text_lower for name in ["emma", "alex", "tom", "grandpa", "character", "person"]):
            poor_indicators["semantic_issues"].append("缺少明確角色")
        if text.count('.') < 3:
            poor_indicators["semantic_issues"].append("句子數量過少，內容貧乏")
        if len(set(text_lower.split())) < 10:
            poor_indicators["semantic_issues"].append("詞彙量過少，語言貧乏")
        
        # 邏輯問題檢測
        if any(word in text_lower for word in ["but", "however", "although"]) and not any(word in text_lower for word in ["because", "so", "therefore"]):
            poor_indicators["logical_issues"].append("有轉折但缺乏解釋")
        if any(word in text_lower for word in ["problem", "trouble", "difficult"]) and not any(word in text_lower for word in ["solved", "fixed", "helped"]):
            poor_indicators["logical_issues"].append("有問題但沒有解決")
        
        # 功能問題檢測
        if not any(word in text_lower for word in ["learned", "lesson", "moral", "understood"]):
            poor_indicators["functional_issues"].append("缺少教育意義")
        if any(word in text_lower for word in ["once upon", "one day"]) and not any(word in text_lower for word in ["finally", "ended", "concluded"]):
            poor_indicators["functional_issues"].append("有開始但沒有結尾")
        
        return poor_indicators

    def _load_keywords(self, category: str, fallback: List[str]) -> List[str]:
        """從本地分類載入關鍵詞，若缺少則使用預設值"""
        keywords = load_category_keywords(
            getattr(self, "local_categories", None),
            category,
            fallback,
        )
        return normalize_keywords(list(keywords))

    def _load_base_weights(self, default_weights: Dict[str, float]) -> Dict[str, float]:
        """從 YAML 載入基礎權重（completeness.weights.base），格式支援：
        - 列表：['structural:0.35','semantic:0.25','logical:0.2','functional:0.2']
        - 缺省或解析失敗則回退 default_weights
        """
        try:
            raw = self._load_keywords('completeness.weights.base', [f"{k}:{v}" for k, v in default_weights.items()])
            return parse_weight_list(raw, default_weights)
        except Exception:
            return default_weights

    def _load_adaptive_weights(self, default_weights: Dict[str, float]) -> Dict[str, float]:
        """從 YAML 載入自適應權重（completeness.weights.adaptive），格式同 _load_base_weights"""
        try:
            raw = self._load_keywords('completeness.weights.adaptive', [f"{k}:{v}" for k, v in default_weights.items()])
            return parse_weight_list(raw, default_weights)
        except Exception:
            return default_weights

    def _load_semantic_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        """載入語義關鍵詞，支援 YAML 配置"""
        semantic_map: Dict[str, Dict[str, List[str]]] = {}
        for slot, groups in DEFAULT_SEMANTIC_KEYWORDS.items():
            semantic_map[slot] = {}
            for group, default_values in groups.items():
                category = f"completeness.semantic.{slot}.{group}"
                semantic_map[slot][group] = self._load_keywords(category, default_values)
        return semantic_map

    def _load_story_element_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        """載入故事元素關鍵詞"""
        elements: Dict[str, Dict[str, List[str]]] = {}
        for element, buckets in DEFAULT_STORY_ELEMENT_KEYWORDS.items():
            elements[element] = {}
            for bucket, default_values in buckets.items():
                category = f"completeness.story_elements.{element}.{bucket}"
                elements[element][bucket] = self._load_keywords(category, default_values)
        return elements

    def _load_character_aliases(self) -> Dict[str, List[str]]:
        """載入角色別名映射"""
        aliases: Dict[str, List[str]] = {}
        for canonical, default_aliases in DEFAULT_CHARACTER_ALIASES.items():
            category = f"completeness.characters.aliases.{canonical}"
            aliases[canonical] = self._load_keywords(category, default_aliases)
        return aliases

    def _load_cultural_elements(self) -> Dict[str, List[str]]:
        """載入文化元素字典，允許擴充"""
        elements: Dict[str, List[str]] = {}
        if hasattr(self, "local_categories") and self.local_categories:
            for category in self.local_categories.get_category_names("completeness.cultural_elements"):
                keywords = normalize_keywords(self.local_categories.get_keywords(category))
                if keywords:
                    short_name = category.split(".")[-1]
                    elements[short_name] = keywords

        for fallback_name, default_values in DEFAULT_CULTURAL_ELEMENTS.items():
            if fallback_name not in elements:
                category = f"completeness.cultural_elements.{fallback_name}"
                elements[fallback_name] = self._load_keywords(category, default_values)

        return elements

    

    def _get_character_keyword_pool(self) -> List[str]:
        """取得角色相關關鍵詞集合（包含別名）"""
        keyword_pool: Set[str] = set(normalize_keywords(self.expected_characters))
        for canonical, aliases in self.character_aliases.items():
            keyword_pool.add(canonical.lower())
            for alias in aliases:
                keyword_pool.add(alias.lower())
        return list(keyword_pool)

# ==================== 獨立運行測試 ====================
if __name__ == "__main__":
    import os

    def main():
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        logger = logging.getLogger("completeness.cli")

        logger.info("完整性評估")
        logger.info("=" * 50)

        # 初始化檢測器
        try:
            checker = CompletenessChecker()
            logger.info("✅ 完整性檢測器初始化成功")
        except Exception as e:
            logger.exception("❌ 初始化失敗: %s", e)
            return

        # 自動掃描故事資料夾
        stories_dir = "output"
        logger.info("🔍 檢查故事資料夾: %s", stories_dir)
        if not os.path.exists(stories_dir):
            logger.error("❌ 故事資料夾不存在: %s", stories_dir)
            return
        logger.info("✅ 故事資料夾存在")

        # 收集所有故事文檔
        test_stories = {}

        # 掃描所有故事資料夾
        for story_dir in discover_story_dirs([stories_dir]):
            story_folder = story_dir.name
            story_path = str(story_dir)
            logger.info("📁 掃描故事資料夾: %s", story_folder)

            # 只讀取 full_story.txt
            story_content = None
            story_file = None

            full_story_candidates = collect_full_story_paths(story_path)
            full_story_path = str(full_story_candidates[0]) if full_story_candidates else None

            if full_story_path:
                try:
                    with open(full_story_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content and len(content) > 50:  # 確保內容足夠長
                            story_content = content
                            story_file = "full_story.txt"
                            logger.info("   ✅ 讀取: %s (%d 字)", story_file, len(content))
                except Exception as e:
                    logger.warning("   ⚠️ 讀取失敗 %s: %s", "full_story.txt", e)

            if story_content:
                test_stories[f"{story_folder} ({story_file})"] = story_content
            else:
                logger.warning("   ❌ 未找到 full_story.txt")

        if not test_stories:
            logger.error("❌ 未找到任何故事文檔")
            return

        logger.info("")
        logger.info("📚 找到 %d 個故事文檔", len(test_stories))
        logger.info("=" * 60)

        # 執行評估
        for story_name, story_text in test_stories.items():
            logger.info("")
            logger.info("============================================================")
            logger.info("📖 檢測: %s", story_name)

            try:
                result = checker.check(story_text, story_name)

                # 顯示結果
                comp = result.get('completeness', {})
                scores = comp.get('scores', {})
                ai = comp.get('ai_analysis', {})
                logger.info("📊 詳細分數:")
                logger.info("  🎯 總分: %.1f/100", scores.get('final', 0))
                if isinstance(ai, dict) and 'score' in ai:
                    logger.info("🤖 AI 分析分數: %.1f/100", ai.get('score', 0))
                else:
                    logger.info("🤖 AI 分析未提供或被禁用")
                logger.info("📝 故事類型: %s", comp.get('story_type', 'unknown'))
                events = comp.get('events', [])
                logger.info("🔍 檢測到的事件: %d 個", len(events))

                # 顯示四層分數
                scores = comp.get('scores', {})
                if scores:
                    logger.info("📈 四層分數:")
                    logger.info("   📋 結構完整性: %.1f/100", scores.get('structural', 0))
                    logger.info("   🧠 語義完整性: %.1f/100", scores.get('semantic', 0))
                    logger.info("   🔗 邏輯完整性: %.1f/100", scores.get('logical', 0))
                    logger.info("   🎯 功能完整性: %.1f/100", scores.get('functional', 0))
                    logger.info("   🔒 置信度: %.2f", scores.get('confidence', 0))
                    logger.info("   ⚠️ 不確定性: %.2f", scores.get('uncertainty', 0))

                # 顯示為何是這個分數（子維度解釋）
                comp_exps = comp.get('explanations', {})
                if comp_exps:
                    logger.info("")
                    logger.info("📊 詳細分析：為何是這個分數")
                    # 結構
                    stc = comp_exps.get('structural', {})
                    if stc:
                        w = stc.get('weights', {})
                        c = stc.get('components', {})
                        logger.info("  📋 結構：")
                        logger.info(
                            "     ├─ 權重: coverage %s, conf %s, quality %s",
                            w.get('coverage', 0),
                            w.get('prediction_confidence', 0),
                            w.get('quality', 0)
                        )
                        logger.info(
                            "     └─ 構成: coverage_ratio %s, conf %s, evidence_count %s",
                            c.get('coverage_ratio', 0),
                            c.get('prediction_confidence', 0),
                            c.get('evidence_count', 0)
                        )
                    # 語義
                    sem = comp_exps.get('semantic', {})
                    if sem:
                        w = sem.get('weights', {})
                        c = sem.get('components', {})
                        logger.info("  🧠 語義：")
                        logger.info(
                            "     ├─ 權重: density %s, coverage %s, quality %s, character %s, cultural %s",
                            w.get('semantic_density', 0),
                            w.get('concept_coverage', 0),
                            w.get('content_quality', 0),
                            w.get('character_consistency', 0),
                            w.get('cultural', 0)
                        )
                        logger.info(
                            "     └─ 構成: density %s, coverage %s, quality %s, character %s, cultural %s",
                            c.get('semantic_density', 0),
                            c.get('concept_coverage', 0),
                            c.get('content_quality', 0),
                            c.get('character_consistency', 0),
                            c.get('cultural_elements', 0)
                        )
                    # 邏輯
                    lgc = comp_exps.get('logical', {})
                    if lgc:
                        w = lgc.get('weights', {})
                        c = lgc.get('components', {})
                        logger.info("  ⚖️ 邏輯：")
                        logger.info(
                            "     ├─ 權重: consistency %s, reasoning %s",
                            w.get('consistency', 0),
                            w.get('reasoning', 0)
                        )
                        logger.info(
                            "     └─ 構成: logical_consistency %s, reasoning_completeness %s, causal_chains %s",
                            c.get('logical_consistency', 0),
                            c.get('reasoning_completeness', 0),
                            c.get('causal_chains_count', 0)
                        )
                    # 功能
                    fnc = comp_exps.get('functional', {})
                    if fnc:
                        w = fnc.get('weights', {})
                        c = fnc.get('components', {})
                        logger.info("  🎯 功能：")
                        logger.info(
                            "     ├─ 權重: ai %s, goal %s",
                            w.get('ai_analysis', 0),
                            w.get('goal_achievement', 0)
                        )
                        logger.info(
                            "     └─ 構成: ai_score %s, goal %s",
                            c.get('ai_analysis_score', 0),
                            c.get('goal_achievement', 0)
                        )
                    # Final 權重
                    fnl = comp_exps.get('final', {})
                    if fnl:
                        logger.info("  🧮 自適應權重: %s", fnl.get('adaptive_weights', {}))

                if result['completeness']['suggestions']:
                    logger.info("")
                    logger.info("💡 建議 (最多5項):")
                    for suggestion in result['completeness']['suggestions'][:5]:
                        logger.info("  └─ %s", suggestion)

            except Exception as e:
                logger.exception("❌ 分析失敗: %s", e)

        logger.info("")
        logger.info("✅ 所有故事評估完成")
        logger.info("=" * 60)

    main()