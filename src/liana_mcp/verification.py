#!/usr/bin/env python3
"""Read back the four real workshop transactions from Liana and Bitcoin Core."""

import json
from decimal import Decimal

from .config import private_file


def sats(amount):
    return int(Decimal(str(amount)) * 100_000_000)


def confirmed_amounts(tx: dict) -> tuple[int, int, int]:
    spent = sum(sats(v["prevout"]["value"]) for v in tx["vin"])
    received = sum(sats(v["value"]) for v in tx["vout"])
    fee = spent - received
    if fee < 0 or fee != sats(tx["fee"]):
        raise RuntimeError("The regtest fee does not match the inputs and outputs.")
    return spent, received, fee


def recovery_payment(demo, run, port: int, flow: dict) -> dict:
    """Measure the single-input, single-output recovery from its confirmed block."""
    block_hash = demo.core_rpc(run, port, "getblockhash", [flow["height"]])
    block = demo.core_rpc(run, port, "getblock", [block_hash, 3])
    tx = next(item for item in block["tx"] if item["txid"] == flow["recovery_id"])
    if (
        len(tx["vin"]) != 1
        or len(tx["vout"]) != 1
        or tx["vin"][0]["txid"] != flow["new_id"]
        or tx["vin"][0]["vout"] != 0
    ):
        raise RuntimeError("The confirmed recovery did not spend the expected output.")
    spent, received, fee = confirmed_amounts(tx)
    return {
        "wallet_input_sats": spent,
        "destination_received_sats": received,
        "miner_fee_sats": fee,
    }


def verify(demo, run_id: str) -> dict:
    demo.guard(run_id)
    status = demo.public_status()
    if (
        status["status"] != "running"
        or status.get("primary_signatures") != 3
        or status.get("primary_keys") != 5
    ):
        raise RuntimeError("Start the prepared 3-of-5 regtest wallet first.")
    state = json.loads(private_file(demo.state_file))
    run = demo.runs_dir / state["run"]

    def call(method, params=None):
        return demo.core_rpc(run, state["rpc_port"], method, params)

    if call("getblockchaininfo")["chain"] != "regtest" or call("getconnectioncount") != 0:
        raise RuntimeError("An isolated regtest chain is required.")
    flow = json.loads(private_file(run / "private/presentation-flow.json"))
    if flow.get("completed") != 4:
        raise RuntimeError("Complete the four regtest transaction steps first.")
    recovery_label = demo.RECOVERY_LABEL
    labels = [
        ("old_id", "01 First deposit"),
        ("new_id", "02 Second deposit"),
        ("refresh_id", "03 Refresh with three signatures"),
        ("recovery_id", recovery_label),
    ]
    expected = {flow[key]: label for key, label in labels}

    if demo.liana_rpc(run, "getlabels", {"items": list(expected)})["labels"] != expected:
        raise RuntimeError("The four transaction labels do not match the experiment.")
    resources = demo.liana_rpc(run, "listtransactions", {"txids": list(expected)})["transactions"]
    rows = []
    seen = set()
    for resource in resources:
        decoded = call("decoderawtransaction", [resource["tx"]])
        txid = decoded["txid"]
        if txid not in expected or txid in seen or not resource.get("height"):
            raise RuntimeError("Liana returned an unexpected or unconfirmed transaction.")
        blockhash = call("getblockhash", [resource["height"]])
        actual = call("getrawtransaction", [txid, True, blockhash])
        if actual["hex"] != resource["tx"] or actual.get("confirmations", 0) < 1:
            raise RuntimeError("Liana and the confirmed Bitcoin Core chain disagree.")
        witness = actual["vin"][0]["txinwitness"]
        if txid == flow["refresh_id"]:
            if len(witness) != 5 or witness[0] != "" or not all(witness[1:4]):
                raise RuntimeError("The refresh does not contain the three primary signatures.")
        if txid == flow["recovery_id"]:
            if (
                len(witness) != 7
                or not witness[0]
                or not witness[1]
                or any(witness[2:6])
                or actual["vin"][0]["sequence"] != 6
            ):
                raise RuntimeError("The recovery does not use the expected single-signature path.")
        block = call("getblock", [blockhash, 3])
        mined = next(tx for tx in block["tx"] if tx["txid"] == txid)
        _, _, fee = confirmed_amounts(mined)
        seen.add(txid)
        rows.append(
            {
                "label": expected[txid],
                "block_height": resource["height"],
                "amount_sats": sats(actual["vout"][0]["value"]),
                "fee_sats": fee,
                "confirmations": actual["confirmations"],
                "liana_and_core_transaction_bytes_equal": True,
            }
        )
    if seen != set(expected):
        raise RuntimeError("At least one of the four regtest transactions is missing.")
    renewed = call("gettxout", [flow["refresh_id"], 0])
    if not renewed or sats(renewed["value"]) != 99000:
        raise RuntimeError("The refreshed output is missing from the UTXO set.")
    if (
        call("gettxout", [flow["old_id"], 0]) is not None
        or call("gettxout", [flow["new_id"], 0]) is not None
    ):
        raise RuntimeError("A spent input unexpectedly remains in the UTXO set.")
    by_label = {row["label"]: row for row in rows}
    renewal = by_label[labels[2][1]]
    recovery = by_label[recovery_label]
    result = {
        "result": "pass",
        "network": "regtest",
        "external_peers": 0,
        "confirmed_transactions_in_liana_and_core": 4,
        "transactions": sorted(rows, key=lambda x: x["label"]),
        "renewal_primary_signatures": 3,
        "recovery_signatures": 1,
        "renewed_unspent_sats": sats(renewed["value"]),
        "wallet_spend_fees_sats": {
            "renewal": renewal["fee_sats"],
            "recovery": recovery["fee_sats"],
        },
        "recovery_destination_sats": recovery["amount_sats"],
        "spent_inputs_absent_from_utxo_set": True,
        "physical_network_disconnection_verified": False,
    }
    return result
