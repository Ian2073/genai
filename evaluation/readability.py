# readability.py - 六維度故事評估系統 - 可讀性維度
# 用途：評估兒童故事的語言表達品質（非年齡適配度）
# 
# 核心理念：評估「兒童故事語言規範符合度」
# - 不評估「適不適合X歲」
# - 評估「是否符合優質兒童故事的語言標準」
# 
# 評分標準（基於兒童文學研究）：
# 1. 詞彙品質（30%）：精準、具象、生動 vs 抽象、模糊、成人化
# 2. 句法品質（30%）：清晰、長短交替、易朗讀 vs 冗長、破碎
# 3. 表達品質（25%）：符合兒童故事特點（對話、感官、動作）vs 枯燥說教
# 4. 認知友好度（15%）：資訊密度適中、邏輯清晰 vs 過載或過薄
# 
# 年齡組處理：
# - 自動偵測語言複雜度 → 推薦適讀年齡（輔助信息）
# - 評分不受年齡影響，純粹基於語言品質
import logging
import re
import math
import json
import numpy as np
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
from consistency import ComprehensiveKnowledgeGraph, AIAnalyzer
from utils import (
    SentenceSplitterMixin,
    ensure_instance,
    get_default_model_path,
    get_kg_path,
    load_spacy_model,
)
from shared.ai_safety import (
    get_dimension_fallback_score,
    normalize_confidence_0_1,
    normalize_score_0_100,
)


logger = logging.getLogger(__name__)

READABILITY_AI_FALLBACK_SCORE = get_dimension_fallback_score("readability")

@dataclass
class ChildrenReadabilityScores:
    vocabulary_appropriateness: float    # 詞彙適宜性
    sentence_simplicity: float          # 句法簡潔性
    cognitive_load: float               # 認知負荷
    final: float

@dataclass
class ReadabilityIssue:
    issue_type: str
    location: str
    description: str
    severity: str
    suggestions: List[str]
    examples: Optional[List[str]] = None

