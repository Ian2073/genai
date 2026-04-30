from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS_FILE = ROOT / "runs" / "terminal_demo_status.json"
DEFAULT_LOG_FILE = ROOT / "runs" / "terminal_demo_detail.log"


STAGE_LABELS = {
    "start": "啟動生成流程",
    "book_start": "建立本次故事任務",
    "init": "載入設定、知識圖譜與模型策略",
    "PRE_EVAL:start": "前置評估：檢查輸入條件",
    "PRE_EVAL:done": "前置評估完成",
    "PRE_EVAL:degraded": "前置評估完成：以降級策略繼續",
    "PRE_EVAL:blocked": "前置評估阻擋：條件未通過",
    "STORY:start": "文字生成：套用 KG 約束、提示詞模板與結構化控制",
    "STORY:done": "文字生成完成：故事草稿與分頁結構已輸出",
    "IMAGE:start": "影像生成：依頁面視覺提示產生圖片",
    "IMAGE:done": "影像生成完成",
    "IMAGE:skip": "影像生成略過",
    "TRANSLATE:start": "翻譯階段：產生多語版本",
    "TRANSLATE:done": "翻譯完成",
    "TRANSLATE:skip": "翻譯略過",
    "VOICE:start": "語音階段：產生旁白音訊",
    "VOICE:done": "語音完成",
    "VOICE:skip": "語音略過",
    "VERIFY:start": "最終驗證：檢查故事、圖片、翻譯與語音輸出",
    "VERIFY:done": "最終驗證完成",
    "VERIFY:skip": "最終驗證略過",
    "EVAL:start": "評估階段：分析生成品質",
    "EVAL:done": "評估完成",
    "EVAL:degraded": "評估完成：部分項目降級",
    "book_done": "本次故事任務完成",
    "retrying": "偵測到失敗，準備重試",
    "done": "生成流程結束",
    "interrupted": "流程已中斷",
}


STORY_STEP_LABELS = {
    "outline": "大綱生成：建立故事主線、轉折點與 KG 約束",
    "title": "標題生成：依主題與角色產生書名",
    "story": "正文生成：產生主線、選擇點與分支內容",
    "narration": "旁白稿生成：整理每頁可朗讀文本",
    "dialogue": "對話抽取：整理角色台詞與互動",
    "scene": "場景描述：建立每頁影像提示基礎",
    "pose": "角色姿態：補齊角色動作與構圖控制",
    "cover": "封面提示：產生封面視覺描述",
    "meta": "故事 metadata：彙整輸出索引與生成證據",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the GenAI pipeline with concise terminal output for demo recording."
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=DEFAULT_STATUS_FILE,
        help="Status JSON written by chief.py.",
    )
    parser.add_argument(
        "--detail-log",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help="Full captured stdout/stderr log.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between status updates.",
    )
    parser.add_argument(
        "chief_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to chief.py.",
    )
    return parser.parse_args()


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def print_step(message: str, *, detail: str | None = None) -> None:
    print(f"[{now()}] {message}", flush=True)
    if detail:
        print(f"          {detail}", flush=True)


