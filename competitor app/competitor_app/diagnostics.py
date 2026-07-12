from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import json

import cv2
import numpy as np

from .config import PrivacyConfig
from .events import CompletedEvent
from .vision import AnalysisResult


class DiagnosticsStore:
    def __init__(self, config: PrivacyConfig):
        self.config = config
        self.root = Path(config.diagnostics_dir)

    def purge_old(self) -> None:
        if not self.root.exists():
            return
        cutoff = datetime.now() - timedelta(days=self.config.retention_days)
        for path in self.root.iterdir():
            if not path.is_dir():
                continue
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                for child in path.iterdir():
                    child.unlink()
                path.rmdir()

    def save_event(self, event: CompletedEvent, contact_sheet: np.ndarray, result: AnalysisResult) -> Path | None:
        if not self.config.save_diagnostics:
            return None
        self.root.mkdir(parents=True, exist_ok=True)
        session_dir = self.root / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        session_dir.mkdir()
        cv2.imwrite(str(session_dir / "contact_sheet.jpg"), contact_sheet)
        metadata = {
            "result": dataclass_to_dict(result),
            "frame_count": len(event.records),
            "motion_areas": [record.motion_area for record in event.records],
        }
        with open(session_dir / "event.json", "w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)
        return session_dir


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value
