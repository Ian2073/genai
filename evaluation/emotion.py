# emotional_impact.py - 六維度故事評估系統 - 情感影響力維度
# 用途：評估故事的情感吸引力和讀者共鳴度
# 重點：測量情感多樣性、強度、共鳴力、真實性
#
# 【GoEmotions 整合】
# 使用 SamLowe/roberta-base-go_emotions (MIT) 進行逐段情感分類，
# 取代原本的純關鍵詞匹配，大幅提升對隱喻、反諷、上下文情感的辨識能力。
# 模型支援 28 類情緒，可捕捉比 8 類關鍵詞詞典更細緻的情感光譜。

import logging
import os
import re
import numpy as np
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Optional, Set
from .consistency import ComprehensiveKnowledgeGraph, AIAnalyzer
from .genre import GenreDetector
from .utils import (
    SentenceSplitterMixin,
    ensure_instance,
    get_default_model_path,
    get_kg_path,
    load_category_keywords,
    load_spacy_model,
)
from .kb import LocalCategoryMatcher
from .shared.ai_safety import (
    get_dimension_fallback_score,
    normalize_confidence_0_1,
    normalize_score_0_100,
)

# ---------------------------------------------------------------------------
# GoEmotions 預訓練情感分類器
# ---------------------------------------------------------------------------

# GoEmotions 28 類情緒 → 8 大情感族群映射
# 用於與原有的 8 類情感框架相容，同時保留 28 類的細粒度資訊
GOEMOTION_TO_FAMILY: Dict[str, str] = {
    # joy 族群
    'joy': 'joy', 'amusement': 'joy', 'excitement': 'joy',
    'optimism': 'joy', 'pride': 'joy', 'relief': 'joy',
    # sadness 族群
    'sadness': 'sadness', 'grief': 'sadness', 'disappointment': 'sadness',
    'remorse': 'sadness',
    # fear 族群
    'fear': 'fear', 'nervousness': 'fear',
    # anger 族群
    'anger': 'anger', 'annoyance': 'anger', 'disapproval': 'anger',
    # surprise 族群
    'surprise': 'surprise', 'realization': 'surprise', 'confusion': 'surprise',
    # love 族群
    'love': 'love', 'admiration': 'love', 'caring': 'love',
    'gratitude': 'love', 'approval': 'love', 'desire': 'love',
    # disgust 族群
    'disgust': 'disgust', 'embarrassment': 'disgust',
    # trust/neutral
    'curiosity': 'trust', 'neutral': 'neutral',
}

# 正向 / 負向 / 中性 情緒分類（用於情感弧線分析）
POSITIVE_EMOTIONS = {'joy', 'amusement', 'excitement', 'optimism', 'pride', 'relief',
                     'love', 'admiration', 'caring', 'gratitude', 'approval', 'desire', 'curiosity'}
NEGATIVE_EMOTIONS = {'sadness', 'grief', 'disappointment', 'remorse', 'fear', 'nervousness',
                     'anger', 'annoyance', 'disapproval', 'disgust', 'embarrassment'}
# 高強度情緒子集
HIGH_AROUSAL_EMOTIONS = {'excitement', 'anger', 'fear', 'grief', 'joy', 'surprise', 'love', 'desire'}

EMOTION_MINIMAL_RESULT_SCORE = get_dimension_fallback_score("emotional_impact")


class GoEmotionsAnalyzer:
    """基於 RoBERTa-GoEmotions 的情感分類器。

    特色：
    - 逐段（segment）推理而非逐句，降低碎片化誤判
    - 支援 multi-label（一個段落可同時有多種情緒）
    - 輸出 28 類機率分佈 → 映射為 8 大情感族群
    - 支援批次推理，GPU 友好
    """

    # 每段的目標 token 上限（RoBERTa 最長 512，留 20 給 special tokens）
    MAX_SEGMENT_TOKENS = 490

    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.tokenizer = None
        self.device = device
        self._available = False

        # 解析模型路徑
        if model_path is None:
            model_path = os.environ.get(
                'GOEMOTION_MODEL_PATH',
                get_default_model_path('roberta-base-go_emotions')
            )
            # 也嘗試常見本地路徑
            candidates = [
                model_path,
                get_default_model_path('roberta-base-go_emotions'),
                os.path.join('models', 'roberta-base-go_emotions'),
            ]
            for candidate in candidates:
                if os.path.isdir(candidate):
                    model_path = candidate
                    break

        self._model_path = model_path
        self._load_model()

    def _load_model(self) -> None:
        """延遲載入 GoEmotions 模型。"""
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch

            if not os.path.isdir(self._model_path):
                self.logger.warning("⚠️ GoEmotions 模型路徑不存在: %s，情感分析將降級為關鍵詞模式", self._model_path)
                return

            self.tokenizer = AutoTokenizer.from_pretrained(self._model_path, local_files_only=True)
            self.model = AutoModelForSequenceClassification.from_pretrained(self._model_path, local_files_only=True)

            # 裝置選擇
            if self.device is None:
                if torch.cuda.is_available():
                    self.device = 'cuda'
                else:
                    self.device = 'cpu'
            self.model.to(self.device)
            self.model.eval()

            # 讀取 label 映射，統一 key 型別避免 int/str 混用造成查找失敗
            raw_id2label = self.model.config.id2label or {}
            self.id2label = {}
            for key, label in raw_id2label.items():
                try:
                    self.id2label[int(key)] = label
                except (TypeError, ValueError):
                    self.id2label[key] = label
            self.num_labels = len(self.id2label)
            self._available = True
            self.logger.info("✅ GoEmotions 模型已載入 (%s, %s labels, device=%s)",
                             self._model_path, self.num_labels, self.device)
        except Exception as exc:
            self.logger.warning("⚠️ GoEmotions 載入失敗: %s，情感分析將降級為關鍵詞模式", exc)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # ----- 核心推理 -----

    def predict_segments(self, segments: List[str], threshold: float = 0.3) -> List[Dict[str, Any]]:
        """對多個文本段落進行情感分類。

        返回:
            每個段落的分析結果列表：
            [{
                'text_preview': str,
                'emotions': {label: prob},       # 超過 threshold 的情緒
                'all_probs': {label: prob},       # 所有 28 類的機率
                'dominant': str,                  # 最強情緒
                'dominant_prob': float,
                'family': str,                    # 映射後的 8 大族群
                'valence': str,                   # 'positive' | 'negative' | 'neutral'
                'arousal': float,                 # 情感強度 (0-1)
            }]
        """
        if not self._available or not segments:
            return [self._empty_result() for _ in (segments or [])]

        import torch
        results = []

        # 批次推理
        batch_size = 16
        for batch_start in range(0, len(segments), batch_size):
            batch = segments[batch_start:batch_start + batch_size]

            # Tokenize
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.MAX_SEGMENT_TOKENS,
                return_tensors='pt'
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.sigmoid(outputs.logits).cpu().numpy()  # multi-label → sigmoid

            for i, prob_vec in enumerate(probs):
                all_probs = {}
                for j in range(self.num_labels):
                    label = self.id2label.get(j, self.id2label.get(str(j), f'label_{j}'))
                    all_probs[label] = float(prob_vec[j])
                # 篩選超過閾值的情緒
                emotions = {label: p for label, p in all_probs.items() if p >= threshold and label != 'neutral'}
                # 若全部低於閾值，取最高的非中性情緒
                if not emotions:
                    non_neutral = {k: v for k, v in all_probs.items() if k != 'neutral'}
                    if non_neutral:
                        top_label = max(non_neutral, key=non_neutral.get)
                        emotions = {top_label: non_neutral[top_label]}

                dominant = max(all_probs, key=all_probs.get) if all_probs else 'neutral'
                dominant_prob = all_probs.get(dominant, 0.0)
                family = GOEMOTION_TO_FAMILY.get(dominant, 'neutral')

                # 計算正負極性
                pos_sum = sum(all_probs.get(e, 0) for e in POSITIVE_EMOTIONS)
                neg_sum = sum(all_probs.get(e, 0) for e in NEGATIVE_EMOTIONS)
                if pos_sum > neg_sum * 1.2:
                    valence = 'positive'
                elif neg_sum > pos_sum * 1.2:
                    valence = 'negative'
                else:
                    valence = 'neutral'

                # 情感強度 = 非中性情緒的最大機率
                arousal = max((all_probs.get(e, 0) for e in HIGH_AROUSAL_EMOTIONS), default=0.0)

                results.append({
                    'text_preview': batch[i][:80],
                    'emotions': emotions,
                    'all_probs': all_probs,
                    'dominant': dominant,
                    'dominant_prob': dominant_prob,
                    'family': family,
                    'valence': valence,
                    'arousal': arousal,
                })

        return results

    def _empty_result(self) -> Dict[str, Any]:
        return {
            'text_preview': '',
            'emotions': {},
            'all_probs': {},
            'dominant': 'neutral',
            'dominant_prob': 0.0,
            'family': 'neutral',
            'valence': 'neutral',
            'arousal': 0.0,
        }

    def release(self) -> None:
        """釋放模型記憶體。"""
        if self.model is not None:
            try:
                import torch
                self.model.cpu()
                del self.model
                self.model = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            self._available = False

