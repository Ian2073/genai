"""
故事專案用的 XTTS 說書語音生成器 (Voice Generator)

本模組使用 Coqui TTS (XTTS v2) 模型，針對指定的故事資料夾生成語音朗讀檔案。
它會自動掃描故事目錄下的 `page_X_narration.txt` 文字檔，並生成對應的音訊。

## 功能特色
- 自動載入 XTTS 模型 (支援 GPU/CPU)。
- 支援指定的說書人聲音樣本 (Speaker Reference)。
- 自動串接所有頁面的語音為單一長檔。
- 解決了 transformers 套件新舊版本的相容性問題。

## 安裝依賴 (Prerequisites)
在使用此腳本前，請確保已安裝以下套件：
pip install torch torchaudio numpy soundfile coqui-tts transformers

## 使用方法 (Usage)
1. 直接執行 (使用預設設定):
   python voice.py

2. 指定故事路徑與語言:
   python voice.py --story_path "output/MyStory" --language "zh"

3. 指定參考音檔與語速:
   python voice.py --speaker_wav "my_voice.wav" --speed 1.0

Author: GitHub Copilot
"""

from __future__ import annotations

import argparse
import gc
import logging
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import soundfile as sf
import torch

# 假設 utils 模組在同一目錄下
from runtime.story_files import (
    collect_narration_pages,
    detect_story_languages,
    filter_narration_pages,
    find_latest_story_root,
    resolve_narration_dir,
)
from utils import cleanup_torch, ensure_dir, load_prompt, setup_logging
from backends.voice import build_voice_backend

# --- 系統設定區 ---
# 針對 Windows/Mac 的多行程與 Log 設定
if platform.system().lower().startswith("win") or platform.system().lower().startswith("darwin"):
    logging.getLogger("torch.distributed.elastic").setLevel(logging.ERROR)

@dataclass
class Config:
    """語音合成配置參數。"""
    provider: str = "coqui_xtts"                 # 後端名稱，方便未來替換 TTS provider
    model_family: Optional[str] = "xtts"         # 預留給其他 TTS 模型家族切換
    model_dir: Path = Path("models/XTTS-v2")    # 模型存放目錄
    device: str = "auto"                        # 執行裝置: 'auto'/'cuda'/'cpu'
    language: str = "en"                        # 語言代碼: 'en', 'zh', 'ja' 等
    speaker_wav: Optional[Path] = None          # 強制指定的參考人聲 WAV 檔案路徑
    speaker_dir: Optional[Path] = None          # 參考人聲資料夾 (會自動抓第一個 WAV)
    sample_dir: Path = Path("models/XTTS-v2/samples") # 預設樣本目錄
    format: str = "wav"                         # 輸出格式
    narration_dir: str = ""                     # 敘述文字的子目錄 (通常留空自動尋找)
    audio_dir: str = "tts"                      # 輸出音訊資料夾名稱
    raw_audio_dir: str = "tts_raw"              # 原始未處理音訊資料夾名稱
    page_start: Optional[int] = None            # 開始頁碼 (測試用，None 代表全部)
    page_end: Optional[int] = None              # 結束頁碼
    gain: float = 1.0                           # 音量增益 (1.0 = 原音量)
    concat: bool = True                         # 是否將所有頁面串接成一個長檔
    keep_raw: bool = True                       # 是否保留原始分頁音檔
    speed: float = 1.0                          # 語速 (預設 1.0 為標準速度)
    temperature: float = 0.7                    # 生成溫度 (較低比較穩定，較高比較有變化)


@dataclass
class RunConfig:
	"""執行流程設定。"""
	story_root: Optional[Path] = None           # 故事專案根目錄
	output_root: Path = Path("output")          # 預設輸出根目錄
	log_level: int = logging.INFO               # Log 等級
	log_format: str = "%(asctime)s [%(levelname)s] %(message)s"
	xtts: Config = field(default_factory=Config)