class ReadabilityChecker(SentenceSplitterMixin):
    # 可讀性檢測器（六維度故事評估系統 - 兒童可讀性維度）
    
    def __init__(self, 
                 kg_path: str = get_kg_path(),
                 model_path: str = get_default_model_path("Qwen2.5-14B"),
                 target_age_group: Optional[str] = None,
                 use_multiple_ai_prompts: bool = False,
                 ai: AIAnalyzer = None,
                 kg: ComprehensiveKnowledgeGraph = None,
                 nlp=None):
        try:
            self.kg = ensure_instance(kg, ComprehensiveKnowledgeGraph, kg_path)
        except Exception as exc:  # 允許回退到基礎功能
            self.kg = None
            logger.warning("⚠️ 知識圖譜載入失敗，將使用基礎功能: %s", exc)
        
        try:
            # 嘗試載入AI分析器（用於深度評估）
            self.ai = ensure_instance(ai, AIAnalyzer, model_path, use_multiple_ai_prompts)
        except Exception as exc:  # 回退到基礎評分邏輯
            self.ai = None
            logger.warning("⚠️ AI模型載入失敗，將使用基礎評分: %s", exc)
            
        # 載入語言處理工具
        self.nlp = ensure_instance(nlp, load_spacy_model)
        # 起始不預設年齡組，先以文本自動偵測；若偵測失敗再回退
        self.target_age_group = target_age_group
        
        # 🎯 兒童年齡分級配置（基於科學研究：Chall 1983, Sulzby 1985, 兒童發展心理學）
        # 參考：Chall的閱讀發展六階段理論、Dolch & Fry詞彙研究、兒童認知發展研究
        self.age_group_configs = {
            "children_2_4": {  # 2-4歲 (前閱讀期 - Pre-reading Stage)
                "name": "前閱讀期",
                "vocabulary_size": 1000,  # 基於兒童早期詞彙發展研究
                "max_sentence_length": 6,  # 基於兒童早期語言發展研究
                "max_syllables_per_word": 1.5,  # 基於兒童音韻意識發展
                "max_difficult_words_ratio": 0.03,  # 基於Dolch Pre-K詞彙研究
                "preferred_structures": ["重複循環式", "韻律式"],
                "weight_distribution": {"vocabulary": 0.60, "sentence": 0.30, "cognitive": 0.10},
                "target_flesch_score": 100,  # 基於Flesch可讀性研究
                "forbidden_concepts": ["death", "violence", "complex emotions", "abstract concepts"],
                "min_vocabulary_score": 35,
                "min_sentence_score": 55,
                "min_structure_score": 35,
                "min_fun_score": 45,
                "min_cognitive_score": 65
            },
            "children_4_6": {  # 4-6歲 (閱讀萌發期 - Emergent Reading Stage)
                "name": "閱讀萌發期",
                "vocabulary_size": 2000,  # 基於Sulzby閱讀萌發量表研究
                "max_sentence_length": 10,  # 基於兒童語言發展里程碑
                "max_syllables_per_word": 2.0,  # 基於兒童音韻意識發展
                "max_difficult_words_ratio": 0.08,  # 基於Dolch K-1詞彙研究
                "preferred_structures": ["簡單三段式", "重複模式"],
                "weight_distribution": {"vocabulary": 0.50, "sentence": 0.35, "cognitive": 0.15},
                "target_flesch_score": 90,  # 基於Flesch可讀性研究
                "forbidden_concepts": ["abstract philosophy", "complex psychology", "mature themes"],
                "min_vocabulary_score": 30,
                "min_sentence_score": 50,
                "min_structure_score": 40,
                "min_fun_score": 40,
                "min_cognitive_score": 60
            },
            "children_7_8": {  # 7-8歲 (初級閱讀期 - Early Reading Stage)
                "name": "初級閱讀期",
                "vocabulary_size": 4000,  # 基於Chall閱讀發展階段理論
                "max_sentence_length": 15,  # 基於兒童閱讀理解發展研究
                "max_syllables_per_word": 2.5,  # 基於兒童詞彙發展研究
                "max_difficult_words_ratio": 0.12,  # 基於Dolch 2-3詞彙研究
                "preferred_structures": ["完整故事弧", "簡單敘述"],
                "weight_distribution": {"vocabulary": 0.45, "sentence": 0.35, "cognitive": 0.20},
                "target_flesch_score": 80,  # 基於Flesch可讀性研究
                "forbidden_concepts": ["mature themes", "complex social issues", "violence"],
                "min_vocabulary_score": 25,
                "min_sentence_score": 40,
                "min_structure_score": 50,
                "min_fun_score": 35,
                "min_cognitive_score": 50
            },
            "children_9_10": {  # 9-10歲 (流暢閱讀期 - Fluent Reading Stage)
                "name": "流暢閱讀期",
                "vocabulary_size": 6000,  # 基於Chall閱讀發展階段理論
                "max_sentence_length": 20,  # 基於兒童閱讀理解發展研究
                "max_syllables_per_word": 3.0,  # 基於兒童詞彙發展研究
                "max_difficult_words_ratio": 0.15,  # 基於Fry 1000詞彙研究
                "preferred_structures": ["完整故事弧", "複雜敘述"],
                "weight_distribution": {"vocabulary": 0.40, "sentence": 0.35, "cognitive": 0.25},
                "target_flesch_score": 70,  # 基於Flesch可讀性研究
                "forbidden_concepts": ["mature themes", "complex social issues"],
                "min_vocabulary_score": 20,
                "min_sentence_score": 35,
                "min_structure_score": 55,
                "min_fun_score": 30,
                "min_cognitive_score": 45
            }
        }
        
        # 📚 兒童年齡分級詞彙庫 (基於科學研究：Dolch 1936, Fry 1980, 兒童詞彙發展研究)
        # 參考：Dolch Sight Words研究、Fry Instant Words研究、兒童詞彙習得研究
        self.children_vocabulary_levels = {
            "dolch_pre_k": {  # 2-4歲核心詞彙 (基於Dolch Pre-Primer研究)
                "sight_words": ["a", "and", "away", "big", "blue", "can", "come", "down", "find", "for", "funny", "go", "help", "here", "I", "in", "is", "it", "jump", "little", "look", "make", "me", "my", "not", "one", "play", "red", "run", "said", "see", "the", "three", "to", "two", "up", "we", "where", "yellow", "you"],
                "basic_nouns": ["cat", "dog", "mom", "dad", "car", "book", "ball", "toy", "house", "tree", "sun", "moon"],  # 基於兒童早期詞彙習得研究
                "simple_verbs": ["run", "jump", "eat", "sleep", "play", "look", "go", "come", "sit", "walk"],  # 基於兒童動作詞彙發展研究
                "basic_adjectives": ["good", "bad", "happy", "sad", "big", "small", "hot", "cold", "fast", "slow"]  # 基於兒童形容詞習得研究
            },
            "dolch_k_1": {  # 4-6歲擴展詞彙 (基於Dolch Primer & First Grade研究)
                "sight_words": ["all", "am", "are", "at", "ate", "be", "black", "brown", "but", "came", "did", "do", "eat", "four", "get", "good", "have", "he", "into", "like", "must", "new", "no", "now", "on", "our", "out", "please", "pretty", "ran", "ride", "saw", "say", "she", "so", "soon", "that", "there", "they", "this", "too", "under", "want", "was", "well", "went", "what", "white", "who", "will", "with", "yes"],
                "emotion_words": ["excited", "surprised", "worried", "brave", "proud", "kind", "gentle", "cheerful"],  # 基於兒童情緒詞彙發展研究
                "story_words": ["adventure", "magic", "forest", "castle", "treasure", "friend", "journey", "wonder"],  # 基於兒童故事詞彙研究
                "descriptive": ["beautiful", "wonderful", "enormous", "tiny", "bright", "dark", "quiet", "loud"]  # 基於兒童描述性詞彙研究
            },
            "dolch_2_3": {  # 7-8歲進階詞彙 (基於Dolch Second & Third Grade研究)
                "sight_words": ["about", "after", "again", "air", "also", "another", "answer", "any", "around", "ask", "back", "before", "boy", "call", "change", "different", "end", "even", "follow", "form", "found", "give", "great", "hand", "help", "here", "home", "house", "just", "kind", "know", "large", "last", "leave", "left", "line", "little", "live", "man", "may", "men", "might", "move", "much", "name", "need", "never", "new", "number", "old", "only", "other", "our", "over", "own", "part", "people", "place", "point", "put", "right", "same", "say", "school", "seem", "should", "show", "small", "sound", "still", "such", "take", "tell", "than", "them", "these", "thing", "think", "through", "time", "try", "turn", "us", "use", "very", "want", "water", "way", "well", "were", "what", "where", "which", "while", "work", "world", "would", "write", "year", "you", "your"],
                "high_frequency": ["about", "after", "again", "air", "also", "another", "answer", "any", "around", "ask", "back", "before", "boy", "call", "change", "different", "end", "even", "follow", "form", "found", "give", "great", "hand", "help", "here", "home", "house", "just", "kind", "know", "large", "last", "leave", "left", "line", "little", "live", "man", "may", "men", "might", "move", "much", "name", "need", "never", "new", "number", "old", "only", "other", "our", "over", "own", "part", "people", "place", "point", "put", "right", "same", "say", "school", "seem", "should", "show", "small", "sound", "still", "such", "take", "tell", "than", "them", "these", "thing", "think", "through", "time", "try", "turn", "us", "use", "very", "want", "water", "way", "well", "were", "what", "where", "which", "while", "work", "world", "would", "write", "year", "you", "your"],
                "complex_concepts": ["friendship", "responsibility", "courage", "mystery", "discovery", "imagination"],  # 基於兒童抽象概念發展研究
                "rich_adjectives": ["magnificent", "peculiar", "tremendous", "delightful", "marvelous", "extraordinary"]  # 基於兒童高級形容詞研究
            },
            "fry_1000": {  # 9-10歲高級詞彙 (基於Fry Instant Words研究)
                "sight_words": ["about", "after", "again", "air", "also", "America", "another", "answer", "any", "around", "ask", "back", "before", "boy", "call", "change", "different", "end", "even", "follow", "form", "found", "give", "great", "hand", "help", "here", "home", "house", "just", "kind", "know", "large", "last", "leave", "left", "line", "little", "live", "man", "may", "men", "might", "move", "much", "name", "need", "never", "new", "number", "old", "only", "other", "our", "over", "own", "part", "people", "place", "point", "put", "right", "same", "say", "school", "seem", "should", "show", "small", "sound", "still", "such", "take", "tell", "than", "them", "these", "thing", "think", "through", "time", "try", "turn", "us", "use", "very", "want", "water", "way", "well", "were", "what", "where", "which", "while", "work", "world", "would", "write", "year", "you", "your"],
                "high_frequency": ["about", "after", "again", "air", "also", "America", "another", "answer", "any", "around", "ask", "back", "before", "boy", "call", "change", "different", "end", "even", "follow", "form", "found", "give", "great", "hand", "help", "here", "home", "house", "just", "kind", "know", "large", "last", "leave", "left", "line", "little", "live", "man", "may", "men", "might", "move", "much", "name", "need", "never", "new", "number", "old", "only", "other", "our", "over", "own", "part", "people", "place", "point", "put", "right", "same", "say", "school", "seem", "should", "show", "small", "sound", "still", "such", "take", "tell", "than", "them", "these", "thing", "think", "through", "time", "try", "turn", "us", "use", "very", "want", "water", "way", "well", "were", "what", "where", "which", "while", "work", "world", "would", "write", "year", "you", "your"],
                "complex_concepts": ["friendship", "responsibility", "courage", "mystery", "discovery", "imagination"],  # 基於兒童高級概念發展研究
                "rich_adjectives": ["magnificent", "peculiar", "tremendous", "delightful", "marvelous", "extraordinary"]  # 基於兒童高級形容詞研究
            }
        }
        
        # 🎨 語言趣味性元素庫
        self.language_fun_elements = {
            "rhyme_patterns": {
                "simple_rhymes": [("cat", "hat"), ("big", "pig"), ("run", "fun"), ("play", "day"), ("see", "tree")],
                "alliteration": ["Peter Piper", "Sally sells", "big brown bear", "little lost lamb"],
                "sound_words": ["meow", "woof", "splash", "bang", "whoosh", "buzz", "chirp", "roar"]
            },
            "repetition_patterns": {
                "cumulative": ["This is the house that Jack built", "There was an old lady who swallowed a fly"],
                "responsive": ["Brown Bear, Brown Bear, what do you see?", "Chicka Chicka Boom Boom"],
                "rhythmic": ["Row, row, row your boat", "Twinkle, twinkle, little star"]
            },
            "sensory_vocabulary": {
                "visual": ["bright", "colorful", "shiny", "sparkly", "glittery", "rainbow", "golden", "silver"],
                "auditory": ["whisper", "shout", "giggle", "thunder", "tinkle", "crash", "rustle"],
                "tactile": ["soft", "rough", "smooth", "bumpy", "fluffy", "sticky", "warm", "cool"],
                "emotional": ["joyful", "peaceful", "cozy", "exciting", "magical", "wonderful"]
            }
        }
        
        # 🚫 困難詞彙列表
        self.difficult_words = {
            "academic": ["phenomenon", "hypothesis", "analysis", "synthesis", "evaluation", "methodology"],
            "abstract": ["consciousness", "philosophy", "ideology", "metaphysics", "existential"],
            "technical": ["algorithm", "infrastructure", "configuration", "optimization", "implementation"],
            "formal": ["nevertheless", "furthermore", "consequently", "therefore", "moreover", "however"],
            "long_words": ["beautiful", "wonderful", "incredible", "fantastic", "amazing", "terrible",
                          "delicious", "dangerous", "important", "interesting", "comfortable",
                          "impossible", "responsible", "necessary", "different", "difficult",
                          "remember", "understand", "everything", "everybody", "anything",
                          "adventure", "discovery", "mysterious", "magical", "extraordinary"]
        }
        
        # 📄 可讀性評估文檔選擇矩陣
        self.document_selection_matrix = {
            'primary': ['full_story.txt'],
            'secondary': [],
            'optional': [],
            'excluded': [],
            'weights': {
                'full_story.txt': 1.0
            }
        }
    
    def get_documents_for_readability(self, available_documents: Dict[str, str]) -> Dict[str, str]:
        # 挑選適合做可讀性分析的文檔（主要文檔優先 → 次要文檔補充）
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
        
        # 添加可選文檔（如果存在）
        for doc_name in self.document_selection_matrix['optional']:
            if doc_name in available_documents and doc_name not in selected_docs:
                selected_docs[doc_name] = available_documents[doc_name]
        
        return selected_docs
    
    def get_document_weights_for_readability(self) -> Dict[str, float]:
        # 回傳各類文檔在可讀性評估中的權重比例
        return self.document_selection_matrix['weights']
    
    def check(self, story_text: str, story_title: str = "Story", 
              dialogue_text: str = None, narration_text: str = None,
              target_age: Optional[str] = None) -> Dict:
        # 兒童故事可讀性總檢測（詞彙/句法/結構/趣味/認知 五維度評分）
        # 簡單流程：
        # 1) 決定年齡組（指定 > KG 推斷 > 自動偵測 > 動態回退）
        # 2) 詞彙/句法/認知 三項客觀指標 + 表達品質（趣味）
        # 3) 若可用，加入 AI 的補充分析
        # 4) 對齊全域分布，生成建議與適讀年齡
        
        # 🎯 若提供 target_age，優先使用；否則才自動偵測
        if target_age:
            age_str = str(target_age).strip()
            try:
                if '-' in age_str:
                    low, high = age_str.split('-', 1)
                    avg_age = (int(low) + int(high)) / 2
                else:
                    avg_age = float(age_str)
            except Exception:
                avg_age = None
            if avg_age is not None:
                if avg_age <= 3.5:  # 2-3歲歸類到2-4歲組
                    self.target_age_group = "children_2_4"
                elif avg_age <= 6.5:  # 4-6歲歸類到4-6歲組
                    self.target_age_group = "children_4_6"
                elif avg_age <= 8.5:  # 7-8歲歸類到7-8歲組
                    self.target_age_group = "children_7_8"
                else:  # 9歲以上歸類到9-10歲組
                    self.target_age_group = "children_9_10"
                logger.info("🎯 以指定年齡 %s 評估 → 年齡組: %s", age_str, self.target_age_group)
        # 統一年齡偵測流程：story_settings.txt > 使用者指定 > KG 推斷 > 文本特徵
        if not self.target_age_group:
            # 先嘗試從 KG 推斷（若可用）
            kg_reader = self._extract_target_reader_from_kg()
            if kg_reader and isinstance(kg_reader, dict) and kg_reader.get('suggested_group'):
                self.target_age_group = kg_reader['suggested_group']
            if not self.target_age_group:
                children_indices = self._calculate_children_readability_indices(story_text)
                # 暫存供最終評分動態權重使用
                try:
                    self._last_children_indices = children_indices
                except Exception:
                    pass
                detected_age_group = children_indices.get('recommended_age_group')
                if detected_age_group:
                    logger.info("🔍 自動檢測年齡組: %s", detected_age_group)
                    self.target_age_group = detected_age_group
                else:
                    # 動態預設：依 Flesch/FKGL 設定更直觀的預設年齡
                    flesch = children_indices.get('flesch_score', 0)
                    fkgl = children_indices.get('fkgl_score', 99)
                    if flesch >= 85 and fkgl <= 2.5:
                        fallback = "children_4_6"
                    elif flesch >= 70 or fkgl <= 4.5:
                        fallback = "children_7_8"
                    else:
                        fallback = "children_9_10"
                    logger.warning("⚠️ 自動檢測失敗，動態回退年齡組: %s", fallback)
                    self.target_age_group = fallback
        
        # 🎯 獲取知識圖譜中的目標讀者信息
        target_reader_info = self._extract_target_reader_from_kg()
        
        # 📚 1) 詞彙適宜性分析
        vocab_score, vocab_issues = self._analyze_vocabulary_appropriateness(story_text)
        
        # ✏️ 2) 句法簡潔性分析
        sentence_score, sentence_issues = self._analyze_sentence_simplicity(story_text)
        
        # 已改為專注年齡適配：移除結構與趣味性分析
        structure_issues = []
        fun_issues = []
        
        # 🧠 5) 認知負荷分析
        cognitive_score, cognitive_issues = self._analyze_cognitive_load(story_text)
        
        # 🤖 6) AI 深度分析
        ai_analysis = self._advanced_children_ai_analysis(story_text)
        
        # 📊 7) 兒童可讀性指數計算（只計算一次）
        children_indices = self._calculate_children_readability_indices(story_text)
        
        # 🎯 8) 綜合評分 (基於語言品質，不受年齡組影響)
        # 重新啟用 fun_score 作為表達品質維度
        fun_score, fun_issues = self._analyze_language_fun(story_text)
        
        final_score = self._calculate_children_final_score(
            vocab_score, sentence_score, 0.0, fun_score, cognitive_score, ai_analysis
        )
        
        # 全域對齊校準（讓可讀性與其他模組分布更一致）
        final_score_aligned = self._calibrate_for_global_alignment(final_score, vocab_score, sentence_score, cognitive_score, children_indices)

        multilingual_note = None
        final_score_aligned, multilingual_note = self._apply_multilingual_readability_calibration(
            story_text,
            final_score_aligned,
            sentence_score,
            cognitive_score,
            fun_score,
        )
        
        # 💡 9) 生成兒童友好的改進建議
        all_issues = vocab_issues + sentence_issues + cognitive_issues
        suggestions = self._generate_children_suggestions(all_issues, ai_analysis, children_indices)
        if multilingual_note:
            suggestions.append(multilingual_note)
        
        # 📋 10) 年齡組推薦（輔助信息，不影響評分）
        age_recommendation = self._assess_age_appropriateness(final_score_aligned, children_indices)
        
        # 品質分群（與其他模組對齊）
        if final_score_aligned >= 80:
            quality_band = "excellent"
        elif final_score_aligned >= 65:
            quality_band = "good"
        elif final_score_aligned >= 50:
            quality_band = "fair"
        else:
            quality_band = "poor"
        
        # 表達極弱保護（避免表達 20-30 但總分偏高的情況）
        try:
            if fun_score < 30 and sentence_score < 65:
                final_score_aligned = max(0.0, final_score_aligned - 4.0)
        except Exception:
            pass
        
        return {
            "meta": {
                "version": "3.0_quality_based_readability",
                "story_title": story_title,
                "evaluation_focus": "語言表達品質（非年齡適配）",
                "word_count": len(story_text.split()),
                "sentence_count": len(self._split_sentences(story_text)),
                "ai_available": self.ai.model_available if self.ai else False,
                "multilingual_calibration": multilingual_note
            },
            "children_readability": {
                "scores": {
                    "vocabulary_quality": round(vocab_score, 1),
                    "sentence_quality": round(sentence_score, 1),
                    "expression_quality": round(fun_score, 1),
                    "cognitive_friendliness": round(cognitive_score, 1),
                    "final": round(final_score_aligned, 1),
                    "confidence": round(
                        normalize_confidence_0_1(ai_analysis.get("confidence", 0.6), 0.6),
                        3,
                    ),
                },
                "quality_band": quality_band,
                "language_indices": children_indices,
                "age_recommendation": age_recommendation,
                "issues": {
                    "vocabulary": vocab_issues,
                    "sentence": sentence_issues,
                    "expression": fun_issues,
                    "cognitive": cognitive_issues,
                    "total_issues": len(all_issues) + len(fun_issues)
                },
                "ai_analysis": ai_analysis,
                "suggestions": suggestions,
                "benchmark_comparison": self._compare_with_benchmarks(final_score_aligned, children_indices)
            }
        }

    def _calibrate_for_global_alignment(self, final_score: float, vocab_score: float, sentence_score: float, cognitive_score: float, indices: Dict) -> float:
        """讓可讀性最終分與其他模組（coherence/completeness/consistency）分布更一致。
        策略：
        - 針對 4–6 歲：高 Flesch 且低 FKGL 給微幅加成
        - 句法/詞彙雙優給小幅加成
        - 認知負荷高（越易讀）給微幅加成
        - 整體小幅拉伸，使 60 上下的文本更易分流
        """
        score = final_score
        flesch = indices.get('flesch_score', 0.0)
        fkgl = indices.get('fkgl_score', 99.0)
        
        # 易讀文本加成
        if flesch >= 85 and fkgl <= 3.0:
            score += 2.0
        
        # 句法+詞彙雙優
        if sentence_score >= 75 and vocab_score >= 65:
            score += 1.2
        
        # 認知負荷越高（代表越易讀），適度加成
        if cognitive_score >= 95:
            score += 0.8
        
    # 中段拉伸（以 60 為中心輕拉伸）
        delta = score - 60.0
        score += 0.18 * delta
        
        # 針對破碎文本的負向校準（平均句長過短或極短句比例過高）
        avg_len = indices.get('avg_sentence_length')
        short_ratio = indices.get('very_short_ratio')
        if (avg_len is not None and avg_len < 8.0) or (short_ratio is not None and short_ratio > 0.5):
            # 最多下調 6 分，與句法權重配合（放寬對兒童短句型的懲罰）
            penalty = 0.0
            if avg_len is not None and avg_len < 8.0:
                penalty += min(4.0, (8.0 - avg_len) * 0.4)
            if short_ratio is not None and short_ratio > 0.5:
                penalty += min(4.0, (short_ratio - 0.5) * 8.0)
            score -= min(6.0, penalty)
        
        # 裁剪
        return round(max(15.0, min(95.0, score)), 1)

    def _apply_multilingual_readability_calibration(
        self,
        text: str,
        score: float,
        sentence_score: float,
        cognitive_score: float,
        expression_score: float,
    ) -> Tuple[float, Optional[str]]:
        """針對 CJK 主導文本做溫和校準，避免英語指標造成過度低估。"""
        if not text:
            return score, None

        cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))
        latin_chars = len(re.findall(r'[A-Za-z]', text))
        if cjk_chars < 80 or cjk_chars <= (latin_chars * 1.5):
            return score, None

        # CJK 文本無空白分詞時，英文導向詞彙指標偏嚴，這裡僅做底線保護。
        floor = 30.0
        floor += min(12.0, max(0.0, sentence_score) * 0.14)
        floor += min(8.0, max(0.0, cognitive_score) * 0.08)
        floor += min(7.0, max(0.0, expression_score) * 0.10)
        floor = max(32.0, min(58.0, floor))

        adjusted = max(score, floor)
        if adjusted > score + 0.1:
            note = f"已套用多語言校準（CJK 主導文本），可讀性底線調整至 {adjusted:.1f} 分。"
            return round(adjusted, 1), note
        return score, None
    
    # =============== 輔助方法實現 ===============
    
    def _extract_target_reader_from_kg(self) -> Dict:
        """從知識圖譜中提取目標讀者信息"""
        if not self.kg:
            return {
                "detected_age_range": "unknown",
                "suggested_group": self.target_age_group,
                "confidence": "low"
            }
            
        try:
            # 讀取角色信息來推斷目標讀者年齡
            characters_file = f"{self.kg.kg_path}/characters.json"
            with open(characters_file, 'r', encoding='utf-8') as f:
                characters_data = json.load(f)
            
            # 分析主要角色年齡群來推斷目標讀者
            main_characters = characters_data.get("relationships", {})
            child_characters = [name for name, info in main_characters.items() 
                              if info.get("type") == "child"]
            
            if child_characters:
                # 根據角色年齡推斷目標讀者
                sample_char = main_characters[child_characters[0]]
                age_range = sample_char.get("age_range", "4-6 years old")
                
                if "4-6" in age_range:
                    suggested_group = "children_4_6"
                elif "6-8" in age_range:
                    suggested_group = "children_7_8"
                elif "8-10" in age_range:
                    suggested_group = "children_9_10"
            else:
                    suggested_group = "children_4_6"
                
            return {
                    "detected_age_range": age_range,
                    "suggested_group": suggested_group,
                    "main_characters": child_characters,
                    "confidence": "high" if len(child_characters) > 0 else "medium"
                }
        except Exception as e:
            pass
        
        return {
            "detected_age_range": "unknown",
            "suggested_group": self.target_age_group,
            "confidence": "low"
        }
    
    def _analyze_vocabulary_appropriateness(self, text: str) -> Tuple[float, List[ReadabilityIssue]]:
        """分析詞彙適宜性 - 基於年齡分級詞彙庫"""
        words = re.findall(r'\b\w+\b', text.lower())
        issues = []
        
        config = self.age_group_configs.get(self.target_age_group, self.age_group_configs["children_4_6"])
        
        # 獲取年齡適宜詞彙
        age_appropriate_words = set()
        if "2_4" in self.target_age_group:
            vocab_level = self.children_vocabulary_levels["dolch_pre_k"]
        elif "4_6" in self.target_age_group:
            vocab_level = self.children_vocabulary_levels["dolch_k_1"]
            age_appropriate_words.update(self.children_vocabulary_levels["dolch_pre_k"]["sight_words"])
        elif "7_8" in self.target_age_group:
            vocab_level = self.children_vocabulary_levels["dolch_2_3"]
            age_appropriate_words.update(self.children_vocabulary_levels["dolch_pre_k"]["sight_words"])
            age_appropriate_words.update(self.children_vocabulary_levels["dolch_k_1"]["sight_words"])
        else:  # 9-10歲
            vocab_level = self.children_vocabulary_levels["fry_1000"]
            age_appropriate_words.update(self.children_vocabulary_levels["dolch_pre_k"]["sight_words"])
            age_appropriate_words.update(self.children_vocabulary_levels["dolch_k_1"]["sight_words"])
            age_appropriate_words.update(self.children_vocabulary_levels["dolch_2_3"]["sight_words"])
        
        # 添加當前年齡級別的詞彙
        for category, word_list in vocab_level.items():
            age_appropriate_words.update(word_list)
        
        # 添加常見的基礎詞彙（更寬鬆的檢測）
        basic_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "must"}
        age_appropriate_words.update(basic_words)
        
        # 詞形還原與專有名詞豁免
        lemmas = []
        proper_nouns_set = set(re.findall(r'\b[A-Z][a-z]+\b', text))
        try:
            if getattr(self.nlp, "pipe_names", None) and words:
                doc = self.nlp(text)
                for token in doc:
                    # 僅統計字母詞
                    if token.text and token.text.strip().isalpha():
                        lemmas.append(token.lemma_.lower())
            else:
                # 後備：簡單 stemming 近似（移除常見結尾）
                suffixes = ("ing","ed","es","s")
                for w in words:
                    lw = w.lower()
                    for suf in suffixes:
                        if lw.endswith(suf) and len(lw) > len(suf) + 2:
                            lw = lw[: -len(suf)]
                            break
                    lemmas.append(lw)
        except Exception:
            lemmas = [w.lower() for w in words]

        # 拓展詞彙：允許稍具挑戰但可理解的詞
        extension_words = {
            "friendship","treasure","forest","castle","dragon","rainbow","mystery",
            "adventure","imagination","king","queen","prince","princess","kingdom",
            "palace","village","giant","dwarf","wizard","witch","spell","curse",
            "magic","magical","hero","heroine","journey","quest","rescue","brave",
            "courage","sacrifice","kindness","loyal","loyalty","forgive","forgiveness",
            "brother","sister","family","guardian","garden","river","mountain",
            "ocean","mermaid","beast","fairy","fairies","pixie","dream","wish","hope"
        }
        age_appropriate_lemmas = set(age_appropriate_words) | extension_words

        # 分析詞彙（專有名詞豁免 + 詞形還原後比對）
        unique_surface = set(words)
        unknown_words = []
        for w in unique_surface:
            if w in proper_nouns_set:
                continue
            lw = w.lower()
            lemma_ok = (lw in age_appropriate_lemmas)
            if not lemma_ok and lemmas:
                # 找到該詞第一個對應 lemma 進行比對
                # 簡化：直接以去尾綴版本再比對一次
                base = lw
                if base.endswith('e') and len(base) > 3:
                    base = base[:-1]
                lemma_ok = base in age_appropriate_lemmas
            if not lemma_ok:
                unknown_words.append(lw)

        unknown_ratio = len(set(unknown_words)) / len(unique_surface) if unique_surface else 0
        max_unknown_ratio = config["max_difficult_words_ratio"]

        target_group = self.target_age_group or ""
        penalized_categories = set(self.difficult_words.keys())
        if target_group in {"children_7_8", "children_9_10"} or "6_12" in target_group:
            penalized_categories.discard("long_words")

        # 檢查困難詞彙
        difficult_words = []
        for word in unknown_words:
            for category, word_list in self.difficult_words.items():
                if category not in penalized_categories:
                    continue
                if word in word_list:
                    difficult_words.append((word, category))
                    break
        
        # 達標率導向：已知詞比例直接成分，但給出更合理的基準
        known_ratio = max(0.0, 1.0 - unknown_ratio)

        tolerance_bonus = 0.0
        if target_group in {"children_7_8","children_9_10"} or any(k in str(target_group or "") for k in ["6_12","8_12","9_12"]):
            tolerance_bonus = 0.12
        elif target_group in {"children_4_6"}:
            tolerance_bonus = 0.05

        try:
            indices = getattr(self, "_last_children_indices", {}) or {}
        except Exception:
            indices = {}
        fkgl_score = indices.get("fkgl_score") if isinstance(indices, dict) else None
        if isinstance(fkgl_score, (int, float)):
            if fkgl_score >= 6.5:
                tolerance_bonus += 0.05
            elif fkgl_score >= 4.5:
                tolerance_bonus += 0.03

        tolerance_bonus = min(0.18, tolerance_bonus)
        effective_known_ratio = min(1.0, known_ratio + tolerance_bonus)
        
        # 設定合理的基準分數（而不是從0開始）
        if effective_known_ratio >= 0.90:
            vocabulary_score = 85 + (effective_known_ratio - 0.90) * 150  # 90%以上給85-100分
        elif effective_known_ratio >= 0.80:
            vocabulary_score = 70 + (effective_known_ratio - 0.80) * 150  # 80-90%給70-85分
        elif effective_known_ratio >= 0.70:
            vocabulary_score = 55 + (effective_known_ratio - 0.70) * 150  # 70-80%給55-70分
        else:
            vocabulary_score = 30 + effective_known_ratio * 357  # 70%以下給30-55分

        # 困難詞彙懲罰（基於兒童故事語言規範，而非年齡組）
        difficult_penalty = 0.0
        for _, category in difficult_words:
            if category == "long_words":
                difficult_penalty += 1.0
            elif category == "formal":
                difficult_penalty += 1.5
            else:
                difficult_penalty += 2.0
        difficult_penalty = min(10, difficult_penalty)

        # 長詞懲罰（僅針對年幼讀者）
        long_word_penalty = 0
        if target_group in {"children_2_4", "children_4_6"}:
            for word in words:
                if len(word) > 12:  # 超過12字母的詞不適合低齡兒童故事
                    long_word_penalty += 1
            long_word_penalty = min(8, long_word_penalty)
        
        # 具象詞彙獎勵（兒童故事應該多用具象、生動的詞彙）
        concrete_words = {'see', 'look', 'hear', 'touch', 'smell', 'taste', 'run', 'jump', 'walk', 
                         'play', 'happy', 'sad', 'big', 'small', 'red', 'blue', 'soft', 'hard'}
        concrete_count = sum(1 for w in words if w.lower() in concrete_words)
        concrete_bonus = min(5, concrete_count * 0.5)
        
        # ⚠️ 新增：詞彙多樣性檢測（Type-Token Ratio）
        unique_words = set(w.lower() for w in words if w.isalpha())
        ttr = len(unique_words) / len(words) if words else 0
        diversity_penalty = 0
        if ttr < 0.32:  # 詞彙過於重複
            diversity_penalty = min(10, (0.32 - ttr) * 25)
        elif ttr > 0.7:  # 詞彙多樣性佳
            concrete_bonus += 3

        # 極度不適合兒童故事的詞彙比例懲罰
        if effective_known_ratio < 0.60:
            vocabulary_score *= 0.7

        # 停用詞過高抑制與滿分抑制（避免表面易讀造成虛高）
        stop_words = {"the","a","an","and","or","but","to","in","on","at","of","is","are","was","were","it","that","this","with","as","for","by"}
        stop_count = sum(1 for w in words if w.lower() in stop_words)
        stop_ratio = (stop_count / len(words)) if words else 0.0
        if stop_ratio > 0.55:
            vocabulary_score *= 0.97
        # 上限抑制（非硬卡）：改用漸近封頂
        vocabulary_score = min(97.0, 90.0 + (vocabulary_score - 90.0) * 0.5) if vocabulary_score > 90.0 else vocabulary_score

        vocabulary_score = max(0, min(100, vocabulary_score - difficult_penalty - long_word_penalty - diversity_penalty + concrete_bonus))
        
        # 生成問題報告
        if unknown_ratio > max_unknown_ratio:
            issues.append(ReadabilityIssue(
                issue_type="vocabulary_too_advanced",
                location="全文",
                description=f"詞彙難度過高 ({unknown_ratio:.1%})",
                severity="high" if unknown_ratio > max_unknown_ratio * 2 else "medium",
                suggestions=["使用更簡單的詞彙", "參考 Dolch 詞表"],
                examples=unknown_words[:5]
            ))
        
        if difficult_words:
            issues.append(ReadabilityIssue(
                issue_type="difficult_vocabulary",
                location="全文",
                description=f"包含 {len(difficult_words)} 個困難詞彙",
                severity="medium",
                suggestions=["替換為更簡單的同義詞"],
                examples=[f"{word}({category})" for word, category in difficult_words[:3]]
            ))
        
        return vocabulary_score, issues
    
    def _analyze_sentence_simplicity(self, text: str) -> Tuple[float, List[ReadabilityIssue]]:
        """分析句法簡潔性（加入超長幅度與從句/被動懲罰）"""
        sentences = self._split_sentences(text)
        issues = []

        config = self.age_group_configs.get(self.target_age_group, self.age_group_configs["children_4_6"])
        max_length = config["max_sentence_length"]

        long_sent_penalty_sum = 0
        long_sent_examples = []
        problematic_count = 0
        per_sentence_penalties = [0] * len(sentences)
        for i, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            if word_count > max_length:
                excess = word_count - max_length
                add = min(6, excess * 0.5)  # 每超1詞扣0.5分，上限6（從1分降到0.5分）
                per_sentence_penalties[i] += add
                long_sent_penalty_sum += add
                if len(long_sent_examples) < 3:
                    long_sent_examples.append((i + 1, sentence))

        complexity_penalty_sum = 0
        try:
            if getattr(self.nlp, "pipe_names", None) and sentences:
                doc = self.nlp(text)
                for sent in doc.sents:
                    has_sub = any(t.dep_ in ["mark", "advcl", "ccomp"] for t in sent)
                    has_pass = any(t.dep_ == "auxpass" for t in sent)
                    add = 0
                    if has_sub:
                        add += 2  # 從4降到2，進一步降低從屬子句懲罰
                    if has_pass:
                        add += 1  # 從2降到1，進一步降低被動懲罰
                    # 單句總懲罰上限（長句+複雜度）
                    idx = getattr(sent, 'i', None)
                    # spaCy 不保證句索引連續，改以累積計數方式
                    # 將 per_sentence_penalties 中下一個非處理過的句子累加
                    # 為簡化，遍歷一次找第一個零或最小索引
                    if len(per_sentence_penalties) > 0:
                        for j in range(len(per_sentence_penalties)):
                            # 以順序近似對齊句段
                            if per_sentence_penalties[j] < 12 and per_sentence_penalties[j] >= 0:
                                per_sentence_penalties[j] = min(12, per_sentence_penalties[j] + add)
                                break
                    complexity_penalty_sum += add
        except Exception:
            pass

        # 問題句數量（有任何懲罰視為問題句）
        problematic_count = sum(1 for p in per_sentence_penalties if p > 0)

        # ⚠️ 新增：平均句長檢測（直接懲罰過短文本）
        if len(sentences) > 0:
            sent_lengths = [len(s.split()) for s in sentences]
            avg_sent_len = sum(sent_lengths) / len(sent_lengths)
        else:
            avg_sent_len = 10
            sent_lengths = []
        
        avg_length_penalty = 0
        if avg_sent_len < 8:  # 平均句長 < 8 詞
            # 放寬對短句的處罰：每少1詞罰5分，最高20分
            avg_length_penalty = min(20, (8 - avg_sent_len) * 5)
        
        # ⚠️ 極短句比例懲罰（更嚴格）
        very_short_sentences = [s for s in sentences if len(s.split()) < 6]
        short_ratio = len(very_short_sentences) / len(sentences) if sentences else 0
        fragmentation_penalty = 0
        if short_ratio > 0.5:  # 超過50%就開始懲罰（從0.7降到0.5）
            # 放寬：0.5-1.0 → 最高 18 分
            fragmentation_penalty = min(18, (short_ratio - 0.5) * 36)
        
        # ⚠️ 句長變化單調懲罰
        monotony_penalty = 0
        if len(sent_lengths) >= 3:
            import statistics
            try:
                std_dev = statistics.stdev(sent_lengths)
                mean_len = statistics.mean(sent_lengths)
                cv = std_dev / mean_len if mean_len > 0 else 0
                if cv < 0.3:
                    # 降低單調性懲罰
                    monotony_penalty = min(18, (0.3 - cv) * 45)
            except:
                pass

        # 計算總懲罰（全局問題直接累加，不平均化）
        per_sentence_penalty = long_sent_penalty_sum + complexity_penalty_sum
        if len(sentences) > 0:
            avg_per_sent = per_sentence_penalty / len(sentences)
            # 降低單句懲罰影響
            normalized_penalty = min(35, avg_per_sent * 6)
        else:
            normalized_penalty = min(35, per_sentence_penalty)
        
        # 全局懲罰直接加上（平均句長、極短句、單調性）
        total_penalty = min(80, normalized_penalty + avg_length_penalty + fragmentation_penalty + monotony_penalty)

        if total_penalty > 0:
            desc = []
            if avg_length_penalty > 0:
                desc.append(f"平均句長過短（{avg_sent_len:.1f} 詞/句）")
            if long_sent_penalty_sum > 0:
                desc.append(f"存在超長句（閾值 {max_length} 詞）")
            if complexity_penalty_sum > 0:
                desc.append("存在從屬子句/被動語態")
            if fragmentation_penalty > 0:
                desc.append(f"極短句過多（{short_ratio:.0%}）")
            if monotony_penalty > 0:
                desc.append("句長變化太小，單調")
            examples = [f"句子{idx}: {s[:50]}..." for idx, s in long_sent_examples]
            issues.append(ReadabilityIssue(
                issue_type="sentence_quality",
                location="全文",
                description="；".join(desc),
                severity="high" if total_penalty > 40 else "medium",
                suggestions=[f"保持句長適中且多樣（建議8-{max_length}詞/句），避免極短句堆疊"],
                examples=examples if examples else None
            ))

        # 設定合理的基準分數，更嚴格的懲罰
        if total_penalty == 0:
            sentence_score = 90  # 沒有問題給90分
        elif total_penalty <= 10:
            sentence_score = 80 - total_penalty * 0.8  # 輕微問題給72-80分
        elif total_penalty <= 25:
            sentence_score = 65 - (total_penalty - 10) * 1.2  # 中等問題給47-65分
        elif total_penalty <= 40:
            sentence_score = 40 - (total_penalty - 25) * 1.0  # 嚴重問題給25-40分
        else:
            sentence_score = 25 - (total_penalty - 40) * 0.5  # 極嚴重給10-25分
        
        sentence_score = max(10, min(95, sentence_score))
        return sentence_score, issues
    
    def _analyze_story_structure(self, text: str) -> Tuple[float, List[ReadabilityIssue]]:
        """分析故事結構"""
        issues = []
        
        # 改進的故事結構檢測
        text_lower = text.lower()
        sentences = self._split_sentences(text)
        
        # 檢測開始標記（更廣泛的開始詞彙）
        beginning_markers = ['once', 'one day', 'long ago', 'there was', 'there were', 'lived', 'emma', 'alex', 'tom', 'little', 'grandpa']
        has_beginning = any(marker in text_lower for marker in beginning_markers)
        
        # 檢測中間發展（更多發展標記）
        middle_markers = ['then', 'next', 'after', 'suddenly', 'but', 'however', 'decided', 'went', 'walked', 'met', 'found', 'discovered']
        has_middle = any(marker in text_lower for marker in middle_markers)
        
        # 檢測結尾（更多結尾標記）
        ending_markers = ['finally', 'at last', 'in the end', 'ever after', 'from then on', 'happy', 'learned', 'found', 'together', 'was very']
        has_ending = any(marker in text_lower for marker in ending_markers)
        
        # 檢測故事元素
        story_elements = 0
        
        # 角色介紹
        if any(name in text_lower for name in ['emma', 'alex', 'tom', 'character', 'little', 'grandpa']):
            story_elements += 1
        
        # 問題/衝突
        if any(word in text_lower for word in ['lost', 'problem', 'trouble', 'difficult', 'worried', 'scared']):
            story_elements += 1
        
        # 行動/解決
        if any(word in text_lower for word in ['went', 'walked', 'ran', 'searched', 'found', 'helped', 'decided']):
            story_elements += 1
        
        # 結果/學習
        if any(word in text_lower for word in ['happy', 'learned', 'discovered', 'together', 'finally', 'realized']):
            story_elements += 1
        
        # 計算結構分數
        structure_score = 0
        
        # 基本結構分數
        if has_beginning:
            structure_score += 25
        if has_middle:
            structure_score += 25
        if has_ending:
            structure_score += 25
        
        # 故事元素分數
        story_elements_score = min(25, story_elements * 6.25)  # 每個元素6.25分
        structure_score += story_elements_score
        
        # 對於短故事，降低要求
        if len(sentences) <= 3:
            structure_score = max(structure_score, 60)  # 短故事最低60分
        
        if structure_score < 50:
            issues.append(ReadabilityIssue(
                issue_type="unclear_structure",
                location="全文",
                description="故事結構不夠清晰",
                severity="medium",
                suggestions=["確保有明確的開頭、中間和結尾", "使用時間標記詞", "添加角色和情節發展"]
            ))
        
        return structure_score, issues
    
    def _analyze_language_fun(self, text: str) -> Tuple[float, List[ReadabilityIssue]]:
        """分析表達品質（兒童故事語言特點）"""
        issues = []
        
        # 改進的表達品質檢測
        text_lower = text.lower()
        words = text_lower.split()
        sentences = self._split_sentences(text)
        
        # 基礎分從40開始（而非30），但要求更嚴格
        base_score = 40
        
        # 1) 對話品質（不只是數量，還要看品質）
        dialogue_count = sum(1 for s in sentences if '"' in s or "'" in s)
        dialogue_ratio = (dialogue_count / len(sentences)) if sentences else 0
        if dialogue_ratio > 0.5:  # 對話過多
            dialogue_score = min(15, dialogue_ratio * 25)
        elif dialogue_ratio > 0.2:  # 適中
            dialogue_score = min(20, dialogue_ratio * 40)
        else:  # 太少
            dialogue_score = dialogue_ratio * 30

        # 2) 描述豐富度（感官詞彙）- 提高要求
        sensory_words = []
        for category, word_list in self.language_fun_elements["sensory_vocabulary"].items():
            sensory_words.extend(word_list)
        sensory_count = sum(1 for word in sensory_words if word in text_lower)
        sensory_ratio = sensory_count / len(words) if words else 0
        if sensory_ratio > 0.05:  # 豐富
            sensory_score = min(20, sensory_count * 4)
        else:  # 不足
            sensory_score = min(10, sensory_count * 2)

        # 3) 情節發展（動作詞 + 連接詞）
        action_words = ['run', 'jump', 'play', 'walk', 'go', 'come', 'see', 'look', 'find', 'help', 'save', 'discover', 'explore']
        action_count = sum(1 for word in action_words if word in text_lower)
        plot_markers = ['then', 'next', 'after', 'suddenly', 'but', 'however', 'finally']
        marker_count = sum(1 for word in plot_markers if word in text_lower)
        plot_score = min(20, action_count * 2 + marker_count * 3)

        # 4) 情感表達
        emotion_words = ['happy', 'sad', 'excited', 'worried', 'brave', 'proud', 'smile', 'laugh', 'cry', 'love']
        emotion_count = sum(1 for word in emotion_words if word in text_lower)
        emotion_score = min(15, emotion_count * 3)

        # 5) 生動性（象聲詞 + 形容詞）
        sound_words = self.language_fun_elements["rhyme_patterns"]["sound_words"]
        sound_count = sum(1 for word in sound_words if word in text_lower)
        vivid_score = min(10, sound_count * 5)
        
        # 累加分數
        expression_score = base_score + dialogue_score + sensory_score + plot_score + emotion_score + vivid_score
        
        # ⚠️ 品質檢測懲罰
        quality_penalty = 0
        
        # 缺乏情節發展
        if marker_count == 0 and len(sentences) > 5:
            quality_penalty += 15
            
        # 缺乏對話或描述
        if dialogue_count == 0 and sensory_count == 0:
            quality_penalty += 20
            
        # 情感表達貧乏
        if emotion_count == 0 and len(words) > 50:
            quality_penalty += 10
        
        expression_score = expression_score - quality_penalty
        
        # 封頂與最低分
        expression_score = min(95, expression_score)
        expression_score = max(25, expression_score)
        
        # 針對極短句與低多樣性加強下修與封頂
        try:
            avg_len_local = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        except Exception:
            avg_len_local = 0
        very_short_ratio_local = (sum(1 for s in sentences if len(s.split()) < 6) / len(sentences)) if sentences else 0
        # 詞彙多樣性（TTR）
        unique_words_local = set(w for w in words if w.isalpha())
        ttr_local = (len(unique_words_local) / len(words)) if words else 0
        
        if avg_len_local < 8 or very_short_ratio_local > 0.5:
            expression_score = min(expression_score, 80)
            expression_score *= 0.90  # 輕度下修
        if ttr_local < 0.4:
            expression_score -= 8
        
        # 重新裁剪
        expression_score = max(20, min(95, expression_score))
        
        if expression_score < 50:
            issues.append(ReadabilityIssue(
                issue_type="weak_expression",
                location="全文",
                description="表達品質不足：缺乏對話、描述或情節發展",
                severity="medium",
                suggestions=["添加生動的對話", "使用感官詞彙豐富描述", "確保情節有發展標記詞", "加入情感表達"]
            ))
        
        return expression_score, issues
    
    def _analyze_cognitive_load(self, text: str) -> Tuple[float, List[ReadabilityIssue]]:
        """分析認知負荷（簡化為分段線性，並回傳子維度狀態）"""
        issues = []

        sentences = self._split_sentences(text)
        num_sentences = len(sentences)
        words = re.findall(r'\b\w+\b', text)
        num_words = len(words)
        avg_sentence_length = (num_words / num_sentences) if num_sentences else 0
        avg_syllables_per_word = (sum(self._estimate_syllables(w) for w in words) / num_words) if num_words else 0

        proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', text)
        concept_density = (len(proper_nouns) / num_sentences) if num_sentences else 0

        clause_per_sentence = 0.0
        coord_per_sentence = 0.0
        try:
            if getattr(self.nlp, "pipe_names", None) and sentences:
                doc = self.nlp(text)
                sents = list(doc.sents)
                for s in sents:
                    clause_markers = sum(1 for t in s if t.dep_ in ("mark","advcl","ccomp","xcomp","relcl"))
                    coord_markers = sum(1 for t in s if t.dep_ in ("cc","conj"))
                    clause_per_sentence += clause_markers
                    coord_per_sentence += coord_markers
                if len(sents) > 0:
                    clause_per_sentence /= len(sents)
                    coord_per_sentence /= len(sents)
        except Exception:
            pass

        syntax_value = (clause_per_sentence + coord_per_sentence) / 2 if (clause_per_sentence or coord_per_sentence) else 0.0

        # 年齡組閾值（放寬要求）
        if self.target_age_group and "2_4" in self.target_age_group:
            th_concepts = 2.5; th_sent_len = 12.0; th_syll = 1.4; th_syntax = 0.4  # 放寬閾值
        elif self.target_age_group and "5_7" in self.target_age_group:
            th_concepts = 4.0; th_sent_len = 22.0; th_syll = 1.5; th_syntax = 0.9  # 放寬閾值
        else:
            th_concepts = 5.0; th_sent_len = 30.0; th_syll = 1.6; th_syntax = 1.2  # 放寬閾值

        # 分段打分（非線性衰減，超標更嚴）
        def piecewise_score(value: float, low: float, high: float) -> float:
            if value <= low:
                return 100.0
            if value >= high:
                return 0.0
            ratio = (value - low) / (high - low)
            return max(0.0, 100.0 * (1.0 - ratio ** 1.5))

        # 上界採用 1.6x 閾值，保留一定容忍
        s_concepts = piecewise_score(concept_density, th_concepts, th_concepts * 1.6)
        s_sentlen = piecewise_score(avg_sentence_length, th_sent_len, th_sent_len * 1.6)
        s_syll = piecewise_score(avg_syllables_per_word, th_syll, th_syll * 1.4)
        s_syntax = piecewise_score(syntax_value, th_syntax, th_syntax * 1.8)

        # 權重（可理解性導向）
        w_concepts, w_syntax, w_morph, w_sentlen = 0.35, 0.25, 0.20, 0.20
        raw_score = (
            s_concepts * w_concepts +
            s_syntax * w_syntax +
            s_syll * w_morph +
            s_sentlen * w_sentlen
        )
        
        # 調整分數，給出更合理的基準
        if raw_score >= 80:
            score = 85 + (raw_score - 80) * 0.75  # 80分以上給85-95分
        elif raw_score >= 60:
            score = 70 + (raw_score - 60) * 0.75  # 60-80分給70-85分
        elif raw_score >= 40:
            score = 55 + (raw_score - 40) * 0.75  # 40-60分給55-70分
        else:
            score = 30 + raw_score * 0.625  # 40分以下給30-55分

        # 過度簡化懲罰（避免極短句/超低複雜度拿滿分）
        # 更嚴格：提升係數、提高觸發區間
        simplicity_penalty = 0.0
        if avg_sentence_length < 10.0:
            simplicity_penalty += min(28.0, (10.0 - avg_sentence_length) * 3.5)
        if avg_syllables_per_word < 1.35:
            simplicity_penalty += min(8.0, (1.35 - avg_syllables_per_word) * 25.0)
        if syntax_value < 0.25:
            simplicity_penalty += min(15.0, (0.25 - syntax_value) * 80.0)
        if concept_density < 0.30:
            simplicity_penalty += min(10.0, (0.30 - concept_density) * 30.0)

        # 若極短句比例過半，進一步封頂
        try:
            very_short_ratio_local = (sum(1 for s in sentences if len(s.text.split()) < 6) / len(sentences)) if sentences else 0.0
        except Exception:
            # 退化處理：基於原文字串切分
            very_short_ratio_local = (sum(1 for s in self._split_sentences(text) if len(s.split()) < 6) / len(self._split_sentences(text))) if self._split_sentences(text) else 0.0
        if very_short_ratio_local > 0.5:
            score = min(score, 75.0)

        score = max(20.0, min(90.0, score - simplicity_penalty))

        # 問題提示（子維度超標即報）
        if concept_density > th_concepts:
            issues.append(ReadabilityIssue(
                issue_type="high_concept_density",
                location="全文",
                description=f"概念密度偏高 ({concept_density:.1f}/句 > {th_concepts})",
                severity="medium",
                suggestions=["降低每句資訊量，拆分複合概念"]
            ))
        if avg_sentence_length > th_sent_len:
            issues.append(ReadabilityIssue(
                issue_type="long_average_sentence",
                location="全文",
                description=f"平均句長偏高 ({avg_sentence_length:.1f} > {th_sent_len})",
                severity="low",
                suggestions=["縮短長句，控制每句資訊量"]
            ))
        if avg_syllables_per_word > th_syll:
            issues.append(ReadabilityIssue(
                issue_type="high_syllable_density",
                location="全文",
                description=f"音節密度偏高 ({avg_syllables_per_word:.2f} > {th_syll})",
                severity="low",
                suggestions=["替換多音節詞為更簡單的同義詞"]
            ))
        if syntax_value > th_syntax:
            issues.append(ReadabilityIssue(
                issue_type="high_syntactic_complexity",
                location="全文",
                description=f"從句/並列偏多 ({syntax_value:.2f} > {th_syntax:.2f})",
                severity="medium",
                suggestions=["減少從句與並列結構，改寫為兩句"]
            ))
        # 過度簡化提示
        if simplicity_penalty >= 8.0:
            issues.append(ReadabilityIssue(
                issue_type="over_simplified_cognition",
                location="全文",
                description="認知負荷過低：平均句長/音節/語法/概念密度過低",
                severity="medium",
                suggestions=["適度增加句長與資訊量","加入連接詞與因果標記","加入具體細節與情境詞"]
            ))

        return round(max(0.0, min(100.0, score)), 1), issues
    
    def _calculate_children_final_score(self, vocab_score: float, sentence_score: float,
                                      structure_score: float, fun_score: float,
                                      cognitive_score: float, ai_analysis: Dict) -> float:
        """計算最終分數 - 基於兒童故事語言規範品質（不受年齡組影響）"""
        
        # 1. 各維度權重（基於語言品質評估）
        weights = {
            'vocab': 0.30,      # 詞彙品質：精準、具象、生動
            'sentence': 0.30,   # 句法品質：清晰、長短交替
            'expression': 0.25, # 表達品質：符合兒童故事特點（使用 fun_score）
            'cognitive': 0.15   # 認知友好度：資訊密度適中
        }
        
        # 動態降權：若文本疑似「極短句破碎」型，降低認知負荷權重並提高句法權重
        try:
            avg_len = self._last_children_indices.get('avg_sentence_length') if hasattr(self, '_last_children_indices') else None
            short_ratio = self._last_children_indices.get('very_short_ratio') if hasattr(self, '_last_children_indices') else None
        except Exception:
            avg_len = None; short_ratio = None
        
        if (avg_len is not None and avg_len < 8) or (short_ratio is not None and short_ratio > 0.5):
            weights['sentence'] = 0.40
            weights['cognitive'] = 0.05
            # 封頂認知負荷分數避免拉高總分
            cognitive_score = min(cognitive_score, 80.0)
        
        # 2. 計算加權平均分數（使用 fun_score 作為表達品質）
        weighted_score = (
            vocab_score * weights['vocab'] +
            sentence_score * weights['sentence'] +
            fun_score * weights['expression'] +
            cognitive_score * weights['cognitive']
        )
        
        # 3. 統一的品質導向映射（不分年齡組）
        # 目標：好故事 80-90 分，壞故事 30-40 分
        # 更嚴格的標準：防止簡單但破碎的文本得高分
        if weighted_score >= 85:
            final_score = 85 + (weighted_score - 85) * 0.5   # 85-100 → 85-92.5
        elif weighted_score >= 75:
            final_score = 75 + (weighted_score - 75) * 1.0   # 75-85 → 75-85
        elif weighted_score >= 65:
            final_score = 63 + (weighted_score - 65) * 1.2   # 65-75 → 63-75
        elif weighted_score >= 55:
            final_score = 48 + (weighted_score - 55) * 1.5   # 55-65 → 48-63
        elif weighted_score >= 45:
            final_score = 33 + (weighted_score - 45) * 1.5   # 45-55 → 33-48
        elif weighted_score >= 35:
            final_score = 20 + (weighted_score - 35) * 1.3   # 35-45 → 20-33
        else:
            final_score = 10 + weighted_score * 0.28         # <35 → 10-20
        
        # 4. 確保分數在合理範圍內
        final_score = max(15.0, min(95.0, final_score))
        
        # 5. 甜點區間調整：以 78 為中心、70–85 為甜點帶
        # 偏離甜點帶外時做輕微扣分，避免過度簡單或過度艱深自動獲得高分
        sweet_center = 78.0
        sweet_half_width = 8.0   # 78 ± 8 → 70–86（近似 70–85）
        deviation = abs(final_score - sweet_center)
        if deviation > sweet_half_width:
            # 每超出 1 分，扣 0.4 分，上限 6 分
            penalty = min(6.0, (deviation - sweet_half_width) * 0.4)
            final_score = max(15.0, final_score - penalty)
        
        return round(final_score, 1)
    
    def _calculate_children_readability_indices(self, text: str) -> Dict:
        """計算兒童可讀性指數"""
        sentences = self._split_sentences(text)
        words = re.findall(r'\b\w+\b', text)
        
        if not sentences or not words:
            return {"flesch_score": 0, "grade_level": "unknown", "age_appropriateness": "unknown"}
        
        # 簡化的 Flesch 分數計算
        avg_sentence_length = len(words) / len(sentences)
        syllable_count = sum(self._estimate_syllables(word) for word in words)
        avg_syllables_per_word = syllable_count / len(words)
        
        flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        flesch_score = max(0, flesch_score)
        
        # FKGL (Flesch-Kincaid Grade Level) 計算
        fkgl_score = 0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59
        fkgl_score = max(0, fkgl_score)
        
        # 基於FKGL的年級判定（收緊閾值以更好區分年齡組）
        if fkgl_score <= 2.0:
            grade_level = "Pre-K to Grade 1"
            age_group = "2-4 歲"
            recommended_age_group = "children_2_4"
        elif fkgl_score <= 4.0:
            grade_level = "Grade 1 to 3"
            age_group = "4-7 歲"
            recommended_age_group = "children_4_6"
        elif fkgl_score <= 6.5:
            grade_level = "Grade 3 to 5"
            age_group = "7-10 歲"
            recommended_age_group = "children_7_8"
        else:
            grade_level = "Grade 5+"
            age_group = "10+ 歲"
            recommended_age_group = "children_9_10"
        
        # 極短句比例（供動態降權使用）
        very_short_ratio = 0.0
        try:
            very_short_ratio = sum(1 for s in sentences if len(s.split()) < 6) / len(sentences)
        except Exception:
            very_short_ratio = 0.0
        
        return {
            "flesch_score": round(flesch_score, 1),
            "fkgl_score": round(fkgl_score, 1),
            "grade_level": grade_level,
            "age_appropriateness": age_group,
            "recommended_age_group": recommended_age_group,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "avg_syllables_per_word": round(avg_syllables_per_word, 2),
            "very_short_ratio": round(very_short_ratio, 2),
            "total_words": len(words),
            "total_sentences": len(sentences)
        }
    
    def _estimate_syllables(self, word: str) -> int:
        """估算音節數"""
        if not word:
            return 0
        
        word = word.lower()
        if word.endswith('e') and len(word) > 3:
            word = word[:-1]
        
        vowels = 'aeiouy'
        syllable_count = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel
        
        return max(1, syllable_count)
    
    def _assess_age_appropriateness(self, final_score: float, indices: Dict) -> Dict:
        """提供年齡組推薦（輔助信息，不影響核心評分）"""
        # 年齡組僅用於提供閱讀建議，核心評分不受影響
        recommended_age_group = indices.get("recommended_age_group", "children_4_6")
        actual_flesch = indices.get("flesch_score", 0)
        fkgl_score = indices.get("fkgl_score", 0)
        
        # 根據推薦年齡組提供閱讀建議
        age_group_names = {
            "children_2_4": "2-4歲",
            "children_4_6": "4-6歲",
            "children_7_8": "7-8歲",
            "children_9_10": "9-10歲"
        }
        
        age_name = age_group_names.get(recommended_age_group, "兒童")
        
        return {
            "recommended_age_group": recommended_age_group,
            "age_range": age_name,
            "actual_flesch": actual_flesch,
            "fkgl_score": fkgl_score,
            "note": f"基於語言複雜度分析，建議適讀年齡為{age_name}",
            "confidence": "high" if 60 <= actual_flesch <= 90 else "medium"
        }
    
    def _advanced_children_ai_analysis(self, story_text: str) -> Dict:
        """AI 分析（兒童讀物專用提示）"""
        if not self.ai or not hasattr(self.ai, 'model_available') or not self.ai.model_available:
            return {"score": READABILITY_AI_FALLBACK_SCORE, "analysis": "AI模型不可用"}

        # 兒童讀物專用提示詞（帶當前年齡組名稱）
        try:
            age_group_name = self.age_group_configs.get(self.target_age_group, {}).get("name", "兒童讀者")
        except Exception:
            age_group_name = "兒童讀者"
        prompt = (
            f"請扮演兒童閱讀專家，針對【{age_group_name}】的英文故事進行評估，並從以下角度給出0-100評分：\n"
            "1) 詞彙是否適齡？是否有過多超齡詞彙？\n"
            "2) 句子是否簡潔易懂？\n"
            "3) 是否有不適當的主題（暴力、恐怖、成熟內容）？\n"
            "4) 給出 3 條具體可操作的改進建議。\n"
            "輸出JSON：{ai_score:number, analysis:string, confidence:number}。\n"
            f"文本開頭：{story_text[:1200]}..."
        )

        try:
            ai_result = self.ai.analyze_consistency(prompt, [], {})
            ai_score = normalize_score_0_100(
                ai_result.get("ai_score", READABILITY_AI_FALLBACK_SCORE),
                READABILITY_AI_FALLBACK_SCORE,
            )
            ai_confidence = normalize_confidence_0_1(ai_result.get("confidence", 0.6), 0.6)
            return {
                "score": ai_score,
                "analysis": ai_result.get("analysis", "AI 兒童可讀性分析完成"),
                "confidence": ai_confidence
            }
        except Exception as e:
            return {"score": READABILITY_AI_FALLBACK_SCORE, "analysis": f"AI分析失敗: {str(e)}"}
    
    def _compare_with_benchmarks(self, final_score: float, indices: Dict) -> Dict:
        """與經典作品比較"""
        benchmarks = {
            "Brown Bear, Brown Bear": {"flesch": 95, "age": "2-4歲"},
            "Green Eggs and Ham": {"flesch": 90, "age": "4-6歲"},
            "Where the Wild Things Are": {"flesch": 85, "age": "4-8歲"},
            "Magic Tree House": {"flesch": 75, "age": "6-9歲"}
        }
        
        actual_flesch = indices.get("flesch_score", 0)
        closest_match = min(benchmarks.items(), 
                           key=lambda x: abs(x[1]["flesch"] - actual_flesch))
        
        return {
            "closest_match": {
                "book": closest_match[0],
                "flesch_difference": abs(closest_match[1]["flesch"] - actual_flesch)
            },
            "performance_level": "優秀" if final_score >= 90 else "良好" if final_score >= 80 else "尚可" if final_score >= 70 else "需改進"
        }
    
    def _generate_children_suggestions(self, issues: List[ReadabilityIssue], 
                                        ai_analysis: Dict, indices: Dict) -> List[str]:
        """生成改進建議"""
        suggestions = []
        
        # 基於問題生成建議
        issue_types = Counter([issue.issue_type for issue in issues])
        
        if issue_types.get('vocabulary_too_advanced', 0) > 0:
            suggestions.append("📚 詞彙難度過高：建議使用更簡單的詞彙")
        
        if issue_types.get('sentence_length', 0) > 0:
            suggestions.append("✏️ 句子過長：建議縮短句子長度")
        
        if issue_types.get('unclear_structure', 0) > 0:
            suggestions.append("📖 故事結構：確保有清晰的開頭、中間和結尾")
        
        if issue_types.get('lack_fun_elements', 0) > 0:
            suggestions.append("🎨 增加趣味性：添加更多感官詞彙和互動元素")
        
        if issue_types.get('high_concept_density', 0) > 0:
            suggestions.append("🧠 概念密度：簡化每句的概念數量")
        
        # 如果沒有問題，給正面建議
        if not suggestions:
            suggestions = [
                "✅ 文本可讀性良好，適合目標年齡群",
                "🎆 繼續保持當前的詞彙選擇和句式結構"
            ]
        
        return suggestions

