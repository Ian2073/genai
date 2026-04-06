"""故事專案的 SDXL 圖像產生流程。"""

from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import torch
from PIL import Image
from tqdm import tqdm



from utils import (
	ensure_dir,
	list_character_prompt_files,
	list_page_prompt_files,
	load_or_create_seed,
	load_prompt,
	page_number_from_prompt,
	resolve_story_root,
	setup_logging,
)
from backends.image import build_image_backend

if platform.system().lower().startswith("win") or platform.system().lower().startswith("darwin"):
	logging.getLogger("torch.distributed.elastic").setLevel(logging.ERROR)

# 抑制 diffusers 和 transformers 的警告輸出（CLIP token 限制已在 story.py 處理）
logging.getLogger("diffusers").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("transformers.models.clip.tokenization_clip").setLevel(logging.ERROR)

@dataclass
class Config:
	"""圖像生成配置參數。"""

	provider: str = "diffusers_sdxl"   # 後端名稱，方便未來替換成其他 image provider
	model_family: Optional[str] = "sdxl" # 預留給不同圖像模型家族的相容策略
	base_model_dir: Path = Path("models/dreamshaperXL_lightningDPMSDE.safetensors") # SDXL Base 模型路徑
	refiner_model_dir: Path = Path("models/stable-diffusion-xl-refiner-1.0")        # SDXL Refiner 模型路徑
	device: str = "auto"            # 運算設備 (auto/cuda/cpu)
	dtype: torch.dtype = torch.float16 # 模型精度
	width: int = 1152               # 預設生成圖片寬度
	height: int = 896               # 預設生成圖片高度
	char_width: int = 1024          # 角色生成圖片寬度
	char_height: int = 1024         # 角色生成圖片高度
	steps: int = 6                  # 推論步數 (Lightning 模型通常較少)
	guidance: float = 2.0           # CFG Scale (引導係數)
	refiner_steps: Optional[int] = None # Refiner 步數，None 表示自動計算
	skip_refiner: bool = True       # 是否跳過 Refiner 階段
	negative_prompt: str = "nsfw, photo, realism, text, watermark, signature, bad anatomy, bad hands, deformed, ugly, worst quality, low quality" # 通用負向提示詞
	cover_prompt_suffix: str = "children's book cover style, vibrant, detailed, whimsical" # 封面提示詞後綴
	character_prompt_suffix: str = "children's book character, full body, white background, cute, expressive" # 角色提示詞後綴
	scene_prompt_suffix: str = "children's storybook art, full scene, detailed, soft lighting" # 場景提示詞後綴
	seed: Optional[int] = None      # 隨機生成種子
	remove_bg: bool = True          # 是否執行去背
	low_vram: bool = True           # 低顯存模式：序列化載入 Base/Refiner 以節省 VRAM


@dataclass
class RunConfig:
	"""控制整體圖像流程的簡單設定，直接在程式碼中調整即可。"""

	story_root: Optional[Path] = None
	output_root: Path = Path("output")
	log_level: int = logging.INFO
	log_format: str = "%(asctime)s [%(levelname)s] %(message)s"
	progress_label: str = "圖像生成"
	sdxl: Config = field(default_factory=Config)



_rembg_session = None

