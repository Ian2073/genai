import re
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from ..shared.story_data import collect_full_story_paths, discover_story_dirs, load_json_dict
except ImportError:
    from shared.story_data import collect_full_story_paths, discover_story_dirs, load_json_dict


def compute_counts(text: str) -> Tuple[int, int]:
    # Word count: include apostrophes/dashes (e.g., don't, mother-in-law)
    words = re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE)
    word_count = len(words)

    # Char count: all characters excluding newline and carriage return
    char_count = sum(1 for ch in text if ch not in ("\n", "\r"))

    return word_count, char_count


def update_metadata_for_story(story_dir: Path) -> Tuple[bool, Dict[str, Any]]:
    full_story_candidates = collect_full_story_paths(story_dir)
    full_text_path = full_story_candidates[0] if full_story_candidates else None
    metadata_path = story_dir / "metadata.json"

    if full_text_path is None or not metadata_path.is_file():
        return False, {"reason": "missing full_story.txt or metadata.json"}

    try:
        text = full_text_path.read_text(encoding="utf-8")
    except Exception as exc:
        return False, {"reason": f"failed to read full_story.txt: {exc}"}

    computed_word_count, computed_char_count = compute_counts(text)
    metadata = load_json_dict(metadata_path)
    if metadata is None:
        return False, {"reason": "invalid metadata.json"}

    original_word_count = metadata.get("word_count")
    original_char_count = metadata.get("char_count")

    changed = False
    if original_word_count != computed_word_count:
        metadata["word_count"] = computed_word_count
        changed = True

    if original_char_count != computed_char_count:
        metadata["char_count"] = computed_char_count
        changed = True

    if changed:
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return changed, {
        "word_count": {
            "old": original_word_count,
            "new": computed_word_count,
        },
        "char_count": {
            "old": original_char_count,
            "new": computed_char_count,
        },
    }


def walk_and_update(root: Path) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    if not root.is_dir():
        return results

    for story_dir in discover_story_dirs([str(root)]):
        changed, detail = update_metadata_for_story(story_dir)
        results[story_dir.name] = {"changed": changed, "detail": detail}
    return results


def main() -> None:
    workspace_root = Path(__file__).resolve().parents[2]
    base_dirs = [workspace_root / "output", workspace_root / "output" / "evaluated"]

    summary: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for base in base_dirs:
        summary[base.name] = walk_and_update(base)

    updated_total = 0
    for label, items in summary.items():
        print(f"[{label}]")
        for story, info in items.items():
            changed = bool(info.get("changed", False))
            if changed:
                updated_total += 1
                detail = info.get("detail", {})
                wc = detail.get("word_count", {})
                cc = detail.get("char_count", {})
                print(
                    f"  - {story}: UPDATED word_count {wc.get('old')} -> {wc.get('new')}, "
                    f"char_count {cc.get('old')} -> {cc.get('new')}"
                )
            else:
                reason = (info.get("detail") or {}).get("reason")
                if reason:
                    print(f"  - {story}: SKIPPED ({reason})")
                else:
                    print(f"  - {story}: OK (no changes)")

    print(f"\nTotal stories updated: {updated_total}")


if __name__ == "__main__":
    main()


