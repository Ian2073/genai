"""
資料輸出後端：預設為 JSONL，也可自行擴充。
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Protocol


class Exporter(Protocol):
	"""輸出器介面。"""

	def emit(self, record_type: str, payload: Dict[str, Any]) -> None:
		...

	def close(self) -> None:
		...


class JsonlExporter:
	"""將觀測資料寫入單一 JSONL 檔案。"""

	def __init__(self, file_path: Path, auto_flush: bool = True) -> None:
		self.file_path = file_path
		self.auto_flush = auto_flush
		self.file_path.parent.mkdir(parents=True, exist_ok=True)
		self._fh = self.file_path.open("a", encoding="utf-8")
		self._lock = Lock()

	def emit(self, record_type: str, payload: Dict[str, Any]) -> None:
		try:
			entry = {"type": record_type, **payload}
			line = json.dumps(entry, ensure_ascii=False, default=str)
		except (TypeError, ValueError, OverflowError):
			return  # 不可序列化的資料直接丟棄，不卡主程式
		try:
			with self._lock:
				self._fh.write(line + "\n")
				if self.auto_flush:
					self._fh.flush()
		except (OSError, IOError):
			pass  # 磁碟 IO 失敗不影響主程式

	def close(self) -> None:
		with self._lock:
			if self._fh.closed:
				return
			self._fh.flush()
			self._fh.close()


class NoOpExporter:
	"""便於測試的 no-op exporter。"""

	def emit(self, record_type: str, payload: Dict[str, Any]) -> None:  # pragma: no cover - simple no-op
		return

	def close(self) -> None:  # pragma: no cover
		return