def find_first_wav(directory: Path) -> Optional[Path]:
    """在指定目錄尋找第一個 .wav 檔案。
    
    Args:
        directory: 要搜尋的目錄路徑。
        
    Returns:
        找到的第一個 .wav 檔案路徑，沒有則返回 None。
    """
    if not directory.exists() or not directory.is_dir():
        return None
    wavs = sorted(directory.glob("*.wav"))
    return wavs[0] if wavs else None


def resolve_speaker_reference(config: Config, logger: logging.Logger) -> Optional[Path]:
    """決定要使用的「說書人參考音檔」(Speaker Reference)。
    
    搜尋順序:
    1. config.speaker_wav (如果使用者有指定)
    2. config.speaker_dir 下的第一個 wav
    3. config.sample_dir 下的對應語言目錄內的 wav
    4. 預設資料集 (LJSpeech) 中找到的 wav
    
    Args:
        config: 語音生成配置。
        logger: 日誌記錄器。
        
    Returns:
        解析到的參考音檔路徑，找不到則返回 None。
    """
    candidates: List[Path] = []
    if config.speaker_wav:
        candidates.append(config.speaker_wav)
    if config.speaker_dir:
        wav = find_first_wav(config.speaker_dir)
        if wav:
            candidates.append(wav)
    
    # 嘗試從 sample_dir 找
    if config.sample_dir.exists():
        lang_specific = config.sample_dir / config.language
        wav = find_first_wav(lang_specific)
        if wav:
            candidates.append(wav)
        wav = find_first_wav(config.sample_dir)
        if wav:
            candidates.append(wav)
    
    # XTTS 預設資料集路徑
    dataset_dir = config.model_dir / "LJSpeech-1.1" / "wavs"
    wav = find_first_wav(dataset_dir)
    if wav:
        candidates.append(wav)

    for candidate in candidates:
        if candidate and candidate.exists():
            logger.info("使用參考音色: %s", candidate)
            return candidate

    logger.error("找不到任何可用的參考音色 (.wav)。請將參考音檔放入 samples 資料夾或透過參數指定。")
    return None


def copy_audio(src: Path, dst: Path) -> None:
    """複製音檔到目標位置。"""
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def concatenate_audio(chunks: Sequence[Path], output_path: Path) -> bool:
    """
    將多個音檔片段合併成一個長檔案。
    
    Args:
        chunks: 音檔路徑列表。
        output_path: 合併後的檔案路徑。
    """
    if not chunks:
        return False
    buffers: List[np.ndarray] = []
    sample_rate: Optional[int] = None
    for chunk in chunks:
        data, sr = sf.read(chunk)
        if sample_rate is None:
            sample_rate = sr
        elif sr != sample_rate:
            raise ValueError(f"取樣率不一致: {chunk} 為 {sr}，但預期為 {sample_rate}")
        buffers.append(data)
    if not buffers or sample_rate is None:
        return False
    combined = np.concatenate(buffers)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, combined, sample_rate)
    return True


def apply_volume_gain(path: Path, gain: float) -> None:
    """調整音檔音量。"""
    if abs(gain - 1.0) < 1e-3:
        return
    data, sr = sf.read(path)
    data = np.clip(data * gain, -1.0, 1.0)
    sf.write(path, data, sr)


