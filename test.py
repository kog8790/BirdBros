from cam_controller import cam_controller
from rois import subject_roi, object_roi
from bound_box_drawer import bound_box_drawer
from motion_detector import motion_detector
import cv2

region = {
    "top": 100,
    "left": 100,
    "width": 900,
    "height": 700
}

cam = cam_controller(region=region, fps=6)
drawer = bound_box_drawer()

subject_motion_detector = motion_detector(min_area=500)
object_motion_detector = motion_detector(min_area=500)

while True:
    frame = cam.get_frame()
    h, w = frame.shape[:2]

    subject_box = subject_roi(w, h)
    object_box = object_roi(w, h)

    subject_crop = frame[
        subject_box.y:subject_box.y + subject_box.h,
        subject_box.x:subject_box.x + subject_box.w
    ]

    object_crop = frame[
        object_box.y:object_box.y + object_box.h,
        object_box.x:object_box.x + object_box.w
    ]

    subject_motion = subject_motion_detector.detect(subject_crop)
    object_motion = object_motion_detector.detect(object_crop)

    drawer.draw_grid(frame, step=100)
    drawer.draw_boxes(
        frame,
        [subject_box, object_box],
        labels=[
            f"subject motion: {subject_motion}",
            f"object motion: {object_motion}"
        ],
        colors=[(0, 255, 0), (255, 0, 0)]
    )

    print("Subject:", subject_motion, "Object:", object_motion)

    cv2.imshow("Bird Bros Motion Test", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break

cv2.destroyAllWindows()
