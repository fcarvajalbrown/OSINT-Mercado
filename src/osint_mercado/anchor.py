import argparse
import json
import os
from pathlib import Path

import requests
import truststore
from dotenv import load_dotenv
from stellar_sdk import Keypair, Network, Server, TransactionBuilder

from osint_mercado.build_site import ITEMS_GLOB, public_dataset, public_queue
from osint_mercado.integrity import record

truststore.inject_into_ssl()

SECRET_ENV = "STELLAR_ANCHOR_SECRET"
HORIZON_URL = "https://horizon-testnet.stellar.org"
FRIENDBOT_URL = "https://friendbot.stellar.org"
EXPLORER_TX_URL = "https://stellar.expert/explorer/testnet/tx/"
DATA_NAME = "osint-mercado"
QUEUE_DATA_NAME = "osint-mercado-queue"


def build_transaction(account, keypair: Keypair, digest_hex: str, queue_hex: str | None = None):
    raw = bytes.fromhex(digest_hex)
    builder = (
        TransactionBuilder(account, Network.TESTNET_NETWORK_PASSPHRASE, base_fee=100)
        .add_hash_memo(raw)
        .append_manage_data_op(DATA_NAME, raw)
    )
    if queue_hex:
        builder = builder.append_manage_data_op(QUEUE_DATA_NAME, bytes.fromhex(queue_hex))
    tx = builder.set_timeout(60).build()
    tx.sign(keypair)
    return tx


def submit_digest(secret: str, digest_hex: str, queue_hex: str | None = None) -> dict:
    keypair = Keypair.from_secret(secret)
    server = Server(HORIZON_URL)
    account = server.load_account(keypair.public_key)
    return server.submit_transaction(build_transaction(account, keypair, digest_hex, queue_hex))


def anchor(flags: list[dict], secret: str, out_path, queue: dict | None = None) -> dict:
    rec = record(flags)
    if queue:
        result = submit_digest(secret, rec["digest"], queue["digest"])
        rec["queue_digest"] = queue["digest"]
        rec["queue_total"] = queue["total"]
    else:
        result = submit_digest(secret, rec["digest"])
    rec["tx_hash"] = result["hash"]
    rec["ledger"] = result["ledger"]
    rec["anchored_at"] = result.get("created_at")
    rec["account"] = result.get("source_account")
    rec["explorer_url"] = EXPLORER_TX_URL + result["hash"]
    Path(out_path).write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return rec


def init_account(env_path: str = ".env") -> str:
    load_dotenv(env_path)
    secret = os.getenv(SECRET_ENV)
    if secret:
        return Keypair.from_secret(secret).public_key
    keypair = Keypair.random()
    resp = requests.get(FRIENDBOT_URL, params={"addr": keypair.public_key}, timeout=60)
    resp.raise_for_status()
    with open(env_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n{SECRET_ENV}={keypair.secret}\n")
    return keypair.public_key


def load_secret() -> str:
    load_dotenv()
    secret = os.getenv(SECRET_ENV)
    if not secret:
        raise RuntimeError(f"{SECRET_ENV} is not set (run `osint-anchor init` first)")
    return secret


def main() -> None:
    ap = argparse.ArgumentParser(description="Anchor the published flags on the Stellar testnet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create and fund the testnet anchoring account in .env")
    pub = sub.add_parser("publish", help="anchor the current published dataset")
    pub.add_argument("--confirmed", default="data/confirmed_flags.json")
    pub.add_argument("--basket", default="data/basket.json")
    pub.add_argument("--items", default=ITEMS_GLOB)
    pub.add_argument("--out", default="data/anchors.json")
    args = ap.parse_args()

    if args.cmd == "init":
        print(f"anchoring account: {init_account()}")
        return

    flags, sources, _mirrors = public_dataset(args.confirmed, args.basket, args.items)
    missing = [f["id"] for f in flags if f["id"] not in sources]
    unmirrored = [f["oc_id"] for f in flags if "mirror_sha256" not in f]
    queue = public_queue()
    rec = anchor(flags, load_secret(), args.out, queue=queue)
    print(f"anchored {len(flags)} flags, digest {rec['digest']}")
    print(f"sealed review queue: {queue['total']} leads, digest {queue['digest']}")
    print(f"tx {rec['tx_hash']} ledger {rec['ledger']}: {rec['explorer_url']}")
    if missing:
        print(f"flags without a source snapshot: {', '.join(missing)}")
    if unmirrored:
        print(f"orders without a mirror (run osint-mirror first): {', '.join(unmirrored)}")


if __name__ == "__main__":
    main()
