"""Release integrity checks for generated story artifacts.

This is the fast, deterministic layer of the quality gate. It catches issues
that should not depend on LLM judgment: missing pages, prompt leakage, severe
duplication, broken endings, and unstable generation traces.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional


_PROMPT_LEAK_MARKERS = (
    "system_prompt",
    "user_prompt",
    "previous_output:",
    "system_feedback:",
    "<state_json>",
    "<refined>",
    "<fixed>",
    "```",
    "TODO",
    "FIXME",
)

_DANGEROUS_CHILD_MARKERS = (
    "blood",
    "corpse",
    "gore",
    "gun",
    "knife",
    "suicide",
    "torture",
)


def _clip(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+|[\u4e00-\u9fff]", text or "")


def _sentences(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])\s*|\n{2,}", text or "") if part.strip()]


def _duplicate_sentence_ratio(sentences: List[str]) -> float:
    normalized = [re.sub(r"\s+", " ", item).strip().casefold() for item in sentences if item.strip()]
    if not normalized:
        return 0.0
    counts = Counter(normalized)
    duplicate_total = sum(count - 1 for count in counts.values() if count > 1)
    return duplicate_total / max(1, len(normalized))


def _expected_total_pages(bundle: Dict[str, Any], fallback_pages: int) -> int:
    layout = bundle.get("layout") if isinstance(bundle.get("layout"), dict) else {}
    branch = bundle.get("branch") if isinstance(bundle.get("branch"), dict) else {}
    for source in (branch, layout):
        value = source.get("total_pages") if isinstance(source, dict) else None
        try:
            total = int(value)
        except Exception:
            total = 0
        if total > 0:
            return total
    return fallback_pages


class ReleaseIntegrityChecker:
    """Deterministic release-readiness checker."""

    def check(
        self,
        story_text: str,
        story_title: str = "Story",
        *,
        story_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        bundle = story_bundle if isinstance(story_bundle, dict) else {}
        pages = bundle.get("pages") if isinstance(bundle.get("pages"), list) else []
        page_texts = [
            str(page.get("text") or "").strip()
            for page in pages
            if isinstance(page, dict)
        ]
        if not story_text and page_texts:
            story_text = "\n\n".join(page_texts)

        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        score = 100.0

        def add_issue(severity: str, code: str, message: str, *, page: Optional[int] = None, penalty: float = 0.0) -> None:
            nonlocal score
            issue = {"severity": severity, "code": code, "message": message}
            if page is not None:
                issue["page"] = page
            issues.append(issue)
            score -= penalty

        total_words = len(_words(story_text))
        all_sentences = _sentences(story_text)
        duplicate_ratio = _duplicate_sentence_ratio(all_sentences)

        if not story_text.strip():
            add_issue("critical", "missing_story_text", "缺少可評估故事全文", penalty=100.0)
        elif total_words < 80:
            add_issue("critical", "story_too_short", f"故事字數過少：{total_words}", penalty=42.0)
        elif total_words < 140:
            add_issue("high", "story_thin", f"故事偏短：{total_words}", penalty=18.0)

        expected_pages = _expected_total_pages(bundle, len(page_texts))
        if expected_pages and len(page_texts) < expected_pages:
            add_issue(
                "critical",
                "missing_pages",
                f"頁數不足：找到 {len(page_texts)} / 預期 {expected_pages}",
                penalty=38.0,
            )

        for page in pages:
            if not isinstance(page, dict):
                continue
            page_number = int(page.get("page") or 0)
            text = str(page.get("text") or "").strip()
            word_count = int(page.get("word_count") or len(_words(text)))
            quality = page.get("quality") if isinstance(page.get("quality"), dict) else {}
            if not text:
                add_issue("critical", "empty_page", "頁面內容為空", page=page_number, penalty=34.0)
            elif word_count < 18:
                add_issue("high", "page_too_short", f"頁面字數過少：{word_count}", page=page_number, penalty=8.0)
            if float(quality.get("score", 100.0) or 100.0) < 60.0:
                add_issue(
                    "high",
                    "low_generation_page_score",
                    f"生成端頁面快速分數偏低：{quality.get('score')}",
                    page=page_number,
                    penalty=10.0,
                )
            for item in quality.get("issues") or []:
                if str(item) in {"text_glitch", "sentence_repetition", "explicit_option_list"}:
                    add_issue(
                        "high",
                        f"generation_{item}",
                        f"生成端偵測到 {item}",
                        page=page_number,
                        penalty=6.0,
                    )

        lowered = story_text.casefold()
        leaked = [marker for marker in _PROMPT_LEAK_MARKERS if marker.casefold() in lowered]
        if leaked:
            add_issue("critical", "prompt_leakage", f"疑似 prompt 或系統標記殘留：{', '.join(leaked[:5])}", penalty=45.0)
        if "�" in story_text:
            add_issue("high", "encoding_glitch", "文字包含替換字元，可能有編碼或模型輸出異常", penalty=20.0)
        if duplicate_ratio >= 0.22:
            add_issue("critical", "high_duplicate_sentence_ratio", f"重複句比例過高：{duplicate_ratio:.0%}", penalty=36.0)
        elif duplicate_ratio >= 0.12:
            add_issue("high", "duplicate_sentence_ratio", f"重複句比例偏高：{duplicate_ratio:.0%}", penalty=16.0)

        dangerous = [marker for marker in _DANGEROUS_CHILD_MARKERS if re.search(rf"\b{re.escape(marker)}\b", lowered)]
        if dangerous:
            add_issue("critical", "age_safety_risk", f"偵測到不適合兒童的高風險詞：{', '.join(dangerous[:5])}", penalty=40.0)

        final_text = page_texts[-1] if page_texts else story_text
        if final_text and final_text.rstrip()[-1] not in ".!?。！？\"'”":
            add_issue("medium", "weak_final_punctuation", "最後一頁結尾標點不完整，可能是斷尾", penalty=8.0)
        if final_text and len(_words(final_text)) < 24:
            add_issue("medium", "thin_final_page", "最後一頁偏薄，收束可能不足", penalty=7.0)

        if not issues:
            suggestions.append("生成完整性良好，可進入發布閘門判斷")
        else:
            suggestions.append("先修復 release_integrity 的 critical/high 問題，再判斷是否可直接使用")
            if any(issue["code"] == "prompt_leakage" for issue in issues):
                suggestions.append("重新生成受污染頁面，並檢查 prompt 清理與輸出截斷邏輯")
            if any(issue["code"] in {"missing_pages", "empty_page"} for issue in issues):
                suggestions.append("補齊缺頁或重新編譯分支 full_story.txt")

        confidence = 0.96
        if any(issue["severity"] == "critical" for issue in issues):
            confidence = 0.9
        elif any(issue["severity"] == "high" for issue in issues):
            confidence = 0.92

        return {
            "dimension": "release_integrity",
            "score": round(_clip(score), 1),
            "confidence": confidence,
            "issues": issues,
            "issues_count": len(issues),
            "suggestions": suggestions[:5],
            "stats": {
                "story_title": story_title,
                "word_count": total_words,
                "sentence_count": len(all_sentences),
                "duplicate_sentence_ratio": round(duplicate_ratio, 4),
                "expected_pages": expected_pages,
                "page_count": len(page_texts),
            },
        }
