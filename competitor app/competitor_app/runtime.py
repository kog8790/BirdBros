from __future__ import annotations

import time

from .actions import ActionContext, ActionRunner
from .capture import FrameSource
from .config import AppConfig
from .contact_sheet import build_contact_sheet
from .diagnostics import DiagnosticsStore
from .events import MotionEventDetector
from .vision import VisionAnalyzer


class BehaviorRuntime:
    def __init__(
        self,
        config: AppConfig,
        frame_source: FrameSource,
        analyzer: VisionAnalyzer,
        action_runner: ActionRunner | None = None,
        diagnostics: DiagnosticsStore | None = None,
    ):
        self.config = config
        self.frame_source = frame_source
        self.analyzer = analyzer
        self.action_runner = action_runner or ActionRunner()
        self.diagnostics = diagnostics or DiagnosticsStore(config.privacy)
        self.detector = MotionEventDetector(config)

    def run(self, max_events: int | None = None) -> int:
        self.diagnostics.purge_old()
        processed = 0
        started = time.time()
        for frame in self.frame_source.frames():
            if time.time() - started < self.config.motion.warmup_seconds:
                self.detector.update(frame)
                continue
            event = self.detector.update(frame)
            if event is None:
                continue
            contact_sheet = build_contact_sheet(event)
            result = self.analyzer.analyze_contact_sheet(contact_sheet, self.config.behavior)
            action = self.config.reward_action if result.rewardable else self.config.no_reward_action
            if result.rewardable:
                label = result.object_label or self.config.behavior.object_label
            else:
                label = "No reward"
            self.action_runner.run(action, ActionContext(result.rewardable, label, result.reason))
            self.diagnostics.save_event(event, contact_sheet, result)
            processed += 1
            if max_events is not None and processed >= max_events:
                break
        self.frame_source.close()
        return processed
