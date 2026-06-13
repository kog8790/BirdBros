""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages loading, saving, and default structure of configuration data.

RESPONSIBILITIES:
- Define default config schema
- Load config from disk (JSON)
- Save config to disk
- Merge missing values from defaults

USED BY:
- control_panel.py
- main.py

DESIGN INTENT:
Centralize configuration so runtime, UI, reward behavior, and prompt labels share one source of truth. """

import json
import os


""" ### SEGMENT: DEFAULT CONFIG DEFINITION ###
Defines the base system config.

INCLUDES:
- capture region
- percent-based ROIs
- motion settings
- display toggles
- prompt/task labels
- reward/no-reward action settings """
DEFAULT_CONFIG = {
    "video_input": {
        "mode": "screen_capture",
        "video_path": "",
        "loop_video": True,
        "fps": 30
    },
    "capture_region": {
        "left": 100,
        "top": 100,
        "width": 900,
        "height": 700
    },
    "subject_roi": {
        "x_pct": 0.46,
        "y_pct": 0.45,
        "w_pct": 0.18,
        "h_pct": 0.15
    },
    "object_roi": {
        "x_pct": 0.46,
        "y_pct": 0.55,
        "w_pct": 0.18,
        "h_pct": 0.10
    },
    "motion": {
        "min_area": 5000
    },
    "display": {
        "show_overlay": True,
        "show_grid": False,
        "show_coords": False,
        "show_capture_border": True,
        "show_labels": True
    },
    "task_labels": {
        "subject_label": "non-human animal",
        "object_label": "man-made litter or trash",
        "target_zone_label": "trash receptacle",
        "action_label": "depositing"
    },
    "behavior_mode": "simple",
    "reward_description": "A bird drops litter into a receptacle.",
    "reward_action": {
        "mode": "debug_popup",
        "x": 735,
        "y": 586,
        "clicks": 3,
        "interval": 0.1,
        "move_duration": 0.0,
        "keys": ["command", "space"],
        "command": "",
        "url": "",
        "method": "POST",
        "timeout": 5,
        "headers": {},
        "payload": {},
        "bearer_token": ""
    },
    "no_reward_action": {
        "mode": "debug_popup"
    }
}


def deep_copy_config(config):
    return json.loads(json.dumps(config))


def _deep_merge(default, loaded):
    merged = deep_copy_config(default)

    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def merge_with_defaults(loaded):
    return _deep_merge(DEFAULT_CONFIG, loaded)


""" ### SEGMENT: LOAD CONFIG ###
load_config():
Loads config from disk. Falls back to defaults if missing or invalid. """
def load_config(config_path="birdbros_config.json"):
    if not os.path.exists(config_path):
        return deep_copy_config(DEFAULT_CONFIG)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return merge_with_defaults(loaded)
    except Exception:
        return deep_copy_config(DEFAULT_CONFIG)


""" ### SEGMENT: SAVE CONFIG ###
save_config():
Writes current config state to disk as JSON. """
def save_config(config, config_path="birdbros_config.json"):
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
config_manager.py
    ↓
control_panel.py edits values
    ↓
main.py consumes runtime config
    ↓
vision_api receives configurable task labels

DESIGN INTENT:
Open-source users can adapt subject/object/action/target labels without editing prompt code. """