def remove_background(input_path: Path, output_path: Path) -> bool:
	"""使用 rembg 去背，若套件不存在則跳過。
	
	Args:
		input_path: 輸入圖片路徑。
		output_path: 輸出圖片路徑。
		
	Returns:
		成功返回 True，失敗或跳過返回 False。
	"""
	global _rembg_session
	try:
		from rembg import remove, new_session
	except ImportError:
		logging.warning("rembg not installed; skipping background removal for %s", input_path)
		return False

	try:
		if _rembg_session is None:
			_rembg_session = new_session("u2net", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
		image = Image.open(input_path).convert("RGBA")
		result = remove(image, session=_rembg_session)
		output_path.parent.mkdir(parents=True, exist_ok=True)
		result.save(output_path)
		return True
	except Exception as exc:  # pragma: no cover - best effort
		logging.warning("Failed to remove background for %s: %s", input_path, exc)
		return False



def _save_image(image: Image.Image, *paths: Path) -> None:
	"""將同一張圖依序寫入多個路徑。"""
	for path in paths:
		ensure_dir(path.parent)
		image.save(path)


def _collect_generation_tasks(
	story_root: Path,
	resources_dir: Path,
	config: Config,
	logger: logging.Logger,
	output_root_override: Optional[Path] = None,
) -> List[Dict[str, Any]]:
	"""收集所有圖像生成任務（封面、角色、場景）。"""

	if output_root_override:
		image_root = output_root_override
	else:
		image_root = story_root / "image"
		
	image_main_dir = image_root / "main"
	image_original_dir = image_root / "original"
	image_nobg_dir = image_root / "nobg"
	
	for d in (image_main_dir, image_original_dir, image_nobg_dir):
		ensure_dir(d)


	story_seed = config.seed if config.seed is not None else load_or_create_seed(resources_dir)
	tasks: List[Dict[str, Any]] = []
	
	# Cover Task
	cover_prompt_path = resources_dir / "book_cover_prompt.txt"
	if cover_prompt_path.exists():
		prompt_text = load_prompt(cover_prompt_path)
		if prompt_text:
			final_prompt = prompt_text
			if config.cover_prompt_suffix:
				final_prompt = f"{final_prompt}, {config.cover_prompt_suffix}"
			tasks.append({
				"type": "cover",
				"id": "cover",
				"prompt": final_prompt,
				"seed": story_seed,
				"width": config.width,
				"height": config.height,
				"output_paths": [image_original_dir / "book_cover.png", image_main_dir / "book_cover.png"],
				"metadata": {"type": "cover"},
				"remove_bg": False
			})
	
	# Character Tasks
	character_files = list_character_prompt_files(resources_dir)
	for char_path in character_files:
		prompt_text = load_prompt(char_path)
		if not prompt_text:
			logger.warning("Character prompt empty: %s", char_path)
			continue
		char_name = char_path.stem.replace("character_", "")
		final_prompt = prompt_text
		if config.character_prompt_suffix:
			final_prompt = f"{final_prompt}, {config.character_prompt_suffix}"
		
		filename = f"character_{char_name}.png"
		tasks.append({
			"type": "character",
			"id": f"char_{char_name}",
			"prompt": final_prompt,
			"seed": story_seed,
			"width": config.char_width,
			"height": config.char_height,
			"output_paths": [image_original_dir / filename, image_main_dir / filename],
			"nobg_path": image_nobg_dir / filename,
			"metadata": {"char": char_name},
			"remove_bg": config.remove_bg
		})
	
	# Page Tasks
	page_files = list_page_prompt_files(resources_dir)
	for page_path in page_files:
		prompt_text = load_prompt(page_path)
		if not prompt_text:
			logger.warning("Page prompt empty: %s", page_path)
			continue
		page_number = page_number_from_prompt(page_path)
		final_prompt = prompt_text
		if config.scene_prompt_suffix:
			final_prompt = f"{final_prompt}, {config.scene_prompt_suffix}"
		
		filename = f"page_{page_number}_scene.png"
		tasks.append({
			"type": "page",
			"id": f"page_{page_number}",
			"prompt": final_prompt,
			"seed": story_seed,
			"width": config.width,
			"height": config.height,
			"output_paths": [image_original_dir / filename, image_main_dir / filename],
			"metadata": {"page": page_number},
			"remove_bg": False
		})
	
	return tasks


def generate_photos_for_story(
	story_root: Path,
	config: Config,
	progress_label: str = "Generating photos",
	console: bool = True,
	kernel_recorder: Any = None,
) -> bool:
	"""整合提示檔並呼叫 SDXL 生成封面/角色/場景（已重構為小方法）。"""
	log_path = story_root / "logs" / "photo.log"
	ensure_dir(log_path.parent)
	logger = setup_logging(f"photo_pipeline_{story_root.name}", log_path, console=console)
	
	# Discovery strategy: Support both linear (root/resource) and branched (nested/resource) structures
	resource_candidates = []
	
	# 1. Check root resource
	root_res = story_root / "resource"
	if root_res.exists():
		resource_candidates.append(root_res)
	else:
		root_res_alt = story_root / "resources"
		if root_res_alt.exists():
			resource_candidates.append(root_res_alt)
			
	# 2. Check recursive resources (e.g. inside branches)
	# Use set to avoid duplicates if root is handled by rglob (though rglob usually skips root depending on pattern)
	# rglob("resource") matches any file/folder named "resource"
	for p in story_root.rglob("resource"):
		if p.is_dir():
			resource_candidates.append(p)
			
	# Deduplicate based on absolute path
	unique_paths = {}
	for p in resource_candidates:
		unique_paths[p.resolve()] = p
	sorted_candidates = sorted(list(unique_paths.values()), key=lambda p: str(p))
	
	if not sorted_candidates:
		logger.error("Resources directory not found (searched recursively in %s)", story_root)
		return False
	
	# Collect tasks from ALL found resource directories
	tasks = []
	for res_dir in sorted_candidates:
		if res_dir.parent.resolve() == story_root.resolve():
			target_image_root = story_root / "image"
		elif res_dir.name in ("resource", "resources"):
			target_image_root = res_dir.parent / "image"
		else:
			target_image_root = story_root / "image"
			
		try:
			res_rel = res_dir.relative_to(story_root)
			img_rel = target_image_root.relative_to(story_root) if target_image_root.is_relative_to(story_root) else target_image_root
			logger.info("Scanning resources: %s -> Output: %s", res_rel, img_rel)
		except ValueError:
			logger.info("Scanning resources: %s -> Output: %s", res_dir, target_image_root)
		
		batch_tasks = _collect_generation_tasks(story_root, res_dir, config, logger, output_root_override=target_image_root)
		tasks.extend(batch_tasks)

	if not tasks:
		logger.error("No prompts found in any resource directories under %s", story_root)
		return False

	logger.info("Found %d tasks total across %d resource groups. Starting Generation...", len(tasks), len(sorted_candidates))

	generator = build_image_backend(config)
	
	try:
		# 建立進度條 (總步驟 = Base + Refiner + Save/Post-process 概抓)
		# 簡單起見，我們用任務數 * 2 (Base + Refiner)
		total_steps = len(tasks) * (2 if not config.skip_refiner else 1)
		progress = tqdm(total=total_steps, desc=progress_label, disable=not console, unit="step")
		base_started_at = time.perf_counter()
		progress_stride = max(1, len(tasks) // 10)

		logger.info("Phase 1: Generating Base Latents...")
		generator.load_base()
		
		for idx, task in enumerate(tasks, start=1):
			# Profiling wrapper
			def _run_base():
				return generator.run_base_step(
					prompt=task["prompt"],
					seed=task["seed"],
					width=task["width"],
					height=task["height"],
					steps=config.steps,
					guidance=config.guidance,
					negative_prompt=config.negative_prompt,
					output_latents=not config.skip_refiner
				)

			if kernel_recorder:
				with kernel_recorder.profile(story_root.name, f"image_base_{task['id']}", metadata=task["metadata"]):
					result = _run_base()
			else:
				result = _run_base()
			
			if config.skip_refiner:
				task["final_image"] = result
			else:
				task["latents"] = result
			
			progress.update(1)
			if (not console) and (idx % progress_stride == 0 or idx == len(tasks)):
				elapsed = time.perf_counter() - base_started_at
				avg = elapsed / max(1, idx)
				eta = max(0.0, avg * (len(tasks) - idx))
				logger.info(
					"Phase 1 progress: %d/%d tasks | elapsed %.1fs | eta %.1fs",
					idx,
					len(tasks),
					elapsed,
					eta,
				)
		
		# Unload Base
		# Phase 2: Refiner (只有在需要時才執行)
		# 後端會自行處理 Base/Refiner 的切換與釋放
		if not config.skip_refiner:
			logger.info("Phase 2: Refining Images...")
			generator.load_refiner()
			refiner_started_at = time.perf_counter()
			
			for idx, task in enumerate(tasks, start=1):
				if task.get("latents") is None:
					continue

				def _run_refiner():
					return generator.run_refiner_step(
						latents=task["latents"],
						prompt=task["prompt"],
						seed=task["seed"],
						steps=config.refiner_steps or max(1, config.steps // 4),
						guidance=config.guidance,
						negative_prompt=config.negative_prompt
					)

				if kernel_recorder:
					with kernel_recorder.profile(story_root.name, f"image_refine_{task['id']}", metadata=task["metadata"]):
						image = _run_refiner()
				else:
					image = _run_refiner()
				
				task["final_image"] = image
				# 釋放 latents
				task["latents"] = None
				progress.update(1)
				if (not console) and (idx % progress_stride == 0 or idx == len(tasks)):
					elapsed = time.perf_counter() - refiner_started_at
					avg = elapsed / max(1, idx)
					eta = max(0.0, avg * (len(tasks) - idx))
					logger.info(
						"Phase 2 progress: %d/%d tasks | elapsed %.1fs | eta %.1fs",
						idx,
						len(tasks),
						elapsed,
						eta,
					)

		# --- Phase 3: Saving & Post-processing ---
		logger.info("Phase 3: Saving Images...")
		saved_count = 0
		for task in tasks:
			image = task.get("final_image")
			if image:
				_save_image(image, *task["output_paths"])
				saved_count += 1
				
				if task["remove_bg"] and "nobg_path" in task:
					# 這裡可以考慮是否要並行處理，但 rembg 也是吃資源的
					remove_background(task["output_paths"][1], task["nobg_path"]) # Use main path as input
			else:
				logger.error("Task %s failed to produce image", task["id"])

		progress.close()

		if saved_count == 0:
			logger.error("No images were successfully generated")
			return False

		logger.info("Successfully generated %d images", saved_count)
		return True
	finally:
		# 清理生成器資源
		generator.cleanup()


DEFAULT_IMAGE_RUN = RunConfig()


def main(config: RunConfig = DEFAULT_IMAGE_RUN) -> None:
	"""圖像模組入口，依程式內建設定自動執行整個流程。"""
	logging.basicConfig(level=config.log_level, format=config.log_format)
	story_root = resolve_story_root(config.story_root, config.output_root)
	logging.info("開始處理圖像：%s", story_root.name)
	success = generate_photos_for_story(
		story_root,
		config.sdxl,
		progress_label=config.progress_label,
		console=True,
	)
	if not success:
		logging.error("圖像生成失敗：%s", story_root)
		raise SystemExit(1)
	logging.info("圖像生成完成：%s", story_root)


if __name__ == "__main__":
	main()
