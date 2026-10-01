"""A7 recording stubs for pages.flow_tabs.* helpers (shared by ver1 and ver3 runs).

Every helper call is appended to the JSON-lines log at $A7_LOG as
{"fn": name, "args": deterministic-repr}.  Helpers build a REAL biosteam
system (biosteam 2.51) from the flow nodes/edges, so graphviz topology,
installed cost, utilities and feed costs are genuine biosteam numbers.
"""
import os, json
import numpy as np
import pandas as pd
import streamlit as st
import biosteam as bst
import thermosteam as tmo

__all__ = ["process_chemical_data", "initialize_flowstate", "upload_chemical", "fill_water3",
           "get_node_feature", "add_node", "delete_node", "sf_tmp", "edit_node",
           "get_node_editor_functions", "session_state_to_spec_data", "get_batch_time",
           "run_biosteam2", "scale_up_system", "price_system", "get_chem_price",
           "get_c_source", "chem_dict_to_pd"]

LOG = os.environ.get("A7_LOG", "/tmp/claude-0/a7/default.log")


def srepr(x, d=0):
    if d > 6:
        return "..."
    if isinstance(x, pd.DataFrame):
        return "DF" + x.round(10).to_json(orient="split", force_ascii=False)
    if isinstance(x, pd.Series):
        return "SER" + x.to_json(force_ascii=False)
    if isinstance(x, dict):
        return "{" + ", ".join(f"{srepr(k, d+1)}: {srepr(v, d+1)}" for k, v in x.items()) + "}"
    if isinstance(x, (list, tuple)):
        return ("[" if isinstance(x, list) else "(") + ", ".join(srepr(v, d+1) for v in x) + ("]" if isinstance(x, list) else ")")
    if isinstance(x, float):
        return repr(round(x, 9))
    if isinstance(x, (np.floating,)):
        return repr(round(float(x), 9))
    if isinstance(x, bst.System):
        return f"<System {x.ID} units={[u.ID for u in x.units]}>"
    if isinstance(x, (bst.Stream,)):
        return f"<Stream {x.ID} {srepr(dict(zip(x.chemicals.IDs, [round(float(v), 9) for v in x.mass])))}>"
    if hasattr(x, "nodes") and hasattr(x, "edges"):
        return f"<FlowState nodes={srepr([(n.id, n.data) for n in x.nodes])} edges={[(e.source, e.target) for e in x.edges]}>"
    if hasattr(x, "IDs"):
        return f"<Chemicals {list(x.IDs)}>"
    if callable(x) and hasattr(x, "__name__"):
        return f"<fn {x.__name__}>"
    return repr(x)


def log(fn, *args, **kw):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"fn": fn, "args": srepr(list(args)), "kw": srepr(kw)}, ensure_ascii=False) + "\n")


# ---- monkeypatch real biosteam entry points so their calls are logged too (harness only)
if not getattr(bst, "_a7_patched", False):
    _orig_clear = bst.main_flowsheet.clear
    _orig_create = bst.main_flowsheet.create_system
    _orig_sim = bst.System.simulate

    def _clear(*a, **k):
        log("bst.main_flowsheet.clear")
        return _orig_clear(*a, **k)

    def _create(ID=None, *a, **k):
        log("bst.main_flowsheet.create_system", ID)
        return _orig_create(ID, *a, **k)

    def _sim(self, *a, **k):
        log("System.simulate", self.ID, [u.ID for u in self.units])
        return _orig_sim(self, *a, **k)

    bst.main_flowsheet.clear = _clear
    bst.main_flowsheet.create_system = _create
    bst.System.simulate = _sim
    bst._a7_patched = True


def process_chemical_data(df):
    log("process_chemical_data", df)
    chems = []
    for name in df["Name"]:
        try:
            c = tmo.Chemical(name)
        except Exception:
            c = tmo.Chemical(name, search_ID="Glucose")
        chems.append(c)
    tmo.settings.set_thermo(chems, cache=True)
    chem_data = df.copy()
    chem_data.index = list(df["Name"])
    return tmo.settings.chemicals, chem_data


def initialize_flowstate():
    log("initialize_flowstate")


def upload_chemical():
    log("upload_chemical")


def fill_water3(sol, vol):
    log("fill_water3", sol, vol)
    sol = {k: float(v) for k, v in sol.items() if k != "Water"}
    sol["Water"] = 1000.0 * vol - sum(sol.values())
    return sol


def get_node_feature():
    log("get_node_feature")
    return {"배치 피드": {}, "발효기": {}, "분배기": {}, "원심분리기": {}, "Mix-Tank": {}, "Product Stream": {}}


def add_node(t):
    log("add_node", t)


def delete_node(i):
    log("delete_node", i)


def sf_tmp(key, state):
    log("sf_tmp", key, state)
    state.selected_id = None
    return state


