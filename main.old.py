"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Main orchestration loop for the Bird Bros system.

RESPONSIBILITIES:
- Initialize all components
- Capture frames
- Apply ROI logic
- Run motion detection and session logic
- Call vision API
- Trigger reward or no-reward actions
- Render overlay and handle UI updates

USED BY:
- Entry point of the application

INPUTS:
- Config (via control_panel)
- Frames (via cam_controller)

OUTPUTS:
- System actions (reward/no reward)
- Overlay visualization

DESIGN INTENT:
Central coordinator that connects all modules without embedding their internal logic.
"""

import os
import time
import cv2
from dotenv import load_dotenv

from cam_controller import cam_controller
from bound_box_define import bound_box_define
from bound_box_drawer import bound_box_drawer
from motion_detector import motion_detector
from subject_session import subject_session
from vision_api import vision_api
from resulting_action import resulting_action
from overlay_window import overlay_window, get_or_create_qt_app
from control_panel import control_panel
from logger import Logger
from session_storyboard import session_storyboard


def encode_frame_to_jpeg_bytes(frame):
    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        raise ValueError("Failed to encode frame to JPEG bytes")
    return buffer.tobytes()


def clamp_roi_to_frame(box, frame_w, frame_h):
    x = max(0, min(box.x, frame_w - 1))
    y = max(0, min(box.y, frame_h - 1))
    w = max(1, min(box.w, frame_w - x))
    h = max(1, min(box.h, frame_h - y))
    return bound_box_define(x=x, y=y, w=w, h=h, label=box.label)


def crop_from_box(frame, box):
    return frame[box.y:box.y + box.h, box.x:box.x + box.w]


def build_capture_region(logical_region, app):
    screen = app.primaryScreen()
    if screen is None:
        return logical_region.copy()

    scale = float(screen.devicePixelRatio())
    geom = screen.geometry()

    screen_left = geom.x()
    screen_top = geom.y()

    return {
        "left": int(round((screen_left + logical_region["left"]) * scale)),
        "top": int(round((screen_top + logical_region["top"]) * scale)),
        "width": int(round(logical_region["width"] * scale)),
        "height": int(round(logical_region["height"] * scale)),
    }


def normalize_captured_frame(frame, expected_width, expected_height):
    frame_h, frame_w = frame.shape[:2]
    if frame_w == expected_width and frame_h == expected_height:
        return frame

    return cv2.resize(
        frame,
        (expected_width, expected_height),
        interpolation=cv2.INTER_LINEAR
    )


def get_display_bool(config, key, default=False):
    return config.get("display", {}).get(key, default)


def main():
    
    """             ### SEGMENT: INITIALIZATION ###
    Sets up all core components including:
    - config + control panel
    - camera controller
    - motion detectors
    - session manager
    - vision API
    - overlay window
    - action handler
    NOTE:   All long-lived objects are instantiated here and persist across the main loop."""
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env")

    vision = vision_api(api_key=api_key)
    logger = Logger()

    app = get_or_create_qt_app()
    running = True

    panel = control_panel()
    current_config = panel.get_current_config()
    
    manual_capture_requested = False

    action = resulting_action(config=current_config)
    storyboard = session_storyboard(logger=logger)

    def on_config_changed(new_config):
        nonlocal current_config
        current_config = new_config

        action.config = current_config
        action.reward_config = current_config.get("reward_action", {})
        action.no_reward_config = current_config.get("no_reward_action", {})

    def on_exit_requested():
        nonlocal running
        running = False
        
    def on_manual_capture_requested():
        nonlocal manual_capture_requested
        manual_capture_requested = True

    panel.config_changed.connect(on_config_changed)
    panel.manual_capture_requested.connect(on_manual_capture_requested)
    panel.exit_requested.connect(on_exit_requested)
    
    region = current_config["capture_region"].copy()
    capture_region = region

    overlay = overlay_window(
        left=region["left"],
        top=region["top"],
        width=region["width"],
        height=region["height"]
    )

    cam = cam_controller(region=region, fps=6)
    drawer = bound_box_drawer()

    motion_min_area = current_config["motion"]["min_area"]
    subject_motion_detector = motion_detector(min_area=motion_min_area)
    object_motion_detector = motion_detector(min_area=motion_min_area)

    session = subject_session()

    startup_time = time.time()
    warmup_seconds = 3.0
    warmup_complete_logged = False

    subject_result = None
    object_result = None

    waiting_for_object = False
    object_checked = False
    last_object_check_time = 0.0
    object_check_cooldown = 1.0

    current_event_text = "Warmup"

    prev_subject_motion = False
    prev_object_motion = False
    prev_session_active = False
    prev_waiting_for_object = False

    prev_region = region.copy()
    prev_motion_min_area = motion_min_area
    prev_subject_roi = current_config["subject_roi"].copy()
    prev_object_roi = current_config["object_roi"].copy()

    panel.move(region["left"] + region["width"] + 20, region["top"])
    panel.show()
    panel.raise_()
    panel.activateWindow()

    def finalize_storyboard_if_active(rewarded=False, label="", frame=None, notes="", subject_frame=None, object_frame=None):
        if storyboard.active:
            storyboard.finalize(
                rewarded=rewarded,
                label=label,
                frame=frame,
                notes=notes,
                subject_frame=subject_frame,
                object_frame=object_frame
            )

    def reset_runtime_state(event_text="Warmup", storyboard_abort_note=None):
        nonlocal startup_time
        nonlocal warmup_complete_logged
        nonlocal current_event_text
        nonlocal subject_result
        nonlocal object_result
        nonlocal waiting_for_object
        nonlocal object_checked
        nonlocal last_object_check_time
        nonlocal prev_subject_motion
        nonlocal prev_object_motion
        nonlocal prev_session_active
        nonlocal prev_waiting_for_object

        if storyboard_abort_note and storyboard.active:
            storyboard.abort(notes=storyboard_abort_note)

        startup_time = time.time()
        warmup_complete_logged = False
        current_event_text = event_text

        session.reset()
        subject_result = None
        object_result = None
        waiting_for_object = False
        object_checked = False
        last_object_check_time = 0.0
        subject_motion_detector.reset()
        object_motion_detector.reset()

        prev_subject_motion = False
        prev_object_motion = False
        prev_session_active = False
        prev_waiting_for_object = False

    logger.log_info(
        "Bird Bros overlay loop started",
        region=region,
        capture_region=capture_region,
        warmup_seconds=warmup_seconds
    )

    print("[INFO] Press Ctrl+C in terminal to stop.")

    try:
        """             ### SEGMENT: MAIN LOOP ###
        Continuously:
        - captures frame
        - updates config
        - processes motion + session logic
        - updates overlay
        - handles system state transitions
        IMPORTANT:  This loop is the heartbeat of the system and must remain efficient.                                                     """
        while running:
            app.processEvents()
            """     ### SEGMENT: CONFIG UPDATE HANDLING ###
            Detects changes from control_panel and applies them at runtime.
            INCLUDES:
            - ROI updates
            - motion sensitivity changes
            - capture region changes
            BEHAVIOR:
            - Resets detectors/session when necessary
            - Keeps runtime state consistent with UI"""
            
            region = current_config["capture_region"].copy()
            motion_min_area = current_config["motion"]["min_area"]
            show_grid = get_display_bool(current_config, "show_grid", True)
            show_coords = get_display_bool(current_config, "show_coords", True)
            show_capture_border = get_display_bool(current_config, "show_capture_border", True)
            show_labels = get_display_bool(current_config, "show_labels", True)

            current_subject_roi = current_config["subject_roi"].copy()
            current_object_roi = current_config["object_roi"].copy()

            action.config = current_config
            action.reward_config = current_config.get("reward_action", {})
            action.no_reward_config = current_config.get("no_reward_action", {})

            if region != prev_region:
                cam.region = region

                overlay.set_overlay_geometry(
                    left=region["left"],
                    top=region["top"],
                    width=region["width"],
                    height=region["height"]
                )

                panel.move(region["left"] + region["width"] + 20, region["top"])
                panel.raise_()
                panel.activateWindow()

                reset_runtime_state(
                    event_text="Warmup",
                    storyboard_abort_note="Storyboard aborted because capture region changed."
                )
                logger.log_info(
                    "Capture region updated",
                    region=region,
                    capture_region=capture_region
                )
                prev_region = region.copy()

            if motion_min_area != prev_motion_min_area:
                subject_motion_detector = motion_detector(min_area=motion_min_area)
                object_motion_detector = motion_detector(min_area=motion_min_area)

                reset_runtime_state(
                    event_text="Warmup",
                    storyboard_abort_note="Storyboard aborted because motion sensitivity changed."
                )
                logger.log_info("Motion sensitivity updated", min_area=motion_min_area)
                prev_motion_min_area = motion_min_area

            roi_changed = (
                current_subject_roi != prev_subject_roi
                or current_object_roi != prev_object_roi
            )

            if roi_changed:
                subject_motion_detector.reset()
                object_motion_detector.reset()

                reset_runtime_state(
                    event_text="ROI Changed",
                    storyboard_abort_note="Storyboard aborted because ROI changed during session."
                )
                logger.log_info(
                    "ROI updated",
                    subject_roi=current_subject_roi,
                    object_roi=current_object_roi
                )

                prev_subject_roi = current_subject_roi.copy()
                prev_object_roi = current_object_roi.copy()

            frame = cam.get_frame()
            #Debug purposes for screen size errors: print(frame.shape)
            frame = normalize_captured_frame(
                frame,
                expected_width=region["width"],
                expected_height=region["height"]
            )
            frame_h, frame_w = frame.shape[:2]

            region_w = region["width"]
            region_h = region["height"]

            subject_roi = current_config["subject_roi"]
            object_roi = current_config["object_roi"]

            """     ### SEGMENT: ROI PROCESSING ###
            Converts ROI percentages → pixel coordinates per frame.

            APPLIES:
            - subject ROI
            - object ROI

            OUTPUT:
            - bound_box_define instances for cropping and visualization"""
            
            subject_box = bound_box_define(
                x=int(subject_roi["x_pct"] * region_w),
                y=int(subject_roi["y_pct"] * region_h),
                w=int(subject_roi["w_pct"] * region_w),
                h=int(subject_roi["h_pct"] * region_h),
                label="subject"
            )

            object_box = bound_box_define(
                x=int(object_roi["x_pct"] * region_w),
                y=int(object_roi["y_pct"] * region_h),
                w=int(object_roi["w_pct"] * region_w),
                h=int(object_roi["h_pct"] * region_h),
                label="object"
            )

            subject_box = clamp_roi_to_frame(subject_box, frame_w, frame_h)
            object_box = clamp_roi_to_frame(object_box, frame_w, frame_h)

            subject_crop = crop_from_box(frame, subject_box)
            object_crop = crop_from_box(frame, object_box)
            
            if manual_capture_requested:
                os.makedirs("debug_captures", exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")

                cv2.imwrite(f"debug_captures/{timestamp}_full_frame.jpg", frame)
                cv2.imwrite(f"debug_captures/{timestamp}_subject_roi.jpg", subject_crop)
                cv2.imwrite(f"debug_captures/{timestamp}_object_roi.jpg", object_crop)

                logger.log_info(
                    "Manual ROI capture saved",
                    full_frame=f"debug_captures/{timestamp}_full_frame.jpg",
                    subject_roi=f"debug_captures/{timestamp}_subject_roi.jpg",
                    object_roi=f"debug_captures/{timestamp}_object_roi.jpg"
                )

                manual_capture_requested = False

            """ ### SEGMENT: MOTION DETECTION ###
            Runs motion detection on subject and object crops.
            OUTPUT:
            - subject_motion (bool)
            - object_motion (bool)

            NOTE:
            Feeds directly into session logic."""
            
            subject_motion = subject_motion_detector.detect(subject_crop)

            object_motion_enabled = session.active or waiting_for_object

            if object_motion_enabled:
                object_motion = object_motion_detector.detect(object_crop)
            else:
                object_motion_detector.reset()
                object_motion = False

            elapsed_since_start = time.time() - startup_time
            in_warmup = elapsed_since_start < warmup_seconds

            if in_warmup:
                remaining = max(0.0, warmup_seconds - elapsed_since_start)

                if current_event_text == "ROI Changed":
                    banner_text = f"ROI Changed | Warmup {remaining:.1f}s"
                else:
                    banner_text = f"Warmup {remaining:.1f}s"

                prev_subject_motion = subject_motion
                prev_object_motion = object_motion
                prev_session_active = session.active
                prev_waiting_for_object = waiting_for_object

                overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)
                overlay_frame = drawer.draw_event_banner(overlay_frame, banner_text)

                if show_capture_border:
                    overlay_frame = drawer.draw_capture_border(overlay_frame, label="Capture Region")

                if show_grid:
                    overlay_frame = drawer.draw_grid(overlay_frame, step=100)

                if show_labels:
                    subject_label = f"subject motion: {subject_motion} | warmup"
                    object_label = f"object motion: {object_motion} | warmup"
                else:
                    subject_label = ""
                    object_label = ""
                labels_to_draw = [subject_label, object_label] if show_labels else None

                overlay_frame = drawer.draw_boxes(
                    overlay_frame,
                    [subject_box, object_box],
                    labels=labels_to_draw,
                    colors=[(0, 255, 0, 255), (255, 0, 0, 255)],
                    show_coords=show_coords
                )

                overlay.update_frame(overlay_frame)
                time.sleep(1 / 60)
                continue

            if not warmup_complete_logged:
                logger.log_info("Warmup complete; live detection enabled")
                warmup_complete_logged = True
                current_event_text = "Idle"

            if subject_motion != prev_subject_motion:
                logger.log_motion("subject", subject_motion)

            if object_motion != prev_object_motion:
                logger.log_motion("object", object_motion)

            prev_subject_motion = subject_motion
            prev_object_motion = object_motion

            if (subject_motion or object_motion) and current_event_text == "Idle":
                current_event_text = "Motion Detected"

            """     ### SEGMENT: SESSION MANAGEMENT ###
            Handles subject interaction lifecycle via subject_session.

            INCLUDES:
            - activation on motion
            - stabilization detection
            - best frame selection
            - readiness signaling"""
            session_status = session.update(subject_crop, subject_motion)

            if session.active and not prev_session_active:
                current_event_text = "Subject_Session Started"
                logger.log_info("Subject session started")
                storyboard.start_session(
                    opening_frame=subject_crop.copy(),
                    notes="Subject session started"
                )

            if not session.active and prev_session_active:
                logger.log_info("Subject session ended/reset")
                if storyboard.active:
                    storyboard.abort(notes="Session reset before reward/object validation completed.")

            prev_session_active = session.active

            if session_status == "ready":
                current_event_text = "Frame Stabilized"
                logger.log_info("Subject frame stabilized and ready")
                if storyboard.active:
                    storyboard.add_event(
                        "subject_ready",
                        frame=subject_crop.copy(),
                        notes="Subject frame stabilized"
                    )

            """         ### SEGMENT: SUBJECT ANALYSIS ###
            When session is ready:
            - sends best frame to vision_api
            - receives classification (bird, holding, object label)
            OUTPUT:
            - subject_result
            - updates session state"""
            
            if session_status == "ready" and session.has_best_frame() and subject_result is None:
                try:
                    best_frame = session.get_best_frame()
                    best_frame_bytes = encode_frame_to_jpeg_bytes(best_frame)

                    current_event_text = "Sending Subject To OpenAI"
                    logger.log_api_call("subject_analysis")

                    subject_result = vision.analyze_subject(best_frame_bytes)

                    logger.log_info(
                        "Subject analysis complete",
                        liveLabel=subject_result.liveLabel,
                        hodlBool=subject_result.hodlBool,
                        hodlClass=subject_result.hodlClass,
                        isMatch=subject_result.isMatch
                    )

                    if storyboard.active:
                        subject_detail = (
                            f"{subject_result.liveLabel}_"
                            f"holding_{subject_result.hodlBool}_"
                            f"{subject_result.hodlClass}_"
                            f"match_{subject_result.isMatch}"
                        )

                        storyboard.add_event(
                            "subject_analysis_complete",
                            subject_frame=best_frame.copy(),
                            object_frame=object_crop.copy(),
                            notes=(
                                f"liveLabel={subject_result.liveLabel}, "
                                f"hodlBool={subject_result.hodlBool}, "
                                f"hodlClass={subject_result.hodlClass}, "
                                f"isMatch={subject_result.isMatch}"
                            ),
                            frame=object_crop.copy()
                        )

                    if subject_result.liveLabel:
                        current_event_text = f"{subject_result.liveLabel} Detected"
                    else:
                        current_event_text = "Subject Analysis Complete"

                    session.carrying = bool(subject_result.hodlBool)
                    session.item_label = subject_result.hodlClass

                    if subject_result.hodlBool and subject_result.isMatch and subject_result.hodlClass:
                        waiting_for_object = True
                        object_checked = False
                        current_event_text = "Litter Detected"
                        logger.log_info(
                            "Waiting for object validation",
                            expected_label=subject_result.hodlClass
                        )
                        if storyboard.active:
                            storyboard.add_event(
                                "waiting_for_object",
                                subject_frame=best_frame.copy(),
                                object_frame=object_crop.copy(),
                                notes=f"Expected object label: {subject_result.hodlClass}"
                            )
                    else:
                        current_event_text = "No Reward"
                        action.no_reward(label="No valid trash detected")
                        logger.log_reward(
                            False,
                            label="No valid trash detected",
                            liveLabel=subject_result.liveLabel,
                            hodlBool=subject_result.hodlBool,
                            hodlClass=subject_result.hodlClass,
                            isMatch=subject_result.isMatch
                        )
                        finalize_storyboard_if_active(
                            rewarded=False,
                            label="No valid trash detected",
                            notes=(
                                "Reward triggered: False. "
                                f"Reason: Subject analysis did not qualify. "
                                f"liveLabel={subject_result.liveLabel}, "
                                f"holding={subject_result.hodlBool}, "
                                f"item={subject_result.hodlClass}, "
                                f"match={subject_result.isMatch}"
                            ),
                            subject_frame=subject_crop.copy(),
                            object_frame=object_crop.copy()
                        )
                        session.reset()
                        subject_result = None
                        object_result = None
                        waiting_for_object = False
                        object_checked = False
                        subject_motion_detector.reset()
                        object_motion_detector.reset()
                        
                except Exception as e:
                    current_event_text = "Subject Analysis Error"
                    logger.log_error("Subject analysis failed", error=str(e))
                    if storyboard.active:
                        storyboard.abort(notes=f"Subject analysis failed: {e}")
                    session.reset()
                    subject_result = None
                    object_result = None
                    waiting_for_object = False
                    object_checked = False
                    subject_motion_detector.reset()
                    object_motion_detector.reset()
                    
            if waiting_for_object and not prev_waiting_for_object:
                logger.log_info("Object wait state entered")

            if not waiting_for_object and prev_waiting_for_object:
                logger.log_info("Object wait state exited")

            prev_waiting_for_object = waiting_for_object

            now = time.time()
            
            """         ### SEGMENT: OBJECT VALIDATION ###
            After valid subject detection:
            - waits for object motion
            - captures object frame
            - validates against expected label via vision_api
            OUTPUT:
            - object_result                                 """
            if (
                waiting_for_object
                and not object_checked
                and object_motion
                and subject_result is not None
                and subject_result.hodlClass
                and (now - last_object_check_time) >= object_check_cooldown
            ):
                try:
                    last_object_check_time = now
                    object_crop_bytes = encode_frame_to_jpeg_bytes(object_crop)

                    current_event_text = "Validating Object"
                    logger.log_api_call(
                        "object_validation",
                        expected_label=subject_result.hodlClass
                    )

                    object_result = vision.analyze_object(
                        object_crop_bytes,
                        expected_label=subject_result.hodlClass
                    )

                    object_checked = True

                    logger.log_info(
                        "Object validation complete",
                        objectLabel=object_result.objectLabel,
                        isMatch=object_result.isMatch
                    )

                    if storyboard.active:
                        object_detail = (
                            f"{object_result.objectLabel}_"
                            f"match_{object_result.isMatch}"
                        )

                        storyboard.add_event(
                            "object_validation_complete",
                            subject_frame=subject_crop.copy(),
                            object_frame=object_crop.copy(),
                            notes=(
                                f"objectLabel={object_result.objectLabel}, "
                                f"isMatch={object_result.isMatch}"
                            )
                        )
                    
                    """ ### SEGMENT: RESULTING ACTION ###
                    Determines final outcome:
                    - reward() if match
                    - no_reward() otherwise
                    SIDE EFFECTS:
                    - treat dispense (via pyautogui or other mode)
                    - logging                                   """
                    if object_result.isMatch and subject_result.isMatch:
                        current_event_text = "Treat Dispensed"
                        reward_label = object_result.objectLabel or subject_result.hodlClass or "Match"
                        action.reward(label=reward_label)
                        session.mark_validated()
                        session.mark_rewarded()
                        logger.log_reward(True, label=reward_label)

                        finalize_storyboard_if_active(
                            rewarded=True,
                            label=reward_label,
                            notes=(
                                "Reward triggered: True. "
                                f"Reason: Object matched expected label. "
                                f"reward_label={reward_label}, "
                                f"objectLabel={object_result.objectLabel}, "
                                f"match={object_result.isMatch}"
                            ),
                            subject_frame=subject_crop.copy(),
                            object_frame=object_crop.copy()
                        )
                    else:
                        current_event_text = "No Reward"
                        no_reward_label = object_result.objectLabel or "Object mismatch"
                        action.no_reward(label=no_reward_label)
                        logger.log_reward(False, label=no_reward_label)

                        finalize_storyboard_if_active(
                            rewarded=False,
                            label=no_reward_label,
                            frame=object_crop.copy(),
                            notes="Object validation failed."
                        )

                    session.reset()
                    subject_result = None
                    object_result = None
                    waiting_for_object = False
                    object_checked = False
                    subject_motion_detector.reset()
                    object_motion_detector.reset()

                except Exception as e:
                    current_event_text = "Object Validation Error"
                    logger.log_error("Object validation failed", error=str(e))
                    if storyboard.active:
                        storyboard.abort(notes=f"Object validation failed: {e}")
                    session.reset()
                    subject_result = None
                    object_result = None
                    waiting_for_object = False
                    object_checked = False
                    subject_motion_detector.reset()
                    object_motion_detector.reset()

            if show_labels:
                subject_label = f"subject motion: {subject_motion}"
                object_label = f"object motion: {object_motion}"
            else:
                subject_label = ""
                object_label = ""

            if session.active:
                subject_label += " | session: active"
            else:
                subject_label += " | session: idle"

            if subject_result is not None:
                subject_label += f" | live: {subject_result.liveLabel}"
                subject_label += f" | holding: {subject_result.hodlBool}"
                if subject_result.hodlClass:
                    subject_label += f" | item: {subject_result.hodlClass}"

            if waiting_for_object:
                object_label += " | waiting: yes"

            if object_result is not None:
                object_label += f" | object: {object_result.objectLabel}"
                object_label += f" | match: {object_result.isMatch}"

            labels_to_draw = [subject_label, object_label] if show_labels else None

            """     ### SEGMENT: OVERLAY RENDERING ###
            Builds visual overlay each frame including:
            - ROI boxes
            - event banner
            - optional grid/border
            USES:
            - bound_box_drawer
            - overlay_window                        """
            overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)
            overlay_frame = drawer.draw_event_banner(overlay_frame, current_event_text)

            if show_capture_border:
                overlay_frame = drawer.draw_capture_border(overlay_frame, label="Capture Region")

            if show_grid:
                overlay_frame = drawer.draw_grid(overlay_frame, step=100)

            overlay_frame = drawer.draw_boxes(
                overlay_frame,
                [subject_box, object_box],
                labels=labels_to_draw,
                colors=[(0, 255, 0, 255), (255, 0, 0, 255)],
                show_coords=show_coords
            )

            overlay.update_frame(overlay_frame)
            time.sleep(1 / 60)

    except KeyboardInterrupt:
        logger.log_info("Bird Bros overlay stopped by user")
        print("\n[INFO] Stopping Bird Bros overlay.")
                      
    finally:
        logger.log_info("Bird Bros shutdown complete")
        if storyboard.active:
            storyboard.abort(notes="Program shutdown before storyboard finalized.")
        overlay.close()
        panel.close()


if __name__ == "__main__":
    main()



"""                 ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

cam_controller → frame
    ↓
ROI processing
    ↓
motion_detector
    ↓
subject_session
    ↓
vision_api (subject → object)
    ↓
resulting_action
    ↓
overlay rendering

DESIGN INTENT:
Keep main.py as a clean orchestration layer coordinating independent modules.
"""
