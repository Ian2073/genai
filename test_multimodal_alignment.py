import shutil
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

from evaluation.multimodal_alignment import Gemma4VisionReviewer, MultimodalAlignmentChecker
from evaluation.shared.story_data import collect_story_visual_assets


def _make_story_root(name: str) -> Path:
    root = Path("output") / ".test_tmp" / name
    shutil.rmtree(root, ignore_errors=True)
    (root / "en" / "branches" / "option_1" / "resource").mkdir(parents=True, exist_ok=True)
    (root / "en" / "branches" / "option_1" / "image" / "main").mkdir(parents=True, exist_ok=True)
    return root


def _draw_test_image(path: Path, *, accent: str) -> None:
    image = Image.new("RGB", (1024, 768), "#f6edd8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 180, 420, 620), fill="#7bb661")
    draw.ellipse((510, 180, 860, 560), fill=accent)
    draw.rectangle((460, 540, 860, 650), fill="#8b5e3c")
    image.save(path)


class MultimodalAlignmentTests(unittest.TestCase):
    def test_gemma4_reviewer_prefers_local_e4b_checkpoint(self) -> None:
        reviewer = Gemma4VisionReviewer()
        self.assertTrue(str(reviewer.model_path or "").lower().endswith("models\\gemma-4-e4b-it"))

    def test_collect_story_visual_assets_pairs_prompts_and_pages(self) -> None:
        root = _make_story_root("multimodal_assets")
        try:
            branch = root / "en" / "branches" / "option_1"
            resource = branch / "resource"
            image_root = branch / "image" / "main"

            (branch / "full_story.txt").write_text(
                "Emma finds a glowing map. She walks to a bright door with Grandpa Tom.",
                encoding="utf-8",
            )
            (branch / "page_1.txt").write_text(
                "Emma finds a glowing map beside a tree stump.",
                encoding="utf-8",
            )
            (branch / "page_2.txt").write_text(
                "Emma and Grandpa Tom walk toward a bright magical door in the forest.",
                encoding="utf-8",
            )
            (resource / "book_cover_prompt.txt").write_text(
                "Emma and Grandpa Tom holding a glowing map near a magical forest door.",
                encoding="utf-8",
            )
            (resource / "page_1_prompt.txt").write_text(
                "Emma kneels beside a tree stump, finding a glowing map in warm forest light.",
                encoding="utf-8",
            )
            (resource / "page_2_prompt.txt").write_text(
                "Emma and Grandpa Tom walk toward a bright magical door under tall trees.",
                encoding="utf-8",
            )
            (resource / "story_meta.json").write_text(
                '{"story_title":"Map Door","input":{"age_group":"Age 4-5","category":"Adventure","theme":"Courage"}}',
                encoding="utf-8",
            )
            (root / "logs").mkdir(parents=True, exist_ok=True)
            (root / "logs" / "photo.log").write_text(
                "Found 3 tasks total across 1 resource groups. Starting Generation...\n"
                "Phase 1 progress: 3/3 tasks | elapsed 12.0s | eta 0.0s\n"
                "Successfully generated 3 images\n",
                encoding="utf-8",
            )

            _draw_test_image(image_root / "book_cover.png", accent="#7aa6ff")
            _draw_test_image(image_root / "page_1_scene.png", accent="#ffcc66")
            _draw_test_image(image_root / "page_2_scene.png", accent="#9b7cff")

            assets = collect_story_visual_assets(
                root,
                branch_id="option_1",
                source_document=branch / "full_story.txt",
            )

            self.assertEqual(len(assets["image_paths"]), 3)
            self.assertEqual(len(assets["pairs"]), 3)
            self.assertTrue(any(pair.get("kind") == "cover" for pair in assets["pairs"]))
            self.assertTrue(any(pair.get("page") == 1 for pair in assets["pairs"]))
            self.assertIn("Starting Generation", assets["photo_log"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_multimodal_alignment_checker_returns_runtime_diagnostics(self) -> None:
        root = _make_story_root("multimodal_checker")
        try:
            branch = root / "en" / "branches" / "option_1"
            resource = branch / "resource"
            image_root = branch / "image" / "main"

            story_text = (
                "Emma finds a glowing map under an oak tree. "
                "She and Grandpa Tom walk together toward a bright magical door."
            )
            (branch / "full_story.txt").write_text(story_text, encoding="utf-8")
            (branch / "page_1.txt").write_text(
                "Emma finds a glowing map under an oak tree.",
                encoding="utf-8",
            )
            (branch / "page_2.txt").write_text(
                "Emma and Grandpa Tom walk together toward a bright magical door.",
                encoding="utf-8",
            )
            (resource / "book_cover_prompt.txt").write_text(
                "Emma and Grandpa Tom with a glowing map before a magical forest door.",
                encoding="utf-8",
            )
            (resource / "page_1_prompt.txt").write_text(
                "Emma kneels under an oak tree and lifts a glowing map in warm light.",
                encoding="utf-8",
            )
            (resource / "page_2_prompt.txt").write_text(
                "Emma and Grandpa Tom walk toward a bright magical door among tall trees.",
                encoding="utf-8",
            )
            (root / "logs").mkdir(parents=True, exist_ok=True)
            (root / "logs" / "photo.log").write_text(
                "Found 3 tasks total across 1 resource groups. Starting Generation...\n"
                "Phase 1 progress: 3/3 tasks | elapsed 9.0s | eta 0.0s\n"
                "Successfully generated 3 images\n",
                encoding="utf-8",
            )
            _draw_test_image(image_root / "book_cover.png", accent="#6db4ff")
            _draw_test_image(image_root / "page_1_scene.png", accent="#ffcf5e")
            _draw_test_image(image_root / "page_2_scene.png", accent="#7dd3a7")

            assets = collect_story_visual_assets(
                root,
                branch_id="option_1",
                source_document=branch / "full_story.txt",
            )
            checker = MultimodalAlignmentChecker()
            result = checker.check(
                story_text,
                "Map Door",
                image_paths=assets["image_paths"],
                image_context=assets,
            )

            self.assertEqual(result["dimension"], "multimodal_alignment")
            self.assertIn("scores", result)
            self.assertIn("runtime_diagnostics", result)
            self.assertGreater(result["score"], 0.0)
            self.assertIn("sdxl_suitability", result["runtime_diagnostics"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_gemma4_reviewer_reports_missing_dependencies_cleanly(self) -> None:
        reviewer = Gemma4VisionReviewer(model_path="models/gemma-4-E4B-it")
        with mock.patch("builtins.__import__") as mocked_import:
            real_import = __import__

            def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name in {"torch", "transformers"}:
                    raise ModuleNotFoundError(name)
                return real_import(name, globals, locals, fromlist, level)

            mocked_import.side_effect = _fake_import
            available = reviewer._ensure_loaded()

        self.assertFalse(available)
        self.assertIn("missing_dependency", str(reviewer.describe_error() or ""))


if __name__ == "__main__":
    unittest.main()
