"""翻譯模組共用常數與文字拆塊工具。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence

SAMPLE_LANGUAGE_MAP = {
    "en": "eng_Latn",
    "de": "deu_Latn",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "ja": "jpn_Jpan",
    "pt": "por_Latn",
    "tr": "tur_Latn",
    "zh": "zho_Hant",
    "zh-tw": "zho_Hant",
    "zh-cn": "zho_Hans",
}


def chunk_text(text: str, max_chars: int) -> List[str]:
    """將長文本拆塊，以符合模型輸入長度限制。"""

    if len(text) <= max_chars:
        return [text]

    parts: Sequence[str] = re.split(r"(\n\s*\n)", text)
    if len(parts) == 1 and len(parts[0]) > max_chars:
        parts = re.split(r"([\.。！？!?]\s+)", text)

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for part in parts:
        if len(part) > max_chars:
            if current:
                chunks.append("".join(current))
                current = []
                current_len = 0
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars])
            continue

        if current and current_len + len(part) > max_chars:
            chunks.append("".join(current))
            current = [part]
            current_len = len(part)
        else:
            current.append(part)
            current_len += len(part)

    if current:
        chunks.append("".join(current))
    return chunks or [text]


def discover_languages(sample_dir: Path) -> List[str]:
    """根據樣本音檔自動偵測可用語言代碼。"""

    if not sample_dir.exists():
        return []

    langs: List[str] = []
    for file in sample_dir.glob("*.wav"):
        base = file.stem
        match = re.match(r"([a-z]{2}(?:-[a-z]{2})?)_?sample", base, re.IGNORECASE)
        if match:
            langs.append(match.group(1).lower())
        elif "-sample" in base:
            langs.append(base.split("-sample")[0].lower())
    return sorted(set(langs))
