from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator
import time

import cv2
import numpy as np

from .config import InputConfig


class FrameSource(ABC):
    @abstractmethod
    def frames(self) -> Iterator[np.ndarray]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class ScreenCaptureSource(FrameSource):
    def __init__(self, config: InputConfig):
        import mss

        self.config = config
        self._mss = mss.mss()
        self._frame_delay = 1.0 / config.fps

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            screenshot = self._mss.grab(self.config.screen_region.as_mss())
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
            yield frame
            time.sleep(self._frame_delay)

    def close(self) -> None:
        self._mss.close()


class VideoFileSource(FrameSource):
    def __init__(self, config: InputConfig):
        self.config = config
        path = Path(config.video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            raise ValueError(f"Unable to open video file: {path}")
        self._frame_delay = 1.0 / config.fps

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            ok, frame = self.capture.read()
            if not ok:
                if not self.config.loop_video:
                    return
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            yield frame
            time.sleep(self._frame_delay)

    def close(self) -> None:
        self.capture.release()


def create_frame_source(config: InputConfig) -> FrameSource:
    if config.kind == "screen_capture":
        return ScreenCaptureSource(config)
    if config.kind == "video_file":
        return VideoFileSource(config)
    raise ValueError(f"Unsupported input kind: {config.kind}")