def generate_narration_for_story(
    story_root: Path,
    config: Config,
    console: bool = True,
) -> bool:
    """
    核心功能：逐頁為故事生成語音旁白。
    
    流程:
    1. 找到指定語言的敘述文字資料夾。
    2. 掃描所有 page_X_narration.txt。
    3. 載入 XTTS 模型。
    4. 確定參考音色。
    5. 逐頁生成語音 (儲存於 raw 資料夾)。
    6. (可選) 串接所有音檔 (儲存於 tts 資料夾)。
    """
    log_path = story_root / "logs" / "voice.log"
    logger = setup_logging(f"voice_pipeline_{story_root.name}", log_path, console=console)
    
    # 防止日誌重複輸出 (因 logging.basicConfig 已設定 root logger，若此處 logger 又 propagate 會導致重複)
    logger.propagate = False

    language_dir = story_root / config.language
    narration_dir = resolve_narration_dir(story_root, config.language, config.narration_dir)

    if narration_dir is None:
        logger.error("在路徑 %s 找不到語言 %s 的敘述文字資料夾", story_root, config.language)
        return False

    # 收集要生成的頁面
    pages = filter_narration_pages(
        collect_narration_pages(narration_dir),
        config.page_start,
        config.page_end,
    )
    if not pages:
        logger.error("在 %s 找不到任何敘述文字檔 (page_X_narration.txt)", narration_dir)
        return False
    
    logger.info("找到 %d 個頁面需要生成語音", len(pages))

    # 尋找參考音色
    speaker_wav = resolve_speaker_reference(config, logger)
    if not speaker_wav:
        return False

    # 準備輸出目錄
    language_output_dir = ensure_dir(language_dir)
    audio_dir = ensure_dir(language_output_dir / config.audio_dir)
    audio_raw_dir = ensure_dir(language_output_dir / config.raw_audio_dir)

    # 初始化生成器
    narrator = build_voice_backend(config)
    generated_files: List[Path] = []
    
    try:
        cleanup_torch() # 清理 GPU 記憶體

        for page_number, txt_path in pages:
            text = load_prompt(txt_path)
            if not text:
                logger.warning("跳過空檔案: %s", txt_path)
                continue
                
            filename = f"page_{page_number}_narration.{config.format}"
            
            # 使用相對路徑避免分支檔案覆蓋，並保持結構
            try:
                rel_dir = txt_path.parent.relative_to(narration_dir)
            except ValueError:
                rel_dir = Path(".")
                
            raw_path = audio_raw_dir / rel_dir / filename
            final_path = audio_dir / rel_dir / filename
            
            ensure_dir(raw_path.parent)
            ensure_dir(final_path.parent)
            
            try:
                # 若 raw 檔已存在且我們想要跳過已生成的，可以在這裡加判斷
                # 但目前邏輯是每次都重新生成，確保內容更新
                
                narrator.synthesize_to_file(
                    text=text,
                    speaker_wav=speaker_wav,
                    language=config.language,
                    output_path=raw_path,
                )
                copy_audio(raw_path, final_path)
                apply_volume_gain(final_path, config.gain)
                
                if not config.keep_raw and raw_path.exists():
                    raw_path.unlink(missing_ok=True)
                    
                generated_files.append(final_path)
                logger.info("已完成第 %s 頁語音: %s", page_number, filename)
                
            except Exception as exc:
                logger.error("生成第 %s 頁時發生錯誤: %s", page_number, exc)

        if not generated_files:
            logger.error("流程結束，但沒有生成任何音檔")
            return False

        if config.concat:
            # 按父目錄分組檔案以支援感知分支的串接
            from collections import defaultdict
            groups = defaultdict(list)
            for p in generated_files:
                groups[p.parent].append(p)
            
            logger.info("Concatenating audio in %d groups...", len(groups))
            for folder, files in groups.items():
                # 按頁碼或名稱對檔案進行排序以確保順序正確
                # 假設檔案命名為 page_X_...
                files.sort(key=lambda x: _parse_page_num(x.name))
                
                full_output = folder / f"narration_full.{config.format}"
                try:
                    success = concatenate_audio(files, full_output)
                    if success:
                        apply_volume_gain(full_output, config.gain)
                        logger.info("已合併 %d 個音檔至: %s", len(files), full_output.relative_to(story_root) if full_output.is_relative_to(story_root) else full_output)
                except Exception as exc:
                    logger.warning("合併語音失敗 (%s): %s", folder.relative_to(story_root) if folder.is_relative_to(story_root) else folder, exc)

        # 若設定不保留原始檔，且 tts_raw 資料夾為空，則將其移除以保持整潔
        if not config.keep_raw and audio_raw_dir.exists():
             # 如果需要，遞歸清理空目錄，但簡單的 rmdir 通常足以處理扁平結構
             # 由於我們現在有結構，我們可能會留下空文件夾。
             # 讓我們嘗試清理我們接觸過的特定子目錄。
             pass

        return True
    finally:
        # 清理 narrator 資源
        narrator.cleanup()

