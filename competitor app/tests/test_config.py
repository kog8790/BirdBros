import pytest

from competitor_app.config import AppConfig, ConfigError


def minimal_config():
    return {
        "input": {
            "kind": "screen_capture",
            "screen_region": {"left": 0, "top": 0, "width": 640, "height": 480},
        },
        "subject_roi": {"x_pct": 0.1, "y_pct": 0.1, "w_pct": 0.2, "h_pct": 0.2},
        "object_roi": {"x_pct": 0.4, "y_pct": 0.4, "w_pct": 0.2, "h_pct": 0.2},
    }


def test_valid_minimal_config_loads():
    config = AppConfig.from_dict(minimal_config())

    assert config.input.screen_region.width == 640
    assert config.reward_action.kind == "status"
    assert config.privacy.save_diagnostics is False


def test_roi_must_stay_inside_frame():
    data = minimal_config()
    data["object_roi"] = {"x_pct": 0.9, "y_pct": 0.4, "w_pct": 0.2, "h_pct": 0.2}

    with pytest.raises(ConfigError):
        AppConfig.from_dict(data)


def test_shell_command_requires_developer_mode():
    data = minimal_config()
    data["reward_action"] = {"kind": "shell_command", "command": ["echo", "ok"]}

    with pytest.raises(ConfigError):
        AppConfig.from_dict(data)


def test_shell_command_rejects_shell_string_even_in_developer_mode():
    data = minimal_config()
    data["developer_mode"] = True
    data["reward_action"] = {"kind": "shell_command", "command": "echo ok"}

    with pytest.raises(ConfigError):
        AppConfig.from_dict(data)
