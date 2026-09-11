#!/usr/bin/env python3
"""Кросс-биржевое сравнение мем-перпов из снимка данных.

Использование:
    python3 scripts/analyze_snapshot.py [snapshot_dir]
Печатает: спреды, объёмы, OI, funding, плечи, комиссии, скорость листингов,
long/short толпы (Gate) и таблицу общих монет.
"""
import json, sys, statistics as st, time
from pathlib import Path

MEMES = {'DOGE','SHIB','PEPE','BONK','FLOKI','WIF','TRUMP','PENGU','FARTCOIN','TURBO','NEIRO','BRETT',
         'MEW','POPCAT','SPX','GIGA','MOG','BOME','PEIPEI','CHILLGUY','ACT','PNUT','GOAT','LUCE',
         'BABYDOGE','BANANAS31','WOJAK','ELON','DOGS','NOT','HAMMY','MICHI','TOSHI','AIXBT','VIRTUAL'}

def norm(s):
    s = s.upper()
    for p in ('K', '1000'):
        if s.startswith(p) and s[len(p):] in MEMES:
            return s[len(p):]
    return s

def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(Path("data").glob("snapshot-*"))[-1]
    J = lambda n: json.loads((d / n).read_text())
    NOW = time.time()

    # MEXC
    mt = J("mexc_ticker.json")["data"]; md = {x["symbol"]: x for x in J("mexc_detail.json")["data"]}
    mexc = []
    for t in mt:
        base = t["symbol"].split("_")[0]
        if base not in MEMES: continue
        c = md.get(t["symbol"], {}); cs = float(c.get("contractSize", 1) or 1)
        mid = (t["bid1"] + t["ask1"]) / 2
        mexc.append(dict(base=base, spread=(t["ask1"]-t["bid1"])/mid*1e4 if mid else None, vol=t["amount24"],
                         oi=t["holdVol"]*cs*t["lastPrice"], fund=float(t["fundingRate"])*100,
                         lev=c.get("maxLeverage"), taker=float(c.get("takerFeeRate", 0))*100))

    # GATE
    gc = J("gate_contracts.json"); gt = {x["contract"]: x for x in J("gate_tickers.json")}
    gate = []
    for c in gc:
        base = c["name"].split("_")[0]
        if base not in MEMES: continue
        t = gt.get(c["name"], {}); b = float(t.get("highest_bid", 0)); a = float(t.get("lowest_ask", 0)); mid = (a+b)/2
        gate.append(dict(base=base, spread=(a-b)/mid*1e4 if mid else None, vol=float(t.get("volume_24h_quote", 0)),
                         oi=float(c["position_size"])*float(c["quanto_multiplier"])*float(c["mark_price"]),
                         fund=float(c["funding_rate"])*100, lev=float(c["leverage_max"]),
                         taker=float(c["taker_fee_rate"])*100, lu=c.get("long_users"), su=c.get("short_users")))

    # BINGX
    bc = J("bingx_contracts.json")["data"]; bt = {x["symbol"]: x for x in J("bingx_ticker.json")["data"]}
    bingx = []
    for c in bc:
        base = c["symbol"].split("-")[0]
        if base not in MEMES: continue
        t = bt.get(c["symbol"])
        if not t: continue
        b = float(t.get("bidPrice", 0)); a = float(t.get("askPrice", 0)); mid = (a+b)/2
        bingx.append(dict(base=base, spread=(a-b)/mid*1e4 if mid else None, vol=float(t.get("quoteVolume", 0)),
                          taker=float(c["takerFeeRate"])*100))

    # HL
    meta, ctxs = J("hl_meta.json")
    hl = [dict(base=norm(u["name"]), lev=u["maxLeverage"], oi=float(c.get("openInterest", 0))*float(c.get("oraclePx", 0)),
               vol=float(c.get("dayNtlVlm", 0)), fund=float(c.get("funding", 0))*100)
          for u, c in zip(meta["universe"], ctxs) if norm(u["name"]) in MEMES]

    def summ(name, rows):
        sp = [r["spread"] for r in rows if r.get("spread")]; vo = [r["vol"] for r in rows if r.get("vol")]
        oi = [r["oi"] for r in rows if r.get("oi")]; fu = [r["fund"] for r in rows if r.get("fund") is not None]
        print(f"\n== {name}: meme perps {len(rows)}")
        if sp: print(f"   spread bps   median {st.median(sp):.2f}  p75 {sorted(sp)[len(sp)*3//4]:.2f}  max {max(sp):.1f}")
        if vo: print(f"   vol24 USDT   sum {sum(vo)/1e6:.0f}M  median {st.median(vo)/1e6:.1f}M  max {max(vo)/1e6:.0f}M")
        if oi: print(f"   OI USDT      sum {sum(oi)/1e6:.0f}M  median {st.median(oi)/1e6:.1f}M")
        if fu: print(f"   funding%     median {st.median(fu):.4f}  |f|>=0.05: {sum(abs(x)>=0.05 for x in fu)}  |f|>=0.1: {sum(abs(x)>=0.1 for x in fu)}")
        lv = [r["lev"] for r in rows if r.get("lev")]
        if lv: print(f"   max leverage median {st.median(lv):.0f}  max {max(lv):.0f}")
        tk = sorted({r["taker"] for r in rows if r.get("taker") is not None})
        if tk: print(f"   taker% {tk}")

    summ("MEXC", mexc); summ("GATE", gate); summ("BINGX", bingx); summ("HYPERLIQUID", hl)

    # скорость листингов (все перпы)
    m_all = [x.get("createTime")/1000 for x in md.values() if x.get("createTime")]
    g_all = [x.get("launch_time") for x in gc if x.get("launch_time")]
    b_all = [float(x.get("launchTime", 0)) for x in bc if x.get("launchTime")]
    b_all = [v/1000 if v > 1e12 else v for v in b_all]
    for name, arr in [("MEXC", m_all), ("GATE", g_all), ("BINGX", b_all)]:
        print(f"{name} listings: total {len(arr)}  new30d {sum(NOW-c < 30*86400 for c in arr)}  new90d {sum(NOW-c < 90*86400 for c in arr)}")

    ls = [(r["base"], r["lu"]/r["su"]) for r in gate if r.get("lu") and r.get("su")]
    if ls:
        rr = [x[1] for x in ls]
        print(f"\nGate long/short users: median {st.median(rr):.2f}, >1.5: {sum(x>1.5 for x in rr)}/{len(rr)}; top: {sorted(ls, key=lambda x: -x[1])[:6]}")

    print("\n== COMMON COINS (spread bps | vol24 M | OI M | fund%) ==")
    for coin in ["PEPE","BONK","FLOKI","WIF","TRUMP","PENGU","FARTCOIN","DOGE","SHIB","TURBO","POPCAT"]:
        parts = [f"{coin:9s}"]
        for name, rows in [("MEXC", mexc), ("GATE", gate), ("BINGX", bingx), ("HL", hl)]:
            r = next((x for x in rows if x["base"] == coin), None)
            parts.append(f"{name} {r.get('spread') or 0:6.1f}bp {r['vol']/1e6:7.1f}M oi {(r.get('oi') or 0)/1e6:7.1f}M f{r.get('fund') or 0:+.4f}" if r else f"{name} {'—':>28s}")
        print(" | ".join(parts))

    if (d / "depth_1pct.json").exists():
        print("\n== 1% depth (min side, $) ==", json.loads((d / "depth_1pct.json").read_text()))

if __name__ == "__main__":
    main()