def read_status(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def normalize_stage(stage: Any) -> str:
    text = str(stage or "").strip()
    if not text:
        return ""
    if text.startswith("IMAGE:progress"):
        return "IMAGE:progress"
    if text.startswith("CLEANUP:"):
        return ""
    return text


def stage_label(stage: str, status: dict[str, Any] | None = None) -> str:
    if stage == "book_done" and status and not status.get("last_story_root"):
        return "本次嘗試未完成，準備重新生成"
    if stage in STAGE_LABELS:
        return STAGE_LABELS[stage]
    if stage.startswith("IMAGE:"):
        return "影像生成進行中"
    return stage


def normalize_story_step_name(name: Any) -> str:
    text = str(name or "").strip().lower()
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    return text


def story_step_label(name: Any) -> str:
    raw_name = str(name or "").strip()
    normalized = normalize_story_step_name(raw_name)
    label = STORY_STEP_LABELS.get(normalized, raw_name or "故事生成步驟")
    if "(" in raw_name and ")" in raw_name:
        branch = raw_name.split("(", 1)[1].split(")", 1)[0].strip()
        if branch:
            return f"{label}（{branch}）"
    return label


def parse_demo_event(line: str) -> dict[str, Any] | None:
    markers = {
        "::DEMO_STEP::": "step",
        "::DEMO_INFO::": "info",
    }
    event_kind = ""
    payload_text = ""
    for marker, kind in markers.items():
        if marker in line:
            event_kind = kind
            payload_text = line.split(marker, 1)[1].strip()
            break
    if not payload_text:
        return None
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        payload["kind"] = event_kind
        return payload
    return None


def compact_detail(status: dict[str, Any], *, stage: str = "") -> str | None:
    parts: list[str] = []
    current_book = status.get("current_book")
    total_books = status.get("total_books")
    current_attempt = status.get("current_attempt")
    stage_detail = status.get("stage_detail")
    pre_eval = status.get("pre_evaluation") if isinstance(status.get("pre_evaluation"), dict) else {}

    if current_book and total_books:
        parts.append(f"Book {current_book}/{total_books}")
    if current_attempt and int(current_attempt) > 1:
        parts.append(f"Attempt {current_attempt}")
    if pre_eval and stage.startswith("PRE_EVAL:"):
        score = pre_eval.get("overall_score", pre_eval.get("heuristic_score"))
        threshold = pre_eval.get("threshold")
        policy = pre_eval.get("policy")
        if score is not None:
            parts.append(f"score={float(score):.1f}")
        if threshold is not None:
            parts.append(f"threshold={float(threshold):.1f}")
        if policy:
            parts.append(f"policy={policy}")
    if stage_detail:
        parts.append(str(stage_detail))
    return " | ".join(parts) if parts else None


def print_pending_story_events(
    event_queue: queue.Queue[dict[str, Any]],
    printed_events: set[str],
) -> None:
    while True:
        try:
            event = event_queue.get_nowait()
        except queue.Empty:
            break

        if event.get("kind") == "info":
            message = str(event.get("message") or "").strip()
            detail = str(event.get("detail") or "").strip() or None
            signature = f"info:{message}:{detail}"
            if signature in printed_events:
                continue
            printed_events.add(signature)
            print_step(message, detail=detail)
            continue

        index = event.get("index")
        signature = f"step:{index}:{event.get('name')}"
        if signature in printed_events:
            continue
        printed_events.add(signature)
        total = event.get("total")
        detail = f"Story step {index}/{total}" if index and total else None
        print_step(story_step_label(event.get("name")), detail=detail)


def drain_output(
    proc: subprocess.Popen[str],
    log_path: Path,
    event_queue: queue.Queue[dict[str, Any]],
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"# Terminal demo detail log started at {datetime.now().isoformat()}\n\n")
        if proc.stdout is None:
            return
        for line in proc.stdout:
            log_file.write(line)
            log_file.flush()
            event = parse_demo_event(line)
            if event:
                event_queue.put(event)


def build_command(args: argparse.Namespace) -> list[str]:
    chief_args = [arg for arg in args.chief_args if arg != "--"]
    if "--count" not in chief_args:
        chief_args = ["--count", "1", *chief_args]
    if "--status-file" not in chief_args:
        chief_args = [*chief_args, "--status-file", str(args.status_file)]
    return [sys.executable, "chief.py", *chief_args]


def main() -> int:
    args = parse_args()
    status_file = args.status_file.resolve()
    detail_log = args.detail_log.resolve()

    status_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        status_file.unlink()
    except FileNotFoundError:
        pass

    env = os.environ.copy()
    env["DEMO_MODE"] = "1"
    env["DEMO_TERMINAL_EVENTS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("TRANSFORMERS_VERBOSITY", "error")
    env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")

    command = build_command(args)
    print("====================================================")
    print("  GenAI Story Generation Pipeline")
    print("====================================================")
    print_step("啟動生成流程", detail="KG constraints + prompt templates + multimodal generation")

    proc = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    reader = threading.Thread(target=drain_output, args=(proc, detail_log, event_queue), daemon=True)
    reader.start()

    last_stage = ""
    last_image_bucket = -1
    last_attempt = 1
    printed_events: set[str] = set()
    while proc.poll() is None:
        print_pending_story_events(event_queue, printed_events)

        status = read_status(status_file)
        stage = normalize_stage(status.get("current_stage"))
        current_attempt = int(status.get("current_attempt") or last_attempt or 1)
        if current_attempt != last_attempt:
            printed_events.clear()
            last_stage = ""
            last_image_bucket = -1
            print_step(
                f"重新嘗試生成：Attempt {current_attempt}",
                detail="上一輪未通過流程檢查，重新抽取條件並生成",
            )
            last_attempt = current_attempt
        if stage and stage != last_stage:
            print_step(stage_label(stage, status), detail=compact_detail(status, stage=stage))
            last_stage = stage

        if stage == "IMAGE:progress":
            progress = status.get("stage_progress") or {}
            total = int(progress.get("total") or 0)
            completed = int(progress.get("completed") or 0)
            if total > 0:
                bucket = int((completed / total) * 4)
                if bucket != last_image_bucket:
                    print_step("影像生成進度", detail=f"{completed}/{total}")
                    last_image_bucket = bucket
        time.sleep(max(0.2, args.poll_interval))

    reader.join(timeout=5)
    print_pending_story_events(event_queue, printed_events)
    final_status = read_status(status_file)
    exit_code = proc.returncode or 0

    print()
    if exit_code == 0 and final_status.get("state") in {"completed", "running", None}:
        print_step("Demo 生成完成")
    else:
        print_step("Demo 生成未成功完成", detail=f"exit_code={exit_code}")

    story_root = final_status.get("last_story_root")
    if story_root:
        print_step("輸出位置", detail=str(story_root))
    if final_status.get("last_error"):
        print_step("錯誤摘要", detail=str(final_status.get("last_error")))
    print_step("詳細 log", detail=str(detail_log))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