def _parse_page_num(filename: str) -> int:
    import re
    m = re.search(r"page_(\d+)", filename)
    return int(m.group(1)) if m else 0



DEFAULT_VOICE_RUN = RunConfig()


def main() -> None:
    """
    程式進入點 (Entry Point)
    
    支援命令列參數 (CLI arguments)。
    """
    parser = argparse.ArgumentParser(description="XTTS 語音說書生成器")
    parser.add_argument("--story_root", type=str, default=None, help="故事專案根目錄路徑，若不指定則自動尋找最新的")
    parser.add_argument("--output_root", type=str, default="output", help="輸出根目錄 (預設: output)")
    parser.add_argument("--language", type=str, default=None, help="語言代碼 (若不指定則自動偵測所有可用語言)")
    parser.add_argument("--speaker_wav", type=str, default=None, help="指定參考人聲 WAV 檔案路徑")
    parser.add_argument("--speed", type=float, default=1.0, help="語速 (預設: 1.0)")
    parser.add_argument("--device", type=str, default="auto", help="執行裝置 (auto/cuda/cpu)")
    parser.add_argument("--no_concat", action="store_true", help="不要合併生成的音檔")
    parser.add_argument("--keep_raw", action="store_true", help="保留原始的 raw 音檔")
    parser.add_argument("--gain", type=float, default=1.0, help="輸出音量增益 (預設: 1.0)")
    
    args = parser.parse_args()
    
    output_root = Path(args.output_root)
    
    # --- 1. 決定故事資料夾 ---
    target_story_root: Path
    if args.story_root:
        target_story_root = Path(args.story_root)
        if not target_story_root.exists():
            print(f"錯誤: 指定的故事路徑不存在: {target_story_root}")
            sys.exit(1)
    else:
        # 自動尋找最新的故事
        found = find_latest_story_root(output_root)
        if found:
            target_story_root = found
            print(f"專案自動偵測: 鎖定最新的故事 '{target_story_root.name}'")
        else:
            print(f"錯誤: 在 '{output_root}' 下找不到任何包含敘述文字的故事專案。")
            print("請確認您是否已經生成了故事文字稿，或者該資料夾結構是否正確。")
            sys.exit(1)

    # --- 2. 決定要處理的語言 ---
    target_languages: List[str] = []
    if args.language:
        target_languages = [args.language]
    else:
        detected = detect_story_languages(target_story_root)
        if detected:
            print(f"語言自動偵測: 找到可用語言 {detected}")
            target_languages = detected
        else:
            print("警告: 偵測不到任何語言資料夾，將嘗試預設語言 'en'")
            target_languages = ["en"]

    # --- 3. 執行語音生成迴圈 ---
    # 初始化 Log
    log_level = logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=log_level, format=log_format)

    total_success = True

    for lang in target_languages:
        logging.info("--------------------------------------------------")
        logging.info(f"正在處理語言: [{lang}]")
        
        # 建立針對該語言的 Config
        xtts_config = Config(
            language=lang,
            speed=args.speed,
            device=args.device,
            concat=(not args.no_concat),
            keep_raw=args.keep_raw,
            gain=args.gain,
            speaker_wav=Path(args.speaker_wav) if args.speaker_wav else None
        )

        run_config = RunConfig(
            story_root=target_story_root,
            output_root=output_root,
            log_level=log_level,
            xtts=xtts_config
        )

        try:
            success = generate_narration_for_story(target_story_root, run_config.xtts, console=True)
            if not success:
               logging.error(f"語言 [{lang}] 生成失敗")
               total_success = False
        except Exception as e:
            logging.error(f"處理語言 [{lang}] 時發生未預期錯誤: {e}")
            total_success = False

    logging.info("========================================")
    if total_success:
        logging.info(f"所有任務完成！故事專案: {target_story_root.name}")
    else:
        logging.error("部分任務失敗，請檢查 Log。")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

