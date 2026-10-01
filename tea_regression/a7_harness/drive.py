"""A7 AppTest driver. usage: drive.py <script.py> <tag>
Writes /tmp/claude-0/a7/out/<tag>.json (results) and <tag>.log (helper-call log)."""
import os, sys, json, io, traceback
OUT = "/tmp/claude-0/a7/out"
os.makedirs(OUT, exist_ok=True)
script, tag = sys.argv[1], sys.argv[2]
os.environ["A7_LOG"] = f"{OUT}/{tag}.log"
open(os.environ["A7_LOG"], "w").close()
sys.path.insert(0, "/tmp/claude-0/a7/env")

import pyarrow as pa
import pandas as pd
from streamlit.testing.v1 import AppTest
from streamlit.proto.WidgetStates_pb2 import WidgetState
from streamlit.testing.v1.element_tree import UnknownElement
import a7_stubcore as core

res = {"steps": []}


def mark(name):
    core.log("=== STEP " + name)


def walk(node):
    yield node
    for c in getattr(node, "children", {}).values():
        yield from walk(c)


def snapshot(at, name):
    snap = {"step": name, "exceptions": [str(e.value) for e in at.exception],
            "buttons": [b.label for b in at.button],
            "dataframes": [], "graphviz": [], "kpi": [], "markdown_n": len(at.markdown)}
    for el in walk(at._tree):
        if True:
            if type(el).__name__ == "Dataframe":
                try:
                    df = el.value
                    disp = ""
                    try:
                        from streamlit import dataframe_util as du
                        sty = el.proto.arrow_data.styler
                        if sty.display_values:
                            disp = du.convert_arrow_bytes_to_pandas_df(sty.display_values).to_csv()
                    except Exception as e:
                        disp = "ERR" + repr(e)
                    snap["dataframes"].append({"id": el.proto.id[-40:] if el.proto.id else "", "editable": bool(el.proto.id),
                                               "csv": df.to_csv(), "display": disp})
                except Exception as e:
                    snap["dataframes"].append({"err": repr(e)})
            elif getattr(el, "type", None) == "graphviz_chart":
                snap["graphviz"].append(el.proto.spec)
    for m in at.markdown:
        if "kpi-container" in m.value:
            snap["kpi"].append(m.value)
    ss = {}
    for k in at.session_state._state._state.filtered_state.keys() if hasattr(at.session_state._state, "_state") else []:
        pass
    try:
        state = at.session_state._state.filtered_state
    except Exception:
        state = {}
    for k, v in state.items():
        ss[str(k)] = core.srepr(v)[:4000]
    snap["session_state"] = ss
    res["steps"].append(snap)
    return snap


def find_button(at, *subs):
    for b in at.button:
        if any(s in b.label for s in subs):
            return b
    raise KeyError(f"button {subs} not found among {[b.label for b in at.button]}")


def editor_id(at, key):
    for el in walk(at._tree):
        if type(el).__name__ == "Dataframe" and el.proto.id and el.proto.id.endswith(key):
            return el.proto.id
    raise KeyError(key)


try:
    at = AppTest.from_file(script, default_timeout=600)
    mark("initial")
    at.run(); snapshot(at, "initial")
    mark("next")
    b = find_button(at, "다음"); res["next_label"] = b.label
    b.click().run(); snapshot(at, "after_next")
    mark("num_sol")
    at.number_input(key="num_sol").set_value(1).run(); snapshot(at, "num_sol")
    for scen, conc in (("A", 50.0), ("B", 150.0)):
        mark("submit_" + scen)
        sb = find_button(at, "용액 저장"); res["submit_label"] = sb.label
        sb.click()
        ws = at._tree.get_widget_states()
        de = editor_id(at, "용액 1_solution")
        w = WidgetState(); w.id = de
        # row 0 of the editor is 'Glucose' (dict order of the stored solution)
        w.string_value = json.dumps({"edited_rows": {"0": {"Concentration [g/L]": conc}}, "added_rows": [], "deleted_rows": []})
        ws.widgets.append(w)
        at._run(ws)
        snapshot(at, "submitted_" + scen)
        mark("calc_" + scen)
        cb = find_button(at, "Calculate", "Run BioSTEAM"); res["calc_label"] = cb.label
        cb.click().run(); snapshot(at, "calc_" + scen)
    mark("detail_감가비")
    at.selectbox[-1].set_value("감가비").run(); snapshot(at, "detail_감가비")
    mark("detail_발효 원재료")
    at.selectbox[-1].set_value("발효 원재료").run(); snapshot(at, "detail_발효원재료")
    mark("gmp_off")
    at.checkbox(key="gmp").uncheck().run(); snapshot(at, "gmp_off")
    mark("load")
    find_button(at, "Load data", "불러오기").click().run(); snapshot(at, "after_load")
    find_button(at, "Calculate", "Run BioSTEAM").click().run(); snapshot(at, "calc_after_load")
except Exception:
    res["fatal"] = traceback.format_exc()
json.dump(res, open(f"{OUT}/{tag}.json", "w"), ensure_ascii=False, indent=1)
print("done", tag, "fatal" in res)