DEFAULT_EMOTION_KEYWORDS = {
    'joy': {
        'words': ['happy', 'joy', 'joyful', 'delight', 'delighted', 'delightful', 'cheerful',
                  'cheer', 'glad', 'gladness', 'pleased', 'content', 'merry', 'bliss',
                  'blissful', 'excited', 'thrilled', 'elated', 'jubilant', 'ecstatic',
                  'overjoyed', 'smile', 'laugh', 'grin', 'beam', 'chuckle', 'giggle',
                  'radiant', 'sparkle'],
        'intensity': 0.8
    },
    'sadness': {
        'words': ['sad', 'unhappy', 'sorrowful', 'sorrow', 'grief', 'melancholy', 'depressed',
                  'miserable', 'gloomy', 'dejected', 'downcast', 'heartbroken', 'tearful',
                  'tears', 'tear', 'cry', 'weep', 'wept', 'sob', 'mourn', 'lament', 'wail',
                  'lonely', 'loneliness', 'despair', 'ache'],
        'intensity': 0.9
    },
    'fear': {
        'words': ['afraid', 'scared', 'frightened', 'terrified', 'fearful', 'anxious',
                  'worried', 'nervous', 'panic', 'dread', 'terror', 'horror', 'alarmed',
                  'uneasy', 'tremble', 'shiver', 'shake', 'shudder', 'cower', 'flee',
                  'hide', 'ominous', 'spook', 'spooky', 'creep', 'crept'],
        'intensity': 0.95
    },
    'anger': {
        'words': ['angry', 'mad', 'furious', 'enraged', 'irate', 'wrathful', 'indignant',
                  'annoyed', 'irritated', 'frustrated', 'outraged', 'livid', 'rage',
                  'resent', 'resentful', 'seethe', 'shout', 'yell', 'scream', 'roar',
                  'storm', 'fume', 'temper', 'grumble'],
        'intensity': 0.85
    },
    'surprise': {
        'words': ['surprised', 'amazed', 'astonished', 'astonishment', 'shocked', 'startled',
                  'stunned', 'astounded', 'bewildered', 'dumbfounded', 'flabbergasted',
                  'wonder', 'gasp', 'stare', 'gape', 'marvel', 'sudden'],
        'intensity': 0.7
    },
    'love': {
        'words': ['love', 'adore', 'cherish', 'treasure', 'care', 'affection', 'devotion',
                  'devoted', 'beloved', 'tenderness', 'warmth', 'fondness', 'attachment',
                  'embrace', 'hug', 'kiss', 'caress', 'cuddle', 'compassion', 'kindness'],
        'intensity': 0.9
    },
    'disgust': {
        'words': ['disgust', 'repulsed', 'revolted', 'nauseated', 'sick', 'loathe',
                  'detest', 'abhor', 'hate', 'despise', 'scorn', 'repel', 'gross',
                  'nasty', 'filthy', 'rotten', 'stench', 'stink'],
        'intensity': 0.75
    },
    'trust': {
        'words': ['trust', 'believe', 'faith', 'confidence', 'rely', 'depend', 'hope',
                  'optimistic', 'assured', 'certain', 'secure', 'safe', 'loyal', 'loyalty',
                  'promise', 'promised', 'faithful', 'honest', 'truth', 'steady'],
        'intensity': 0.65
    }
}

DEFAULT_EMOTIONAL_TRANSITIONS = ['but', 'however', 'yet', 'although', 'nevertheless', 'still',
                                 'despite', 'suddenly', 'then', 'when', 'until', 'after',
                                 'before', 'while']

DEFAULT_INTENSIFIERS = ['very', 'extremely', 'incredibly', 'absolutely', 'completely', 'totally',
                        'utterly', 'deeply', 'profoundly', 'intensely', 'overwhelmingly', 'so', 'such']

DEFAULT_ACTION_VERBS = ['scream', 'shout', 'cry', 'weep', 'sob', 'tremble', 'shake', 'rush',
                        'flee', 'chase', 'fight', 'struggle', 'embrace', 'kiss', 'hug',
                        'hold', 'cling', 'console', 'comfort', 'save', 'protect']

DEFAULT_UNIVERSAL_THEMES = {
    'family': ['family', 'mother', 'father', 'parent', 'child', 'son', 'daughter', 'home',
               'parents', 'brother', 'sister', 'siblings', 'grandmother', 'grandfather'],
    'friendship': ['friend', 'friends', 'companion', 'companions', 'together', 'share',
                   'help', 'support', 'ally', 'allies'],
    'love': ['love', 'heart', 'care', 'cherish', 'beloved', 'dear', 'devotion', 'devoted',
             'affection', 'caring'],
    'loss': ['lose', 'lost', 'gone', 'death', 'leave', 'farewell', 'goodbye', 'miss',
             'mourning', 'grief', 'sorrow'],
    'growth': ['learn', 'grow', 'change', 'discover', 'realize', 'understand', 'wise',
               'courage', 'bravery', 'sacrifice', 'lesson']
}

@dataclass
class EmotionalImpactScores:
    """情感影響力分數"""
    diversity: float      # 情感多樣性
    intensity: float      # 情感強度
    resonance: float      # 情感共鳴力
    authenticity: float   # 情感真實性
    final: float         # 最終綜合分數
    confidence: float    # 評估置信度

