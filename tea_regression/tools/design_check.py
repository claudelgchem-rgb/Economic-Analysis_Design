"""A6 Design Preservation Checker: every ver2 design element must exist in ver3.

Usage: python design_check.py ver2.py ver3.py
Checks (multiset containment ver2 ⊆ ver3):
  1. CSS rules (selector + declarations) inside <style> blocks
  2. st.markdown HTML blocks (static text, whitespace-collapsed; f-string placeholders -> {…})
  3. st.set_page_config kwargs
  4. widget label + display kwargs (type, use_container_width, help, placeholder, expanded, format, width)
  5. st.column_config.* labels/format/width
  6. st.columns(...) ratios/kwargs, st.container(border=True) count, st.expander labels/expanded
  7. visual section order (section-badge titles), resolving st.container() placeholders
"""
import ast
import re
import sys
from collections import Counter

EXPECTED_CSS_CHANGES = {
    # (ver2 selector -> ver3 selector) : user-directed fix of the universal font rule
    "*": 'html, body, [class*="css"]',
}
DISPLAY_KW = {"type", "use_container_width", "help", "placeholder", "expanded", "format",
              "width", "gap", "vertical_alignment", "border", "label", "index"}
WIDGETS = {"text_input", "button", "selectbox", "number_input", "checkbox",
           "form_submit_button", "data_editor"}


def ws(s):
    return re.sub(r"\s+", " ", s).strip()


def st_name(f):
    if isinstance(f, ast.Attribute):
        if isinstance(f.value, ast.Name) and f.value.id == "st":
            return f.attr
        if isinstance(f.value, ast.Attribute) and f.value.attr == "column_config":
            return "column_config." + f.attr
    return None


def static_text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            parts.append(v.value if isinstance(v, ast.Constant) else "{…}")
        return "".join(parts)
    return None


def css_rules(text):
    m = re.search(r"<style>(.*)</style>", text, re.S)
    if not m:
        return []
    css = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
    css = re.sub(r"@import\s+url\([^)]*\)\s*;", lambda x: "@@" + ws(x.group(0)) + "{}", css)
    rules = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = tuple(ws(d) for d in body.split(";") if d.strip())
        rules.append((ws(sel), decls))
    return rules


def collect(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    info = {k: Counter() for k in ("css", "html", "page", "widgets", "colcfg", "columns",
                                   "container_border", "expander")}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        n = st_name(node.func)
        if n is None:
            continue
        kw = {k.arg: ast.unparse(k.value) for k in node.keywords if k.arg}
        if n == "markdown" and node.args:
            t = static_text(node.args[0])
            if t is None:
                continue
            if "<style>" in t:
                for r in css_rules(t):
                    info["css"][r] += 1
            else:
                info["html"][ws(t)] += 1
        elif n == "set_page_config":
            for k, v in kw.items():
                info["page"][(k, v)] += 1
        elif n in WIDGETS:
            label = static_text(node.args[0]) if node.args and n != "data_editor" else kw.get("label")
            disp = tuple(sorted((k, v) for k, v in kw.items() if k in DISPLAY_KW and k != "label"))
            info["widgets"][(n, label, disp)] += 1
        elif n.startswith("column_config."):
            label = static_text(node.args[0]) if node.args else None
            disp = tuple(sorted((k, v) for k, v in kw.items() if k in ("width", "format")))
            info["colcfg"][(n, label, disp)] += 1
        elif n == "columns":
            info["columns"][ast.unparse(node)] += 1
        elif n == "container" and kw.get("border") == "True":
            info["container_border"]["st.container(border=True)"] += 1
        elif n == "expander":
            info["expander"][(static_text(node.args[0]), kw.get("expanded"))] += 1
    info["order"] = visual_order(tree)
    return info


def badges_in(node):
    out = []
    for sub in ast.walk(node) if not isinstance(node, list) else [x for n in node for x in ast.walk(n)]:
        if isinstance(sub, ast.Call) and st_name(sub.func) == "markdown" and sub.args:
            t = static_text(sub.args[0]) or ""
            m = re.search(r'section-badge-num">([^<]*)</span>\s*<span class="section-badge-title">([^<]*)<', t)
            if m:
                out.append((sub.lineno, f"{m.group(1)} {m.group(2)}"))
    return [b for _, b in sorted(out)]


def visual_order(tree):
    slots, order = {}, []
    for s in tree.body:
        if (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
                and isinstance(s.value, ast.Call) and st_name(s.value.func) == "container"):
            slots[s.targets[0].id] = []
            order.append(slots[s.targets[0].id])
            continue
        if (isinstance(s, ast.With) and len(s.items) == 1 and isinstance(s.items[0].context_expr, ast.Name)
                and s.items[0].context_expr.id in slots):
            slots[s.items[0].context_expr.id].extend(badges_in(s.body))
            continue
        order.append(badges_in(s))
    return [b for grp in order for b in grp]


def main(v2, v3):
    a, b = collect(v2), collect(v3)
    fails = 0
    print(f"# A6 design preservation  ver2={v2}  ver3={v3}")
    for key in ("css", "html", "page", "widgets", "colcfg", "columns", "container_border", "expander"):
        missing = a[key] - b[key]
        extra = b[key] - a[key]
        notes = []
        if key == "css":
            for (sel, decls), cnt in list(missing.items()):
                if sel in EXPECTED_CSS_CHANGES and (EXPECTED_CSS_CHANGES[sel], decls) in extra:
                    notes.append(f"    (의도된 변경) selector '{sel}' -> '{EXPECTED_CSS_CHANGES[sel]}', declarations identical")
                    del missing[(sel, decls)]
                    del extra[(EXPECTED_CSS_CHANGES[sel], decls)]
        status = "PASS" if not missing else "FAIL"
        fails += bool(missing)
        print(f"\n[{status}] {key}: ver2 items={sum(a[key].values())}  ver3 items={sum(b[key].values())}  missing={sum(missing.values())}  extra={sum(extra.values())}")
        for n in notes:
            print(n)
        for item, c in missing.items():
            print(f"    MISSING x{c}: {str(item)[:300]}")
        for item, c in extra.items():
            print(f"    EXTRA   x{c}: {str(item)[:300]}")
    same = a["order"] == b["order"]
    fails += not same
    print(f"\n[{'PASS' if same else 'FAIL'}] visual section order")
    print("    ver2:", a["order"])
    print("    ver3:", b["order"])
    print("\nRESULT:", "PASS" if fails == 0 else f"FAIL ({fails} categories)")
    return fails


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
