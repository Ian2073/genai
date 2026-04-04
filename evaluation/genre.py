"""文體偵測工具，負責辨識敘事風格並提供評分參數建議。"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any, Dict, Mapping, Optional, Tuple

from kb import LocalCategoryMatcher

DEFAULT_GENRE_KEYWORDS = {
    "fable": {
        "strong": [
            "moral",
            "lesson",
            "moral of the story",
            "teaches us",
            "learned that",
        ],
        "medium": [
            "wise",
            "foolish",
            "greed",
            "honesty",
            "virtue",
            "vice",
        ],
        "animals": [
            "fox",
            "crow",
            "lion",
            "mouse",
            "ant",
            "grasshopper",
            "tortoise",
            "hare",
        ],
    },
    "fairy_tale": {
        "openings": [
            "once upon a time",
            "long ago",
            "in a faraway land",
        ],
        "endings": [
            "happily ever after",
            "lived happily",
            "never seen again",
        ],
        "magic": [
            "magic",
            "spell",
            "enchant",
            "fairy",
            "witch",
            "wizard",
            "curse",
            "transform",
        ],
        "royalty": [
            "king",
            "queen",
            "prince",
            "princess",
            "castle",
            "kingdom",
        ],
    },
    "poem": {
        "structure": True,
    },
}

GENRE_PARAMETER_TEMPLATES = {
    "poem": {
        "completeness": {
            "penalty_weight": 0.3,
            "min_floor": 50.0,
            "semantic_threshold": 0.5,
        },
        "emotional": {"ai_weight": 0.35, "objective_weight": 0.65},
        "coherence": {
            "transition_tolerance": 0.8,
            "logic_strictness": 0.3,
        },
    },
    "fable": {
        "completeness": {
            "penalty_weight": 0.5,
            "min_floor": 48.0,
            "semantic_threshold": 0.55,
        },
        "emotional": {"ai_weight": 0.30, "objective_weight": 0.70},
        "coherence": {
            "transition_tolerance": 0.7,
            "logic_strictness": 0.4,
        },
    },
    "fairy_tale": {
        "completeness": {
            "penalty_weight": 0.7,
            "min_floor": 45.0,
            "semantic_threshold": 0.6,
        },
        "emotional": {"ai_weight": 0.25, "objective_weight": 0.75},
        "coherence": {
            "transition_tolerance": 0.6,
            "logic_strictness": 0.5,
        },
    },
    "novel": {
        "completeness": {
            "penalty_weight": 1.0,
            "min_floor": 0.0,
            "semantic_threshold": 0.7,
        },
        "emotional": {"ai_weight": 0.3, "objective_weight": 0.7},
        "coherence": {
            "transition_tolerance": 0.3,
            "logic_strictness": 0.9,
        },
    },
    "short_story": {
        "completeness": {
            "penalty_weight": 0.8,
            "min_floor": 40.0,
            "semantic_threshold": 0.65,
        },
        "emotional": {"ai_weight": 0.35, "objective_weight": 0.65},
        "coherence": {
            "transition_tolerance": 0.5,
            "logic_strictness": 0.7,
        },
    },
}

NEUTRAL_PARAMS = {
    "completeness": {
        "penalty_weight": 0.8,
        "min_floor": 40.0,
        "semantic_threshold": 0.65,
    },
    "emotional": {"ai_weight": 0.35, "objective_weight": 0.65},
    "coherence": {"transition_tolerance": 0.5, "logic_strictness": 0.7},
}

PARAMETER_GROUP_KEYS = {
    "completeness": ("penalty_weight", "min_floor", "semantic_threshold"),
    "emotional": ("ai_weight", "objective_weight"),
    "coherence": ("transition_tolerance", "logic_strictness"),
}

PARAMETER_CLAMP_RANGES = {
    ("completeness", "penalty_weight"): (0.2, 1.2),
    ("completeness", "min_floor"): (0.0, 60.0),
    ("completeness", "semantic_threshold"): (0.45, 0.8),
    ("emotional", "ai_weight"): (0.2, 0.7),
    ("emotional", "objective_weight"): (0.3, 0.8),
    ("coherence", "transition_tolerance"): (0.3, 0.9),
    ("coherence", "logic_strictness"): (0.3, 0.95),
}


@dataclass(frozen=True)
class StoryFeatures:
    """封裝文本特徵，避免重複計算。"""

    text: str
    text_lower: str
    title_lower: str
    word_count: int
    lines: Tuple[str, ...]
    avg_line_length: float
    newline_density: float
    dialogue_estimate: int

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass(frozen=True)
class GenreDetectionResult:
    """文體偵測輸出格式。"""

    scores: Dict[str, float]
    dominant: str
    confidence: float
    raw_scores: Dict[str, float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scores": dict(self.scores),
            "dominant": self.dominant,
            "confidence": self.confidence,
            "raw_scores": dict(self.raw_scores),
        }


class GenreDetector:
    """辨識故事文體並輸出評分參數建議。"""

    def __init__(
        self,
        local_categories: Optional[LocalCategoryMatcher] = None,
        genre_keywords: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ) -> None:
        self.local_categories = local_categories or LocalCategoryMatcher()
        self.genre_keywords = self._load_genre_keywords(genre_keywords)

    def detect(self, text: str, story_title: str = "") -> Dict[str, Any]:
        """回傳文體分布以及主導文體。"""
        features = self._extract_features(text, story_title)
        raw_scores = self._compute_raw_scores(features)
        scores = self._normalize_scores(raw_scores)
        dominant, confidence = self._resolve_dominant(scores)
        result = GenreDetectionResult(scores, dominant, confidence, raw_scores)
        return result.as_dict()

    def get_scoring_params(
        self, genre_info: Mapping[str, Any] | GenreDetectionResult
    ) -> Dict[str, Dict[str, float]]:
        """依文體分布混合評分參數。"""
        if isinstance(genre_info, GenreDetectionResult):
            scores = dict(genre_info.scores)
            confidence = float(genre_info.confidence)
        else:
            scores = dict(genre_info.get("scores", {}))
            confidence = float(genre_info.get("confidence", 0.0))

        if not scores or confidence < 0.4:
            return {group: dict(values) for group, values in NEUTRAL_PARAMS.items()}

        top_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
        top_total = sum(weight for _, weight in top_items)
        if top_total <= 0:
            return {group: dict(values) for group, values in NEUTRAL_PARAMS.items()}

        mixed_weights = {genre: weight / top_total for genre, weight in top_items}
        mixed_params: Dict[str, Dict[str, float]] = {
            group: {key: 0.0 for key in keys} for group, keys in PARAMETER_GROUP_KEYS.items()
        }

        # 以前三高分的文體作權重混合，提高參數穩健性
        for genre, weight in mixed_weights.items():
            template = GENRE_PARAMETER_TEMPLATES.get(genre, NEUTRAL_PARAMS)
            for group, keys in PARAMETER_GROUP_KEYS.items():
                group_template = template.get(group, NEUTRAL_PARAMS[group])
                for key in keys:
                    mixed_params[group][key] += group_template[key] * weight

        self._clamp_params(mixed_params)
        return {
            group: {key: float(value) for key, value in values.items()}
            for group, values in mixed_params.items()
        }

    def _extract_features(self, text: str, story_title: str) -> StoryFeatures:
        """抽取文體判斷所需的統計特徵。"""
        text_lower = text.lower()
        word_count = len(text_lower.split())
        lines = tuple(line.strip() for line in text.splitlines() if line.strip())
        word_lengths = [len(line.split()) for line in lines if line]
        avg_line_length = fmean(word_lengths) if word_lengths else 0.0
        newline_density = len(lines) / max(word_count, 1)
        dialogue_pairs = max(text.count("\"") // 2, text.count("'") // 4)
        return StoryFeatures(
            text=text,
            text_lower=text_lower,
            title_lower=story_title.lower(),
            word_count=word_count,
            lines=lines,
            avg_line_length=avg_line_length,
            newline_density=newline_density,
            dialogue_estimate=dialogue_pairs,
        )

    def _compute_raw_scores(self, features: StoryFeatures) -> Dict[str, float]:
        """計算各文體的原始得分。"""
        raw_scores = {
            "poem": self._check_poem(features),
            "fable": self._check_fable(features),
            "fairy_tale": self._check_fairy_tale(features),
            "novel": self._check_novel(features.word_count),
            "short_story": 0.0,
        }
        raw_scores["short_story"] = self._check_short_story(features, raw_scores["novel"])
        return raw_scores

    def _normalize_scores(self, raw_scores: Mapping[str, float]) -> Dict[str, float]:
        positives = {genre: max(score, 0.0) for genre, score in raw_scores.items()}
        total = sum(positives.values())
        if total <= 0:
            return {genre: 0.0 for genre in positives}
        return {genre: value / total for genre, value in positives.items()}

    @staticmethod
    def _resolve_dominant(scores: Mapping[str, float]) -> Tuple[str, float]:
        if not scores:
            return "short_story", 0.0
        dominant_genre, confidence = max(scores.items(), key=lambda item: item[1])
        return dominant_genre, float(confidence)

    def _check_poem(self, features: StoryFeatures) -> float:
        if features.line_count < 3:
            return 0.0

        score = 0.0
        if features.avg_line_length < 8:
            score += 0.35
        elif features.avg_line_length < 12:
            score += 0.2

        if features.newline_density > 0.2:
            score += 0.25
        elif features.newline_density > 0.1:
            score += 0.15

        score += self._detect_rhyme(features.lines) * 0.3

        if features.word_count < 300:
            score += 0.1

        if any(
            keyword in features.text_lower or keyword in features.title_lower
            for keyword in ("song", "poem", "verse", "rhyme")
        ):
            score += 0.1

        return min(1.0, score)

    def _check_fable(self, features: StoryFeatures) -> float:
        score = 0.0
        text_lower = features.text_lower
        keywords = self.genre_keywords["fable"]

        strong_hits = sum(1 for kw in keywords["strong"] if kw in text_lower)
        if strong_hits >= 1:
            score += 0.4

        medium_hits = sum(1 for kw in keywords["medium"] if kw in text_lower)
        if medium_hits >= 2:
            score += 0.2

        animal_hits = sum(1 for kw in keywords["animals"] if kw in text_lower)
        if animal_hits >= 2:
            score += 0.2
        elif animal_hits >= 1:
            score += 0.1

        if 200 < features.word_count < 1000:
            score += 0.2
        elif features.word_count <= 200:
            score += 0.1

        closing_window = " ".join(text_lower.split()[-40:])
        if any(kw in closing_window for kw in keywords["strong"]):
            score += 0.05

        return min(1.0, score)

    def _check_fairy_tale(self, features: StoryFeatures) -> float:
        score = 0.0
        text_lower = features.text_lower
        keywords = self.genre_keywords["fairy_tale"]

        if any(phrase in text_lower for phrase in keywords["openings"]):
            score += 0.3

        if any(phrase in text_lower for phrase in keywords["endings"]):
            score += 0.2

        magic_hits = sum(1 for kw in keywords["magic"] if kw in text_lower)
        if magic_hits >= 3:
            score += 0.3
        elif magic_hits >= 1:
            score += 0.15

        royalty_hits = sum(1 for kw in keywords["royalty"] if kw in text_lower)
        if royalty_hits >= 2:
            score += 0.2
        elif royalty_hits >= 1:
            score += 0.1

        if 500 <= features.word_count <= 3000:
            score += 0.1

        return min(1.0, score)

    @staticmethod
    def _check_novel(word_count: int) -> float:
        if word_count > 5000:
            return 0.8
        if word_count > 3000:
            return 0.5
        if word_count > 2000:
            return 0.3
        return 0.0

    def _check_short_story(self, features: StoryFeatures, novel_score: float) -> float:
        score = 0.0
        word_count = features.word_count

        if 150 <= word_count <= 3200:
            score += 0.2
        if 300 <= word_count <= 2000:
            score += 0.15
        if word_count < 150:
            score += 0.05

        if features.dialogue_estimate >= 3:
            score += 0.1
        if features.line_count > 20 and features.avg_line_length >= 8:
            score += 0.05

        if word_count > 3500 or novel_score >= 0.5:
            score *= 0.6

        return min(1.0, score)

    @staticmethod
    def _detect_rhyme(lines: Tuple[str, ...]) -> float:
        if len(lines) < 4:
            return 0.0

        endings = []
        for line in lines:
            words = line.rstrip(".,!?;:'\"").split()
            if not words:
                continue
            last_word = words[-1].lower()
            if len(last_word) >= 3:
                endings.append(last_word[-3:])
            elif len(last_word) >= 2:
                endings.append(last_word[-2:])

        if len(endings) < 4:
            return 0.0

        rhyme_pairs = 0
        for index in range(0, len(endings) - 1, 2):
            if endings[index] == endings[index + 1]:
                rhyme_pairs += 1

        for index in range(0, len(endings) - 3, 2):
            if endings[index] == endings[index + 2]:
                rhyme_pairs += 1

        for index in range(1, len(endings) - 2, 4):
            if endings[index] == endings[index + 2]:
                rhyme_pairs += 1

        total_pairs = max(len(endings) // 2, 1)
        rhyme_rate = rhyme_pairs / total_pairs
        return min(1.0, rhyme_rate * 2.0)

    def _load_genre_keywords(
        self, overrides: Optional[Mapping[str, Mapping[str, Any]]]
    ) -> Dict[str, Dict[str, Any]]:
        """優先採用外部覆寫，其次讀取本地設定，最後落回預設表。"""
        loaded: Dict[str, Dict[str, Any]] = {}
        overrides = overrides or {}

        for genre, sections in DEFAULT_GENRE_KEYWORDS.items():
            loaded[genre] = {}
            override_sections = dict(overrides.get(genre, {}))
            for section, fallback in sections.items():
                if isinstance(fallback, list):
                    config_key = f"genre.{genre}.{section}"
                    explicit = self._normalize_keyword_list(override_sections.get(section))
                    configured = self._normalize_keyword_list(
                        self.local_categories.get_keywords(config_key)
                    )
                    fallback_list = self._normalize_keyword_list(fallback)
                    loaded[genre][section] = explicit or configured or fallback_list
                else:
                    loaded[genre][section] = override_sections.get(section, fallback)

        return loaded

    @staticmethod
    def _normalize_keyword_list(values: Optional[Any]) -> list[str]:
        """整理關鍵字清單並統一大小寫。"""
        if values is None:
            return []
        if isinstance(values, str):
            values = [values]
        normalized: list[str] = []
        for raw in values:
            text = str(raw).strip().lower()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _clamp_params(params: Dict[str, Dict[str, float]]) -> None:
        """限制參數落在合理範圍，避免離群值。"""
        for (group, key), (lower, upper) in PARAMETER_CLAMP_RANGES.items():
            params[group][key] = float(min(upper, max(lower, params[group][key])))
