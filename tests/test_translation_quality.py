import unittest
from pathlib import Path
import shutil

from trans import (
    _extract_title_text,
    _looks_like_bad_translation,
    build_translated_title_payload,
    load_story_translation_hints,
)


def _make_sandbox(name: str) -> Path:
    root = Path('output') / '.test_tmp' / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


class TranslationQualityTests(unittest.TestCase):
    def test_extract_title_text_from_json(self) -> None:
        self.assertEqual(_extract_title_text('{"title": "A Night of Wonders"}'), "A Night of Wonders")

    def test_build_translated_title_payload_keeps_json_shape(self) -> None:
        payload = build_translated_title_payload("A Night of Wonders", "Starry Wonder Night")
        self.assertIn('"title"', payload)
        self.assertIn("Starry Wonder Night", payload)

    def test_bad_translation_heuristic_flags_garbled_text(self) -> None:
        self.assertTrue(_looks_like_bad_translation("?"))
        self.assertFalse(_looks_like_bad_translation("Starry Wonder Night"))

    def test_load_story_translation_hints_extracts_title_and_names(self) -> None:
        tmp_dir = _make_sandbox('translation_hints')
        try:
            title_path = tmp_dir / "en" / "branches" / "option_1" / "title.txt"
            profile_path = tmp_dir / "en" / "branches" / "option_1" / "resource" / "kg_profile.json"
            title_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            title_path.write_text('{"title": "A Night of Wonders"}', encoding="utf-8")
            profile_path.write_text(
                '{"kg_payload": {"characters": ["Emma (protagonist)", "Grandpa Tom"]}}',
                encoding="utf-8",
            )

            hints = load_story_translation_hints(tmp_dir, "en")

            self.assertEqual(hints["title"], "A Night of Wonders")
            self.assertEqual(hints["entity_lock_names"], ["Emma", "Grandpa Tom"])
            self.assertIn("A Night of Wonders", hints["glossary"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
