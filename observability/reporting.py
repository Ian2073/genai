"""
JSONL 觀測資料轉換工具：輸出 Parquet / SQLite / Excel。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pandas as pd


def from_jsonl(
	jsonl_path: Path,
	output_dir: Optional[Path] = None,
	formats: Optional[Sequence[str]] = None,
) -> Dict[str, Path]:
	"""
	讀取單一 JSONL，輸出指定格式的報表檔案。

	Args:
		jsonl_path: 觀測 JSONL 檔案路徑。
		output_dir: 輸出資料夾，預設為 jsonl 同層的資料夾。
		formats: 可選 "parquet" / "sqlite" / "excel"，預設三種都出。
	"""
	jsonl_path = Path(jsonl_path)
	if output_dir is None:
		output_dir = jsonl_path.parent
	output_dir.mkdir(parents=True, exist_ok=True)
	formats = tuple(formats or ("parquet", "sqlite", "excel"))
	records = _load_jsonl(jsonl_path)
	if not records:
		return {}
	master_df, type_frames = _build_dataframes(records)
	run_id = master_df["run_id"].iloc[0] if not master_df.empty else jsonl_path.stem
	outputs: Dict[str, Path] = {}
	if "parquet" in formats and not master_df.empty:
		parquet_path = output_dir / f"{run_id}.parquet"
		master_df.to_parquet(parquet_path, index=False)
		outputs["parquet"] = parquet_path
	if "sqlite" in formats and not master_df.empty:
		sqlite_path = output_dir / f"{run_id}.sqlite"
		_write_sqlite(master_df, sqlite_path)
		outputs["sqlite"] = sqlite_path
	if "excel" in formats:
		excel_path = output_dir / f"{run_id}.xlsx"
		_write_excel(master_df, type_frames, excel_path)
		outputs["excel"] = excel_path
	return outputs


def from_dir(
	jsonl_dir: Path,
	output_dir: Optional[Path] = None,
	formats: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, Path]]:
	"""
	掃描資料夾內所有 JSONL，逐一輸出報表。
	"""
	jsonl_dir = Path(jsonl_dir)
	if not jsonl_dir.exists():
		return {}
	outputs: Dict[str, Dict[str, Path]] = {}
	for jsonl_path in sorted(jsonl_dir.glob("*.jsonl")):
		result = from_jsonl(
			jsonl_path,
			output_dir=output_dir,
			formats=formats,
		)
		if result:
			outputs[jsonl_path.stem] = result
	return outputs


def _load_jsonl(path: Path) -> List[Mapping[str, object]]:
	records: List[Mapping[str, object]] = []
	with path.open("r", encoding="utf-8") as fh:
		for line in fh:
			line = line.strip()
			if not line:
				continue
			try:
				records.append(json.loads(line))
			except json.JSONDecodeError:
				continue
	return records


def _flatten_payload(payload: MutableMapping[str, object], prefix: str = "") -> Dict[str, object]:
	items: Dict[str, object] = {}
	for key, value in payload.items():
		name = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
		if isinstance(value, MutableMapping):
			items.update(_flatten_payload(value, prefix=name))
		elif isinstance(value, list):
			items[name] = json.dumps(value, ensure_ascii=False)
		else:
			items[name] = value
	return items


def _build_dataframes(
	records: Iterable[Mapping[str, object]]
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
	rows: List[Dict[str, object]] = []
	type_rows: Dict[str, List[Dict[str, object]]] = {}
	for rec in records:
		payload = rec.get("payload", {}) if isinstance(rec.get("payload"), dict) else {}
		base = {
			"run_id": rec.get("run_id"),
			"ts": rec.get("ts"),
			"record_type": rec.get("record_type"),
			"env": json.dumps(rec.get("env", {}), ensure_ascii=False) if rec.get("env") else None,
			"tags": json.dumps(rec.get("tags", {}), ensure_ascii=False) if rec.get("tags") else None,
			"run_metadata": json.dumps(rec.get("run_metadata", {}), ensure_ascii=False)
			if rec.get("run_metadata")
			else None,
		}
		base.update(_flatten_payload(payload))
		rows.append(base)
		record_type = str(rec.get("record_type") or "unknown")
		type_rows.setdefault(record_type, []).append(base.copy())
	master_df = pd.DataFrame(rows)
	type_frames = {rtype: pd.DataFrame(rlist) for rtype, rlist in type_rows.items()}
	return master_df, type_frames


def _write_sqlite(df: pd.DataFrame, path: Path) -> None:
	with sqlite3.connect(path) as conn:
		df.to_sql("observations", conn, if_exists="replace", index=False)


def _write_excel(
	master_df: pd.DataFrame,
	type_frames: Mapping[str, pd.DataFrame],
	path: Path,
) -> None:
	with pd.ExcelWriter(path, engine="openpyxl") as writer:
		limit_rows = master_df.head(100000)
		limit_rows.to_excel(writer, sheet_name="records", index=False)
		for record_type, frame in type_frames.items():
			if frame.empty:
				continue
			sheet_name = _sanitize_sheet_name(record_type)
			frame_limit = frame.head(50000)
			frame_limit.to_excel(writer, sheet_name=sheet_name, index=False)


def _sanitize_sheet_name(name: str) -> str:
	invalid = {":", "\\", "/", "?", "*", "[", "]"}
	for char in invalid:
		name = name.replace(char, "_")
	return (name or "sheet")[:31]


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Convert observability JSONL to reports.")
	parser.add_argument(
		"jsonl",
		type=Path,
		help="Input JSONL file or directory",
	)
	parser.add_argument("--output-dir", type=Path, default=None, help="Directory for reports")
	parser.add_argument(
		"--formats",
		nargs="+",
		default=("parquet", "sqlite", "excel"),
		choices=("parquet", "sqlite", "excel"),
		help="Output formats",
	)
	return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
	args = _parse_args(argv)
	target = args.jsonl
	if target.is_dir():
		from_dir(target, output_dir=args.output_dir, formats=args.formats)
	else:
		from_jsonl(target, output_dir=args.output_dir, formats=args.formats)


if __name__ == "__main__":
	main()


