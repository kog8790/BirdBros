# Competitor App

Competitor App is a clean-room behavior-observation and reward-triggering app. It covers the same functional surface as BirdBros:

- watch a screen region or video file
- track motion in a configured trigger region
- collect pre-event and event frames
- build contact sheets
- ask OpenAI Vision whether the configured behavior happened
- trigger a configured reward action
- optionally save diagnostics for review

The codebase is intentionally structured around the weaknesses identified in the original review:

- config is validated before runtime use
- dangerous shell actions are disabled unless explicitly allowed
- webhook secrets are read from environment variables, not saved config
- screen captures and storyboards are opt-in and retained for a limited time
- AI parsing does not fabricate evidence fields
- runtime orchestration is split into testable modules
- tests cover config validation, event detection, AI parsing, action safety, and diagnostics behavior

## Run

```bash
cd "competitor app"
python3 -m competitor_app.cli --config examples/config.example.json
```

The default example runs in dry mode unless you provide an OpenAI API key and choose a real input source.

## Test

```bash
cd "competitor app"
python3 -m pytest
```

## Config

Start from `examples/config.example.json`. User-specific configs should not be committed. The `.gitignore` excludes `.env`, logs, diagnostics, captures, and local config files.

Webhook bearer tokens are referenced by environment variable name:

```json
{
  "reward_action": {
    "kind": "webhook",
    "bearer_token_env": "REWARD_WEBHOOK_TOKEN"
  }
}
```

Shell commands are blocked unless both the config sets `developer_mode: true` and the process environment contains:

```bash
COMPETITOR_ALLOW_SHELL_ACTIONS=1
```

This keeps the signed/user-facing path away from arbitrary command execution.
