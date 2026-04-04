"""語音模型後端層。"""

from __future__ import annotations

import io
import logging
import torch
import warnings
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Sequence

from backends.common import resolve_torch_runtime
from runtime.compat import patch_tts_instance_after_load, prepare_tts_runtime


@contextmanager
def _suppress_io() -> Iterator[None]:
    """隱藏模型載入時的大量標準輸出。"""
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        yield


class BaseVoiceBackend:
    """語音合成後端介面。"""

    def synthesize_to_file(
        self,
        text: str,
        speaker_wav: Path,
        language: str,
        output_path: Path,
    ) -> None:
        raise NotImplementedError

    def cleanup(self) -> None:
        raise NotImplementedError


class CoquiXTTSBackend(BaseVoiceBackend):
    """Coqui XTTS v2 語音合成後端。"""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.config.device, _ = resolve_torch_runtime(
            self.config.device,
            torch.float32,
            module_name="Voice pipeline",
        )
        self.tts = self._load_model()

    def _load_model(self):
        warnings.filterwarnings("ignore", message=".*GPT2InferenceModel has generative capabilities.*")
        warnings.filterwarnings("ignore", message=".*The attention mask is not set.*")
        logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)

        prepare_tts_runtime()

        try:
            with _suppress_io():
                from TTS.api import TTS
        except ImportError as exc:
            raise RuntimeError(
                "找不到 coqui-TTS 套件。請執行 `pip install TTS` 進行安裝。"
            ) from exc

        gpu_enabled = self.config.device.startswith("cuda") and torch.cuda.is_available()
        model_root = self.config.model_dir
        base_dir = model_root.parent if model_root.is_file() else model_root

        model_file = base_dir / "model.pth"
        config_path = base_dir / "config.json"
        if not model_file.exists() or not config_path.exists():
            raise FileNotFoundError(
                f"XTTS 模型檔案缺失，請確認 {base_dir} 內含 model.pth 與 config.json"
            )

        logging.info("正在載入 XTTS 模型: %s (GPU加速: %s)", model_file, gpu_enabled)

        with _suppress_io():
            tts_instance = TTS(
                model_path=str(base_dir),
                config_path=str(config_path),
                gpu=gpu_enabled,
                progress_bar=False,
            )

        patch_tts_instance_after_load(tts_instance)
        return tts_instance

    def offload_model(self) -> None:
        if self.tts is not None:
            try:
                self.tts.to("cpu")
                torch.cuda.empty_cache()
                logging.info("XTTS 模型已移至 CPU")
            except Exception as exc:
                logging.warning("無法將 XTTS 移至 CPU: %s", exc)

    def load_model(self, device: str = "cuda") -> None:
        if self.tts is not None:
            try:
                self.tts.to(device)
                logging.info("XTTS 模型已移回 %s", device)
            except Exception as exc:
                logging.error("無法還原 XTTS 至 GPU: %s", exc)

    def cleanup(self) -> None:
        from utils import ResourceManager

        if hasattr(self, "tts") and self.tts is not None:
            try:
                if hasattr(self.tts, "synthesizer") and hasattr(self.tts.synthesizer, "tts_model"):
                    del self.tts.synthesizer.tts_model
            except Exception:
                pass
            ResourceManager.cleanup_model(self.tts, aggressive=True)
            self.tts = None

    def synthesize_to_file(
        self,
        text: str,
        speaker_wav: Path,
        language: str,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with _suppress_io():
            self.tts.tts_to_file(
                text=text,
                speaker_wav=str(speaker_wav),
                language=language,
                file_path=str(output_path),
                speed=self.config.speed,
                temperature=self.config.temperature,
            )

    def stream(
        self,
        text: str,
        speaker_wav: Path,
        language: str,
    ) -> Iterator[Dict[str, Any]]:
        if self.config.device.startswith("cuda") and torch.cuda.is_available():
            self.load_model(self.config.device)

        gpt_cond, speaker_emb = self.tts.synthesizer.tts_model.get_conditioning_latents(
            audio_path=[str(speaker_wav)]
        )
        chunks = self.tts.synthesizer.tts_model.inference_stream(
            text,
            language,
            gpt_cond,
            speaker_emb,
            speed=self.config.speed,
            temperature=self.config.temperature,
            enable_text_splitting=True,
        )

        for i, chunk in enumerate(chunks):
            yield {
                "chunk": i,
                "audio": chunk,
                "end": False,
            }

        yield {
            "chunk": -1,
            "audio": None,
            "end": True,
        }


VoiceBackendBuilder = Callable[[Any], BaseVoiceBackend]

_VOICE_BACKEND_BUILDERS: Dict[str, VoiceBackendBuilder] = {}
_VOICE_BACKEND_CANONICAL: Dict[str, str] = {}


def register_voice_provider(
    name: str,
    builder: VoiceBackendBuilder,
    aliases: Sequence[str] = (),
) -> None:
    canonical = name.strip().lower()
    _VOICE_BACKEND_BUILDERS[canonical] = builder
    _VOICE_BACKEND_CANONICAL[canonical] = canonical
    for alias in aliases:
        normalized = alias.strip().lower()
        _VOICE_BACKEND_BUILDERS[normalized] = builder
        _VOICE_BACKEND_CANONICAL[normalized] = canonical


def available_voice_providers() -> List[str]:
    return sorted(set(_VOICE_BACKEND_CANONICAL.values()))


def build_voice_backend(config: Any) -> BaseVoiceBackend:
    provider = (getattr(config, "provider", None) or "coqui_xtts").strip().lower()
    canonical = _VOICE_BACKEND_CANONICAL.get(provider, provider)
    builder = _VOICE_BACKEND_BUILDERS.get(canonical)
    if builder is None:
        raise ValueError(
            f"Unknown voice provider '{getattr(config, 'provider', None)}'. Available providers: {', '.join(available_voice_providers())}"
        )
    return builder(config)


register_voice_provider(
    "coqui_xtts",
    CoquiXTTSBackend,
    aliases=("xtts", "coqui"),
)


Generator = CoquiXTTSBackend
