""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Main orchestration loop for the Bird Bros system.

CORE FLOW:
- Capture frame
- Build subject/object/combined ROIs
- Track object ROI motion as centroid detections
- Event session manager manages one or more active motion events
- Completed sessions become contact sheets
- Contact sheet is sent to OpenAI using configurable task labels
- Reward depends on the returned event judgment

DESIGN INTENT:
Keep main.py as the coordinator while capture, tracking, event management,
storyboarding, OpenAI calls, and reward actions remain modular. """

import os
import time
from collections import deque

import cv2
from dotenv import load_dotenv

from cam_controller import cam_controller
from bound_box_define import bound_box_define
from bound_box_drawer import bound_box_drawer
from motion_object_tracker import motion_object_tracker
from event_session_manager import event_session_manager
from frame_change_analyzer import frame_change_analyzer
from contact_sheet_builder import contact_sheet_builder
from vision_api import vision_api
from resulting_action import resulting_action
from overlay_window import overlay_window, get_or_create_qt_app
from status_window import status_window
from control_panel import control_panel
from logger import Logger
from session_storyboard import session_storyboard
from api_key_store import get_openai_api_key
from first_run_setup import run_first_run_setup


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


def build_combined_box(subject_box, object_box, frame_w, frame_h, padding=0):
    x1 = min(subject_box.x, object_box.x) - padding
    y1 = min(subject_box.y, object_box.y) - padding
    x2 = max(subject_box.x + subject_box.w, object_box.x + object_box.w) + padding
    y2 = max(subject_box.y + subject_box.h, object_box.y + object_box.h) + padding

    combined_box = bound_box_define(
        x=x1,
        y=y1,
        w=x2 - x1,
        h=y2 - y1,
        label="combined"
    )

    return clamp_roi_to_frame(combined_box, frame_w, frame_h)


def get_display_bool(config, key, default=False):
    return config.get("display", {}).get(key, default)


def main():
    """ ### SEGMENT: INITIALIZATION ###
    Sets up config, UI, capture, object tracker, event manager, contact sheet builder,
    logging, vision, reward action, and storyboard tracking. """

    load_dotenv()

    app = get_or_create_qt_app()

    api_key = get_openai_api_key()

    if not api_key:
        api_key = run_first_run_setup()

        if not api_key:
            return

    vision = vision_api(api_key=api_key)
    logger = Logger()

    logger.purge_old_files(log_retention_days=90, storyboard_retention_days=14)

    running = True

    panel = control_panel()
    current_config = panel.get_current_config()

    manual_capture_requested = False
    detection_paused = True

    action = resulting_action(config=current_config, logger=logger)
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

    status = status_window(
        left=region["left"],
        top=max(0, region["top"] - 52),
        width=region["width"],
        height=42
    )

    video_config = current_config.get("video_input", {}).copy()

    def create_camera(active_region, active_video_config):
        return cam_controller(
            capture_region=active_region.copy(),
            fps=active_video_config.get("fps", 6),
            input_mode=active_video_config.get("mode", "screen_capture"),
            video_path=active_video_config.get("video_path", ""),
            loop_video=active_video_config.get("loop_video", True)
        )

    cam = create_camera(region, video_config)

    # Original constructor retained below by replacement guard.
    if False:
        cam = cam_controller(
        capture_region=region,
        fps=video_config.get("fps", 30),
        input_mode=video_config.get("mode", "screen_capture"),
        video_path=video_config.get("video_path", ""),
        loop_video=video_config.get("loop_video", True)
    )

    drawer = bound_box_drawer()

    motion_min_area = current_config["motion"]["min_area"]
    object_tracker = motion_object_tracker(min_area=motion_min_area)
    change_analyzer = frame_change_analyzer()
    deposit_event_manager = event_session_manager(distance_threshold=125, max_missing_frames=12)
    sheet_builder = contact_sheet_builder(
        cell_width=220,
        cell_height=220,
        padding=6,
        show_index=True,
        show_frame_tags=True
    )
    frame_ring_buffer = deque(maxlen=30)
    recent_event_paths = deque(maxlen=10)

    startup_time = time.time()
    warmup_seconds = 3.0
    warmup_complete_logged = False

    current_event_text = "Paused"
    previous_session_status = "None"
    api_event_count = 0
    latest_api_storyboard_path = None
    prev_object_motion = False

    prev_region = region.copy()
    prev_video_config = video_config.copy()
    prev_motion_min_area = motion_min_area
    prev_subject_roi = current_config["subject_roi"].copy()
    prev_object_roi = current_config["object_roi"].copy()
    prev_task_labels = current_config.get("task_labels", {}).copy()

    screen = app.primaryScreen().availableGeometry()

    def clamp_value(value, minimum, maximum):
        return max(minimum, min(maximum, value))

    def calculate_panel_geometry():
        active_screen = app.primaryScreen().availableGeometry()
        responsive_width = int(active_screen.width() * 0.34)
        panel_width = clamp_value(responsive_width, 500, 620)
        panel_height = active_screen.height()
        panel_x = active_screen.x() + active_screen.width() - panel_width
        panel_y = active_screen.y()
        return active_screen, panel_x, panel_y, panel_width, panel_height

    def calculate_status_height(active_screen):
        return int(clamp_value(int(active_screen.height() * 0.045), 40, 52))

    def calculate_status_top(active_screen, active_region, status_height):
        preferred_top = active_region["top"] - status_height - 10
        minimum_top = active_screen.top() + 10
        return max(minimum_top, preferred_top)

    screen, panel_x, panel_y, panel_width, panel_height = calculate_panel_geometry()

    panel.resize(panel_width, panel_height)
    panel.move(panel_x, panel_y)

    status_height = calculate_status_height(screen)
    status.set_status_geometry(
        left=region["left"],
        top=calculate_status_top(screen, region, status_height),
        width=region["width"],
        height=status_height
    )
    panel.show()
    panel.raise_()
    panel.activateWindow()
    
    status.keep_on_top()

    def bring_app_surfaces_to_front():
        overlay.show()
        overlay.raise_()
        status.keep_on_top()
        panel.raise_()
            
    status.permanent_surface_clicked.connect(bring_app_surfaces_to_front)
    panel.permanent_surface_clicked.connect(bring_app_surfaces_to_front)
    
    def reset_runtime_state(event_text="Warmup", storyboard_abort_note=None):
        nonlocal startup_time
        nonlocal warmup_complete_logged
        nonlocal current_event_text
        nonlocal previous_session_status
        nonlocal prev_object_motion

        if storyboard_abort_note and storyboard.active:
            storyboard.abort(notes=storyboard_abort_note)

        startup_time = time.time()
        warmup_complete_logged = False
        current_event_text = event_text

        object_tracker.reset()
        change_analyzer.reset()
        deposit_event_manager.reset()
        frame_ring_buffer.clear()
        recent_event_paths.clear()

        prev_object_motion = False
        
    def on_detection_paused_changed(paused):
        nonlocal detection_paused
        nonlocal current_event_text
        nonlocal previous_session_status
        nonlocal prev_object_motion

        detection_paused = paused

        if detection_paused:
            current_event_text = "Paused"
            object_tracker.reset()
            deposit_event_manager.reset()
            prev_object_motion = False

            if storyboard.active:
                storyboard.abort(notes="Storyboard aborted because detection was paused.")
        else:
            reset_runtime_state(
                event_text="Warmup",
                storyboard_abort_note="Storyboard aborted because detection was restarted."
            )

    panel.detection_paused_changed.connect(on_detection_paused_changed)

    def finalize_storyboard_if_active(
        rewarded=False,
        label="",
        frame=None,
        subject_frame=None,
        object_frame=None,
        notes=""
    ):
        if storyboard.active:
            return storyboard.finalize(
                rewarded=rewarded,
                label=label,
                frame=frame,
                subject_frame=subject_frame,
                object_frame=object_frame,
                notes=notes
            )

        return None
            
    # ================================
    # TRAJECTORY DUPLICATE SUPPRESSION
    # ================================

    def normalize_centroid_path(path, target_points=6):
        if not path:
            return []

        if len(path) <= target_points:
            return path

        step = (len(path) - 1) / (target_points - 1)
        indexes = [round(i * step) for i in range(target_points)]

        return [path[index] for index in indexes]

    def calculate_centroid_path_distance(path_a, path_b):
        normalized_a = normalize_centroid_path(path_a)
        normalized_b = normalize_centroid_path(path_b)

        if not normalized_a or not normalized_b:
            return float("inf")

        compare_count = min(len(normalized_a), len(normalized_b))

        if compare_count < 3:
            return float("inf")

        total_distance = 0.0

        for index in range(compare_count):
            ax, ay = normalized_a[index]
            bx, by = normalized_b[index]
            total_distance += ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

        return total_distance / compare_count

    def is_duplicate_centroid_path(path, recent_paths, threshold=35):
        if len(path) < 3:
            return False

        for recent_path in recent_paths:
            distance = calculate_centroid_path_distance(path, recent_path)

            if distance <= threshold:
                return True

        return False

    logger.log_info(
        "Bird Bros overlay loop started",
        region=region,
        capture_region=capture_region,
        task_labels=current_config.get("task_labels", {}),
        warmup_seconds=warmup_seconds
    )

    print("[INFO] Press Ctrl+C in terminal to stop.")

    try:
        """ ### SEGMENT: MAIN LOOP ###
        Captures frames, updates runtime config, tracks object detections,
        manages event sessions, analyzes ready events, and renders overlay. """

        while running:
            app.processEvents()

            """ ### SEGMENT: CONFIG UPDATE HANDLING ###
            Applies live control panel changes and resets tracker/manager when geometry
            or sensitivity changes. """

            region = current_config["capture_region"].copy()
            motion_min_area = current_config["motion"]["min_area"]
            task_labels = current_config.get("task_labels", {})

            show_overlay = get_display_bool(current_config, "show_overlay", True)
            show_grid = get_display_bool(current_config, "show_grid", True)
            show_coords = get_display_bool(current_config, "show_coords", True)
            show_capture_border = get_display_bool(current_config, "show_capture_border", True)
            show_labels = get_display_bool(current_config, "show_labels", True)

            current_subject_roi = current_config["subject_roi"].copy()
            current_object_roi = current_config["object_roi"].copy()
            current_task_labels = task_labels.copy()

            action.config = current_config
            action.reward_config = current_config.get("reward_action", {})
            action.no_reward_config = current_config.get("no_reward_action", {})

            if region != prev_region:
                cam.capture_region = region.copy()

                overlay.set_overlay_geometry(
                    left=region["left"],
                    top=region["top"],
                    width=region["width"],
                    height=region["height"]
                )

                screen, panel_x, panel_y, panel_width, panel_height = calculate_panel_geometry()
                status_height = calculate_status_height(screen)

                status.set_status_geometry(
                    left=region["left"],
                    top=calculate_status_top(screen, region, status_height),
                    width=region["width"],
                    height=status_height
                )

                reset_runtime_state(
                    event_text="Warmup",
                    storyboard_abort_note="Storyboard aborted because capture region changed."
                )

                logger.log_info("Capture region updated", region=region, capture_region=region)
                prev_region = region.copy()

            if motion_min_area != prev_motion_min_area:
                object_tracker = motion_object_tracker(min_area=motion_min_area)

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
                reset_runtime_state(
                    event_text="ROI Changed",
                    storyboard_abort_note="Storyboard aborted because ROI changed during event."
                )

                logger.log_info("ROI updated", subject_roi=current_subject_roi, object_roi=current_object_roi)
                prev_subject_roi = current_subject_roi.copy()
                prev_object_roi = current_object_roi.copy()

            if current_task_labels != prev_task_labels:
                logger.log_info("Task labels updated", task_labels=current_task_labels)
                prev_task_labels = current_task_labels.copy()

            current_video_config = current_config.get("video_input", {}).copy()

            if current_video_config != prev_video_config:
                try:
                    cam.stop()
                    cam = create_camera(region, current_video_config)
                    reset_runtime_state(
                        event_text="Video Input Changed",
                        storyboard_abort_note="Storyboard aborted because video input changed."
                    )
                    logger.log_info("Video input updated", video_input=current_video_config)
                    prev_video_config = current_video_config.copy()
                except Exception as e:
                    current_event_text = "Video Input Error"
                    logger.log_error("Video input update failed", error=str(e), video_input=current_video_config)
                    status.update_status(
                        current_event_text,
                        active_events=0,
                        api_events=api_event_count,
                        previous_status=previous_session_status,
                        storyboard_path=latest_api_storyboard_path
                    )
                    time.sleep(1 / 60)
                    continue

            frame = cam.get_frame()

            if frame is None:
                current_event_text = "No Frame"
                status.update_status(
                    current_event_text,
                    active_events=0,
                    api_events=api_event_count,
                    previous_status=previous_session_status,
                    storyboard_path=latest_api_storyboard_path
                )
                time.sleep(1 / 60)
                continue

            frame_h, frame_w = frame.shape[:2]

            region_w = frame_w
            region_h = frame_h

            behavior_mode = current_config.get(
                "behavior_mode",
                "simple"
            )

            subject_roi = current_config["subject_roi"]
            object_roi = current_config["object_roi"]

            """ ### SEGMENT: ROI PROCESSING ###
            Simple Mode:
                - Full capture region becomes AI context.
                - Object ROI becomes trigger zone.

            Advanced Mode:
                - Subject ROI + Object ROI build combined AI context.
            """

            if behavior_mode == "simple":

                object_box = bound_box_define(
                    x=int(object_roi["x_pct"] * region_w),
                    y=int(object_roi["y_pct"] * region_h),
                    w=int(object_roi["w_pct"] * region_w),
                    h=int(object_roi["h_pct"] * region_h),
                    label="trigger"
                )

                object_box = clamp_roi_to_frame(
                    object_box,
                    frame_w,
                    frame_h
                )

                subject_box = None
                combined_box = None

                object_crop = crop_from_box(
                    frame,
                    object_box
                )

                subject_crop = frame.copy()
                combined_crop = frame.copy()

            else:

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

                subject_box = clamp_roi_to_frame(
                    subject_box,
                    frame_w,
                    frame_h
                )

                object_box = clamp_roi_to_frame(
                    object_box,
                    frame_w,
                    frame_h
                )

                combined_box = build_combined_box(
                    subject_box,
                    object_box,
                    frame_w,
                    frame_h,
                    padding=0
                )

                subject_crop = crop_from_box(
                    frame,
                    subject_box
                )

                object_crop = crop_from_box(
                    frame,
                    object_box
                )

                combined_crop = crop_from_box(
                    frame,
                    combined_box
                )

            change_metrics = change_analyzer.analyze(
                combined_frame=combined_crop,
                object_frame=object_crop
            )

            """ ### SEGMENT: ALWAYS-ON RING BUFFER ###
            Stores recent pre-event frames so new event sessions can include context
            from before object motion was detected. """

            pre_event_buffer_snapshot = list(frame_ring_buffer)

            pre_event_record = {
                "timestamp": time.time(),
                "combined_frame": combined_crop.copy(),
                "subject_frame": subject_crop.copy(),
                "object_frame": object_crop.copy(),
                "source": "pre"
            }

            pre_event_record.update(change_metrics)
            frame_ring_buffer.append(pre_event_record)

            if manual_capture_requested:
                os.makedirs("debug_captures", exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")

                full_path = f"debug_captures/{timestamp}_full_frame.jpg"
                subject_path = f"debug_captures/{timestamp}_subject_roi.jpg"
                object_path = f"debug_captures/{timestamp}_object_roi.jpg"
                combined_path = f"debug_captures/{timestamp}_combined_roi.jpg"

                cv2.imwrite(full_path, frame)
                cv2.imwrite(subject_path, subject_crop)
                cv2.imwrite(object_path, object_crop)
                cv2.imwrite(combined_path, combined_crop)

                logger.log_info(
                    "Manual ROI capture saved",
                    full_frame=full_path,
                    subject_roi=subject_path,
                    object_roi=object_path,
                    combined_roi=combined_path
                )
                manual_capture_requested = False

            if detection_paused:
                current_event_text = "Paused"

                if show_overlay:
                    overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

                    if show_capture_border:
                        overlay_frame = drawer.draw_capture_border(overlay_frame, label="Capture Region")

                    if show_grid:
                        overlay_frame = drawer.draw_grid(overlay_frame, step=100)

                    boxes_to_draw = [box for box in [subject_box, object_box] if box is not None]

                    labels_to_draw = None
                    if show_labels:
                        labels_to_draw = ["trigger ROI | paused"] if behavior_mode == "simple" else ["subject context", "object ROI | paused"]

                    colors_to_draw = (
                        [(255, 0, 0, 255)]
                        if behavior_mode == "simple"
                        else [(0, 255, 0, 255), (255, 0, 0, 255)]
                    )

                    overlay_frame = drawer.draw_boxes(
                        overlay_frame,
                        boxes_to_draw,
                        labels=labels_to_draw,
                        colors=colors_to_draw,
                        show_coords=show_coords
                    )
                else:
                    overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

                status.update_status(
                    "Paused",
                    active_events=0,
                    api_events=api_event_count,
                    previous_status=previous_session_status,
                    storyboard_path=latest_api_storyboard_path
                )
                overlay.update_frame(overlay_frame)
                time.sleep(1 / 60)
                continue

            """ ### SEGMENT: OBJECT MOTION TRACKING ###
            Converts object ROI frame differences into centroid/bbox detections.
            Multiple detections can be assigned to separate event sessions. """

            detections = object_tracker.detect(object_crop)
            object_motion = len(detections) > 0

            elapsed_since_start = time.time() - startup_time
            in_warmup = elapsed_since_start < warmup_seconds

            if in_warmup:
                remaining = max(0.0, warmup_seconds - elapsed_since_start)
                banner_text = f"ROI Changed | Warmup {remaining:.1f}s" if current_event_text == "ROI Changed" else f"Warmup {remaining:.1f}s"

                prev_object_motion = object_motion

                if show_overlay:
                    overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

                    if show_capture_border:
                        overlay_frame = drawer.draw_capture_border(overlay_frame, label="Capture Region")

                    if show_grid:
                        overlay_frame = drawer.draw_grid(overlay_frame, step=100)

                    if show_labels:
                        labels_to_draw = ["trigger ROI | warmup"] if behavior_mode == "simple" else ["subject context", "object ROI | warmup"]
                    else:
                        labels_to_draw = None

                    overlay_frame = drawer.draw_boxes(
                        overlay_frame,
                        [box for box in [subject_box, object_box] if box is not None],
                        labels=labels_to_draw,
                        colors=([(255, 0, 0, 255)] if behavior_mode == "simple" else [(0, 255, 0, 255), (255, 0, 0, 255)]),
                        show_coords=show_coords
                    )
                else:
                    overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

                status.update_status(
                    banner_text,
                    active_events=0,
                    api_events=api_event_count,
                    previous_status=previous_session_status,
                    storyboard_path=latest_api_storyboard_path
                )
                overlay.update_frame(overlay_frame)
                time.sleep(1 / 60)
                continue

            if not warmup_complete_logged:
                logger.log_info("Warmup complete; live detection enabled")
                warmup_complete_logged = True
                current_event_text = "Idle"

            if object_motion != prev_object_motion:
                logger.log_motion("object", object_motion)

            prev_object_motion = object_motion

            """ ### SEGMENT: EVENT SESSION MANAGEMENT ###
            Updates manager with current detections. New sessions receive pre-event
            frames from the ring buffer. """

            deposit_event_manager.update(
                detections=detections,
                combined_frame=combined_crop,
                object_frame=object_crop,
                pre_buffer=pre_event_buffer_snapshot,
                change_metrics=change_metrics
            )

            active_event_count = deposit_event_manager.get_active_count()
            completed_event_count = deposit_event_manager.get_completed_count()

            if active_event_count > 0:
                current_event_text = f"Object Events Active: {active_event_count}"
            elif current_event_text.startswith("Object Events Active:"):
                current_event_text = "Monitoring"
                
            rejected_event = deposit_event_manager.get_next_rejected_event()

            if rejected_event:

                first_stable_record = rejected_event.get_first_stable_record()
                best_record = rejected_event.get_best_record()

                first_stable_frame = (
                    first_stable_record.get("combined_frame")
                    if first_stable_record
                    else None
                )

                best_event_frame = (
                    best_record.get("combined_frame")
                    if best_record
                    else None
                )

                rejected_frames = rejected_event.get_contact_sheet_frames()
                rejected_contact_sheet = sheet_builder.build(rejected_frames)

                storyboard.start_session(
                    rejected=True,
                    opening_frame=first_stable_frame,
                    notes=(
                        f"Rejected event. "
                        f"Reason: {rejected_event.get_rejection_reason()}."
                    ),
                    task_labels=current_config.get("task_labels", {})
                )

                storyboard.add_event(
                    "rejected_event_best_frame",
                    frame=best_event_frame,
                    notes=(
                        "Best available frame selected from rejected event."
                    )
                )

                storyboard.finalize(
                    rewarded=False,
                    label="Rejected Event",
                    frame=rejected_contact_sheet,
                    notes=(
                        f"This event was rejected before API analysis. "
                        f"Reason={rejected_event.get_rejection_reason()}. "
                        f"Frames={len(rejected_event.get_records())}. "
                        f"Duration={rejected_event.get_duration_seconds():.3f}s. "
                        f"PathLength={rejected_event.get_event_path_length():.1f}."
                    )
                )

            ready_event = deposit_event_manager.get_next_ready_event()

            """ ### SEGMENT: DEPOSIT EVENT ANALYSIS ###
            Converts one completed event session into a contact sheet, then sends that
            contact sheet to OpenAI using configurable task labels. """

            if ready_event:
                current_event_text = "Deposit Event Ready"

                try:
                    selected_frames = ready_event.get_contact_sheet_frames()

                    if not selected_frames:
                        logger.log_warning("Ready deposit event had no selected frames")
                    else:
                        centroid_path = ready_event.get_full_centroid_path()
                        if centroid_path:
                            recent_event_paths.append(centroid_path)

                        contact_sheet = sheet_builder.build(selected_frames)
                        best_record = ready_event.get_best_record()
                        first_stable_record = ready_event.get_first_stable_record()

                        best_event_frame = best_record.get("combined_frame") if best_record else None
                        first_stable_frame = first_stable_record.get("combined_frame") if first_stable_record else None

                        if storyboard.active:
                            storyboard.abort(notes="New deposit event started before previous storyboard finalized.")

                        storyboard.start_session(
                            opening_frame=first_stable_frame.copy() if first_stable_frame is not None else None,
                            notes="Deposit event session started; first stable post-motion frame captured.",
                            task_labels=task_labels
                        )

                        contact_sheet_event = storyboard.add_event(
                            "deposit_event_contact_sheet_ready",
                            frame=contact_sheet.copy(),
                            notes="Best mid-trajectory event frame selected; contact sheet built from selected pre-event and event frames.",
                            data={"task_labels": task_labels}
                        )

                        logger.log_api_call("deposit_event_contact_sheet_analysis", task_labels=task_labels)
                        current_event_text = "Sending Contact Sheet To OpenAI"

                        contact_sheet_bytes = encode_frame_to_jpeg_bytes(contact_sheet)

                        behavior_mode = current_config.get(
                            "behavior_mode",
                            "simple"
                        )

                        reward_description = current_config.get(
                            "reward_description",
                            ""
                        )

                        deposit_result = vision.analyze_event_contact_sheet(
                            image_bytes=contact_sheet_bytes,
                            subject_label=task_labels.get(
                                "subject_label",
                                "non-human animal"
                            ),
                            object_label=task_labels.get(
                                "object_label",
                                "man-made litter or trash"
                            ),
                            target_zone_label=task_labels.get(
                                "target_zone_label",
                                "trash receptacle"
                            ),
                            action_label=task_labels.get(
                                "action_label",
                                "depositing"
                            ),
                            behavior_mode=behavior_mode,
                            reward_description=reward_description
                        )

                        subject_present = deposit_result["subjectPresent"]
                        subject_label_result = deposit_result["subjectLabel"]
                        object_present = deposit_result["objectPresent"]
                        object_label_result = deposit_result["objectLabel"]
                        action_observed = deposit_result["actionObserved"]
                        target_zone_visible = deposit_result["targetZoneVisible"]
                        rewardable = deposit_result["rewardable"]
                        best_frame_index = deposit_result["bestFrameIndex"]
                        reason = deposit_result["reason"]
                        justification = deposit_result.get("justification", "")

                        logger.log_api_result(
                            "deposit_event_contact_sheet_analysis",
                            subjectPresent=subject_present,
                            subjectLabel=subject_label_result,
                            objectPresent=object_present,
                            objectLabel=object_label_result,
                            actionObserved=action_observed,
                            targetZoneVisible=target_zone_visible,
                            rewardable=rewardable,
                            bestFrameIndex=best_frame_index,
                            reason=reason,
                            justification=justification,
                            task_labels=task_labels
                        )

                        storyboard.add_event(
                            "deposit_event_analysis_complete",
                            notes=(
                                f"subjectPresent={subject_present}, "
                                f"subjectLabel={subject_label_result}, "
                                f"objectPresent={object_present}, "
                                f"objectLabel={object_label_result}, "
                                f"actionObserved={action_observed}, "
                                f"targetZoneVisible={target_zone_visible}, "
                                f"rewardable={rewardable}, "
                                f"bestFrameIndex={best_frame_index}, "
                                f"reason={reason}, "
                                f"justification={justification}, "
                                f"openai_input_image={contact_sheet_event.get('image')}"
                            ),
                            data={
                                **deposit_result,
                                "openai_input_storyboard_event": "deposit_event_contact_sheet_ready",
                                "openai_input_image": contact_sheet_event.get("image")
                            }
                        )

                        if rewardable:
                            reward_label = object_label_result or task_labels.get("object_label", "Rewardable object")
                            previous_session_status = "Rewarded"
                            current_event_text = "Treat Dispensed"

                            action.reward(label=reward_label)
                            logger.log_reward(True, label=reward_label, reason=reason, bestFrameIndex=best_frame_index)

                            latest_storyboard_path = finalize_storyboard_if_active(
                                rewarded=True,
                                label=reward_label,
                                frame=contact_sheet.copy(),
                                notes=f"Reward triggered: True. Reason: {reason}. Justification: {justification}. bestFrameIndex={best_frame_index}"
                            )

                            api_event_count += 1

                            if latest_storyboard_path:
                                latest_api_storyboard_path = latest_storyboard_path

                        else:
                            no_reward_label = object_label_result or "No reward"
                            previous_session_status = "Not Rewarded"
                            current_event_text = "No Reward"

                            action.no_reward(label=no_reward_label)
                            logger.log_reward(False, label=no_reward_label, reason=reason, bestFrameIndex=best_frame_index)

                            latest_storyboard_path = finalize_storyboard_if_active(
                                rewarded=False,
                                label=no_reward_label,
                                frame=contact_sheet.copy(),
                                notes=f"Reward triggered: False. Reason: {reason}. Justification: {justification}. bestFrameIndex={best_frame_index}"
                            )

                            api_event_count += 1

                            if latest_storyboard_path:
                                latest_api_storyboard_path = latest_storyboard_path

                except Exception as e:
                    current_event_text = "Deposit Event Error"
                    logger.log_error("Deposit event analysis failed", error=str(e))

                    if storyboard.active:
                        storyboard.abort(notes=f"Deposit event analysis failed: {e}")

            if current_event_text == "Idle" and object_motion:
                current_event_text = "Motion Detected"

            """ ### SEGMENT: OVERLAY RENDERING ###
            Draws subject/object ROI boxes and current system state. """

            if show_labels:
                labels_to_draw = ["trigger ROI"] if behavior_mode == "simple" else ["subject context", "object ROI"]
            else:
                labels_to_draw = None

            if show_overlay:
                overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

                if show_capture_border:
                    overlay_frame = drawer.draw_capture_border(overlay_frame, label="Capture Region")

                if show_grid:
                    overlay_frame = drawer.draw_grid(overlay_frame, step=100)

                overlay_frame = drawer.draw_boxes(
                    overlay_frame,
                    [box for box in [subject_box, object_box] if box is not None],
                    labels=labels_to_draw,
                    colors=[(0, 255, 0, 255), (255, 0, 0, 255)],
                    show_coords=show_coords
                )
            else:
                overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

            status.update_status(
                current_event_text,
                active_events=active_event_count,
                api_events=api_event_count,
                previous_status=previous_session_status,
                storyboard_path=latest_api_storyboard_path
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

        cam.stop()
        status.close()
        overlay.close()
        panel.close()


if __name__ == "__main__":
    main()


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
cam_controller → frame
    ↓
ROI processing
    ↓
motion_object_tracker
    ↓
event_session_manager
    ↓
event_session selected frames
    ↓
contact_sheet_builder
    ↓
vision_api.analyze_event_contact_sheet()
    ↓
resulting_action reward/no-reward
    ↓
storyboard + logs + overlay

DESIGN INTENT:
Object motion is tracked as independent events. Subject ROI is context.
Contact sheets provide temporal evidence to OpenAI instead of relying on one frame. """
