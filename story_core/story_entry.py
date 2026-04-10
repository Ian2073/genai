"""Story pipeline 的公開入口與 standalone CLI。"""

from __future__ import annotations

import argparse
import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Union

from backends.llm import GenerationParams, LLMConfig, build_llm
from .story_helpers import _apply_default_step_generations
from .story_types import DEFAULT_STORY_CONFIG, PipelineOptions, StoryInput, StoryRunConfig
from utils import (
    build_story_profile,
    build_story_relative_path,
    create_story_root,
    setup_logging,
)


def _as_path(value: Union[str, Path]) -> Path:
    """Normalize string/path inputs into `Path`."""

    return value if isinstance(value, Path) else Path(value)


def generate_story_id(inputs: StoryInput) -> str:
    """以日期與輸入屬性組成唯一 story_id。"""

    stamp = datetime.utcnow().strftime("%Y%m%d")
    slug = f"{inputs.age_group}_{inputs.category}_{inputs.theme}".lower().replace(" ", "-")
    suffix = f"{int(time.time()) % 10000:04d}"
    return f"{stamp}_{slug}_{suffix}"


def main(config: StoryRunConfig = DEFAULT_STORY_CONFIG):
    """故事模組入口，使用內建組態驅動完整流程。"""

    from story import StoryPipeline

    output_root = _as_path(config.output_root)

    profile_rng = random.Random(config.llm_seed)
    profile = build_story_profile(
        language="en",
        age=config.age_group,
        category=config.category,
        subcategory=None,
        theme=None,
        rng=profile_rng,
    )
    story_inputs = StoryInput(
        language=profile.language,
        age_group=profile.age_label,
        category=profile.category_label,
        subcategory=profile.subcategory_label,
        theme=profile.theme_label,
        kg_payload=profile.kg_payload,
        kg_profile=profile,
    )
    story_id = config.story_id or generate_story_id(story_inputs)
    relative_path = build_story_relative_path(profile, story_id)
    story_root = create_story_root(output_root, relative_path, languages=[profile.language])
    log_path = story_root / "logs" / "generation.log"
    logger = setup_logging(f"story_pipeline_{story_id}", log_path, console=True)

    base_generation = GenerationParams(
        max_tokens=512,
        min_tokens=32,
        temperature=0.7,
        top_p=0.9,
        top_k=50,
        repetition_penalty=1.05,
        no_repeat_ngram_size=None,
    )
    step_generations = _apply_default_step_generations(base_generation, {})

    options = PipelineOptions(
        pages_expected=profile.pages_expected,
        max_page_chars=380,
        max_page_sentences=4,
        generation=base_generation,
        model_name=config.llm_model_name,
        prompt_set="general_v1",
        cover_source="outline",
        kg_enabled=True,
        kg_version=profile.kg_version,
        step_generations=step_generations,
    )
    llm = build_llm(
        LLMConfig(
            model_dir=config.llm_model_dir,
            device_map=config.llm_device_map,
            dtype=config.llm_dtype,
            seed=config.llm_seed,
            quantization=config.llm_quantization,
        )
    )
    pipeline = StoryPipeline(
        story_inputs,
        story_id,
        relative_path,
        output_root,
        story_root,
        llm,
        options,
        logger,
    )
    meta = pipeline.run()
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def cli() -> None:
    """命令列入口，支援批次生成測試。"""

    parser = argparse.ArgumentParser(description="Story Generation Standalone Tool")
    parser.add_argument("-n", "--count", type=int, default=1, help="Number of stories to generate")
    parser.add_argument("--age", type=str, default=None, help="Target age group (e.g., '4-5')")
    parser.add_argument("--category", type=str, default=None, help="Target category (e.g., 'Fantasy')")

    args = parser.parse_args()

    print(f"🚀 Starting batch generation: {args.count} stories")
    if args.age:
        print(f"🎯 Target Age: {args.age}")

    for i in range(args.count):
        print(f"\n[Batch {i+1}/{args.count}] Initializing...")
        config = StoryRunConfig(
            age_group=args.age,
            category=args.category,
            llm_seed=random.randint(1, 999999),
        )
        try:
            main(config)
            print(f"✅ [Batch {i+1}/{args.count}] Completed successfully.")
        except Exception as exc:
            logging.error(f"❌ [Batch {i+1}/{args.count}] Failed: {exc}", exc_info=True)

    print("\n✨ All batch jobs finished.")


if __name__ == "__main__":
    cli()
