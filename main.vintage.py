from collections import deque

from contact_sheet_builder import contact_sheet_builder

# --- EXISTING IMPORTS (unchanged) ---

from motion_object_tracker import motion_object_tracker

from event_session_manager import event_session_manager

# ================================

# INITIALIZATION (UNCHANGED CONTEXT)

# ================================

object_tracker = motion_object_tracker(min_area=motion_min_area)

event_manager = event_session_manager()

# --- NEW ---

frame_ring_buffer = deque(maxlen=30)

sheet_builder = contact_sheet_builder()

# -----------

# ================================

# MAIN LOOP

# ================================

while running:

    # --- FRAME CAPTURE (UNCHANGED) ---

    frame = cam.get_frame()

    frame_h, frame_w = frame.shape[:2]

    subject_crop = crop_from_box(frame, subject_box)

    object_crop = crop_from_box(frame, object_box)

    combined_crop = crop_from_box(frame, combined_box)

    # ================================

    # 🔥 ALWAYS-ON RING BUFFER

    # ================================

    frame_ring_buffer.append({

        "combined_frame": combined_crop.copy(),

        "object_frame": object_crop.copy(),

        "subject_frame": subject_crop.copy(),

        "timestamp": time.time()

    })

    # ================================

    # OBJECT DETECTIONS (NEW)

    # ================================

    detections = object_tracker.detect(object_crop)

    object_motion = len(detections) > 0

    # ================================

    # EVENT SESSION MANAGER (NEW CORE)

    # ================================

    event_manager.update(

        detections=detections,

        combined_frame=combined_crop,

        object_frame=object_crop,

        pre_buffer=list(frame_ring_buffer)

    )

    active_event_count = len(event_manager.active_sessions)

    completed_event_count = len(event_manager.completed_sessions)

    # ================================

    # PROCESS READY EVENT

    # ================================

    ready_event = None

    if not event_in_progress:

        ready_event = event_manager.get_next_ready_event()

    if ready_event is not None and not event_in_progress:

        event_in_progress = True

        current_event_text = "Deposit Event Ready"

        try:

            # ================================

            # 🔥 CONTACT SHEET FLOW

            # ================================

            selected_frames = ready_event.get_contact_sheet_frames()

            if not selected_frames:

                logger.log_warning("No frames selected for contact sheet")

                event_in_progress = False

                continue

            contact_sheet = sheet_builder.build(selected_frames)

            # ================================

            # STORYBOARD START

            # ================================

            if storyboard.active:

                storyboard.abort(notes="New event before finalize")

            storyboard.start_session(

                opening_frame=contact_sheet.copy(),

                notes="Contact sheet generated from event session"

            )

            # ================================

            # API CALL

            # ================================

            logger.log_api_call("deposit_event_analysis")

            current_event_text = "Sending Contact Sheet To OpenAI"

            deposit_result = analyze_deposit_event(vision, contact_sheet)

            animal_present = deposit_result["animalPresent"]

            animal_label = deposit_result["animalLabel"]

            object_present = deposit_result["objectPresent"]

            object_label = deposit_result["objectLabel"]

            object_is_litter = deposit_result["objectIsManMadeLitter"]

            rewardable = deposit_result["rewardable"]

            reason = deposit_result["reason"]

            logger.log_info(

                "Deposit event analysis complete",

                animalPresent=animal_present,

                animalLabel=animal_label,

                objectPresent=object_present,

                objectLabel=object_label,

                objectIsManMadeLitter=object_is_litter,

                rewardable=rewardable,

                reason=reason

            )

            # ================================

            # STORYBOARD UPDATE

            # ================================

            storyboard.add_event(

                "deposit_event_analysis_complete",

                frame=contact_sheet.copy(),

                notes=(

                    f"animalPresent={animal_present}, "

                    f"animalLabel={animal_label}, "

                    f"objectPresent={object_present}, "

                    f"objectLabel={object_label}, "

                    f"objectIsManMadeLitter={object_is_litter}, "

                    f"rewardable={rewardable}, "

                    f"reason={reason}"

                ),

                data=deposit_result

            )

            # ================================

            # REWARD LOGIC

            # ================================

            if rewardable:

                reward_label = object_label or "Rewardable litter"

                current_event_text = "Treat Dispensed"

                action.reward(label=reward_label)

                logger.log_reward(True, label=reward_label, reason=reason)

                finalize_storyboard_if_active(

                    rewarded=True,

                    label=reward_label,

                    frame=contact_sheet.copy(),

                    notes=f"Reward triggered: True. Reason: {reason}"

                )

            else:

                no_reward_label = object_label or "No reward"

                current_event_text = "No Reward"

                action.no_reward(label=no_reward_label)

                logger.log_reward(False, label=no_reward_label, reason=reason)

                finalize_storyboard_if_active(

                    rewarded=False,

                    label=no_reward_label,

                    frame=contact_sheet.copy(),

                    notes=f"Reward triggered: False. Reason: {reason}"

                )

        except Exception as e:

            current_event_text = "Deposit Event Error"

            logger.log_error("Deposit event analysis failed", error=str(e))

            if storyboard.active:

                storyboard.abort(notes=f"Deposit event analysis failed: {e}")

        finally:

            event_in_progress = False

    # ================================

    # OVERLAY (UNCHANGED EXCEPT CLEAN LABELS)

    # ================================

    if show_labels:

        labels_to_draw = [

            "subject context",

            "object ROI"

        ]

    else:

        labels_to_draw = None

    if show_overlay:

        overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

        overlay_frame = drawer.draw_event_banner(overlay_frame, current_event_text)

        if show_capture_border:

            overlay_frame = drawer.draw_capture_border(overlay_frame)

        if show_grid:

            overlay_frame = drawer.draw_grid(overlay_frame)

        overlay_frame = drawer.draw_boxes(

            overlay_frame,

            [subject_box, object_box],

            labels=labels_to_draw,

            show_coords=show_coords

        )

    else:

        overlay_frame = drawer.make_overlay_canvas(frame_w, frame_h)

    overlay.update_frame(overlay_frame)
