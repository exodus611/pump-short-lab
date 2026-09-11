#!/usr/bin/env python3
"""Снимок живых данных 4 бирж (MEXC, Gate, BingX, Hyperliquid) для анализа памп-механик.

Использование:
    python3 scripts/collect_exchange_snapshot.py [out_dir]
По умолчанию пишет в data/snapshot-YYYY-MM-DD/ (относительно корня репо или CWD).
Только публичные эндпоинты, ключи не нужны.
"""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = {"User-Agent": "pump-short-lab/0.1", "Content-Type": "application/json"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)

def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)

def save(out: Path, name: str, obj):
    (out / name).write_text(json.dumps(obj))
    print(f"  saved {name}")

def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data") / f"snapshot-{datetime.now(timezone.utc):%Y-%m-%d}"
    root.mkdir(parents=True, exist_ok=True)
    print(f"snapshot -> {root}")

    print("MEXC");  save(root, "mexc_ticker.json", get("https://contract.mexc.com/api/v1/contract/ticker"))
    save(root, "mexc_detail.json", get("https://contract.mexc.com/api/v1/contract/detail"))
    print("GATE");  save(root, "gate_contracts.json", get("https://api.gateio.ws/api/v4/futures/usdt/contracts"))
    save(root, "gate_tickers.json", get("https://api.gateio.ws/api/v4/futures/usdt/tickers"))
    print("BINGX"); save(root, "bingx_contracts.json", get("https://open-api.bingx.com/openApi/swap/v2/quote/contracts"))
    save(root, "bingx_ticker.json", get("https://open-api.bingx.com/openApi/swap/v2/quote/ticker"))
    print("HL");    save(root, "hl_meta.json", post("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"}))

    # глубина стаканов в 1% по ключевым мем-монетам (для оценки проскальзывания)
    coins = ["PEPE", "WIF", "TRUMP", "FARTCOIN", "PENGU"]
    md = {x["symbol"]: x for x in json.loads((root / "mexc_detail.json").read_text())["data"]}
    mt = {x["symbol"]: x for x in json.loads((root / "mexc_ticker.json").read_text())["data"]}
    gc = {x["name"]: x for x in json.loads((root / "gate_contracts.json").read_text())}
    depth = {}
    for coin in coins:
        row = {}
        # MEXC
        try:
            d = get(f"https://contract.mexc.com/api/v1/contract/depth/{coin}_USDT")["data"]
            cs = float(md[f"{coin}_USDT"]["contractSize"]); mid = float(mt[f"{coin}_USDT"]["lastPrice"])
            bid = sum(p * s * cs for p, s, _ in ((float(a), float(b), c) for a, b, c in d["bids"]) if p >= mid * 0.99)
            ask = sum(p * s * cs for p, s, _ in ((float(a), float(b), c) for a, b, c in d["asks"]) if p <= mid * 1.01)
            row["mexc"] = round(min(bid, ask), 1)
        except Exception as e: row["mexc"] = f"err:{e}"
        # GATE
        try:
            b = get(f"https://api.gateio.ws/api/v4/futures/usdt/order_book?contract={coin}_USDT&limit=100")
            q = float(gc[f"{coin}_USDT"]["quanto_multiplier"]); mid = float(gc[f"{coin}_USDT"]["mark_price"])
            bid = sum(float(x["p"]) * float(x["s"]) * q for x in b["bids"] if float(x["p"]) >= mid * 0.99)
            ask = sum(float(x["p"]) * float(x["s"]) * q for x in b["asks"] if float(x["p"]) <= mid * 1.01)
            row["gate"] = round(min(bid, ask), 1)
        except Exception as e: row["gate"] = f"err:{e}"
        # BINGX
        try:
            b = get(f"https://open-api.bingx.com/openApi/swap/v2/quote/depth?symbol={coin}-USDT&limit=100")["data"]
            mid = float(b["bids"][0][0])
            bid = sum(float(p) * float(q2) for p, q2 in b["bids"] if float(p) >= mid * 0.99)
            ask = sum(float(p) * float(q2) for p, q2 in b["asks"] if float(p) <= mid * 1.01)
            row["bingx"] = round(min(bid, ask), 1)
        except Exception as e: row["bingx"] = f"err:{e}"
        # HYPERLIQUID
        try:
            name = "kPEPE" if coin == "PEPE" else coin
            b = post("https://api.hyperliquid.xyz/info", {"type": "l2Book", "coin": name, "nLevels": 100})
            mid = (float(b["levels"][0][0]["px"]) + float(b["levels"][1][0]["px"])) / 2
            bid = sum(float(x["px"]) * float(x["sz"]) for x in b["levels"][0] if float(x["px"]) >= mid * 0.99)
            ask = sum(float(x["px"]) * float(x["sz"]) for x in b["levels"][1] if float(x["px"]) <= mid * 1.01)
            row["hyperliquid"] = round(min(bid, ask), 1)
        except Exception as e: row["hyperliquid"] = f"err:{e}"
        depth[coin] = row
        print(f"  depth {coin}: {row}")
    save(root, "depth_1pct.json", depth)
    print("done")

if __name__ == "__main__":
    main()
