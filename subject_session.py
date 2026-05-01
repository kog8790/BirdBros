"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages the lifecycle of a subject interaction session (bird presence, stabilization, and readiness).

RESPONSIBILITIES:
- Track whether a subject is actively present
- Determine when motion stabilizes
- Store best frame during a session
- Signal when a frame is ready for analysis

USED BY:
- main.py (core session orchestration)

INPUTS:
- Cropped subject frames
- Motion boolean from motion_detector

OUTPUTS:
- Session state (active, ready, reset conditions)
- Best frame for API analysis

DESIGN INTENT:
Centralize session logic so motion detection and API decisions remain decoupled.
"""


import time
from motion_triggered_buffer import motion_triggered_buffer
from motion_analysis import motion_analysis

"""             ### SEGMENT: SESSION STATE MANAGEMENT ###
subject_session

STATE:
- active (bool)
- stable (bool)
- best_frame (image)
- carrying / item_label (post-analysis state)

BEHAVIOR:
- Activates when motion is detected
- Tracks stabilization over time
- Captures best frame during stable window
- Resets after completion or failure

IMPORTANT:
Single instance must persist across frames.                                 """

class subject_session:
    def __init__(self, max_buffer_size=30):
        self.active = False
        self.start_time = None

        self.buffer = motion_triggered_buffer(maxlen=max_buffer_size)
        self.analysis = motion_analysis()

        self.best_frame = None

        self.carrying = False
        self.item_label = None
        self.validated = False
        self.reward_fired = False
        self.ready_sent = False

    def start(self):
        self.active = True
        self.start_time = time.time()

        self.buffer.clear()
        self.best_frame = None

        self.carrying = False
        self.item_label = None
        self.validated = False
        self.reward_fired = False
        self.ready_sent = False

    def end(self):
        self.active = False

    def reset(self):
        self.active = False
        self.start_time = None

        self.buffer.clear()
        self.best_frame = None

        self.carrying = False
        self.item_label = None
        self.validated = False
        self.reward_fired = False
        self.ready_sent = False
        
    """             ### SEGMENT: SESSION UPDATE ###
    update():
    Processes incoming frame + motion signal to advance session state and detect readiness.                                                            """

    def update(self, frame, motion_detected):
        # Start new session
        if not self.active and motion_detected:
            self.start()

        if not self.active:
            return None

        # Add frame to buffer
        self.buffer.add(frame)

        frames = self.buffer.get_all()

        # Need at least 2 frames to evaluate stability
        if len(frames) < 2:
            return None

        # Check stabilization
        stable = self.analysis.is_stable(frames)

        if stable and not self.ready_sent:
            self.best_frame = self.analysis.select_best_frame(frames)
            self.ready_sent = True
            return "ready"

        return None

    def has_best_frame(self):
        return self.best_frame is not None

    def get_best_frame(self):
        return self.best_frame

    def mark_validated(self):
        self.validated = True

    def mark_rewarded(self):
        self.reward_fired = True




"""                 ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

motion_detector → subject_motion
    ↓
subject_session.update()
    ↓
"ready" signal
    ↓
main.py triggers vision_api

POST-ANALYSIS:
- session stores carrying + item label
- drives object validation + reward flow

DESIGN INTENT:
Acts as the bridge between low-level motion and high-level decision logic.
"""
