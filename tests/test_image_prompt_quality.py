import logging
import shutil
import unittest
from pathlib import Path

from image import Config, _collect_generation_tasks
from utils import list_character_prompt_files


def _make_sandbox(name: str) -> Path:
    root = Path('output') / '.test_tmp' / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


class ImagePromptQualityTests(unittest.TestCase):
    def test_list_character_prompt_files_excludes_pose_aggregate(self) -> None:
        tmp_dir = _make_sandbox('image_prompts')
        try:
            (tmp_dir / "character_poses.txt").write_text("pose aggregate", encoding="utf-8")
            (tmp_dir / "character_emma.txt").write_text("Emma reference", encoding="utf-8")
            files = list_character_prompt_files(tmp_dir)
            self.assertEqual([path.name for path in files], ["character_emma.txt"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_collect_generation_tasks_builds_character_fallbacks_from_context(self) -> None:
        tmp_dir = _make_sandbox('image_story')
        try:
            resource_dir = tmp_dir / "resource"
            resource_dir.mkdir(parents=True, exist_ok=True)
            (resource_dir / "seed.txt").write_text("123", encoding="utf-8")
            (resource_dir / "book_cover_prompt.txt").write_text("Emma explores a moonlit bridge", encoding="utf-8")
            (resource_dir / "page_1_prompt.txt").write_text("Emma walks across a glowing bridge", encoding="utf-8")
            (resource_dir / "story_meta.json").write_text(
                '{"story_title": "Moon Bridge", "input": {"age_group": "Age 4-5", "category": "Adventure", "theme": "Dream Adventure"}}',
                encoding="utf-8",
            )
            (resource_dir / "kg_profile.json").write_text(
                '{"visual_style": "Hand-painted picture-book style", "kg_payload": {"characters": ["Emma (protagonist)", "Grandpa Tom"], "scenes": ["glowing bridge at night"]}}',
                encoding="utf-8",
            )

            tasks = _collect_generation_tasks(tmp_dir, resource_dir, config=Config(), logger=logging.getLogger("test"))

            character_tasks = [task for task in tasks if task.get("type") == "character"]
            self.assertEqual(len(character_tasks), 2)
            self.assertTrue(any(task["metadata"]["char"] == "Emma" for task in character_tasks))
            self.assertTrue(all("picture-book" in task["prompt"] for task in character_tasks))
            self.assertFalse(any(task["id"] == "char_poses" for task in tasks))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
