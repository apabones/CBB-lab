#!/usr/bin/env python3
"""
Critter Lab data builder: rebuilds the Critter Board's ratings as of each game day of a past season, using only games
played BEFORE that day, then joins them to closing spreads and final scores.

  python build_lab.py 2026 pillar_run_2025-26.csv    -> lab_2025-26.json
  python build_lab.py 2025 pillar_run_2024-25.csv    -> lab_2024-25.json   (held out: not loaded by the Lab page)

Needs fetch_ncaab.py (the board's data job) next to it, so the Lab uses exactly the board's rules.
Season files come from sportsdataverse (cached in ./cache if present).
"""
import importlib.util, io, json, os, sys, time
import numpy as np, pandas as pd

YEAR, LINES = sys.argv[1], sys.argv[2]
CACHE = os.environ.get("LAB_CACHE", "cache")
spec = importlib.util.spec_from_file_location("board", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_ncaab.py"))
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
f.SEASON = int(YEAR)


def get(url, tries=3, raw=False):
    p = os.path.join(CACHE, url.rsplit("/", 1)[1])
    if os.path.exists(p):
        b = open(p, "rb").read()
    else:
        import urllib.request
        b = urllib.request.urlopen(urllib.request.Request(url, headers=f.UA), timeout=300).read()
    return b if raw else json.loads(b)
f.get = get

t0 = time.time()
t, P = f.load_boxes()
d1 = f.load_d1()
G_all, meta = f.team_games(t, d1)
G_all["date"] = G_all.date.str[:10]
F = f.pbp_features(d1)
G_all = G_all.merge(F, on=["g", "team"], how="left")
t["d"] = t.game_date.astype(str).str[:10]
print(f"season loaded: {len(G_all)} team-games, {time.time() - t0:.0f}s", flush=True)

L = pd.read_csv(LINES, low_memory=False)
L = L.drop_duplicates(["date", "fav", "dog"])[["date", "fav", "dog", "line", "fav_final_margin"]]
name2id = {}
for r in t.drop_duplicates("team_id").itertuples():
    name2id[str(r.team_display_name)] = str(r.team_id)
L["fav_id"], L["dog_id"] = L.fav.map(name2id), L.dog.map(name2id)
miss = L[L.fav_id.isna() | L.dog_id.isna()]
L = L.dropna(subset=["fav_id", "dog_id"])
# home / away / neutral from the box scores for that day
bx = t[["d", "team_id", "opponent_team_id", "team_home_away", "game_id"]].astype(str)
bx = bx.drop_duplicates(["d", "team_id", "opponent_team_id"]).set_index(["d", "team_id", "opponent_team_id"])

R = lambda x, d=2: None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)
PIL = list(f.PILLARS)
TR = [k for k, _ in f.APEX_TRAITS]


def snap(T, crit, apx, tid):
    if tid not in T.index:
        return None
    r, c, a = T.loc[tid], crit.get(tid) or {}, apx.get(tid) or {}
    tr = a.get("traits") or {}
    return dict(g=int(r.games), w=int(r.wins), sp=c.get("sp", "Blob"), role=c.get("role", "none"), size=c.get("size"), core=c.get("core"),
                pil=[R(r.get(p)) for p in PIL], st=[R(r.get(p + " steady")) for p in PIL], ato=R(r.get("ato_raw")),
                efg=R(r.get("eFG z")), rank=a.get("rank"), of=a.get("of"), acore=a.get("core"),
                tp=[R((tr.get(k) or {}).get("pct"), 3) for k in TR], ta=[bool((tr.get(k) or {}).get("apex")) for k in TR],
                own3=R(r.get("own3"), 3), own3a=None if pd.isna(r.get("own3a")) else int(r.own3a), opp3=R(r.get("opp3"), 3),
                opp3a=None if pd.isna(r.get("opp3a")) else int(r.opp3a), exp3=R(r.get("exp3"), 3), oexp3=R(r.get("opp_exp3"), 3),
                down=(c.get("hunt") or {}).get("net"), mg=R(r.margin, 1))


pool_state, games, dates = {}, [], sorted(L.date.unique())
if os.environ.get("LAB_MAXDAYS"):
    dates = dates[:int(os.environ["LAB_MAXDAYS"])]   # quick test runs
for i, D in enumerate(dates):
    f.TODAY = pd.Timestamp(D).date()
    G = G_all[G_all.date < D]
    f.RAW["t"], f.RAW["d1"] = t[t.d < D], d1
    T = f.team_table(G, meta)
    apx = f.apex_profile(T, G, pool_state)
    crit = f.critters(T, G, pool_state, apx)
    for r in L[L.date == D].itertuples():
        fs, ds = snap(T, crit, apx, r.fav_id), snap(T, crit, apx, r.dog_id)
        if not fs or not ds:
            continue
        try:
            ha, gid = bx.loc[(D, r.fav_id, r.dog_id)]
        except KeyError:
            ha, gid = "unknown", ""
        site = "neutral" if gid in f.NEUTRAL else ha
        games.append(dict(d=D, gid=gid, f=r.fav_id, u=r.dog_id, line=float(r.line), m=float(r.fav_final_margin), site=site, F=fs, U=ds))
    if i % 10 == 0:
        print(f"{D}: {len(games)} games so far, {time.time() - t0:.0f}s", flush=True)

names = {k: v["short"] for k, v in f.D1_INFO.items()}
season = f"{int(YEAR) - 1}-{YEAR[2:]}"
out = dict(season=season, built=time.strftime("%Y-%m-%d"), pillars=PIL, traits=[l for _, l in f.APEX_TRAITS],
           apex_cut=f.APEX, lg3=f.POOL.get("lg3"), names=names, games=games,
           note="Ratings rebuilt as of each game day from earlier games only. No injuries (no history). Spreads are closing lines.")
path = f"lab_{season}.json"                      # sits next to index.html in the Lab repo
json.dump(out, open(path, "w"), separators=(",", ":"))
print(f"wrote {path}: {len(games)} games, {os.path.getsize(path) / 1e6:.1f} MB, unmatched names {len(miss)}, {time.time() - t0:.0f}s")
