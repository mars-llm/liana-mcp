"""Native children must not inherit the MCP transport's input or process session."""

import json
import sys

from liana_mcp.runtime import Runtime


def test_backend_child_has_no_mcp_stdin_and_owns_session(settings, tmp_path):
    runtime = Runtime(settings)
    runtime.spawn(
        [
            sys.executable,
            "-c",
            "import json, os, sys; "
            "print(json.dumps({'input': sys.stdin.read(1), "
            "'own_session': os.getsid(0) == os.getpid()}))",
        ],
        tmp_path,
        "child.log",
    )
    assert runtime.children[0].wait(timeout=5) == 0
    assert json.loads((tmp_path / "child.log").read_text()) == {
        "input": "",
        "own_session": True,
    }
