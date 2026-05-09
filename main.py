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
from contact_sheet_builder import contact_sheet_builder
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

    cam = cam_controller(region=region, fps=30)
    drawer = bound_box_drawer()

    motion_min_area = current_config["motion"]["min_area"]
    object_tracker = motion_object_tracker(min_area=motion_min_area)
    deposit_event_manager = event_session_manager(distance_threshold=125, max_missing_frames=12)
    sheet_builder = contact_sheet_builder(cell_width=220, cell_height=220, padding=6, show_index=True)
    frame_ring_buffer = deque(maxlen=30)
    recent_event_paths = deque(maxlen=10)

    startup_time = time.time()
    warmup_seconds = 3.0
    warmup_complete_logged = False

    current_event_text = "Warmup"
    prev_object_motion = False

    prev_region = region.copy()
    prev_motion_min_area = motion_min_area
    prev_subject_roi = current_config["subject_roi"].copy()
    prev_object_roi = current_config["object_roi"].copy()
    prev_task_labels = current_config.get("task_labels", {}).copy()

    panel.show()
    panel.raise_()
    panel.activateWindow()

    def reset_runtime_state(event_text="Warmup", storyboard_abort_note=None):
        nonlocal startup_time
        nonlocal warmup_complete_logged
        nonlocal current_event_text
        nonlocal prev_object_motion

        if storyboard_abort_note and storyboard.active:
            storyboard.abort(notes=storyboard_abort_note)

        startup_time = time.time()
        warmup_complete_logged = False
        current_event_text = event_text

        object_tracker.reset()
        deposit_event_manager.reset()
        frame_ring_buffer.clear()
        recent_event_paths.clear()

        prev_object_motion = False

    def finalize_storyboard_if_active(
        rewarded=False,
        label="",
        frame=None,
        subject_frame=None,
        object_frame=None,
        notes=""
    ):
        if storyboard.active:
            storyboard.finalize(
                rewarded=rewarded,
                label=label,
                frame=frame,
                subject_frame=subject_frame,
                object_frame=object_frame,
                notes=notes
            )
            
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
                cam.region = region

                overlay.set_overlay_geometry(
                    left=region["left"],
                    top=region["top"],
                    width=region["width"],
                    height=region["height"]
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

            frame = cam.get_frame()
            frame_h, frame_w = frame.shape[:2]

            region_w = region["width"]
            region_h = region["height"]

            subject_roi = current_config["subject_roi"]
            object_roi = current_config["object_roi"]

            """ ### SEGMENT: ROI PROCESSING ###
            Converts subject/object ROI percentages into pixel boxes, then builds
            one combined crop used for contact sheet event analysis. """

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
            combined_box = build_combined_box(subject_box, object_box, frame_w, frame_h, padding=0)

            subject_crop = crop_from_box(frame, subject_box)
            object_crop = crop_from_box(frame, object_box)
            combined_crop = crop_from_box(frame, combined_box)

            """ ### SEGMENT: ALWAYS-ON RING BUFFER ###
            Stores recent pre-event frames so new event sessions can include context
            from before object motion was detected. """

            frame_ring_buffer.append({
                "timestamp": time.time(),
                "combined_frame": combined_crop.copy(),
                "subject_frame": subject_crop.copy(),
                "object_frame": object_crop.copy(),
                "source": "pre"
            })

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
                    overlay_frame = drawer.draw_event_banner(overlay_frame, banner_text)

                    if show_capture_border:
                        overlay_frame = drawer.draw_capture_border(overlay_frame, label="Capture Region")

                    if show_grid:
                        overlay_frame = drawer.draw_grid(overlay_frame, step=100)

                    labels_to_draw = ["subject context", "object ROI | warmup"] if show_labels else None

                    overlay_frame = drawer.draw_boxes(
                        overlay_frame,
                        [subject_box, object_box],
                        labels=labels_to_draw,
                        colors=[(0, 255, 0, 255), (255, 0, 0, 255)],
                        show_coords=show_coords
                    )
                else:
                    overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

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
                pre_buffer=list(frame_ring_buffer)
            )

            active_event_count = deposit_event_manager.get_active_count()
            completed_event_count = deposit_event_manager.get_completed_count()

            if active_event_count > 0:
                current_event_text = f"Object Events Active: {active_event_count}"

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

                        if is_duplicate_centroid_path(centroid_path, recent_event_paths):
                            logger.log_info(
                                "Duplicate centroid trajectory suppressed before API call",
                                centroid_path_length=len(centroid_path)
                            )
                            continue

                        recent_event_paths.append(centroid_path)

                        contact_sheet = sheet_builder.build(selected_frames)
                        best_record = ready_event.get_best_record()
                        best_object_crop = best_record.get("object_frame") if best_record else None
                        best_subject_crop = best_record.get("subject_frame") if best_record else None

                        if storyboard.active:
                            storyboard.abort(notes="New deposit event started before previous storyboard finalized.")

                        storyboard.start_session(                            notes="Deposit event contact sheet created after object motion cleared.",
                            task_labels=task_labels
                        )

                        storyboard.add_event(
                            "deposit_event_contact_sheet_ready",
                            notes="Contact sheet built from selected pre-event and event frames.",
                            data={"task_labels": task_labels}
                        )

                        logger.log_api_call("deposit_event_contact_sheet_analysis", task_labels=task_labels)
                        current_event_text = "Sending Contact Sheet To OpenAI"

                        contact_sheet_bytes = encode_frame_to_jpeg_bytes(contact_sheet)
                        deposit_result = vision.analyze_event_contact_sheet(
                            image_bytes=contact_sheet_bytes,
                            subject_label=task_labels.get("subject_label", "non-human animal"),
                            object_label=task_labels.get("object_label", "man-made litter or trash"),
                            target_zone_label=task_labels.get("target_zone_label", "trash receptacle"),
                            action_label=task_labels.get("action_label", "depositing")
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
                                f"reason={reason}"
                            ),
                            data=deposit_result
                        )

                        if rewardable:
                            reward_label = object_label_result or task_labels.get("object_label", "Rewardable object")
                            current_event_text = "Treat Dispensed"

                            action.reward(label=reward_label)
                            logger.log_reward(True, label=reward_label, reason=reason, bestFrameIndex=best_frame_index)

                            finalize_storyboard_if_active(
                                rewarded=True,
                                label=reward_label,
                                frame=contact_sheet.copy(),
                                notes=f"Reward triggered: True. Reason: {reason}. bestFrameIndex={best_frame_index}"
                            )

                        else:
                            no_reward_label = object_label_result or "No reward"
                            current_event_text = "No Reward"

                            action.no_reward(label=no_reward_label)
                            logger.log_reward(False, label=no_reward_label, reason=reason, bestFrameIndex=best_frame_index)

                            finalize_storyboard_if_active(
                                rewarded=False,
                                label=no_reward_label,
                                frame=contact_sheet.copy(),
                                notes=f"Reward triggered: False. Reason: {reason}. bestFrameIndex={best_frame_index}"
                            )

                except Exception as e:
                    current_event_text = "Deposit Event Error"
                    logger.log_error("Deposit event analysis failed", error=str(e))

                    if storyboard.active:
                        storyboard.abort(notes=f"Deposit event analysis failed: {e}")

            if current_event_text == "Idle" and object_motion:
                current_event_text = "Motion Detected"

            """ ### SEGMENT: OVERLAY RENDERING ###
            Draws subject/object ROI boxes and current system state. """

            labels_to_draw = ["subject context", "object ROI"] if show_labels else None

            if show_overlay:
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
            else:
                overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

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
