"""Consensus checks using synthetic coins in the bounded, owned Regtest only."""

import json
from itertools import combinations

from embit import bip32, script, transaction
from embit.descriptor import Descriptor
from embit.networks import NETWORKS

from .config import private_file


def _progress(d, initiator="liana-mcp"):
    state = json.loads(private_file(d.state_file))
    run = d.runs_dir / state["run"]
    receipt = run / "policy-proof.json"
    d.guard()
    status = d.public_status()
    if (
        status["status"] != "running"
        or status.get("primary_signatures") != 3
        or status.get("primary_keys") != 5
    ):
        raise RuntimeError("Start the prepared 3-of-5 Regtest wallet first")
    if receipt.exists():
        return json.loads(private_file(receipt))
    if (
        d.core_rpc(run, state["rpc_port"], "getblockchaininfo")["chain"] != "regtest"
        or d.core_rpc(run, state["rpc_port"], "getconnectioncount") != 0
    ):
        raise RuntimeError("Isolated Regtest required")
    port = state["rpc_port"]

    def call(method, params=None):
        return d.core_rpc(run, port, method, params)

    # Keys never leave this process or appear in public results.
    seeds = json.loads(private_file(run / "private/demo-signers.json"))["seed_hex"]
    roots = [
        bip32.HDKey.from_seed(bytes.fromhex(s), version=NETWORKS["test"]["xprv"]) for s in seeds
    ]
    accounts = [r.derive("m/48h/1h/0h/2h") for r in roots]
    import tomllib

    desc = Descriptor.from_string(
        tomllib.loads(private_file(run / "liana/regtest/daemon.toml").decode())["main_descriptor"]
    )
    mine_script = script.p2wpkh(accounts[0].get_public_key())
    mine_address = mine_script.address(NETWORKS["regtest"])

    def mine(n):
        call("generatetoaddress", [n, mine_address])

    def pay(txid, vout, value, outputs, key):
        tx = transaction.Transaction(
            version=2,
            vin=[transaction.TransactionInput(bytes.fromhex(txid), vout)],
            vout=[transaction.TransactionOutput(v, s) for v, s in outputs],
        )
        sighash = tx.sighash_segwit(0, script.p2pkh(key.get_public_key()), value)
        sig = key.key.sign(sighash).serialize() + b"\x01"
        tx.vin[0].witness = transaction.Witness([sig, key.get_public_key().sec()])
        return tx

    def wallet_spend(txid, value, index, recovery=False, primary_indices=(0, 1, 3)):
        derived = desc.derive(index, branch_index=0)
        ws = derived.witness_script()
        tx = transaction.Transaction(
            version=2,
            vin=[
                transaction.TransactionInput(
                    bytes.fromhex(txid), 0, sequence=6 if recovery else 0xFFFFFFFD
                )
            ],
            vout=[transaction.TransactionOutput(value - 1000, mine_script)],
        )
        h = tx.sighash_segwit(0, ws, value)
        if recovery:
            key = accounts[2].derive([2, index])
            sig = key.key.sign(h).serialize() + b"\x01"
            stack = [sig, key.get_public_key().sec(), b"", b"", b"", b"", ws.data]
        else:
            keys = [accounts[i].derive([0, index]) for i in primary_indices]
            sigs = [k.key.sign(h).serialize() + b"\x01" for k in keys]
            stack = [b"", *sigs, *([b""] * (3 - len(sigs))), ws.data]
        tx.vin[0].witness = transaction.Witness(stack)
        return tx

    def accepted(tx):
        return bool(call("testmempoolaccept", [[tx.serialize().hex()]])[0].get("allowed"))

    flow_file = run / "private/presentation-flow.json"
    flow = (
        json.loads(private_file(flow_file))
        if flow_file.exists()
        else {"completed": 0, "checks": {}, "initiator": initiator, "height": 1}
    )
    if call("getblockcount") != flow["height"]:
        raise RuntimeError("Regtest changed outside the presentation workflow; start a fresh demo")
    initial = flow["completed"]
    checks = flow["checks"]

    def update_labels():
        labels = {mine_address: "Recovery test destination"}
        for key, index, tx_label, coin_label, address_label in [
            (
                "old_id",
                0,
                "01 First deposit",
                "First deposit · later refreshed",
                "First deposit · 3 of 5",
            ),
            (
                "new_id",
                1,
                "02 Second deposit",
                "Second deposit · separate delay",
                "Second deposit · separate delay",
            ),
            (
                "refresh_id",
                2,
                "03 Refresh with three signatures",
                "Refreshed output · new delay",
                "Refresh · new delay",
            ),
        ]:
            if key in flow:
                labels[flow[key]] = tx_label
                labels[flow[key] + ":0"] = coin_label
                labels[desc.derive(index, branch_index=0).address(NETWORKS["regtest"])] = (
                    address_label
                )
        if "recovery_id" in flow:
            labels[flow["recovery_id"]] = d.RECOVERY_LABEL
        d.liana_rpc(run, "updatelabels", {"labels": labels})
        actual = d.liana_rpc(run, "getlabels", {"items": list(labels)})["labels"]
        if any(actual.get(k) != v for k, v in labels.items()):
            raise RuntimeError("Wallet label readback failed")
        d.write_json(run / "private/display-labels.json", labels)
        return len(labels)

    def unspent_coins():
        coins = []
        for key, label_text in [
            ("old_id", "First deposit"),
            ("new_id", "Second deposit"),
            ("refresh_id", "Refreshed output · new delay"),
        ]:
            if key not in flow:
                continue
            coin = call("gettxout", [flow[key], 0])
            if coin:
                conf = coin["confirmations"]
                coins.append(
                    {
                        "label": label_text,
                        "amount_sats": round(coin["value"] * 100000000),
                        "confirmations": conf,
                        "recovery_available": conf >= 6,
                        "blocks_remaining": max(0, 6 - conf),
                    }
                )
        return coins

    def checkpoint(number, label):
        flow["completed"] = number
        flow["height"] = call("getblockcount")
        flow["label_count"] = update_labels()
        d.write_json(flow_file, flow)
        result = {
            "status": "step_complete",
            "step": number,
            "step_label": label,
            "network": "regtest",
            "initiator": flow["initiator"],
            "coins": unspent_coins(),
            "checks": dict(checks),
            "display_labels_verified": True,
            "blocks_produced_immediately": True,
            "mainnet_blocks_accelerated": False,
            "complete": False,
        }
        d.write_json(run / "presentation-step.json", result)
        return result

    if flow["completed"] < 1:
        if call("getblockcount") != 1:
            raise RuntimeError("Fresh Regtest required")
        mine(100)
        block = call("getblock", [call("getblockhash", [1]), 2])
        coinbase = block["tx"][0]
        vout = next(v for v in coinbase["vout"] if v["scriptPubKey"].get("address") == mine_address)
        value = round(vout["value"] * 100000000)
        old_amount = 100000
        change = value - old_amount - 1000
        funding = pay(
            coinbase["txid"],
            vout["n"],
            value,
            [(old_amount, desc.derive(0, branch_index=0).script_pubkey()), (change, mine_script)],
            accounts[0],
        )
        old_id = call("sendrawtransaction", [funding.serialize().hex()])
        mine(1)
        checks.update(
            primary_three=all(
                accepted(wallet_spend(old_id, old_amount, 0, primary_indices=indices))
                for indices in combinations(range(5), 3)
            ),
            primary_two_rejected=all(
                not accepted(wallet_spend(old_id, old_amount, 0, primary_indices=indices))
                for indices in combinations(range(5), 2)
            ),
            primary_one_rejected=not accepted(
                wallet_spend(old_id, old_amount, 0, primary_indices=(0,))
            ),
            early_rejected=not accepted(wallet_spend(old_id, old_amount, 0, recovery=True)),
        )
        if not all(checks.values()):
            raise RuntimeError("Initial signature checks failed")
        flow.update(old_id=old_id, old_amount=old_amount, change=change)
        value = checkpoint(1, "First deposit and primary spending path")
        if initial < 1:
            yield value
    old_id = flow["old_id"]
    old_amount = flow["old_amount"]
    change = flow["change"]
    if flow["completed"] < 2:
        new_amount = 10000
        topup = pay(
            old_id,
            1,
            change,
            [
                (new_amount, desc.derive(1, branch_index=0).script_pubkey()),
                (change - new_amount - 1000, mine_script),
            ],
            accounts[0],
        )
        new_id = call("sendrawtransaction", [topup.serialize().hex()])
        mine(1)
        mine(4)
        checks.update(
            old_ready=accepted(wallet_spend(old_id, old_amount, 0, recovery=True)),
            young_locked=not accepted(wallet_spend(new_id, new_amount, 1, recovery=True)),
            primary_after_topup=accepted(wallet_spend(old_id, old_amount, 0))
            and accepted(wallet_spend(new_id, new_amount, 1)),
        )
        if not all(checks.values()):
            raise RuntimeError("Deposit and maturity checks failed")
        flow.update(new_id=new_id, new_amount=new_amount)
        value = checkpoint(2, "Second deposit and recovery delay")
        if initial < 2:
            yield value
    new_id = flow["new_id"]
    new_amount = flow["new_amount"]
    if flow["completed"] < 3:
        refreshed = wallet_spend(old_id, old_amount, 0)
        refreshed.vout[0].script_pubkey = desc.derive(2, branch_index=0).script_pubkey()
        refreshed.clear_cache()
        ws = desc.derive(0, branch_index=0).witness_script()
        h = refreshed.sighash_segwit(0, ws, old_amount)
        sigs = [
            a.derive([0, 0]).key.sign(h).serialize() + b"\x01"
            for a in (accounts[i] for i in (0, 1, 3))
        ]
        refreshed.vin[0].witness = transaction.Witness([b"", *sigs, ws.data])
        refresh_id = call("sendrawtransaction", [refreshed.serialize().hex()])
        mine(1)
        checks["refresh_locked"] = not accepted(
            wallet_spend(refresh_id, old_amount - 1000, 2, recovery=True)
        )
        checks["primary_after_refresh"] = accepted(wallet_spend(refresh_id, old_amount - 1000, 2))
        if not all(checks.values()):
            raise RuntimeError("Refresh check failed")
        flow["refresh_id"] = refresh_id
        value = checkpoint(3, "Alice, Bob and Dave refresh the first deposit")
        if initial < 3:
            yield value
    if flow["completed"] < 4:
        recovery = wallet_spend(new_id, new_amount, 1, recovery=True)
        checks["single_ready"] = accepted(recovery)
        if not all(checks.values()):
            raise RuntimeError("Recovery check failed")
        flow["recovery_id"] = call("sendrawtransaction", [recovery.serialize().hex()])
        mine(1)
        checkpoint(4, "Carol spends through the recovery path")
    result = {
        "status": "pass",
        "step": 4,
        "step_label": "Carol’s recovery confirmed",
        "complete": True,
        "network": "regtest",
        "initiator": flow["initiator"],
        "synthetic_coins_only": True,
        "primary_three_signatures_accepted": checks["primary_three"],
        "all_ten_primary_triples_accepted": checks["primary_three"],
        "primary_two_signatures_rejected": checks["primary_two_rejected"],
        "all_ten_primary_pairs_rejected": checks["primary_two_rejected"],
        "primary_one_signature_rejected": checks["primary_one_rejected"],
        "recovery_before_six_blocks_rejected": checks["early_rejected"],
        "old_coin_recoverable_after_six_blocks": checks["old_ready"],
        "additional_deposit_did_not_reset_old_coin": checks["old_ready"] and checks["young_locked"],
        "refreshed_coin_locked_again": checks["refresh_locked"],
        "checks": dict(checks),
        "coins": unspent_coins(),
        "single_signature_recovery_broadcast_and_confirmed": True,
        "recovery_blocks": 6,
        "real_funds": False,
        "peer_connections": call("getconnectioncount"),
        "display_labels_verified": True,
        "label_count": flow["label_count"],
        "primary_signatures": 3,
        "primary_keys": 5,
        "wallet_name": "Workshop · 3 of 5",
        "signer_labels": ["Alice", "Bob", "Carol", "Dave", "Eve"],
        "blocks_produced_immediately": True,
    }
    d.write_json(receipt, result)
    d.write_json(run / "presentation-step.json", result)
    return result


def advance(d, initiator="liana-mcp"):
    generator = _progress(d, initiator)
    try:
        try:
            return next(generator)
        except StopIteration as finished:
            return finished.value
    finally:
        generator.close()