class EmotionalImpactChecker(SentenceSplitterMixin):
    """情感影響力檢測器（六維度故事評估系統 - 情感影響力維度）
    
    整合 GoEmotions (RoBERTa) 預訓練模型進行逐段情感分類，
    取代純關鍵詞匹配，支援 28 類情緒辨識 + 情感弧線分析。
    當 GoEmotions 不可用時自動降級為關鍵詞模式。
    """
    
    def __init__(self,
                 kg_path: str = get_kg_path(),
                 model_path: str = get_default_model_path("Qwen2.5-14B"),
                 use_multiple_ai_prompts: bool = False,
                 ai: AIAnalyzer = None,
                 kg: ComprehensiveKnowledgeGraph = None,
                 nlp=None,
                 debug_logs: bool = False,
                 goemotion_model: Optional[GoEmotionsAnalyzer] = None):
        # 載入核心分析工具（可外部注入避免重複載入）
        self.kg = ensure_instance(kg, ComprehensiveKnowledgeGraph, kg_path)
        self.ai = ensure_instance(ai, AIAnalyzer, model_path, use_multiple_ai_prompts)
        self.nlp = ensure_instance(nlp, load_spacy_model)
        
        # GoEmotions 預訓練情感分類器（可由 evaluator 外部注入）
        if goemotion_model is not None:
            self.goemotion = goemotion_model
        else:
            self.goemotion = GoEmotionsAnalyzer()
        
        # 文體檢測器
        self.genre_detector = GenreDetector()

        self.logger = logging.getLogger(__name__)
        self.debug_logs = debug_logs

        # 中央化關鍵字資源
        self.local_categories = LocalCategoryMatcher()
        self.emotion_keywords = self._load_emotion_keywords()
        self.emotional_transitions = self._load_keywords('emotion.transitions.default', DEFAULT_EMOTIONAL_TRANSITIONS)
        self.intensifiers = self._load_keywords('emotion.intensifiers.core', DEFAULT_INTENSIFIERS)
        self.action_verbs = self._load_keywords('emotion.action_verbs.expressive', DEFAULT_ACTION_VERBS)
        self.universal_themes = self._load_universal_themes()
        
        # 故事情感弧線模板
        self.emotional_arc_templates = {
            'classic': ['neutral', 'positive', 'conflict', 'crisis', 'resolution', 'positive'],
            'tragedy': ['positive', 'conflict', 'crisis', 'negative', 'negative'],
            'comedy': ['neutral', 'conflict', 'positive', 'positive'],
            'adventure': ['neutral', 'excitement', 'conflict', 'resolution', 'triumph']
        }
        
        # 子維度權重
        self.sub_weights = {
            'diversity': 0.20,      # 情感多樣性（20%）
            'intensity': 0.25,      # 情感強度（25%）
            'resonance': 0.35,      # 情感共鳴力（35% - 最重要）
            'authenticity': 0.20    # 情感真實性（20%）
        }

        # 建立常見詞彙參考集，輔助詞形還原
        self._lemma_reference_words = self._build_reference_lemmas()
    
    def _build_reference_lemmas(self) -> Set[str]:
        """建立常見詞彙集合，供簡易詞形還原時參考。"""
        reference: Set[str] = set()
        for data in self.emotion_keywords.values():
            reference.update(word.lower() for word in data['words'])
        reference.update(word.lower() for word in self.emotional_transitions)
        reference.update(word.lower() for word in self.intensifiers)
        reference.update(word.lower() for word in self.action_verbs)
        for words in self.universal_themes.values():
            reference.update(word.lower() for word in words)
        # 加入常見角色與敘事詞彙，提升童話文本覆蓋率
        reference.update({
            'said', 'asked', 'answered', 'replied', 'told', 'promised', 'promise',
            'smile', 'tear', 'tears', 'hope', 'hopeful', 'brave', 'courage',
            'mother', 'father', 'brother', 'sister', 'king', 'queen', 'princess',
            'prince', 'witch', 'wizard', 'rescue', 'save', 'protect'
        })
        return reference

    def _simple_lemma(self, token: str) -> str:
        """簡化詞形還原，支援情感關鍵詞的常見變化。"""
        word = (token or '').lower()
        if not word:
            return word
        if word in self._lemma_reference_words:
            return word

        irregulars = {
            'better': 'good', 'best': 'good', 'worse': 'bad', 'worst': 'bad',
            'children': 'child', 'people': 'person', 'feet': 'foot', 'teeth': 'tooth'
        }
        if word in irregulars:
            return irregulars[word]

        if word.endswith('ily') and len(word) > 4:
            candidate = word[:-3] + 'y'
            return candidate if candidate else word

        if word.endswith('ies') and len(word) > 4:
            candidate = word[:-3] + 'y'
            if candidate in self._lemma_reference_words:
                return candidate
            return candidate

        if word.endswith('ves') and len(word) > 4:
            candidate = word[:-3] + 'f'
            if candidate in self._lemma_reference_words:
                return candidate
            return candidate

        suffixes = ('ing', 'ers', 'er', 'ed', 'ly', 'es', 's')
        for suffix in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                base = word[:-len(suffix)]
                if suffix in {'ing', 'ed'}:
                    if len(base) >= 3 and base[-1] == base[-2]:
                        base = base[:-1]
                    candidate_e = base + 'e'
                    if candidate_e in self._lemma_reference_words:
                        return candidate_e
                if base in self._lemma_reference_words:
                    return base
                return base

        return word

    def _extract_token_stats(self, text: str, sentences: List[str]) -> Dict[str, Any]:
        """取得全文與逐句的詞彙統計（tokens 與 lemmas）。"""
        tokens = re.findall(r"\b[\w']+\b", text.lower())
        token_counts = Counter(tokens)
        sentence_tokens = [re.findall(r"\b[\w']+\b", s.lower()) for s in sentences]

        lemma_counts: Counter = Counter()
        sentence_lemmas: List[Counter] = []
        doc = None
        if getattr(self.nlp, 'pipe_names', None):
            try:
                doc = self.nlp(text)
            except Exception:
                doc = None
        if doc:
            lemma_list = [token.lemma_.lower() for token in doc if token.text.strip()]
            lemma_counts = Counter(lemma_list)
            doc_sentence_lemmas = [
                Counter(token.lemma_.lower() for token in sent if token.text.strip())
                for sent in doc.sents
            ]
            if len(doc_sentence_lemmas) == len(sentences):
                sentence_lemmas = doc_sentence_lemmas

        if not lemma_counts:
            lemma_list = [self._simple_lemma(tok) for tok in tokens]
            lemma_counts = Counter(lemma_list)

        if not sentence_lemmas:
            sentence_lemmas = [
                Counter(self._simple_lemma(tok) for tok in sent_tokens)
                for sent_tokens in sentence_tokens
            ]

        return {
            'tokens': tokens,
            'token_counts': token_counts,
            'lemma_counts': lemma_counts,
            'sentence_tokens': sentence_tokens,
            'sentence_lemmas': sentence_lemmas
        }

    def check(self, text: str, story_title: str = "Story") -> Dict:
        """主要情感影響力檢測接口

        簡單流程：
        1) 文體檢測 → 決定 AI 與客觀指標的融合比例
        2) GoEmotions 逐段推理 → 產生情感分佈與弧線
        3) 基於模型輸出計算四項：多樣性/強度/共鳴/真實性
        4) AI 分析補充（短篇/詩歌給適度補償）
        5) 合成最終分，附上建議與細節
        """
        # 🎭 文體檢測
        genre_info = self.genre_detector.detect(text, story_title)
        genre_params = self.genre_detector.get_scoring_params(genre_info)
        
        # 根據文體動態調整 AI 和客觀指標的權重
        ai_weight = genre_params['emotional']['ai_weight']
        objective_weight = genre_params['emotional']['objective_weight']

        self._debug(
            f"🎭 情感評估文體調整: {genre_info['dominant']} → AI權重={ai_weight:.2f}, 客觀權重={objective_weight:.2f}"
        )
        
        # 分句
        sentences = self._split_sentences(text)
        
        if len(sentences) < 3:
            return self._create_minimal_result(text, story_title)

        token_stats = self._extract_token_stats(text, sentences)
        
        # ====================================================================
        # GoEmotions 逐段推理（核心改進）
        # ====================================================================
        # 將句子合併為段落（每段 2-4 句），避免短句碎片化誤判
        segments = self._build_segments(sentences, target_sentences_per_segment=3)
        goemotion_results = self.goemotion.predict_segments(segments) if self.goemotion.available else []
        
        use_model = bool(goemotion_results) and self.goemotion.available
        self._debug(f"🧠 GoEmotions 模式: {'啟用 ({} 段)'.format(len(segments)) if use_model else '降級為關鍵詞'}")
        
        # ====================================================================
        # 四子維度分析（模型驅動 vs. 關鍵詞降級）
        # ====================================================================
        if use_model:
            diversity_score, diversity_details = self._analyze_diversity_model(goemotion_results)
            intensity_score, intensity_details = self._analyze_intensity_model(goemotion_results, text, token_stats)
            resonance_score, resonance_details = self._analyze_resonance_model(goemotion_results, text, sentences, token_stats)
            authenticity_score, authenticity_details = self._analyze_authenticity_model(goemotion_results, text, sentences, token_stats)
        else:
            # 降級：使用原始關鍵詞方式
            diversity_score, diversity_details = self._analyze_emotional_diversity(text, sentences, token_stats)
            intensity_score, intensity_details = self._analyze_emotional_intensity(text, token_stats)
            resonance_score, resonance_details = self._analyze_emotional_resonance(text, sentences, token_stats)
            authenticity_score, authenticity_details = self._analyze_emotional_authenticity(text, sentences, token_stats)
        
        # 5. AI 深度分析（權重由文體決定）
        ai_score, ai_insights = self._ai_emotional_analysis(text, story_title)
        
        # 計算最終分數
        objective_score = (
            diversity_score * self.sub_weights['diversity'] +
            intensity_score * self.sub_weights['intensity'] +
            resonance_score * self.sub_weights['resonance'] +
            authenticity_score * self.sub_weights['authenticity']
        )
        
        # 🎯 根據文體動態融合 AI 分析
        final_score = objective_score * objective_weight + ai_score * ai_weight
        
        # 🎯 文體特定調整
        word_count = len(text.split())
        
        # 短篇補償
        if word_count < 500 and genre_info['dominant'] in ['poem', 'fable', 'short_story']:
            avg_emotion_density = (diversity_score + intensity_score) / 2.0
            
            if genre_info['dominant'] == 'poem' and genre_info['confidence'] > 0.5:
                boost = min(12.0, avg_emotion_density * 0.15)
                final_score = min(100.0, final_score + boost)
                self._debug(f"  📝 詩歌補償: +{boost:.1f}")
            elif avg_emotion_density >= 45:
                base_boost = (avg_emotion_density - 45) * 0.2 + 3.0
                if word_count < 300:
                    boost = min(8.0, base_boost)
                else:
                    boost = min(6.0, base_boost * 0.75)
                final_score = min(100.0, final_score + boost)
                self._debug(f"  📖 短篇補償: +{boost:.1f}")
        
        # 寓言/童話共鳴補償
        if genre_info['dominant'] in ['fable', 'fairy_tale'] and genre_info['confidence'] > 0.5:
            base_empathy = (resonance_score + authenticity_score) / 2.0
            if base_empathy >= 40:
                boost = min(8.0, (base_empathy - 40.0) * 0.12 + 2.5)
                final_score = min(100.0, final_score + boost)
                self._debug(f"  🦊 {genre_info['dominant']}共鳴補償: +{boost:.1f}")
        
        # 高共鳴力補償
        if resonance_score >= 65:
            resonance_gap = resonance_score - final_score
            if resonance_gap > 5:
                boost = min(8.0, (resonance_gap - 5) * 0.4 + 2.5)
                final_score = min(100.0, final_score + boost)
                self._debug(f"  💫 高共鳴補償: +{boost:.1f}")
            elif resonance_score >= 70 and final_score < 78:
                boost = min(6.0, (70 - final_score) * 0.25 + 3.0)
                final_score = min(100.0, final_score + boost)
        
        # 象徵/隱喻表達補償
        if intensity_score < 65 and resonance_score >= 65 and authenticity_score >= 60:
            symbolic_boost = min(7.0, (resonance_score - 65) * 0.2 + 2.5)
            final_score = min(100.0, final_score + symbolic_boost)
            self._debug(f"  🎨 象徵性表達補償: +{symbolic_boost:.1f}")
        
        # 經典作品補償
        if resonance_score >= 70 and authenticity_score >= 70 and final_score < 80:
            classic_boost = min(5.0, (min(resonance_score, authenticity_score) - 70) * 0.3 + 2.0)
            final_score = min(100.0, final_score + classic_boost)

        # 主題稀少防膨脹抑制
        try:
            themes_count = len(resonance_details.get('universal_themes', {}) or {})
            dialogue_emotions = float(resonance_details.get('dialogue_count', 0) or 0)
            cliche_count = int(authenticity_details.get('cliche_count', 0) or 0)
            if (
                themes_count <= 1 and
                authenticity_score < 58 and
                (intensity_score >= 70 or dialogue_emotions >= 8)
            ):
                penalty = 3.0
                if cliche_count >= 3:
                    penalty += 3.0
                elif cliche_count >= 2:
                    penalty += 2.0
                if dialogue_emotions >= 12:
                    penalty += 2.0
                elif dialogue_emotions >= 10:
                    penalty += 1.5
                if diversity_score < 45:
                    penalty += 1.5
                elif diversity_score < 50:
                    penalty += 1.0
                penalty = min(penalty, 10.0)
                if penalty > 0:
                    final_score = max(0.0, final_score - penalty)
                    self._debug(f"  🛡️ 主題稀少抑制: -{penalty:.1f}")
        except Exception:
            pass
        
        # 計算置信度
        confidence = self._calculate_confidence(diversity_details, intensity_details, 
                                                resonance_details, authenticity_details)

        return {
            'dimension': 'emotional_impact',
            'score': final_score,
            'scores': EmotionalImpactScores(
                diversity=diversity_score,
                intensity=intensity_score,
                resonance=resonance_score,
                authenticity=authenticity_score,
                final=final_score,
                confidence=confidence
            ),
            'details': {
                'diversity': diversity_details,
                'intensity': intensity_details,
                'resonance': resonance_details,
                'authenticity': authenticity_details,
                'goemotion_enabled': use_model,
            },
            'ai_insights': ai_insights,
            'suggestions': self._generate_suggestions(diversity_score, intensity_score, 
                                                     resonance_score, authenticity_score)
        }

    def _debug(self, message: str) -> None:
        if self.debug_logs:
            self.logger.debug(message)
    
    def _load_keywords(self, category: str, fallback: List[str]) -> List[str]:
        keywords = load_category_keywords(self.local_categories, category, fallback)
        return list(keywords)

    def _load_emotion_keywords(self) -> Dict[str, Dict[str, Any]]:
        emotion_map: Dict[str, Dict[str, Any]] = {}
        for emotion, config in DEFAULT_EMOTION_KEYWORDS.items():
            words = self._load_keywords(f"emotion.{emotion}.words", config['words'])
            emotion_map[emotion] = {
                'words': words,
                'intensity': config['intensity']
            }
        return emotion_map

    def _load_universal_themes(self) -> Dict[str, List[str]]:
        themes: Dict[str, List[str]] = {}
        for theme, fallback in DEFAULT_UNIVERSAL_THEMES.items():
            keywords = self._load_keywords(f"emotion.universal_themes.{theme}", fallback)
            if keywords:
                themes[theme] = keywords
        return themes

    # =================================================================
    # 段落建構（GoEmotions 推理用）
    # =================================================================

    def _build_segments(self, sentences: List[str], target_sentences_per_segment: int = 3) -> List[str]:
        """將句子合併為段落，每段約 target 句。
        
        避免逐句推理造成的碎片化（如 'He said.' 被判為 neutral），
        合併後的段落能提供更多上下文給模型。
        """
        if not sentences:
            return []
        segments = []
        current_segment: List[str] = []
        for sent in sentences:
            current_segment.append(sent)
            if len(current_segment) >= target_sentences_per_segment:
                segments.append(' '.join(current_segment))
                current_segment = []
        if current_segment:
            # 最後不足 target 的句子：若很短就併入上一段
            remainder = ' '.join(current_segment)
            if segments and len(current_segment) == 1 and len(remainder.split()) < 10:
                segments[-1] = segments[-1] + ' ' + remainder
            else:
                segments.append(remainder)
        return segments

    # =================================================================
    # GoEmotions 模型驅動的四子維度分析
    # =================================================================

    def _analyze_diversity_model(self, goemotion_results: List[Dict[str, Any]]) -> Tuple[float, Dict]:
        """基於 GoEmotions 的情感多樣性分析。
        
        改進：用模型預測的 28 類情緒分佈取代 8 類關鍵詞匹配，
        能捕捉到「admiration」「curiosity」「remorse」等詞典方式無法覆蓋的情感。
        """
        if not goemotion_results:
            return 50.0, {'method': 'fallback'}
        
        # 統計出現過的情緒類型（28 類細粒度）
        all_detected_emotions: Counter = Counter()
        family_counts: Counter = Counter()  # 8 大族群
        segment_emotions: List[Set[str]] = []

        for result in goemotion_results:
            seg_emos = set()
            for label, prob in result.get('emotions', {}).items():
                all_detected_emotions[label] += 1
                family = GOEMOTION_TO_FAMILY.get(label, 'neutral')
                if family != 'neutral':
                    family_counts[family] += 1
                    seg_emos.add(family)
            segment_emotions.append(seg_emos)

        # 細粒度多樣性（28 類中出現了多少類）
        unique_fine = len(all_detected_emotions)
        # 粗粒度多樣性（8 大族群中出現了多少）
        unique_family = len(family_counts)

        # 類型多樣性分數（8 族群滿分需 5 種以上）
        if unique_family >= 6:
            type_score = 100
        elif unique_family >= 5:
            type_score = 90
        elif unique_family >= 4:
            type_score = 78
        elif unique_family >= 3:
            type_score = 65
        elif unique_family >= 2:
            type_score = 50
        else:
            type_score = 25

        # 細粒度加成（28 類中偵測到越多種越好）
        fine_bonus = min(15, (unique_fine - unique_family) * 2) if unique_fine > unique_family else 0

        # 均衡度分數（各族群出現頻率的標準差越小越均衡）
        if len(family_counts) > 1:
            total = sum(family_counts.values())
            ratios = [v / total for v in family_counts.values()]
            balance_score = max(0, (1 - np.std(ratios) * 2.5)) * 100
        else:
            balance_score = 30

        # 情感轉折分數（段落間主導情緒是否有變化）
        transitions = 0
        prev_family = None
        for result in goemotion_results:
            current_family = result.get('family', 'neutral')
            if prev_family and current_family != prev_family and current_family != 'neutral':
                transitions += 1
            prev_family = current_family
        transition_score = min(transitions * 15, 100)

        diversity_score = type_score * 0.35 + balance_score * 0.25 + transition_score * 0.25 + fine_bonus * 1.0

        return min(100, diversity_score), {
            'method': 'goemotion',
            'unique_emotions_28': unique_fine,
            'unique_families_8': unique_family,
            'family_counts': dict(family_counts),
            'fine_emotions': dict(all_detected_emotions),
            'emotional_transitions': transitions,
            'type_score': type_score,
            'balance_score': balance_score,
            'transition_score': transition_score,
            'fine_bonus': fine_bonus,
            # 相容欄位
            'unique_emotions': unique_family,
            'total_emotion_words': sum(all_detected_emotions.values()),
            'transitions': transitions,
        }

    def _analyze_intensity_model(self, goemotion_results: List[Dict[str, Any]],
                                  text: str, token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """基於 GoEmotions 的情感強度分析。
        
        改進：用模型輸出的 arousal（情感激活度）和機率值取代
        關鍵詞 intensity 權重的簡單加總。
        """
        if not goemotion_results:
            return 50.0, {'method': 'fallback'}

        # 1. 模型驅動：arousal 均值和峰值
        arousal_values = [r['arousal'] for r in goemotion_results]
        mean_arousal = np.mean(arousal_values) if arousal_values else 0.0
        peak_arousal = max(arousal_values) if arousal_values else 0.0
        
        # 高 arousal 段落的比例
        high_arousal_ratio = sum(1 for a in arousal_values if a > 0.5) / max(len(arousal_values), 1)
        
        # arousal 分數（0-1 映射到 0-100）
        arousal_score = (mean_arousal * 0.4 + peak_arousal * 0.35 + high_arousal_ratio * 0.25) * 100

        # 2. 高強度情緒的機率平均值
        high_intensity_probs = []
        for r in goemotion_results:
            for emo in HIGH_AROUSAL_EMOTIONS:
                p = r.get('all_probs', {}).get(emo, 0.0)
                if p > 0.2:
                    high_intensity_probs.append(p)
        hi_mean = np.mean(high_intensity_probs) if high_intensity_probs else 0.0
        hi_score = min(100, hi_mean * 130)  # 放大到 0-100 量級

        # 3. 保留部分表層特徵（驚嘆號、動作動詞）作為補充
        token_counts = token_stats.get('token_counts', Counter())
        lemma_counts = token_stats.get('lemma_counts', Counter())
        exclamations = text.count('!') + text.count('！')
        action_count = sum(lemma_counts.get(verb.lower(), 0) for verb in self.action_verbs)
        surface_score = min((exclamations * 4 + action_count * 6), 100)

        # 加權合成（模型為主 70%，表層為輔 30%）
        intensity_score = arousal_score * 0.45 + hi_score * 0.25 + surface_score * 0.30

        return min(100, intensity_score), {
            'method': 'goemotion',
            'mean_arousal': round(mean_arousal, 3),
            'peak_arousal': round(peak_arousal, 3),
            'high_arousal_ratio': round(high_arousal_ratio, 3),
            'high_intensity_emotion_avg': round(hi_mean, 3),
            'exclamations': exclamations,
            'action_verbs': action_count,
            'arousal_score': round(arousal_score, 1),
            'hi_score': round(hi_score, 1),
            'surface_score': round(surface_score, 1),
        }

    def _analyze_resonance_model(self, goemotion_results: List[Dict[str, Any]],
                                  text: str, sentences: List[str],
                                  token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """基於 GoEmotions 的情感共鳴力分析。
        
        改進：
        1. 用模型預測的情感弧線（valence 序列）取代關鍵詞匹配的時間線
        2. 計算弧線的「敘事完整度」（是否有起伏和收束）
        3. 偵測情感高潮點（peak moments）
        """
        if not goemotion_results:
            return 50.0, {'method': 'fallback'}

        lemma_counts = token_stats.get('lemma_counts', Counter())

        # 1. 普世主題偵測（保留關鍵詞方式，這部分模型無法取代）
        theme_counts: Dict[str, int] = {}
        for theme, keywords in self.universal_themes.items():
            count = sum(lemma_counts.get(word.lower(), 0) for word in keywords)
            if count > 0:
                theme_counts[theme] = count
        theme_score = min(len(theme_counts) * 25, 100)

        # 2. 情感弧線分析（模型驅動）
        valence_sequence = []
        for r in goemotion_results:
            v = r.get('valence', 'neutral')
            valence_sequence.append(v)

        # 弧線分析指標
        arc_transitions = 0
        for i in range(1, len(valence_sequence)):
            if valence_sequence[i] != valence_sequence[i - 1]:
                arc_transitions += 1

        # 情感高潮偵測（arousal 最高的段落）
        arousal_values = [r.get('arousal', 0) for r in goemotion_results]
        if arousal_values:
            peak_idx = int(np.argmax(arousal_values))
            peak_position_ratio = peak_idx / max(len(arousal_values) - 1, 1)
            # 高潮在中後段（40%-85%）更符合敘事結構
            if 0.4 <= peak_position_ratio <= 0.85:
                peak_position_score = 100
            elif 0.25 <= peak_position_ratio <= 0.90:
                peak_position_score = 75
            else:
                peak_position_score = 50
        else:
            peak_position_score = 50

        # 弧線是否有收束（最後段是否為正向或中性）
        if valence_sequence:
            ending_valence = valence_sequence[-1]
            if ending_valence == 'positive':
                resolution_score = 90
            elif ending_valence == 'neutral':
                resolution_score = 70
            else:  # negative ending (tragedy arc) - 也有價值
                resolution_score = 60
        else:
            resolution_score = 50

        arc_score = (
            min(arc_transitions * 15, 60) * 0.35 +
            peak_position_score * 0.35 +
            resolution_score * 0.30
        )

        # 3. 對話情感偵測（保留）
        dialogue_markers = {
            'said', 'asked', 'replied', 'answered', 'told', 'cried', 'sobbed', 'shouted',
            'whispered', 'yelled', 'called', 'pleaded', 'promised'
        }
        sentence_lemmas = token_stats.get('sentence_lemmas', [])
        dialogue_sentences = sum(1 for lemmas in sentence_lemmas if any(lemmas.get(m, 0) for m in dialogue_markers))
        dialogue_quotes = sum(1 for s in sentences if any(ch in s for ch in ['"', '"', '"']))
        dialogue_emotions = min(len(sentences), dialogue_sentences + dialogue_quotes)
        
        dialogue_base = min(dialogue_emotions * 2.5, 100)
        theme_count = len(theme_counts)
        if theme_count <= 1:
            depth_score = dialogue_base * 0.7
        elif theme_count == 2:
            depth_score = dialogue_base * 0.85
        else:
            depth_score = dialogue_base

        resonance_score = (
            theme_score * 0.35 +
            arc_score * 0.40 +
            depth_score * 0.25
        )

        return min(100, resonance_score), {
            'method': 'goemotion',
            'universal_themes': theme_counts,
            'valence_arc': valence_sequence,
            'arc_transitions': arc_transitions,
            'peak_position_ratio': round(peak_position_ratio, 2) if arousal_values else None,
            'peak_position_score': peak_position_score,
            'resolution_score': resolution_score,
            'dialogue_count': int(dialogue_emotions),
            'theme_score': theme_score,
            'arc_score': round(arc_score, 1),
            'depth_score': round(depth_score, 1),
            'emotional_turns': arc_transitions,
        }

    def _analyze_authenticity_model(self, goemotion_results: List[Dict[str, Any]],
                                     text: str, sentences: List[str],
                                     token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """基於 GoEmotions 的情感真實性分析。
        
        改進：
        1. 用模型預測的情感一致性取代關鍵詞矛盾偵測
        2. 情感過渡的平滑度分析（突兀的正負切換 = 不真實）
        3. 保留陳腔濫調偵測和具體表達計數
        """
        if not goemotion_results:
            return 50.0, {'method': 'fallback'}

        text_lower = text.lower()
        lemma_counts = token_stats.get('lemma_counts', Counter())

        # 1. 陳腔濫調偵測（保留，模型無法取代）
        cliches = [
            'happily ever after', 'lived happily', 'true love', 'love at first sight',
            'broken heart', 'tears of joy', 'evil villain', 'brave hero'
        ]
        cliche_count = sum(text_lower.count(phrase) for phrase in cliches)
        cliche_penalty = min(cliche_count * 15, 50)
        cliche_score = 100 - cliche_penalty

        # 2. 具體表達計數（保留，模型無法取代）
        concrete_expressions = [
            'tear', 'tears', 'smile', 'laugh', 'sob', 'cry', 'sigh', 'gasp', 'hug',
            'hold', 'embrace', 'hand', 'hands', 'arm', 'arms', 'face', 'cheek', 'voice',
            'eyes', 'heartbeat', 'breath', 'tremble', 'shiver'
        ]
        concrete_count = sum(lemma_counts.get(word, 0) for word in concrete_expressions)
        concrete_score = min(concrete_count * 4, 100)

        # 3. 情感過渡平滑度（模型驅動 — 取代關鍵詞矛盾偵測）
        #    檢查相鄰段落的 valence 是否有「不合理的突然反轉」
        #    合理的反轉：有過渡詞（but, however）或段落較長
        #    不合理的反轉：極短段落內正負極性突變
        abrupt_contradictions = 0
        smooth_transitions = 0
        transition_words = set(self.emotional_transitions)
        
        for i in range(1, len(goemotion_results)):
            prev_valence = goemotion_results[i - 1].get('valence', 'neutral')
            curr_valence = goemotion_results[i].get('valence', 'neutral')
            
            if prev_valence != 'neutral' and curr_valence != 'neutral' and prev_valence != curr_valence:
                # 正負極性反轉
                segment_text = goemotion_results[i].get('text_preview', '').lower()
                has_transition = any(tw in segment_text for tw in transition_words)
                
                if has_transition:
                    smooth_transitions += 1  # 有過渡詞 = 合理反轉
                else:
                    # 檢查 confidence：高信心的突然反轉更可能是真正的矛盾
                    prev_conf = goemotion_results[i - 1].get('dominant_prob', 0.5)
                    curr_conf = goemotion_results[i].get('dominant_prob', 0.5)
                    if prev_conf > 0.5 and curr_conf > 0.5:
                        abrupt_contradictions += 1
        
        # 突兀矛盾懲罰（每個 -15 分，上限 -45）
        contradiction_penalty = min(abrupt_contradictions * 15, 45)
        # 平滑過渡加分（每個 +8 分，上限 +20）
        transition_bonus = min(smooth_transitions * 8, 20)
        consistency_score = max(0, 100 - contradiction_penalty + transition_bonus)
        consistency_score = min(100, consistency_score)

        # 4. 情感深度一致性（模型驅動）
        #    段落內的多情緒共存（mixed emotions）= 更真實的情感表現
        mixed_emotion_count = 0
        for r in goemotion_results:
            detected = r.get('emotions', {})
            if len(detected) >= 2:
                # 同時有正面和負面情緒 = 複雜情感（更真實）
                has_positive = any(e in POSITIVE_EMOTIONS for e in detected)
                has_negative = any(e in NEGATIVE_EMOTIONS for e in detected)
                if has_positive and has_negative:
                    mixed_emotion_count += 1
        mixed_bonus = min(mixed_emotion_count * 8, 20)

        authenticity_score = (
            cliche_score * 0.25 +
            concrete_score * 0.30 +
            consistency_score * 0.30 +
            min(100, mixed_bonus * 5) * 0.15
        )

        return min(100, authenticity_score), {
            'method': 'goemotion',
            'cliche_count': cliche_count,
            'concrete_expressions': concrete_count,
            'abrupt_contradictions': abrupt_contradictions,
            'smooth_transitions': smooth_transitions,
            'mixed_emotion_segments': mixed_emotion_count,
            'cliche_score': cliche_score,
            'concrete_score': concrete_score,
            'consistency_score': consistency_score,
            'mixed_bonus': mixed_bonus,
            # 相容欄位
            'emotional_contradictions': abrupt_contradictions,
        }
    
    def _analyze_emotional_diversity(self, text: str, sentences: List[str], token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """分析情感多樣性，採用詞形還原後的統計提升敏感度。"""
        lemma_counts: Counter = token_stats['lemma_counts']
        sentence_lemmas: List[Counter] = token_stats['sentence_lemmas']
        emotion_counts = defaultdict(int)
        emotion_positions = defaultdict(list)

        for emotion_type, emotion_data in self.emotion_keywords.items():
            base_words = [word.lower() for word in emotion_data['words']]
            total_count = sum(lemma_counts.get(word, 0) for word in base_words)
            if total_count <= 0:
                continue
            emotion_counts[emotion_type] = total_count
            for idx, lemma_counter in enumerate(sentence_lemmas):
                if any(lemma_counter.get(word, 0) for word in base_words):
                    emotion_positions[emotion_type].append(idx)

        unique_emotions = len(emotion_counts)
        total_emotions = sum(emotion_counts.values())

        if unique_emotions >= 5:
            type_score = 100
        elif unique_emotions >= 3:
            type_score = 70 + (unique_emotions - 3) * 15
        elif unique_emotions >= 2:
            type_score = 50 + (unique_emotions - 2) * 20
        else:
            type_score = unique_emotions * 30

        if total_emotions > 0:
            emotion_ratios = [emotion_counts[e] / total_emotions for e in emotion_counts]
            balance_score = (1 - np.std(emotion_ratios)) * 100 if len(emotion_ratios) > 1 else 55
        else:
            balance_score = 0

        transition_hits = sum(token_stats['token_counts'].get(word, 0) for word in self.emotional_transitions)
        transition_score = min(transition_hits * 12, 100)

        diversity_score = type_score * 0.4 + balance_score * 0.3 + transition_score * 0.3

        return diversity_score, {
            'unique_emotions': unique_emotions,
            'total_emotion_words': total_emotions,
            'emotion_counts': dict(emotion_counts),
            'emotion_positions': {k: len(v) for k, v in emotion_positions.items()},
            'transitions': transition_hits,
            'type_score': type_score,
            'balance_score': balance_score,
            'transition_score': transition_score
        }
    
    def _analyze_emotional_intensity(self, text: str, token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """分析情感強度"""
        token_counts: Counter = token_stats['token_counts']
        lemma_counts: Counter = token_stats['lemma_counts']

        intensifier_count = sum(token_counts.get(word, 0) for word in self.intensifiers)

        high_intensity_total = 0
        for emotion_type, emotion_data in self.emotion_keywords.items():
            if emotion_data['intensity'] < 0.8:
                continue
            base_words = [word.lower() for word in emotion_data['words']]
            high_intensity_total += sum(lemma_counts.get(word, 0) for word in base_words)

        exclamations = text.count('!') + text.count('！')
        action_count = sum(lemma_counts.get(verb.lower(), 0) for verb in self.action_verbs)

        intensifier_score = min(intensifier_count * 8, 100)
        high_intensity_score = min(high_intensity_total * 12, 100)
        expression_score = min((exclamations * 5 + action_count * 8), 100)

        intensity_score = (
            intensifier_score * 0.3 +
            high_intensity_score * 0.4 +
            expression_score * 0.3
        )

        return intensity_score, {
            'intensifier_count': intensifier_count,
            'high_intensity_emotions': high_intensity_total,
            'exclamations': exclamations,
            'action_verbs': action_count,
            'intensifier_score': intensifier_score,
            'high_intensity_score': high_intensity_score,
            'expression_score': expression_score
        }
    
    def _analyze_emotional_resonance(self, text: str, sentences: List[str], token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """分析情感共鳴力（最重要，35%權重）"""
        lemma_counts: Counter = token_stats['lemma_counts']
        sentence_lemmas: List[Counter] = token_stats['sentence_lemmas']

        theme_counts: Dict[str, int] = {}
        for theme, keywords in self.universal_themes.items():
            count = sum(lemma_counts.get(word.lower(), 0) for word in keywords)
            if count > 0:
                theme_counts[theme] = count

        emotion_timeline: List[str] = []
        for lemma_counter in sentence_lemmas:
            sentence_emotions = {}
            for emotion_type, emotion_data in self.emotion_keywords.items():
                base_words = [word.lower() for word in emotion_data['words']]
                count = sum(lemma_counter.get(word, 0) for word in base_words)
                if count > 0:
                    sentence_emotions[emotion_type] = count
            if sentence_emotions:
                dominant_emotion = max(sentence_emotions, key=sentence_emotions.get)
                emotion_timeline.append(dominant_emotion)
            else:
                emotion_timeline.append('neutral')

        emotional_turns = 0
        for i in range(1, len(emotion_timeline)):
            if emotion_timeline[i] != emotion_timeline[i - 1] and emotion_timeline[i] != 'neutral':
                emotional_turns += 1

        dialogue_markers = {
            'said', 'asked', 'replied', 'answered', 'told', 'cried', 'sobbed', 'shouted',
            'whispered', 'yelled', 'called', 'pleaded', 'promised'
        }
        dialogue_sentences = sum(1 for lemmas in sentence_lemmas if any(lemmas.get(marker, 0) for marker in dialogue_markers))
        dialogue_quotes = sum(1 for s in sentences if any(ch in s for ch in ['"', '“', '”']))
        dialogue_emotions = min(len(sentences), dialogue_sentences + dialogue_quotes)

        theme_score = min(len(theme_counts) * 25, 100)
        arc_score = min(emotional_turns * 12, 100)
        # 對以對話堆疊為主、但普世主題稀少的文本降低對話帶來的深度分數，避免喜劇/民間故事類型被過度加分
        dialogue_base = min(dialogue_emotions * 2.5, 100)  # 從3降到2.5，減少對話膨脹
        theme_count = len(theme_counts)
        if theme_count <= 1:
            depth_score = dialogue_base * 0.7
        elif theme_count == 2:
            depth_score = dialogue_base * 0.85
        else:
            depth_score = dialogue_base

        resonance_score = (
            theme_score * 0.4 +
            arc_score * 0.35 +
            depth_score * 0.25
        )

        return resonance_score, {
            'universal_themes': theme_counts,
            'emotional_turns': emotional_turns,
            'dialogue_count': int(dialogue_emotions),
            'emotion_timeline_length': len(emotion_timeline),
            'theme_score': theme_score,
            'arc_score': arc_score,
            'depth_score': depth_score
        }
    
    def _analyze_emotional_authenticity(self, text: str, sentences: List[str], token_stats: Dict[str, Any]) -> Tuple[float, Dict]:
        """分析情感真實性"""
        text_lower = text.lower()
        lemma_counts: Counter = token_stats['lemma_counts']
        sentence_lemmas: List[Counter] = token_stats['sentence_lemmas']

        cliches = [
            'happily ever after', 'lived happily', 'true love', 'love at first sight',
            'broken heart', 'tears of joy', 'evil villain', 'brave hero'
        ]
        cliche_count = sum(text_lower.count(phrase) for phrase in cliches)

        concrete_expressions = [
            'tear', 'tears', 'smile', 'laugh', 'sob', 'cry', 'sigh', 'gasp', 'hug',
            'hold', 'embrace', 'hand', 'hands', 'arm', 'arms', 'face', 'cheek', 'voice',
            'eyes', 'heartbeat', 'breath', 'tremble', 'shiver'
        ]
        concrete_count = sum(lemma_counts.get(word, 0) for word in concrete_expressions)

        contradictions = 0
        positive_emotions = ['joy', 'love', 'trust']
        negative_emotions = ['sadness', 'fear', 'anger', 'disgust']
        transition_tokens = {word.lower() for word in self.emotional_transitions}

        for i in range(len(sentence_lemmas) - 1):
            current = sentence_lemmas[i]
            nxt = sentence_lemmas[i + 1]

            current_positive = any(
                any(current.get(word.lower(), 0) for word in self.emotion_keywords[e]['words'])
                for e in positive_emotions
            )
            current_negative = any(
                any(current.get(word.lower(), 0) for word in self.emotion_keywords[e]['words'])
                for e in negative_emotions
            )
            next_positive = any(
                any(nxt.get(word.lower(), 0) for word in self.emotion_keywords[e]['words'])
                for e in positive_emotions
            )
            next_negative = any(
                any(nxt.get(word.lower(), 0) for word in self.emotion_keywords[e]['words'])
                for e in negative_emotions
            )

            has_transition = any(current.get(token, 0) or nxt.get(token, 0) for token in transition_tokens)

            if not has_transition and ((current_positive and next_negative) or (current_negative and next_positive)):
                contradictions += 1

        cliche_penalty = min(cliche_count * 15, 50)
        cliche_score = 100 - cliche_penalty
        concrete_score = min(concrete_count * 4, 100)
        consistency_penalty = min(contradictions * 20, 60)
        consistency_score = 100 - consistency_penalty

        authenticity_score = (
            cliche_score * 0.3 +
            concrete_score * 0.4 +
            consistency_score * 0.3
        )

        return authenticity_score, {
            'cliche_count': cliche_count,
            'concrete_expressions': concrete_count,
            'emotional_contradictions': contradictions,
            'cliche_score': cliche_score,
            'concrete_score': concrete_score,
            'consistency_score': consistency_score
        }
    
    def _ai_emotional_analysis(self, text: str, story_title: str) -> Tuple[float, Dict]:
        """AI 深度情感分析（30% 權重）"""
        if not self.ai or not self.ai.model_available:
            return 50.0, {
                'available': False,
                'reason': 'AI model not available',
                'confidence': normalize_confidence_0_1(0.4, 0.4),
            }
        
        try:
            # 限制文本長度
            max_length = 1500
            text_sample = text[:max_length] if len(text) > max_length else text
            
            prompt = f"""Analyze the emotional impact of this story titled "{story_title}".

Story excerpt:
{text_sample}

Rate the following aspects (0-100):
1. Overall emotional engagement
2. Character emotional depth
3. Reader connection potential
4. Emotional authenticity

Provide scores in format:
Engagement: [score]
Depth: [score]
Connection: [score]
Authenticity: [score]"""

            response = self.ai._generate_text(prompt, max_length=200)
            
            # 解析評分
            scores = {}
            for line in response.split('\n'):
                for key in ['Engagement', 'Depth', 'Connection', 'Authenticity']:
                    if key.lower() in line.lower():
                        match = re.search(r'(\d+)', line)
                        if match:
                            scores[key.lower()] = int(match.group(1))
            
            if scores:
                avg_score = normalize_score_0_100(
                    np.mean([v for v in scores.values() if 0 <= v <= 100]),
                    50.0,
                )
                return avg_score, {
                    'available': True,
                    'scores': scores,
                    'analysis': response[:300],
                    'confidence': normalize_confidence_0_1(0.7, 0.7),
                }
            else:
                return 50.0, {
                    'available': False,
                    'reason': 'Failed to parse AI response',
                    'confidence': normalize_confidence_0_1(0.4, 0.4),
                }
                
        except Exception as e:
            return 50.0, {
                'available': False,
                'reason': str(e),
                'confidence': normalize_confidence_0_1(0.3, 0.3),
            }
    
    def _calculate_confidence(self, diversity_details: Dict, intensity_details: Dict,
                             resonance_details: Dict, authenticity_details: Dict) -> float:
        """計算評估置信度"""
        factors = []
        
        # 情感詞數量充足性
        if diversity_details['total_emotion_words'] >= 10:
            factors.append(1.0)
        elif diversity_details['total_emotion_words'] >= 5:
            factors.append(0.8)
        else:
            factors.append(0.5)
        
        # 情感類型多樣性
        if diversity_details['unique_emotions'] >= 3:
            factors.append(1.0)
        else:
            factors.append(0.6)
        
        # 具體性
        if authenticity_details['concrete_expressions'] >= 8:
            factors.append(1.0)
        else:
            factors.append(0.7)
        
        return np.mean(factors)
    
    def _generate_suggestions(self, diversity_score: float, intensity_score: float,
                             resonance_score: float, authenticity_score: float) -> List[str]:
        """生成改進建議"""
        suggestions = []
        
        if diversity_score < 60:
            suggestions.append("增加情感類型的多樣性，避免單一情感主導整個故事")
        
        if intensity_score < 60:
            suggestions.append("加強情感表達的力度，使用更生動的描寫和強化詞")
        
        if resonance_score < 60:
            suggestions.append("深化普世情感主題（家庭、友誼、成長等），增強讀者共鳴")
        
        if authenticity_score < 60:
            suggestions.append("避免陳詞濫調，使用更具體和真實的情感描寫")
        
        if not suggestions:
            suggestions.append("情感表達整體良好，繼續保持自然真摯的風格")
        
        return suggestions
    
    def _create_minimal_result(self, text: str, story_title: str) -> Dict:
        """創建最小化結果（文本太短時）"""
        return {
            'dimension': 'emotional_impact',
            'score': EMOTION_MINIMAL_RESULT_SCORE,
            'scores': EmotionalImpactScores(
                diversity=EMOTION_MINIMAL_RESULT_SCORE,
                intensity=EMOTION_MINIMAL_RESULT_SCORE,
                resonance=EMOTION_MINIMAL_RESULT_SCORE,
                authenticity=EMOTION_MINIMAL_RESULT_SCORE,
                final=EMOTION_MINIMAL_RESULT_SCORE,
                confidence=0.3
            ),
            'details': {
                'error': 'Text too short for emotional analysis',
                'min_sentences_required': 3
            },
            'ai_insights': {'available': False},
            'suggestions': ['故事太短，無法進行完整的情感分析']
        }
