"""Story pipeline 的文字清理與一致性工具。"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Dict, List, Optional, Sequence, Set

from .story_helpers import split_sentences


def enforce_dynamic_consistency(
    text: str,
    primary_characters: Sequence[str],
    logger: Optional[logging.Logger] = None,
) -> str:
    """使用模糊匹配修復角色名稱錯誤。"""

    if not text or not primary_characters:
        return text

    potential_entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
    ignore_list = {
        "The",
        "A",
        "An",
        "It",
        "He",
        "She",
        "They",
        "We",
        "You",
        "I",
        "In",
        "On",
        "At",
        "Then",
        "After",
        "Suddenly",
        "Finally",
        "Once",
        "One",
        "Page",
    }

    corrections: Dict[str, str] = {}
    for entity in potential_entities:
        if entity in ignore_list or entity in primary_characters:
            continue
        for real_name in primary_characters:
            similarity = difflib.SequenceMatcher(None, entity, real_name).ratio()
            threshold = 0.85 if len(real_name) > 4 else 0.90
            if similarity > threshold:
                corrections[entity] = real_name
                if logger:
                    logger.info(
                        "Auto-correcting consistency: '%s' -> '%s' (similarity: %.2f)",
                        entity,
                        real_name,
                        similarity,
                    )
                break
            if "Grandpa" in real_name and "Grandma" in entity and real_name.split()[-1] == entity.split()[-1]:
                corrections[entity] = real_name
                if logger:
                    logger.info("Auto-correcting gender swap: '%s' -> '%s'", entity, real_name)
                break

    for bad, good in corrections.items():
        text = re.sub(r"\b" + re.escape(bad) + r"\b", good, text)
    return text


def sanitize_text(
    text: str,
    primary_characters: Sequence[str],
    logger: Optional[logging.Logger] = None,
) -> str:
    """清理文本中的格式問題，並做基礎名稱一致性修復。"""

    if not text:
        return text

    text = re.sub(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]+", "", text)
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)
    text = re.sub(r"\bit(?!s\b|self\b)([a-z])", r"it \1", text)
    text = re.sub(r"\bit([A-Z])", r"it \1", text)
    text = re.sub(r"\band([A-Z])", r"and \1", text)
    text = re.sub(r"\bGrandpa([A-Z][a-z]+)", r"Grandpa \1", text)
    text = re.sub(r"\bas([A-Z])", r"as \1", text)
    text = re.sub(r"\bto([A-Z])", r"to \1", text)
    text = re.sub(r"\b(mid)([A-Z])", r"\1-\2", text)

    text = re.sub(
        r"\b(can|don|won|isn|aren|wasn|weren|haven|hasn|hadn|wouldn|shouldn|couldn|didn|doesn) t\b",
        r"\1't",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(I|you|we|they) (ll|re|ve|d|m)\b", r"\1'\2", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(he|she|it|that|who|what|where|when|why|how) (s|ll|d)\b",
        r"\1'\2",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(^|[.!?]\s+)It s\b", r"\1It's", text)
    text = re.sub(r"\bit s\b", "its", text)
    text = re.sub(r"\b([A-Z][a-z]+) s\b", r"\1's", text)

    text = enforce_dynamic_consistency(text, primary_characters, logger)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("<refined>", "").replace("</refined>", "")
    text = text.replace("<story>", "").replace("</story>", "")
    return text


def build_character_alias_map(primary_characters: Sequence[str]) -> Dict[str, str]:
    """建立 alias -> canonical 的角色映射。"""

    alias_map: Dict[str, str] = {}
    for raw_name in primary_characters:
        name = str(raw_name or "").strip()
        if not name:
            continue
        canonical = name.lower()
        alias_map[canonical] = canonical
        for part in name.split():
            part = part.strip().lower()
            if len(part) >= 2:
                alias_map[part] = canonical
    return alias_map


def count_character_mentions(text: str, alias_map: Dict[str, str]) -> int:
    """估算句內被提及的不同角色數。"""

    if not text or not alias_map:
        return 0
    lowered = text.lower()
    found: Set[str] = set()
    for alias, canonical in alias_map.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            found.add(canonical)
    return len(found)


def coref_ambiguity_score(text: str, primary_characters: Sequence[str]) -> int:
    """以輕量規則估算文本中的代名詞歧義風險分數。"""

    if not text:
        return 0
    sentences = split_sentences(text)
    if not sentences:
        return 0

    alias_map = build_character_alias_map(primary_characters)
    pron_pat = re.compile(r"\b(he|she|they|him|her|them|his|hers|their|theirs)\b", re.IGNORECASE)
    pair_pat = re.compile(r"\b(he|she|they)\b[^.!?\n]{0,80}\b(him|her|them|he|she|they)\b", re.IGNORECASE)
    sent_start_pron_pat = re.compile(r"^\s*(he|she|they|him|her|them|his|their)\b", re.IGNORECASE)

    score = 0
    for idx, sentence in enumerate(sentences):
        s = sentence.strip()
        if not s or not pron_pat.search(s):
            continue
        if pair_pat.search(s):
            score += 2
        mention_count = count_character_mentions(s, alias_map)
        if mention_count >= 2:
            score += 2
        if idx > 0 and sent_start_pron_pat.search(s):
            prev_mentions = count_character_mentions(sentences[idx - 1], alias_map)
            if prev_mentions >= 2:
                score += 1
    return score


def enforce_name_consistency(text: str, primary_characters: Sequence[str]) -> str:
    """以確定性規則修正常見人名變體與黏連。"""

    if not text:
        return text
    fixed = text
    for name in primary_characters:
        name = (name or "").strip()
        if not name:
            continue
        if " " in name:
            compact = re.sub(r"[\s\-]", "", name)
            fixed = re.sub(rf"\b{re.escape(compact)}\b", name, fixed)
    fixed = re.sub(r"\bGrandpa\s*-\s*Tom\b", "Grandpa Tom", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\bGrandpa\s+Tommy\b", "Grandpa Tom", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\bGrandpad\b", "Grandpa Tom", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\bGrandpop\b", "Grandpa Tom", fixed, flags=re.IGNORECASE)
    return fixed
