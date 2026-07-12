from __future__ import annotations

import argparse

from .actions import ActionRunner
from .capture import create_frame_source
from .config import load_config
from .diagnostics import DiagnosticsStore
from .runtime import BehaviorRuntime
from .vision import DryRunVisionAnalyzer, OpenAIVisionAnalyzer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Competitor App")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Do not call OpenAI; always return no reward.")
    parser.add_argument("--max-events", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    source = create_frame_source(config.input)
    analyzer = DryRunVisionAnalyzer(False) if args.dry_run else OpenAIVisionAnalyzer(model=config.openai_model)
    runtime = BehaviorRuntime(
        config=config,
        frame_source=source,
        analyzer=analyzer,
        action_runner=ActionRunner(),
        diagnostics=DiagnosticsStore(config.privacy),
    )
    count = runtime.run(max_events=args.max_events)
    print(f"Processed {count} event(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
