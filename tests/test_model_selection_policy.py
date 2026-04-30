import shutil
import unittest
from pathlib import Path

from backends.llm_runtime_strategy import DEFAULT_MODEL_PRESETS
from pipeline.model_plan import (
    HardwareProfile,
    IMAGE_MODEL_REGISTRY,
    MODEL_PLAN_SPECS,
    SUPPORTED_IMAGE_PROVIDERS,
    classify_image_model,
    classify_image_provider,
    resolve_image_defaults,
)


class ModelSelectionPolicyTests(unittest.TestCase):
    def test_gpu_plans_only_keep_primary_gptq_story_model(self) -> None:
        for plan_key in ("quality", "balanced", "portable"):
            candidates = MODEL_PLAN_SPECS[plan_key].story_candidates
            self.assertEqual(len(candidates), 1, plan_key)
            self.assertEqual(candidates[0].path, "Qwen2.5-14B-Instruct-GPTQ-Int4", plan_key)
            self.assertEqual(candidates[0].quantization, "gptq", plan_key)

    def test_runtime_presets_only_keep_primary_gptq_candidate(self) -> None:
        self.assertEqual(len(DEFAULT_MODEL_PRESETS), 1)
        self.assertEqual(str(DEFAULT_MODEL_PRESETS[0].path).replace("\\", "/"), "models/Qwen2.5-14B-Instruct-GPTQ-Int4")
        self.assertEqual(DEFAULT_MODEL_PRESETS[0].cuda_quantization, "gptq")

    def test_cpu_plan_only_keeps_single_cpu_story_model(self) -> None:
        candidates = MODEL_PLAN_SPECS["cpu"].story_candidates
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].path, "Qwen3-8B")
        self.assertIsNone(candidates[0].quantization)

    def test_image_policy_only_keeps_primary_flux_model(self) -> None:
        self.assertEqual(SUPPORTED_IMAGE_PROVIDERS, ("diffusers_flux",))
        self.assertEqual(len(IMAGE_MODEL_REGISTRY), 1)
        self.assertEqual(IMAGE_MODEL_REGISTRY[0].path, "FLUX.1-schnell")

    def test_image_policy_classification_is_fixed_to_flux(self) -> None:
        self.assertEqual(classify_image_provider(None), "diffusers_flux")
        self.assertEqual(classify_image_model(None), "flux_schnell")
        self.assertEqual(classify_image_provider(Path("models/anything")), "diffusers_flux")
        self.assertEqual(classify_image_model(Path("models/anything")), "flux_schnell")

    def test_resolve_image_defaults_disables_refiner_and_clamps_flux_profile(self) -> None:
        temp_root = Path(__file__).resolve().parent / "_tmp_model_selection_policy"
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        try:
            models_dir = temp_root
            (models_dir / "FLUX.1-schnell").mkdir(parents=True)
            hardware = HardwareProfile(
                accelerator="cuda",
                gpu_names=("Test GPU",),
                gpu_vram_gb=16.0,
                system_ram_gb=32.0,
                gpu_count=1,
                cuda_version="12.1",
            )
            _plan_key, image_base, image_refiner, image_profile, notes = resolve_image_defaults(
                "quality",
                models_dir=models_dir,
                hardware=hardware,
            )
            self.assertEqual(image_base, temp_root / "FLUX.1-schnell")
            self.assertIsNone(image_refiner)
            self.assertEqual(image_profile.steps, 4)
            self.assertEqual(image_profile.guidance, 0.0)
            self.assertTrue(image_profile.skip_refiner)
            self.assertIsNone(image_profile.refiner_steps)
            self.assertTrue(notes)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