# ==================== 獨立運行測試 ====================
if __name__ == "__main__":
    import os
    import json
    import logging

    logging.basicConfig(
        level=getattr(logging, os.environ.get("READABILITY_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(message)s"
    )
    
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
    
    logger.info("開始可讀性評估")
    logger.info("%s", "=" * 60)
    logger.info("📁 掃描 output，找到 %s 個故事資料夾", len(story_dirs))

    # 單次初始化，避免每本故事重載模型
    checker = ReadabilityChecker()

    for story_dir in story_dirs:
        en_dir = os.path.join(story_dir, 'en')
        base_dir = en_dir if os.path.exists(en_dir) else story_dir
        main_file = os.path.join(base_dir, 'full_story.txt')
        if not os.path.exists(main_file):
            logger.warning("- 略過：%s (無 full_story.txt)", os.path.basename(story_dir))
            continue
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                text = f.read()
            story_name = os.path.basename(story_dir)
            # 優先順序：ages-file 指定 > story_settings.txt > --target-age > 自動偵測
            story_target_age = None
            per_story_age_map = globals().get('per_story_age')
            if per_story_age_map:
                story_target_age = per_story_age_map.get(story_name)
            if not story_target_age:
                settings_path = os.path.join(story_dir, 'story_settings.txt')
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, 'r', encoding='utf-8') as sf:
                            for line in sf:
                                if line.lower().startswith('target_age'):
                                    parts = line.split(':', 1)
                                    if len(parts) == 2:
                                        story_target_age = parts[1].strip()
                                        break
                    except Exception:
                        pass
            if not story_target_age:
                args_obj = globals().get('args')
                story_target_age = getattr(args_obj, 'target_age', None) if args_obj else None
            result = checker.check(text, story_name, target_age=story_target_age)
            scores = result['children_readability']['scores']
            indices = result['children_readability']['language_indices']
            age_rec = result['children_readability']['age_recommendation']
            issues = result['children_readability']['issues']
            quality_band = result['children_readability']['quality_band']

            logger.info("")
            logger.info("%s", "=" * 60)
            logger.info("📖 檢測: %s", os.path.basename(story_dir))
            logger.info("📄 文檔: %s", os.path.basename(main_file))
            logger.info("📊 詳細分數:")
            logger.info("  🎯 總分: %.1f/100 [%s]", scores['final'], quality_band)
            logger.info("  📚 詞彙品質: %.1f/100", scores['vocabulary_quality'])
            logger.info("  ✏️ 句法品質: %.1f/100", scores['sentence_quality'])
            logger.info("  🎨 表達品質: %.1f/100", scores['expression_quality'])
            logger.info("  🧠 認知友好度: %.1f/100", scores['cognitive_friendliness'])

            logger.info("")
            logger.info("📈 語言指標:")
            logger.info(
                "  Flesch: %.1f | FKGL: %.1f | 句長: %.1f | 音節/詞: %.2f",
                indices['flesch_score'],
                indices.get('fkgl_score', 0),
                indices['avg_sentence_length'],
                indices['avg_syllables_per_word'],
            )
            # 顯示推薦適讀年齡（輔助信息）
            age_range = age_rec.get('age_range', '未知')
            logger.info("  💡 建議適讀年齡: %s", age_range)

            total_issues = issues.get('total_issues', 0)
            if total_issues > 0:
                logger.info("")
                logger.info("⚠️  問題概覽:")
                for k in ['vocabulary','sentence','expression','cognitive']:
                    v = issues.get(k, [])
                    if v:
                        logger.info("  🔸 %s: %s 項", k, len(v))
            else:
                logger.info("")
                logger.info("✅ 未發現明顯語言品質問題")

            sugg = result['children_readability'].get('suggestions', [])
            if sugg:
                logger.info("")
                logger.info("💡 建議 (最多3項):")
                for s in sugg[:3]:
                    logger.info("  └─ %s", s)

            logger.info("%s", "=" * 60)
        except Exception as e:
            logger.exception("❌ 失敗 %s: %s", os.path.basename(story_dir), e)

