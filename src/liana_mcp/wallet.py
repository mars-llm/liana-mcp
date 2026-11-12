"""Compose approved actions on a generated wallet and its own isolated regtest chain."""

import json
import time
import tomllib
from typing import Annotated, Literal

from embit import bip32, script, transaction
from embit.descriptor import Descriptor
from embit.networks import NETWORKS
from pydantic import BaseModel, ConfigDict, Field

from .approval import consume
from .config import private_file
from .errors import SafetyError
from .policy import WalletPolicy
from .runtime import Runtime
from .verification import confirmed_amounts, sats

FEE = 1000
Signer = Annotated[int, Field(ge=1, le=8)]
RunId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


class WalletInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Deposit(WalletInput):
    kind: Literal["deposit"]
    amount_sats: int = Field(ge=2000, le=10_000_000)


class Mine(WalletInput):
    kind: Literal["mine"]
    blocks: int = Field(ge=1, le=144)


class Spend(WalletInput):
    kind: Literal["spend"]
    coin: int = Field(ge=0, le=255, description="Coin number returned by wallet status.")
    path: Literal["primary", "recovery"]
    signers: list[Signer] = Field(
        max_length=8, description="One-based primary signers. Empty for the recovery path."
    )
    destination: Literal["wallet", "test_sink"]


class WalletSetup(WalletInput):
    kind: Literal["setup"]
    policy: WalletPolicy


class WalletAction(WalletInput):
    kind: Literal["act"]
    run_id: RunId
    expected_revision: int = Field(ge=0, le=999)
    action: Annotated[Deposit | Mine | Spend, Field(discriminator="kind")]


WalletRequest = Annotated[WalletSetup | WalletAction, Field(discriminator="kind")]


class WalletCoin(BaseModel):
    coin: int
    amount_sats: int
    confirmations: int
    recovery_blocks_remaining: int


class WalletTransaction(BaseModel):
    txid: str
    block_height: int
    output_sats: int
    fee_sats: int
    verified_in_liana_and_core: Literal[True] = True


class WalletStatus(BaseModel):
    network: Literal["regtest"] = "regtest"
    status: Literal["not_started", "starting", "failed", "stopped", "running"]
    run_id: RunId | None = None
    policy: WalletPolicy | None = None
    revision: int | None = None
    block_height: int | None = None
    peer_connections: Literal[0] | None = None
    coins: list[WalletCoin] = Field(default_factory=list)
    transaction: WalletTransaction | None = None


def configure_wallet(runtime: Runtime, request: WalletSetup) -> WalletStatus:
    if runtime.state_file.exists() and runtime.record().stage == "ready":
        if runtime.record().policy != request.policy:
            raise SafetyError("Stop this wallet before setting up a different policy.")
    else:
        consume(runtime, "wallet_setup", request.model_dump(mode="json"))
        runtime.setup(request.policy)
    return wallet_status(runtime)


