from __future__ import annotations

import cv2
import numpy as np

from .events import CompletedEvent


def build_contact_sheet(event: CompletedEvent, columns: int = 3, cell_size: int = 220, padding: int = 8) -> np.ndarray:
    frames = select_frames(event)
    if not frames:
        raise ValueError("Cannot build contact sheet without frames")
    rows = int(np.ceil(len(frames) / columns))
    sheet_h = rows * cell_size + (rows + 1) * padding
    sheet_w = columns * cell_size + (columns + 1) * padding
    sheet = np.full((sheet_h, sheet_w, 3), 245, dtype=np.uint8)
    for index, frame in enumerate(frames):
        row = index // columns
        col = index % columns
        x = padding + col * (cell_size + padding)
        y = padding + row * (cell_size + padding)
        resized = resize_contained(frame, cell_size, cell_size)
        y_offset = y + (cell_size - resized.shape[0]) // 2
        x_offset = x + (cell_size - resized.shape[1]) // 2
        sheet[y_offset:y_offset + resized.shape[0], x_offset:x_offset + resized.shape[1]] = resized
        cv2.putText(sheet, str(index + 1), (x + 8, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    return sheet


def select_frames(event: CompletedEvent, target_count: int = 9) -> list[np.ndarray]:
    records = list(event.records)
    if len(records) <= target_count:
        return [record.frame for record in records]
    indices = np.linspace(0, len(records) - 1, target_count).round().astype(int)
    return [records[int(index)].frame for index in indices]


def resize_contained(frame: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    height, width = frame.shape[:2]
    scale = min(max_width / width, max_height / height)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
