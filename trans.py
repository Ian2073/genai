"""使用本地 NLLB 模型的故事翻譯流程。"""

from __future__ import annotations

import gc
import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import torch
import time

from backends.translation_common import SAMPLE_LANGUAGE_MAP, discover_languages
from utils import ensure_dir, resolve_story_root, setup_logging, cleanup_torch
from backends.translation import BaseTranslationBackend, build_translation_backend
from runtime.story_files import gather_language_files, relative_to_language

if platform.system().lower().startswith("win") or platform.system().lower().startswith("darwin"):
	logging.getLogger("torch.distributed.elastic").setLevel(logging.ERROR)

@dataclass
class Config:
	"""翻譯模組配置參數。"""
	provider: str = "transformers_nllb"  # 後端名稱，方便未來替換翻譯模型
	model_family: Optional[str] = "nllb"  # 預留給 MarianMT / M2M100 等家族切換
	model_dir: Path = Path("models/nllb-200-3.3B")
	device: str = "auto"
	dtype: torch.dtype = torch.float16
	source_lang: str = "eng_Latn"
	source_folder: str = "en"
	target_langs: Sequence[str] = field(default_factory=list)
	sample_dir: Path = Path("models/XTTS-v2/samples")
	output_dir_name: str = ""
	max_input: int = 512   # 輸入文本最大長度（避免 OOM）
	max_output: int = 512
	chunk_size: int = 800        # 分塊大小
	beam_size: int = 1           # Beam Search 大小（預設 1 以避免卡死）
	length_penalty: float = 1.0  # 長度懲罰
	no_repeat_ngram_size: int = 3 # 禁止 3-gram 重複
	quantize: bool = True     # 預設啟用 8-bit 量化
	batch_size: int = 16           # 批次翻譯大小


@dataclass
class RunConfig:
	"""翻譯流程的統一設定，集中於程式內部。"""

	story_root: Optional[Path] = None
	output_root: Path = Path("output")
	log_level: int = logging.INFO
	log_format: str = "%(asctime)s [%(levelname)s] %(message)s"
	progress_label: str = "翻譯生成"
	translation: Config = field(default_factory=Config)

	# 術語強制對映表（預設為繁體中文）
	glossary: Dict[str, str] = field(default_factory=lambda: {
		"Grandpa Tom": "湯姆爺爺", 
		"Grandpa": "爺爺",
		"Alex": "艾力克斯",
		"Emma": "艾瑪",
		"Cardamom": "豆蔻",
		"Locket": "掛墜盒", 
		"Star Bridge": "星之橋",
		"Rainbow Bridge": "彩虹橋",
	})

def ensure_languages(config: Config) -> List[str]:
	"""若使用者未指定語言就依樣本資料自動推導。"""
	if config.target_langs:
		return list(config.target_langs)
	discovered = discover_languages(config.sample_dir)
	return discovered or ["en"]



def translate_story(
	story_root: Path,
	config: Config,
	console: bool = True,
) -> Dict[str, List[Path]]:
	"""使用 NLLB 將指定故事資料夾翻譯到多語語系。"""
	log_path = story_root / "logs" / "translation.log"
	logger = setup_logging(f"translation_pipeline_{story_root.name}", log_path, console=console)
	translator = build_translation_backend(config)
	source_dir = story_root / config.source_folder
	if not source_dir.exists():
		raise FileNotFoundError(f"Source language folder not found: {source_dir}")
	files = gather_language_files(source_dir)
	if not files:
		logger.error("No translatable files found in %s (searched recursively)", source_dir)
		raise FileNotFoundError("No translatable files found in source language directory")

	languages = [
		lang for lang in ensure_languages(config)
		if lang.lower() != config.source_folder.lower()
	]
	if not languages:
		raise ValueError("翻譯語言集合為空，請確認 config 或樣本語系設定")
	
	total_tasks = len(files) * len(languages)
	logger.info("Translating %s files into %s languages (%s total tasks)", len(files), len(languages), total_tasks)

	base_output_dir = story_root / config.output_dir_name if config.output_dir_name else story_root
	ensure_dir(base_output_dir)
	outputs: Dict[str, List[Path]] = {}
	
	# 預先讀取所有源文件內容
	file_contents: List[str] = []
	files_to_process: List[Path] = []
	
	for file_path in files:
		content = file_path.read_text(encoding="utf-8")
		if content.strip():
			file_contents.append(content)
			files_to_process.append(file_path)
		else:
			# 創建空檔案
			for lang in languages:
				lang_dir = base_output_dir / lang
				relative = relative_to_language(file_path, source_dir)
				out = ensure_dir(lang_dir / relative)
				out.write_text("", encoding="utf-8")

	if not files_to_process:
		logger.info("No content to translate.")
		return outputs

	try:
		for lang_idx, lang in enumerate(languages):
			target_code = SAMPLE_LANGUAGE_MAP.get(lang.lower(), lang)
			logger.info("→ [%d/%d] %s (%s) | Batch processing %d files...", lang_idx + 1, len(languages), lang, target_code, len(files_to_process))
			
			start_time = time.time()
			# 使用批次翻譯
			translated_texts = translator.translate_multiple(file_contents, lang)
			duration = time.time() - start_time
			logger.info("  Translation finished in %.2fs (%.2fs/file)", duration, duration / len(files_to_process))
			
			lang_outputs: List[Path] = []
			lang_dir = ensure_dir(base_output_dir / lang)
			ensure_dir(lang_dir / "tts")
			
			for i, file_path in enumerate(files_to_process):
				relative_path = relative_to_language(file_path, source_dir)
				output_path = lang_dir / relative_path
				ensure_dir(output_path.parent)
				output_path.write_text(translated_texts[i] + "\n", encoding="utf-8")
				lang_outputs.append(output_path)
			
			outputs[lang] = lang_outputs
			
			# 每個語言完成後完整的資源清理
			cleanup_torch()
			gc.collect()
			
	finally:
		translator.cleanup()
	return outputs


DEFAULT_TRANSLATION_RUN = RunConfig()


def main(config: RunConfig = DEFAULT_TRANSLATION_RUN) -> None:
	"""翻譯模組入口，依內建設定執行。"""

	logging.basicConfig(level=config.log_level, format=config.log_format)
	story_root = resolve_story_root(config.story_root, config.output_root)
	logging.info("開始翻譯：%s", story_root.name)
	outputs = translate_story(story_root, config.translation, console=True)
	logging.info("翻譯完成，產出語言：%s", ", ".join(outputs.keys()))


if __name__ == "__main__":
	main()
