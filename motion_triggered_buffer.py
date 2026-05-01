"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Buffers frames during motion events to retain short sequences of activity.

USED BY:
- motion-driven logic (session / validation flows)

INPUTS:
- incoming frames
- motion trigger (implicit via usage)

OUTPUTS:
- list of buffered frames

DESIGN INTENT:
Provide short-term context around motion events without storing full video streams. """

from collections import deque


class motion_triggered_buffer:
    def __init__(self, maxlen=30):
        self.maxlen = maxlen
        self.frames = deque(maxlen=maxlen)

    def add(self, frame):
        self.frames.append(frame)

    def get_all(self):
        return list(self.frames)

    def clear(self):
        self.frames.clear()

    def is_empty(self):
        return len(self.frames) == 0

    def __len__(self):
        return len(self.frames)
