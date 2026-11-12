"""One-use operator permits for workshop steps and exact wallet requests."""

import hashlib
import json
import time

from .config import private_file
from .errors import SafetyError
from .runtime import Runtime, write_json

APPROVAL_SECONDS = 300


def scope(runtime: Runtime, action: str, request: dict | None = None) -> dict:
    record = runtime.record() if runtime.state_file.exists() else None
    if action in ("setup", "wallet_setup"):
        if record is not None and record.stage != "stopped":
            raise SafetyError("Setup approval requires a fresh or stopped regtest.")
        completed = 0
    elif action == "wallet_action":
        if request is None:
            raise SafetyError("A specific wallet action is required.")
        record, run, _ = runtime.guard(request["run_id"])
        if record.policy is None:
            raise SafetyError("This action requires a configurable regtest wallet.")
        state = json.loads(private_file(run / "private/wallet-state.json"))
        if state.get("pending") or state["revision"] != request["expected_revision"]:
            raise SafetyError("Read the current wallet checkpoint before approving an action.")
        completed = state["revision"]
    else:
        status = runtime.public_status()
        completed = status.get("completed_step", 0)
        if (
            status["status"] != "running"
            or (record and record.policy is not None)
            or completed >= 4
            or action != str(completed + 1)
        ):
            raise SafetyError("Approve only the next step of the current running regtest.")
    return {
        "action": action,
        "run_id": record.run if record else None,
        "completed_step": completed,
        "state_digest": (
            hashlib.sha256(private_file(runtime.state_file)).hexdigest() if record else None
        ),
        **({"request": request} if request is not None else {}),
    }


def approve(runtime: Runtime, action: str, request: dict | None = None) -> None:
    """Called by the local CLI while holding the operation lock."""
    if not runtime.settings.require_operator_approval:
        raise SafetyError("Enable require_operator_approval in the private configuration first.")
    permit = {**scope(runtime, action, request), "expires_at": time.time() + APPROVAL_SECONDS}
    write_json(runtime.root / "operator-approval.json", permit)


def consume(runtime: Runtime, action: str, request: dict | None = None) -> None:
    """Consume a matching permit before mutation, under the same operation lock."""
    if not runtime.settings.require_operator_approval:
        return
    path = runtime.root / "operator-approval.json"
    try:
        permit = json.loads(private_file(path))
        if not isinstance(permit, dict):
            raise ValueError("Invalid permit")
        expires_at = permit.pop("expires_at", None)
        remaining = expires_at - time.time() if type(expires_at) in (int, float) else 0
        if not 0 < remaining <= APPROVAL_SECONDS or permit != scope(runtime, action, request):
            raise ValueError("Permit is stale or belongs to a different step")
    except (SafetyError, ValueError, OverflowError) as error:
        raise SafetyError(
            "This mutation requires a fresh one-use local operator approval."
        ) from error
    path.unlink()
