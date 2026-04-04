"""
Transformers 與 TTS 相容性修補模組

此模組包含修補 transformers 4.50+ 與 XTTS v2 之間相容性問題的黑科技。
主要解決：
1. BeamSearchScorer 在新版 transformers 被移除的問題
2. torch.load weights_only 安全限制問題
3. GPT2InferenceModel.generate 方法缺失問題
"""

import importlib
import logging
from typing import Any


SAFE_PICKLE_TYPES = [
    "TTS.tts.configs.xtts_config.XttsConfig",
    "TTS.tts.models.xtts.XttsArgs",
    "TTS.tts.models.xtts.XttsAudioConfig",
    "TTS.config.shared_configs.BaseDatasetConfig",
]


def _register_beam_in_import_structure() -> None:
    try:
        from transformers.utils import import_utils  # type: ignore
    except Exception:
        return

    import_structure = getattr(import_utils, "_import_structure", None)
    if not isinstance(import_structure, dict):
        return

    for key in ("generation", "generation_utils", "generation.utils"):
        entries = import_structure.get(key)
        if isinstance(entries, list) and "BeamSearchScorer" not in entries:
            entries.append("BeamSearchScorer")


def patch_beam_search_scorer() -> None:
    try:
        import transformers
    except Exception:
        logging.warning("transformers not installed, skipping BeamSearchScorer patch")
        return

    if getattr(transformers, "BeamSearchScorer", None) is not None:
        return

    for module_name in (
        "transformers.generation.beam_search",
        "transformers.generation.utils",
        "transformers.generation",
    ):
        try:
            module = importlib.import_module(module_name)
            beam_class = getattr(module, "BeamSearchScorer", None)
            if beam_class is not None:
                setattr(transformers, "BeamSearchScorer", beam_class)
                _register_beam_in_import_structure()
                logging.debug("BeamSearchScorer restored from %s", module_name)
                return
        except Exception:
            continue

    try:
        from transformers.generation.beam_search import BeamScorer

        class _BeamSearchScorerCompat(BeamScorer):
            def __init__(self, *args, **kwargs) -> None:
                pass

            def process(self, *args, **kwargs):
                return None

            def finalize(self, *args, **kwargs):
                return None

        setattr(transformers, "BeamSearchScorer", _BeamSearchScorerCompat)
        _register_beam_in_import_structure()
        logging.debug("BeamSearchScorer compatibility shim created for transformers 4.50+")
        return
    except Exception:
        pass

    class _MissingBeamSearchScorer:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def process(self, *args, **kwargs):
            return None

        def finalize(self, *args, **kwargs):
            return None

    setattr(transformers, "BeamSearchScorer", _MissingBeamSearchScorer)
    _register_beam_in_import_structure()
    logging.debug("BeamSearchScorer minimal stub created")


def patch_torch_safe_globals() -> None:
    try:
        from torch.serialization import add_safe_globals
    except Exception:
        return

    safe_classes = []
    for dotted in SAFE_PICKLE_TYPES:
        try:
            module_name, attr_name = dotted.rsplit(".", 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, attr_name)
            safe_classes.append(cls)
        except Exception:
            continue

    if safe_classes:
        add_safe_globals(safe_classes)
        logging.debug("Added %d safe globals for torch serialization", len(safe_classes))


def patch_torch_load_weights_only() -> None:
    try:
        import torch
    except Exception:
        return

    origin = getattr(torch.load, "__wrapped__", torch.load)
    if getattr(torch.load, "_legacy_weights_only_patch", False):
        return

    def patched_load(*args, **kwargs):
        if "weights_only" not in kwargs:
            kwargs["weights_only"] = False
        return origin(*args, **kwargs)

    patched_load._legacy_weights_only_patch = True  # type: ignore[attr-defined]
    patched_load.__wrapped__ = origin  # type: ignore[attr-defined]
    torch.load = patched_load  # type: ignore[assignment]
    logging.debug("torch.load patched to disable weights_only by default")


def patch_gpt2_generate_method(tts_instance: Any) -> None:
    try:
        if hasattr(tts_instance, "synthesizer") and hasattr(tts_instance.synthesizer, "tts_model"):
            tts_model = tts_instance.synthesizer.tts_model
            if hasattr(tts_model, "model") and hasattr(tts_model.model, "decoder"):
                decoder = tts_model.model.decoder
                if not hasattr(decoder, "generate"):
                    from transformers import PreTrainedModel

                    if hasattr(PreTrainedModel, "generate"):
                        decoder.generate = PreTrainedModel.generate.__get__(decoder, type(decoder))
                        logging.debug("GPT2InferenceModel.generate method patched")
    except Exception as exc:
        logging.debug("Failed to patch GPT2 generate method: %s", exc)


def apply_all_patches() -> None:
    logging.debug("Applying transformers compatibility patches...")
    patch_beam_search_scorer()
    patch_torch_safe_globals()
    patch_torch_load_weights_only()
    logging.debug("All patches applied successfully")