def edit_node(node):
    log("edit_node", node.id)
    return {"content": node.data["content"], "Value": node.data["Value"]}


def get_node_editor_functions(t):
    log("get_node_editor_functions", t)
    return None, (lambda v: v)


def session_state_to_spec_data(input_unit, nodes):
    log("session_state_to_spec_data", input_unit, nodes)
    st.session_state.spec_data = {nid: {**input_unit.get(n["node_type"], {}), **n.get("Value", {})} for nid, n in nodes.items()}


def get_batch_time(nodes):
    log("get_batch_time", nodes)
    return 27.0


def _topo(nodes, edges):
    indeg = {n: 0 for n in nodes}
    for s, ts in edges.items():
        for t in ts:
            indeg[t] += 1
    order, q = [], [n for n in nodes if indeg[n] == 0]
    while q:
        n = q.pop(0); order.append(n)
        for t in edges.get(n, []):
            indeg[t] -= 1
            if indeg[t] == 0:
                q.append(t)
    return order


def run_biosteam2(nodes, edges, solutions, feat_data, batch_time):
    log("run_biosteam2", nodes, edges, solutions, feat_data, batch_time)
    autoclave, sols, prices = solutions
    preds = {n: [] for n in nodes}
    for s, ts in edges.items():
        for t in ts:
            preds[t].append(s)
    outs = {}  # (src, dst) -> stream
    units = []
    for nid in _topo(nodes, edges):
        d = nodes[nid]; t = d["node_type"]
        ins = [outs[(p, nid)] for p in preds[nid]]
        nxt = edges.get(nid, [])
        if t == "배치 피드":
            sol = sols[d["Value"]["solution"]]
            s = bst.Stream(f"feed_{nid}", T=298.15, units="kg/hr", **{k: v for k, v in sol.items()})
            for x in nxt:
                outs[(nid, x)] = s
            continue
        if t == "발효기":
            u = bst.MixTank(nid, ins=ins, tau=batch_time)
        elif t == "분배기":
            u = bst.Splitter(nid, ins=ins, outs=[f"{nid}_{i}" for i in range(len(nxt))][:2], split=0.5)
        elif t == "원심분리기":
            u = bst.StorageTank(nid, ins=ins, tau=4)
        elif t == "Mix-Tank":
            u = bst.Mixer(nid, ins=ins)
        elif t == "Product Stream":
            ins[0].ID = "product"
            continue
        else:
            raise ValueError(t)
        units.append(u)
        if t == "발효기":
            hx = bst.HXutility(nid + "_HX", ins=u - 0, T=310.15)
            pump = bst.Pump(nid + "_P", ins=hx - 0)
            units += [hx, pump]
            src = pump
        else:
            src = u
        for i, x in enumerate(nxt):
            outs[(nid, x)] = src.outs[i] if len(src.outs) > i else src.outs[0]
    sys = bst.System.from_units("ferm_tmp", units)
    return sys


def scale_up_system(sys, main_product, target_amount, nodes):
    log("scale_up_system", sys, main_product, target_amount, nodes)
    hours = float(st.session_state.operating_hours)
    for s in sys.feeds:
        cur = s.imass[main_product]
        if cur > 0:
            f = target_amount / (cur * hours)
            break
    else:
        f = 1.0
    for s in sys.feeds:
        s.mass[:] *= f
    return sys


def price_system(sys):
    log("price_system", sys)
    cd = st.session_state.chem_data
    for s in sys.feeds:
        cost = sum(float(cd["Price (USD/kg)"][c]) * float(m) for c, m in zip(s.chemicals.IDs, s.mass))
        s.price = cost / s.F_mass if s.F_mass else 0
    return sys


def get_chem_price(ins):
    log("get_chem_price", [s for s in ins])
    tot = {}
    for s in ins:
        if s.source is None:
            for c, m in zip(s.chemicals.IDs, s.mass):
                if m:
                    tot[c] = tot.get(c, 0.0) + float(m)
    return tot


def get_c_source(total, source):
    log("get_c_source", total, source)
    c = {k: v for k, v in total.items() if k in source}
    up = {k: v for k, v in total.items() if k not in source}
    return up, c


def chem_dict_to_pd(d, target_amount):
    log("chem_dict_to_pd", d, target_amount)
    hours = float(st.session_state.operating_hours)
    cd = st.session_state.chem_data
    rows = {}
    for k, v in d.items():
        unit = v * hours / target_amount
        price = float(cd["Price (USD/kg)"][k])
        rows[k] = [unit, price, unit * price * 1000]
    return pd.DataFrame.from_dict(rows, orient="index", columns=["원단위", "단가", "제조원가"]) if rows else pd.DataFrame(columns=["원단위", "단가", "제조원가"], dtype=float)
