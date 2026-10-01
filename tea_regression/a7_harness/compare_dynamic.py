import json, re, difflib, io
import pandas as pd
O = "/tmp/claude-0/a7/out/"
l1 = [json.loads(x) for x in open(O + "v1.log", encoding="utf-8")]
l3 = [json.loads(x) for x in open(O + "v3.log", encoding="utf-8")]
k1 = [json.dumps(x, ensure_ascii=False) for x in l1]
k3 = [json.dumps(x, ensure_ascii=False) for x in l3]
print(f"helper-call log entries: v1={len(k1)} v3={len(k3)} identical={k1 == k3}")
for op, a, b, c, d in difflib.SequenceMatcher(None, k1, k3, autojunk=False).get_opcodes():
    if op != "equal":
        print(op, k1[a:b][:3], k3[c:d][:3])
print("call names seq:", [x["fn"] for x in l1 if not x["fn"].startswith("===")][:0] or "")
r1 = json.load(open(O + "v1.json", encoding="utf-8"))
r3 = json.load(open(O + "v3.json", encoding="utf-8"))
for s1, s3 in zip(r1["steps"], r3["steps"]):
    name = s1["step"]
    # session state
    ks1, ks3 = set(s1["session_state"]), set(s3["session_state"])
    diffkeys = sorted(ks1 ^ ks3)
    diffvals = sorted(k for k in ks1 & ks3 if s1["session_state"][k] != s3["session_state"][k])
    assert all("csv" in a for a in s1["dataframes"] + s3["dataframes"]), "df capture failed"
    dfs_same = [a.get("csv") == b.get("csv") and a.get("display") == b.get("display") for a, b in zip(s1["dataframes"], s3["dataframes"])]
    def gnorm(g):
        ids = {}
        return re.sub(r"\b\d{10,}\b", lambda m: ids.setdefault(m.group(0), f"N{len(ids)}"), g)
    s1["graphviz"] = [gnorm(g) for g in s1["graphviz"]]; s3["graphviz"] = [gnorm(g) for g in s3["graphviz"]]
    print(f"[{name}] exc v1={s1['exceptions']} v3={s3['exceptions']} | ss keys only-in-one={diffkeys} | ss value diffs={diffvals} | "
          f"#df {len(s1['dataframes'])}/{len(s3['dataframes'])} same={all(dfs_same) and len(s1['dataframes'])==len(s3['dataframes'])} | graphviz same={s1['graphviz']==s3['graphviz']}")
    if s1["dataframes"] and not all(dfs_same):
        for i, (a, b) in enumerate(zip(s1["dataframes"], s3["dataframes"])):
            if a.get("csv") != b.get("csv"):
                print("   df", i, "differs\n", a.get("csv")[:300], "\n---\n", b.get("csv")[:300])
    for k in diffvals:
        print("   ", k, "\n     v1:", s1["session_state"][k][:300], "\n     v3:", s3["session_state"][k][:300])

# ver3 KPI vs sum_price
def sum_price_of(step):
    for d in step["dataframes"]:
        if "제조 원가 [/MT]" in d.get("csv", ""):
            df = pd.read_csv(io.StringIO(d["csv"]), index_col=0)
            return df
for scen in ("calc_A", "calc_B"):
    s1 = [s for s in r1["steps"] if s["step"] == scen][0]
    s3 = [s for s in r3["steps"] if s["step"] == scen][0]
    sp1, sp3 = sum_price_of(s1), sum_price_of(s3)
    cost1 = float(sp1.loc["제조 원가 [/MT]"].iloc[0]); cost3 = float(sp3.loc["제조 원가 [/MT]"].iloc[0])
    kpi = [k for k in s3["kpi"] if "<style>" not in k][0]
    vals = re.findall(r'kpi-title">([^<]*)</div>\s*<div class="kpi-value">([^<]*)</div>', kpi)
    unit = [v for t, v in vals if "단위당 제조원가" in t][0]
    num = float(re.sub(r"[^0-9.]", "", unit.split(" ", 1)[1]))
    # find avg_price_df to get '비중' column sum (what the buggy design version would show)
    print(f"{scen}: v1 sum_price 제조원가/MT={cost1:,.4f}  v3 sum_price={cost3:,.4f}  v3 KPI '단위당 제조원가' text={unit!r} -> {num:,.0f}  "
          f"match(round)={round(cost3)==num}")
    print("   KPI cards:", vals)
    print("   v1 sum_price:\n", sp1.to_string())
a = sum_price_of([s for s in r1["steps"] if s["step"] == "calc_A"][0])
b = sum_price_of([s for s in r1["steps"] if s["step"] == "calc_B"][0])
print("scenario sensitivity (v1): A cost/MT", a.loc["제조 원가 [/MT]"].iloc[0], " B cost/MT", b.loc["제조 원가 [/MT]"].iloc[0])
print("labels mapping:", {k: (r1.get(k), r3.get(k)) for k in ("next_label", "submit_label", "calc_label")})
g = [s for s in r3["steps"] if s["step"] == "calc_A"][0]["graphviz"][0]
print("graphviz edges (v3, calc_A):", re.findall(r'(\d+) -> (\d+)', g)[:20])