class WalletRun:
    def __init__(self, runtime: Runtime, run_id: str | None = None):
        self.runtime = runtime
        self.record, self.run, _ = runtime.guard(run_id)
        policy = self.record.policy
        if policy is None:
            raise SafetyError("The current run uses the workshop tools.")
        self.policy = policy
        self.state_file = self.run / "private/wallet-state.json"
        self.state = json.loads(private_file(self.state_file))
        if self.state.get("pending"):
            raise SafetyError("A wallet action was interrupted. Inspect this regtest locally.")

    def core(self, method: str, params: list | None = None):
        return self.runtime.core_rpc(self.run, self.record.rpc_port, method, params)

    def status(self) -> WalletStatus:
        coins = []
        for number, txid in self.state["coins"].items():
            coin = self.core("gettxout", [txid, 0])
            if coin:
                coins.append(
                    WalletCoin(
                        coin=int(number),
                        amount_sats=sats(coin["value"]),
                        confirmations=coin["confirmations"],
                        recovery_blocks_remaining=max(
                            0, self.policy.recovery_blocks - coin["confirmations"]
                        ),
                    )
                )
        return WalletStatus(
            status="running",
            run_id=self.record.run,
            policy=self.policy,
            revision=self.state["revision"],
            block_height=self.state["height"],
            peer_connections=0,
            coins=coins,
            transaction=self.state.get("last_transaction"),
        )

    def keys(self):
        seeds = json.loads(private_file(self.run / "private/demo-signers.json"))["seed_hex"]
        return [
            bip32.HDKey.from_seed(bytes.fromhex(seed), version=NETWORKS["test"]["xprv"]).derive(
                "m/48h/1h/0h/2h"
            )
            for seed in seeds
        ]

    def next_coin(self) -> int:
        index = len(self.state["coins"])
        if index >= 256:
            raise SafetyError("This test run has reached its output limit.")
        return index

    def prepare(self, action: Deposit | Spend):
        keys = self.keys()
        config = tomllib.loads(private_file(self.run / "liana/regtest/daemon.toml").decode())
        descriptor = Descriptor.from_string(config["main_descriptor"])
        sink = script.p2wpkh(keys[0].get_public_key())

        if isinstance(action, Deposit):
            index = self.next_coin()
            reserve = self.state["reserve"]
            if reserve is None:
                block = self.core("getblock", [self.core("getblockhash", [1]), 2])
                coinbase = block["tx"][0]
                output = next(
                    v for v in coinbase["vout"] if v["scriptPubKey"]["hex"] == sink.data.hex()
                )
                reserve = [coinbase["txid"], output["n"]]
            coin = self.core("gettxout", reserve)
            if not coin or sats(coin["value"]) - action.amount_sats - FEE < 1000:
                raise SafetyError("The test funding reserve cannot cover this deposit.")
            value = sats(coin["value"])
            tx = transaction.Transaction(
                version=2,
                vin=[transaction.TransactionInput(bytes.fromhex(reserve[0]), reserve[1])],
                vout=[
                    transaction.TransactionOutput(
                        action.amount_sats, descriptor.derive(index).script_pubkey()
                    ),
                    transaction.TransactionOutput(value - action.amount_sats - FEE, sink),
                ],
            )
            key = keys[0]
            digest = tx.sighash_segwit(0, script.p2pkh(key.get_public_key()), value)
            stack = [key.key.sign(digest).serialize() + b"\x01", key.get_public_key().sec()]
        else:
            txid = self.state["coins"].get(str(action.coin))
            coin = self.core("gettxout", [txid, 0]) if txid else None
            if not coin or sats(coin["value"]) - FEE < 1000:
                raise SafetyError("Choose an unspent test coin with at least 2,000 sats.")
            value = sats(coin["value"])
            recovery = action.path == "recovery"
            threshold = self.policy.primary_signatures
            if recovery:
                if action.signers or coin["confirmations"] < self.policy.recovery_blocks:
                    raise SafetyError("Recovery requires an empty signer list and a mature coin.")
            elif (
                len(action.signers) != threshold
                or len(set(action.signers)) != threshold
                or max(action.signers) > self.policy.primary_keys
            ):
                raise SafetyError("Select exactly the required number of distinct primary signers.")
            index = self.next_coin() if action.destination == "wallet" else None
            ws = descriptor.derive(action.coin).witness_script()
            tx = transaction.Transaction(
                version=2,
                vin=[
                    transaction.TransactionInput(
                        bytes.fromhex(txid),
                        0,
                        sequence=self.policy.recovery_blocks if recovery else 0xFFFFFFFD,
                    )
                ],
                vout=[
                    transaction.TransactionOutput(
                        value - FEE,
                        descriptor.derive(index).script_pubkey() if index is not None else sink,
                    )
                ],
            )
            digest = tx.sighash_segwit(0, ws, value)
            if recovery:
                key = keys[self.policy.recovery_signer - 1].derive([2, action.coin])
                stack = [
                    key.key.sign(digest).serialize() + b"\x01",
                    key.get_public_key().sec(),
                    *([b""] * (threshold + 1)),
                    ws.data,
                ]
            else:
                stack = [
                    b"",
                    *(
                        keys[signer - 1].derive([0, action.coin]).key.sign(digest).serialize()
                        + b"\x01"
                        for signer in sorted(action.signers)
                    ),
                    ws.data,
                ]
        tx.vin[0].witness = transaction.Witness(stack)
        raw = tx.serialize().hex()
        if not self.core("testmempoolaccept", [[raw]])[0].get("allowed"):
            raise SafetyError("Bitcoin Core rejected the proposed test transaction.")
        return raw, index

    def confirm(self, txid: str, block_hash: str, raw: str) -> WalletTransaction:
        block = self.core("getblock", [block_hash, 3])
        mined = next(tx for tx in block["tx"] if tx["txid"] == txid)
        core_tx = self.core("getrawtransaction", [txid, True, block_hash])
        _, _, fee = confirmed_amounts(mined)
        deadline = time.monotonic() + 10
        while True:
            rows = self.runtime.liana_rpc(self.run, "listtransactions", {"txids": [txid]})[
                "transactions"
            ]
            if core_tx["hex"] == raw and any(
                row["tx"] == raw and row["height"] == block["height"] for row in rows
            ):
                return WalletTransaction(
                    txid=txid,
                    block_height=block["height"],
                    output_sats=sats(mined["vout"][0]["value"]),
                    fee_sats=fee,
                )
            if time.monotonic() >= deadline:
                raise SafetyError("The test transaction was broadcast but readback is incomplete.")
            time.sleep(0.2)

    def execute(self, request: WalletAction) -> WalletStatus:
        payload = request.model_dump(mode="json")
        if self.state.get("last_request") == payload:
            return self.status()
        if self.state["revision"] != request.expected_revision:
            raise SafetyError("The wallet revision changed. Read status before continuing.")
        action = request.action
        if isinstance(action, Mine):
            blocks = action.blocks
        else:
            raw, index = self.prepare(action)
            blocks = 1
        consume(self.runtime, "wallet_action", payload)
        self.runtime.write_json(self.state_file, {**self.state, "pending": payload})
        if not isinstance(action, Mine):
            txid = self.core("sendrawtransaction", [raw])
        hashes = self.core("generatetoaddress", [blocks, self.runtime.mining_address(self.run)])
        if len(hashes) != blocks:
            raise SafetyError("Bitcoin Core did not produce the requested blocks.")
        receipt = None
        if not isinstance(action, Mine):
            receipt = self.confirm(txid, hashes[0], raw).model_dump(mode="json")
            if index is not None:
                self.state["coins"][str(index)] = txid
            if isinstance(action, Deposit):
                self.state["reserve"] = [txid, 1]
        self.state.update(
            height=self.state["height"] + blocks,
            revision=self.state["revision"] + 1,
            last_request=payload,
            last_transaction=receipt,
        )
        self.runtime.write_json(self.state_file, self.state)
        return self.status()


def wallet_status(runtime: Runtime) -> WalletStatus:
    if not runtime.state_file.exists():
        return WalletStatus(status="not_started")
    record = runtime.record()
    if record.stage != "ready":
        return WalletStatus(status=record.stage)
    return WalletRun(runtime).status()
