"""One operator-configured regtest namespace; never attach to existing wallets."""

import contextlib
import fcntl
import hashlib
import json
import os
import secrets
import socket
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from embit import bip32, script
from embit.descriptor.checksum import add_checksum
from embit.networks import NETWORKS
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings, private_directory, private_file
from .errors import SafetyError
from .policy import WORKSHOP_POLICY, WalletPolicy
from .release_docs import LIANA_RELEASE
from .rpc import RPCError, core_call, liana_call


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run: str = Field(pattern=r"^[0-9a-f]{32}$")
    rpc_port: int = Field(ge=1, le=65535)
    descriptor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    core_sha256: str
    lianad_sha256: str
    stage: Literal["starting", "ready", "failed", "stopped"] = "starting"
    gui_language: str
    seconds: float = 0.0
    policy: WalletPolicy | None = None


def write_json(path: Path, value: object) -> None:
    if path.is_symlink():
        raise SafetyError("Refusing a symlink state file.")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".state-", delete=False) as stream:
        name = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            name.unlink(missing_ok=True)


class Runtime:
    RECOVERY_LABEL = "04 Carol’s recovery"

    def __init__(self, settings: Settings):
        if os.geteuid() == 0:
            raise SafetyError("Root execution is not permitted.")
        self.settings = settings
        self.root = Path(settings.state_directory)
        private_directory(self.root, create=True)
        self.runs_dir = private_directory(self.root / "runs", create=True)
        self.state_file = self.root / "current.json"
        self.children: list[subprocess.Popen] = []

    @contextlib.contextmanager
    def operation(self, *, mutate: bool = False):
        private_directory(self.root)
        private_directory(self.runs_dir)
        if mutate and not self.settings.enable_regtest_mutations:
            raise SafetyError("Regtest mutations are disabled by the operator.")
        fd = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise SafetyError("Invalid private operation lock.")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise SafetyError(
                    "Another operation is active; read status before retrying."
                ) from error
            yield
        finally:
            os.close(fd)

    def record(self) -> Run:
        try:
            return Run.model_validate_json(private_file(self.state_file))
        except ValueError as error:
            raise SafetyError("Invalid private run record.") from error

    def save(self, record: Run) -> None:
        write_json(self.state_file, record.model_dump())

    def run_path(self, record: Run) -> Path:
        return private_directory(self.runs_dir / record.run)

    @staticmethod
    def core_rpc(run: Path, port: int, method: str, params: list | None = None):
        return core_call(run, port, method, params)

    @staticmethod
    def liana_rpc(run: Path, method: str, params: dict | None = None):
        return liana_call(run, method, params)

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        write_json(path, value)

    def guard(
        self, run_id: str | None = None, *, check_height: bool = True
    ) -> tuple[Run, Path, dict]:
        record = self.record()
        if record.stage != "ready" or (run_id is not None and run_id != record.run):
            raise SafetyError("No matching ready regtest run. Read status before continuing.")
        if (
            record.core_sha256 != self.settings.core.sha256
            or record.lianad_sha256 != self.settings.lianad.sha256
        ):
            raise SafetyError("Runtime pins changed. Do not reuse this run.")
        self.settings.core.checked()
        self.settings.lianad.checked()
        run = self.run_path(record)
        private_directory(run / "private")
        for directory in (
            run / "liana",
            run / "liana/regtest",
            run / "bitcoin",
            run / "bitcoin/regtest",
        ):
            private_directory(directory)
        info = self.core_rpc(run, record.rpc_port, "getblockchaininfo")
        if (
            info.get("chain") != "regtest"
            or self.core_rpc(run, record.rpc_port, "getconnectioncount") != 0
        ):
            raise SafetyError("An isolated regtest backend with zero peers is required.")
        wallet = self.liana_rpc(run, "getinfo")
        if wallet.get("network") != "regtest":
            raise SafetyError("The wallet is not on regtest.")
        if wallet.get("version") != LIANA_RELEASE:
            raise SafetyError("This Liana version is outside the current compatibility contract.")
        flow = run / (
            "private/wallet-state.json" if record.policy else "private/presentation-flow.json"
        )
        expected_height = json.loads(private_file(flow))["height"] if flow.exists() else 1
        if check_height and info.get("blocks") != expected_height:
            raise SafetyError("The regtest changed outside this workflow. Inspect it locally.")
        import tomllib

        descriptor = tomllib.loads(private_file(run / "liana/regtest/daemon.toml").decode())[
            "main_descriptor"
        ]
        if hashlib.sha256(descriptor.encode()).hexdigest() != record.descriptor_sha256:
            raise SafetyError("The wallet policy changed outside this server.")
        # Check the live daemon's policy, not just the local file.
        descriptors = wallet.get("descriptors", {})
        if descriptors.get("main", {}).get("multi_desc") != descriptor:
            raise SafetyError("The live wallet policy does not match this test run.")
        return record, run, wallet

    def public_status(self) -> dict:
        if not self.state_file.exists():
            return {
                "status": "not_started",
                "network": "regtest",
                "experimental": True,
                "mutations_enabled": self.settings.enable_regtest_mutations,
            }
        record = self.record()
        if record.stage != "ready":
            return {
                "status": record.stage,
                "network": "regtest",
                "experimental": True,
                "mutations_enabled": self.settings.enable_regtest_mutations,
            }
        record, run, wallet = self.guard()
        policy = record.policy or WORKSHOP_POLICY
        flow_file = run / "private/presentation-flow.json"
        step = json.loads(private_file(flow_file)).get("completed", 0) if flow_file.exists() else 0
        return {
            "status": "running",
            "network": "regtest",
            "experimental": True,
            "run_id": record.run,
            "completed_step": step,
            "primary_signatures": policy.primary_signatures,
            "primary_keys": policy.primary_keys,
            "recovery_blocks": policy.recovery_blocks,
            "peer_connections": 0,
            "liana_version": wallet.get("version", "unknown"),
            "mutations_enabled": self.settings.enable_regtest_mutations,
            "setup_seconds": record.seconds,
        }

    def spawn(self, args: list[str], run: Path, log_name: str) -> None:
        # No shell; do not inherit credentials, proxy settings, DYLD or Python injection variables.
        env = {"PATH": "/usr/bin:/bin", "HOME": str(run), "LANG": "C.UTF-8"}
        with (run / log_name).open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            child = subprocess.Popen(  # noqa: S603
                args,
                env=env,
                cwd=run,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=stream,
                start_new_session=True,
            )
        self.children.append(child)

    def setup(self, policy: WalletPolicy | None = None) -> dict:
        if self.state_file.exists():
            record = self.record()
            if record.stage == "ready":
                if record.policy != policy:
                    raise SafetyError("Stop this wallet before setting up a different policy.")
                return self.public_status()
            if record.stage in ("starting", "failed"):
                raise SafetyError(
                    "Previous setup was interrupted. Inspect locally; do not retry blindly."
                )
        core, daemon = self.settings.core.checked(), self.settings.lianad.checked()
        gui = self.settings.gui.checked() if self.settings.gui else None
        run = self.runs_dir / secrets.token_hex(16)
        if len(os.fsencode(run / "liana/regtest/lianad_rpc")) >= 104:
            raise SafetyError("Choose a shorter private state directory for Unix sockets.")
        run.mkdir(mode=0o700)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        descriptor = self.wallet_files(run, port, policy)
        record = Run(
            run=run.name,
            rpc_port=port,
            descriptor_sha256=hashlib.sha256(descriptor.encode()).hexdigest(),
            core_sha256=self.settings.core.sha256,
            lianad_sha256=self.settings.lianad.sha256,
            gui_language=self.settings.language,
            policy=policy,
        )
        self.save(record)
        started = time.monotonic()
        try:
            args = [
                str(core),
                "-datadir=" + str(run / "bitcoin"),
                "-regtest=1",
                "-server=1",
                "-dbcache=16",
                "-maxmempool=8",
                "-par=1",
                "-rpcthreads=1",
                "-rpcworkqueue=4",
                "-listen=0",
                "-maxconnections=0",
                "-connect=0",
                "-dnsseed=0",
                "-fixedseeds=0",
                "-discover=0",
                "-listenonion=0",
                "-onion=0",
                "-persistmempool=0",
                "-rpcbind=127.0.0.1",
                "-rpcallowip=127.0.0.1",
                "-rpcport=" + str(port),
            ]
            self.spawn(args, run, "bitcoin.log")
            deadline = time.monotonic() + 30
            while True:
                if self.children[-1].poll() is not None:
                    raise SafetyError("The native regtest backend did not start.")
                try:
                    if self.core_rpc(run, port, "getblockchaininfo").get("chain") != "regtest":
                        raise SafetyError("Unexpected Bitcoin network.")
                    break
                except (SafetyError, OSError) as error:
                    if isinstance(error, RPCError) and error.code != -28:
                        raise
                    if time.monotonic() >= deadline:
                        raise SafetyError("Timed out starting the regtest backend.") from error
                    time.sleep(0.1)
            address = self.mining_address(run)
            height = 101 if policy else 1
            self.core_rpc(run, port, "generatetoaddress", [height, address])
            if policy:
                write_json(
                    run / "private/wallet-state.json",
                    {"height": height, "revision": 0, "coins": {}, "reserve": None},
                )
            self.spawn(
                [str(daemon), "--conf", str(run / "liana/regtest/daemon.toml")], run, "lianad.log"
            )
            deadline = time.monotonic() + 30
            while True:
                if self.children[-1].poll() is not None:
                    raise SafetyError("The wallet daemon did not start.")
                try:
                    info = self.liana_rpc(run, "getinfo")
                    if info.get("network") != "regtest":
                        raise SafetyError("Unexpected wallet network.")
                    if info.get("block_height", 0) >= height:
                        break
                except (OSError, SafetyError):
                    pass
                if time.monotonic() >= deadline:
                    raise SafetyError("Timed out synchronizing the test wallet.")
                time.sleep(0.1)
            record.stage = "ready"
            record.seconds = round(time.monotonic() - started, 3)
            self.save(record)
            self.guard(record.run)
            if gui:
                self.spawn([str(gui), "--datadir", str(run / "liana"), "--regtest"], run, "gui.log")
            return self.public_status()
        except BaseException:
            record.stage = "failed"
            self.save(record)
            # Popen handles belong to this setup, so cleanup cannot target a reused saved PID.
            for child in reversed(self.children):
                if child.poll() is None:
                    child.terminate()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        child.wait(timeout=5)
            raise

    def wallet_files(self, run: Path, port: int, policy: WalletPolicy | None = None) -> str:
        (run / "bitcoin").mkdir(mode=0o700)
        private = private_directory(run / "private", create=True)
        rule = policy or WORKSHOP_POLICY
        seeds = [secrets.token_bytes(32) for _ in range(rule.primary_keys)]
        roots = [bip32.HDKey.from_seed(seed, version=NETWORKS["test"]["xprv"]) for seed in seeds]
        accounts = [key.derive("m/48h/1h/0h/2h") for key in roots]
        keys = [
            "["
            + key.my_fingerprint.hex()
            + "/48'/1'/0'/2']"
            + account.to_public().to_base58()
            + "/<0;1>/*"
            for key, account in zip(roots, accounts, strict=True)
        ]
        recovery = keys[rule.recovery_signer - 1].replace("/<0;1>/*", "/<2;3>/*")
        descriptor = add_checksum(
            f"wsh(or_d(multi({rule.primary_signatures},{','.join(keys)}),"
            f"and_v(v:pkh({recovery}),older({rule.recovery_blocks}))))"
        )
        write_json(private / "demo-signers.json", {"seed_hex": [x.hex() for x in seeds]})
        wallet = private_directory(run / "liana", create=True)
        network = private_directory(wallet / "regtest", create=True)
        conf = {"data_directory": str(network), "main_descriptor": descriptor, "log_level": "info"}
        text = "\n".join(k + " = " + json.dumps(v) for k, v in conf.items())
        text += '\n[bitcoin_config]\nnetwork = "regtest"\npoll_interval_secs = 1\n'
        text += '\n[bitcoind_config]\naddr = "127.0.0.1:' + str(port) + '"\n'
        text += "cookie_path = " + json.dumps(str(run / "bitcoin/regtest/.cookie")) + "\n"
        with (network / "daemon.toml").open("x") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(text)
        with (network / "gui.toml").open("x") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write('start_internal_bitcoind = false\nlog_level = "info"\n')
        threshold = f"{rule.primary_signatures} of {rule.primary_keys}"
        names = (
            [f"Test signer {index + 1}" for index in range(rule.primary_keys)]
            if policy
            else ["Alice", "Bob", "Carol", "Dave", "Eve"]
        )
        write_json(
            network / "settings.json",
            {
                "wallets": [
                    {
                        "name": f"Experimental Liana · {threshold}",
                        "alias": f"{'Regtest' if policy else 'Workshop'} · {threshold}",
                        "descriptor_checksum": descriptor.split("#")[1],
                        "pinned_at": None,
                        "keys": [
                            {
                                "name": name,
                                "master_fingerprint": key.my_fingerprint.hex(),
                                "provider_key": None,
                            }
                            for name, key in zip(names, roots, strict=True)
                        ],
                        "hardware_wallets": [],
                        "remote_backend_auth": None,
                        "start_internal_bitcoind": False,
                        "fiat_price": None,
                    }
                ]
            },
        )
        write_json(
            wallet / "global_settings.json",
            {
                "bitbox": None,
                "window_config": {"width": 1180.0, "height": 760.0},
                "locale": self.settings.language,
            },
        )
        return descriptor

    @staticmethod
    def mining_address(run: Path) -> str:
        seed = json.loads(private_file(run / "private/demo-signers.json"))["seed_hex"][0]
        root = bip32.HDKey.from_seed(bytes.fromhex(seed), version=NETWORKS["test"]["xprv"])
        return script.p2wpkh(root.derive("m/48h/1h/0h/2h").get_public_key()).address(
            NETWORKS["regtest"]
        )

    def stop(self) -> dict:
        record, run, _ = self.guard(check_height=False)
        self.liana_rpc(run, "stop")
        self.core_rpc(run, record.rpc_port, "stop")
        for child in reversed(self.children):
            if child.poll() is None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    child.wait(timeout=5)
        record.stage = "stopped"
        self.save(record)
        return {"status": "stopped", "files_preserved": True}
