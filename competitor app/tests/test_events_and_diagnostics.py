from pathlib import Path

import numpy as np

from competitor_app.config import AppConfig, PrivacyConfig
from competitor_app.diagnostics import DiagnosticsStore
from competitor_app.events import CompletedEvent, FrameRecord, MotionEventDetector
from competitor_app.contact_sheet import build_contact_sheet
from competitor_app.vision import AnalysisResult
from tests.test_config import minimal_config


def test_motion_detector_completes_event():
    data = minimal_config()
    data["motion"] = {"min_area": 10, "warmup_seconds": 0.0, "still_frames_to_end": 2, "pre_event_frames": 1, "max_event_frames": 10}
    config = AppConfig.from_dict(data)
    detector = MotionEventDetector(config)

    blank = np.zeros((120, 160, 3), dtype=np.uint8)
    moved = blank.copy()
    moved[52:70, 70:92] = 255

    assert detector.update(blank) is None
    assert detector.update(moved) is None
    assert detector.update(blank) is None
    assert detector.update(blank) is None
    event = detector.update(blank)

    assert event is not None
    assert len(event.records) >= 3


def test_contact_sheet_builds_from_event():
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    record = FrameRecord(frame=frame, object_crop=frame, motion_detected=True, motion_area=100)
    sheet = build_contact_sheet(CompletedEvent(records=(record, record, record)))

    assert sheet.shape[0] > 0
    assert sheet.shape[1] > 0


def test_diagnostics_are_opt_in(tmp_path):
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    event = CompletedEvent(records=(FrameRecord(frame=frame, object_crop=frame, motion_detected=True, motion_area=100),))
    result = AnalysisResult(False, None, "dry", "")
    disabled = DiagnosticsStore(PrivacyConfig(save_diagnostics=False, diagnostics_dir=str(tmp_path)))

    assert disabled.save_event(event, frame, result) is None
    assert list(Path(tmp_path).glob("*")) == []

    enabled = DiagnosticsStore(PrivacyConfig(save_diagnostics=True, diagnostics_dir=str(tmp_path)))
    path = enabled.save_event(event, frame, result)

    assert path is not None
    assert (path / "contact_sheet.jpg").exists()
    assert (path / "event.json").exists()
