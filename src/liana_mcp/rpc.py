"""Bounded local JSON-RPC. No proxy, URL, method or credentials come from an LLM."""

import base64
import http.client
import json
import secrets
import socket
import stat
import time
from pathlib import Path

from .config import private_file
from .errors import SafetyError

MAX_RESPONSE = 1_048_576
CORE_METHODS = frozenset(
    {
        "getblockchaininfo",
        "getconnectioncount",
        "generatetoaddress",
        "getblockcount",
        "getblock",
        "getblockhash",
        "testmempoolaccept",
        "sendrawtransaction",
        "gettxout",
        "getrawtransaction",
        "decoderawtransaction",
        "stop",
    }
)
LIANA_METHODS = frozenset(
    {
        "getinfo",
        "getnewaddress",
        "listcoins",
        "updatelabels",
        "getlabels",
        "listtransactions",
        "stop",
    }
)


class RPCError(SafetyError):
    def __init__(self, code: int):
        self.code = code
        super().__init__("The local regtest backend rejected the request.")


def decode(data: bytes, identity: str):
    try:
        reply = json.loads(data)
        if not isinstance(reply, dict) or reply.get("id") != identity:
            raise ValueError
        if reply.get("error") is not None:
            code = reply["error"].get("code")
            if type(code) is not int:
                raise ValueError
            raise RPCError(code)
        if "result" not in reply:
            raise ValueError
        return reply["result"]
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise SafetyError("Invalid local RPC response.") from error


def core_call(run: Path, port: int, method: str, params: list | None = None):
    if method not in CORE_METHODS or type(port) is not int or not 1 <= port <= 65535:
        raise SafetyError("Unsupported local RPC request.")
    cookie = private_file(run / "bitcoin/regtest/.cookie").strip()
    if b"\n" in cookie or b"\r" in cookie or b":" not in cookie:
        raise SafetyError("Invalid local RPC credentials.")
    identity = secrets.token_hex(16)
    body = json.dumps({"jsonrpc": "2.0", "id": identity, "method": method, "params": params or []})
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(
            "POST",
            "/",
            body,
            {
                "Content-Type": "application/json",
                "Authorization": "Basic " + base64.b64encode(cookie).decode(),
            },
        )
        response = connection.getresponse()
        data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE or response.status not in (200, 500):
            raise SafetyError("Unexpected local RPC response size or HTTP status.")
        return decode(data, identity)
    except (OSError, http.client.HTTPException) as error:
        raise SafetyError("The local regtest RPC is unavailable.") from error
    finally:
        connection.close()


def liana_call(run: Path, method: str, params: dict | None = None):
    if method not in LIANA_METHODS:
        raise SafetyError("Unsupported local wallet RPC request.")
    path = run / "liana/regtest/lianad_rpc"
    if not stat.S_ISSOCK(path.lstat().st_mode):
        raise SafetyError("The local wallet socket is unavailable.")
    identity = secrets.token_hex(16)
    request = {"jsonrpc": "2.0", "id": identity, "method": method, "params": params or {}}
    encoded = json.dumps(request).encode() + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(str(path))
            client.sendall(encoded)
            data = b""
            deadline = time.monotonic() + 5
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SafetyError("The local wallet response timed out.")
                client.settimeout(remaining)
                part = client.recv(65536)
                if not part:
                    raise SafetyError("The local wallet closed an incomplete response.")
                data += part
                if len(data) > MAX_RESPONSE:
                    raise SafetyError("The local wallet response is too large.")
                # Liana v16 writes a complete JSON object without a newline terminator.
                # A recv() boundary is not a message boundary; accept only a complete object.
                if data.rstrip().endswith(b"}"):
                    try:
                        json.loads(data)
                    except (ValueError, UnicodeError):
                        continue
                    return decode(data, identity)
    except OSError as error:
        raise SafetyError("The local wallet RPC is unavailable.") from error
