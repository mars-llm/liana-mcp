"""Local stdio entry point; mutation consent belongs to the operator, never the model."""

import argparse
import json
import os
import sys
from pathlib import Path

from .approval import APPROVAL_SECONDS, approve
from .config import Settings
from .errors import SafetyError
from .runtime import Runtime
from .server import create_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental Liana MCP, isolated regtest only")
    parser.add_argument("--config", type=Path, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--stop", action="store_true", help="Stop this owned regtest")
    action.add_argument(
        "--approve-step",
        choices=["setup", "1", "2", "3", "4"],
        help="Authorize one mutation in the current isolated regtest",
    )
    args = parser.parse_args()
    os.umask(0o077)
    os.environ["OTEL_SDK_DISABLED"] = "true"
    try:
        runtime = Runtime(Settings.load(args.config))
        if args.stop:
            with runtime.operation(mutate=True):
                print(json.dumps(runtime.stop()))
        elif args.approve_step:
            with runtime.operation(mutate=True):
                approve(runtime, args.approve_step)
            print(json.dumps({"approved_step": args.approve_step, "expires_in": APPROVAL_SECONDS}))
        else:
            create_server(runtime).run(transport="stdio")
        return 0
    except (SafetyError, OSError):
        # Startup failures go to stderr, never corrupting the MCP stdout stream.
        print(
            "Liana MCP refused the operation. Check the private local configuration and regtest status.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
