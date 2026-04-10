import json
import logging
import shutil
import unittest
from pathlib import Path

from image import Config, _collect_generation_tasks
from story import StoryPipeline


def _make_sandbox(name: str) -> Path:
    root = Path("output") / ".test_tmp" / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


class UnityAssetPipelineTests(unittest.TestCase):
    def _write_min_story_context(self, resource_dir: Path) -> None:
        (resource_dir / "seed.txt").write_text("123", encoding="utf-8")
        (resource_dir / "book_cover_prompt.txt").write_text("Emma explores a moonlit bridge", encoding="utf-8")
        (resource_dir / "character_Emma.txt").write_text("Emma in a yellow raincoat", encoding="utf-8")
        (resource_dir / "character_Grandpa_Tom.txt").write_text("Grandpa Tom with a warm lantern", encoding="utf-8")
        (resource_dir / "page_1_prompt.txt").write_text("Emma walks across a glowing bridge", encoding="utf-8")
        (resource_dir / "story_meta.json").write_text(
            '{"story_id": "story-001", "story_title": "Moon Bridge", "input": {"age_group": "Age 4-5", "category": "Adventure", "theme": "Dream Adventure"}}',
            encoding="utf-8",
        )
        (resource_dir / "kg_profile.json").write_text(
            json.dumps(
                {
                    "visual_style": "Hand-painted picture-book style",
                    "kg_payload": {
                        "characters": [
                            {"label": "Emma", "role": "protagonist", "appearance": "short black bob", "description": "curious girl", "outfit": "yellow raincoat", "props": ["lantern"]},
                            {"label": "Grandpa Tom", "role": "recurring guide", "appearance": "gray hair", "description": "kind elder", "outfit": "brown vest", "props": ["map"]},
                        ],
                        "scenes": ["glowing bridge at night"],
                    },
                }
            ),
            encoding="utf-8",
        )
        (resource_dir / "character_bible.json").write_text(
            json.dumps(
                {
                    "characters": [
                        {"name": "Emma", "outfit_core": "yellow raincoat", "hair": "short black bob", "color_lock": ["yellow"], "expression_style": "curious eyes", "role": "protagonist"},
                        {"name": "Grandpa Tom", "outfit_core": "brown vest", "hair": "gray hair", "color_lock": ["brown"], "expression_style": "warm smile", "role": "recurring guide"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (resource_dir / "world_style_lock.json").write_text(
            json.dumps(
                {
                    "style_lock": "storybook, soft illustrative, staged composition",
                    "render_principle": "Stable, readable picture-book storytelling frames instead of showcase art.",
                    "forbidden_styles": ["photorealism", "3d render", "text overlay"],
                }
            ),
            encoding="utf-8",
        )
        (resource_dir / "page_1_visual_plan.json").write_text(
            json.dumps(
                {
                    "page_number": 1,
                    "branch_id": "option_1",
                    "scene_core": "Emma reaches toward the glowing bridge.",
                    "shot": "mid",
                    "lighting": "dim",
                    "stage": "action",
                    "focus_subject": "pair",
                    "motion_level": "active",
                    "emotion_density": "wonder",
                    "composition_balance": "layered",
                    "world_anchor": "star bridge entrance",
                    "foreground_subjects": ["grass and lantern glow"],
                    "midground_subjects": ["Emma and Grandpa Tom by the bridge"],
                    "background_subjects": ["glowing bridge arch and stars"],
                    "required_characters": ["Emma", "Grandpa Tom"],
                    "continuity_keys": {"emma_outfit": "yellow raincoat", "grandpa_tom_outfit": "brown vest"},
                    "story_readability_goal": "one clear child-readable story moment",
                }
            ),
            encoding="utf-8",
        )
        (resource_dir / "page_1_asset_plan.json").write_text(
            json.dumps(
                {
                    "page_number": 1,
                    "branch_id": "option_1",
                    "world_anchor": "star bridge entrance",
                    "shot": "mid",
                    "lighting": "dim",
                    "stage": "action",
                    "story_readability_goal": "one clear child-readable story moment",
                    "backdrop_prompt": "star bridge entrance backdrop, dim night lighting, no characters, open stage space for Unity assembly",
                    "foreground_overlay_prompt": "grass and lantern glow, foreground overlay only, transparent-friendly decor layer",
                    "midground_objects": [
                        {"canonical_id": "bridge_arch", "label": "bridge arch", "prompt": "bridge arch isolated midground object", "layer": "midground_objects", "slot": "center", "remove_bg": True}
                    ],
                    "characters": [
                        {"character_id": "emma", "label": "Emma", "pose_id": "reach", "facing": "left_3q", "layer": "characters", "slot": "left", "scale_hint": "medium", "remove_bg": True},
                        {"character_id": "grandpa_tom", "label": "Grandpa Tom", "pose_id": "hold", "facing": "right_3q", "layer": "characters", "slot": "right", "scale_hint": "medium", "remove_bg": True}
                    ],
                    "props": [
                        {"canonical_id": "lantern", "label": "lantern", "prompt": "isolated lantern prop", "interactive": False, "layer": "props", "slot": "center", "remove_bg": True}
                    ],
                    "interactives": [
                        {"canonical_id": "lantern", "label": "lantern", "prompt": "isolated lantern prop", "interactive": True, "layer": "props", "slot": "center", "remove_bg": True}
                    ],
                    "assembly_order": ["backdrop", "midground_objects", "characters", "props", "foreground_overlay"]
                }
            ),
            encoding="utf-8",
        )

    def test_story_build_page_asset_plan_structure_complete(self) -> None:
        pipeline = StoryPipeline.__new__(StoryPipeline)
        pipeline.current_branch_id = "option_1"
        pipeline._story_character_records = lambda: [
            {"name": "Emma", "role": "protagonist", "appearance": "short black bob", "description": "curious girl", "outfit": "yellow raincoat", "props": ["lantern"]},
            {"name": "Grandpa Tom", "role": "guide", "appearance": "gray hair", "description": "kind elder", "outfit": "brown vest", "props": ["map"]},
        ]
        page_plan = {
            "world_anchor": "star bridge entrance",
            "shot": "mid",
            "lighting": "dim",
            "stage": "action",
            "focus_subject": "pair",
            "motion_level": "active",
            "emotion_density": "wonder",
            "scene_core": "Emma reaches toward the glowing bridge",
            "required_characters": ["Emma", "Grandpa Tom"],
            "foreground_subjects": ["grass and lantern glow"],
            "midground_subjects": ["Emma and Grandpa Tom by the bridge"],
            "background_subjects": ["glowing bridge arch and stars"],
            "continuity_keys": {"emma_outfit": "yellow raincoat"},
            "pose_reference": "Emma reaching while Grandpa Tom holds a map",
            "story_readability_goal": "one clear child-readable story moment",
        }
        asset_plan = StoryPipeline._build_page_asset_plan(
            pipeline,
            1,
            "Emma reached toward the glowing bridge with her lantern while Grandpa Tom held the map.",
            page_plan,
            {"branch_trigger": True, "page_function": "INTERACTION"},
            {},
        )
        self.assertEqual(asset_plan["page_number"], 1)
        self.assertIn("backdrop_prompt", asset_plan)
        self.assertIn("foreground_overlay_prompt", asset_plan)
        self.assertTrue(asset_plan["characters"])
        self.assertTrue(asset_plan["props"])
        self.assertTrue(asset_plan["interactives"])
        self.assertEqual(asset_plan["assembly_order"], ["backdrop", "midground_objects", "characters", "props", "foreground_overlay"])
        self.assertTrue(all("pose_id" in item and "facing" in item and "slot" in item for item in asset_plan["characters"]))

    def test_collect_generation_tasks_dual_mode_writes_unity_assets(self) -> None:
        tmp_dir = _make_sandbox("image_story_unity_dual")
        try:
            resource_dir = tmp_dir / "resource"
            resource_dir.mkdir(parents=True, exist_ok=True)
            self._write_min_story_context(resource_dir)

            tasks = _collect_generation_tasks(tmp_dir, resource_dir, config=Config(output_mode="dual"), logger=logging.getLogger("test"))

            task_types = {task.get("type") for task in tasks}
            self.assertIn("cover", task_types)
            self.assertIn("character", task_types)
            self.assertIn("page", task_types)
            self.assertIn("character_pose_variant", task_types)
            self.assertIn("page_backdrop", task_types)
            self.assertIn("page_foreground_overlay", task_types)
            self.assertIn("page_midground_object", task_types)
            self.assertIn("prop_sprite", task_types)

            manifest_path = resource_dir / "unity_story_asset_manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["story_id"], "story-001")
            self.assertEqual(len(manifest["pages"]), 1)
            page_manifest = manifest["pages"][0]
            self.assertTrue(page_manifest["characters"])
            self.assertTrue(page_manifest["props"])
            page_assets_path = tmp_dir / "image" / "unity" / "pages" / "page_1" / "page_assets.json"
            self.assertTrue(page_assets_path.exists())
            page_assets = json.loads(page_assets_path.read_text(encoding="utf-8"))
            self.assertTrue(all(item.get("pose_id") and item.get("facing") and item.get("slot") for item in page_assets["characters"]))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_collect_generation_tasks_marks_transparent_unity_assets(self) -> None:
        tmp_dir = _make_sandbox("image_story_unity_transparency")
        try:
            resource_dir = tmp_dir / "resource"
            resource_dir.mkdir(parents=True, exist_ok=True)
            self._write_min_story_context(resource_dir)

            tasks = _collect_generation_tasks(
                tmp_dir,
                resource_dir,
                config=Config(output_mode="unity_assets_only", bg_removal_policy="characters_props"),
                logger=logging.getLogger("test"),
            )

            by_type = {}
            for task in tasks:
                by_type.setdefault(task["type"], []).append(task)

            self.assertNotIn("character", by_type)
            self.assertNotIn("page", by_type)
            self.assertTrue(all(task["remove_bg"] for task in by_type["character_pose_variant"]))
            self.assertTrue(all(task["remove_bg"] for task in by_type["prop_sprite"]))
            self.assertTrue(all(task["remove_bg"] for task in by_type["page_foreground_overlay"]))
            self.assertTrue(all(task["remove_bg"] for task in by_type["page_midground_object"]))
            self.assertTrue(all(not task["remove_bg"] for task in by_type["page_backdrop"]))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
