"""A7 independent AST-based static comparator (ver1 vs ver3).

Normalisation (only the ALLOWED differences are erased):
  * st.markdown / st.divider / st.success / st.info / st.header / st.subheader /
    st.set_page_config  -> removed (pure display); recorded in a side list
  * st.write(...)  -> removed, recorded with its args (so we can see removed debug writes
    and whether any arg had a side-effecting call)
  * `with <layout>:` (st.container / st.expander / st.columns element / names bound to
    st.container()/st.columns()) -> unwrapped (body inlined, source order kept, which is
    also execution order)
  * assignments whose value is st.columns(...) / st.container(...) -> removed
  * widget calls: first positional (label) dropped and display kwargs dropped
    (help, placeholder, use_container_width, type, format, width, gap,
     vertical_alignment, expanded, label); column_config.* labels/width/format dropped
Everything else is compared with ast.dump (no line numbers) as a flat pre-order
sequence of (depth, statement-header) and diffed with difflib.
"""
import ast, sys, difflib, json

DISPLAY_CALLS = {"markdown", "divider", "success", "info", "header", "subheader",
                 "set_page_config", "caption"}
LAYOUT_CALLS = {"container", "expander", "columns"}
WIDGETS = {"button", "selectbox", "number_input", "text_input", "checkbox", "data_editor",
           "form_submit_button", "TextColumn", "NumberColumn", "SelectboxColumn",
           "dataframe", "graphviz_chart"}
DISPLAY_KW = {"help", "placeholder", "use_container_width", "type", "format", "width",
              "gap", "vertical_alignment", "expanded", "label", "initial_sidebar_state"}


def st_attr(call):
    """return attr name if call is st.X(...) or st.column_config.X(...) or <x>.map/style chain"""
    f = call.func
    if isinstance(f, ast.Attribute):
        v = f.value
        if isinstance(v, ast.Name) and v.id == "st":
            return f.attr
        if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id == "st" and v.attr == "column_config":
            return f.attr
    return None


class Norm(ast.NodeTransformer):
    def __init__(self, tag):
        self.tag = tag
        self.layout_names = set()
        self.removed = []  # (lineno, kind, src)

    # --- calls inside expressions: strip labels / display kwargs
    def visit_Call(self, node):
        self.generic_visit(node)
        a = st_attr(node)
        if a in WIDGETS:
            # drop label positional only for widgets that have one
            if a not in ("data_editor", "dataframe", "graphviz_chart") and node.args and isinstance(node.args[0], (ast.Constant, ast.JoinedStr)):
                node.args = node.args[1:]
            node.keywords = [k for k in node.keywords if k.arg not in DISPLAY_KW]
        # style.map(lambda v: 'css') -> css string is display
        if isinstance(node.func, ast.Attribute) and node.func.attr == "map" and node.args and isinstance(node.args[0], ast.Lambda):
            node.args = [ast.Constant("<css-lambda>")]
        # sum_price.style.format(...) is display; keep but neutral
        return node

    def _is_layout_expr(self, e):
        if isinstance(e, ast.Call) and st_attr(e) in LAYOUT_CALLS:
            return True
        if isinstance(e, ast.Name) and e.id in self.layout_names:
            return True
        if isinstance(e, ast.Subscript):
            return self._is_layout_expr(e.value)
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) is False and st_attr(e) == "form":
            return False
        return False

    def stmts(self, body):
        out = []
        for s in body:
            r = self.stmt(s)
            out.extend(r)
        return out

    def stmt(self, s):
        src = ast.get_source_segment(self.source, s) or ""
        # expression statement with st display call / st.write
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
            a = st_attr(s.value)
            if a in DISPLAY_CALLS:
                self.removed.append((s.lineno, a, src.split("\n")[0][:110]))
                return []
            if a == "write":
                self.removed.append((s.lineno, "write", src[:140]))
                return []
        # layout assignment
        if isinstance(s, ast.Assign) and isinstance(s.value, ast.Call) and st_attr(s.value) in LAYOUT_CALLS:
            for t in s.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        self.layout_names.add(n.id)
            if not isinstance(s.value.func, ast.Attribute) or True:
                # dict comprehension of columns (sol_ui) is NOT a plain call -> kept
                self.removed.append((s.lineno, "layout-assign", src.split("\n")[0][:110]))
                return []
        if isinstance(s, ast.Assign) and isinstance(s.value, ast.DictComp):
            # sol_ui = {..: st.columns(4)}  -> layout
            if isinstance(s.value.value, ast.Call) and st_attr(s.value.value) == "columns":
                for t in s.targets:
                    if isinstance(t, ast.Name):
                        self.layout_names.add(t.id)
                self.removed.append((s.lineno, "layout-assign", src.split("\n")[0][:110]))
                return []
        if isinstance(s, ast.With) and all(self._is_layout_expr(it.context_expr) for it in s.items):
            return self.stmts(s.body)
        # recurse into compound statements
        for field in ("body", "orelse", "finalbody"):
            if hasattr(s, field) and isinstance(getattr(s, field), list):
                setattr(s, field, self.stmts(getattr(s, field)))
        if isinstance(s, ast.Try):
            for h in s.handlers:
                h.body = self.stmts(h.body)
        if isinstance(s, (ast.If, ast.While)):
            s.test = self.visit(s.test)
        elif isinstance(s, ast.For):
            s.iter = self.visit(s.iter); s.target = self.visit(s.target)
        elif isinstance(s, ast.With):
            for it in s.items:
                it.context_expr = self.visit(it.context_expr)
        elif isinstance(s, (ast.Try, ast.FunctionDef)):
            pass
        else:
            s = self.visit(s)
        return [s]


def flatten(body, depth=0, out=None):
    out = [] if out is None else out
    for s in body:
        hdr = s
        if isinstance(s, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef)):
            c = ast.copy_location(type(s)(**{f: getattr(s, f) for f in s._fields}), s)
            for f in ("body", "orelse", "finalbody", "handlers"):
                if hasattr(c, f):
                    setattr(c, f, [])
            key = ast.dump(c, include_attributes=False)
            out.append((depth, key, s.lineno, ast.unparse(c).split("\n")[0]))
            flatten(s.body, depth + 1, out)
            if isinstance(s, ast.Try):
                for h in s.handlers:
                    out.append((depth, "except:" + ast.dump(h.type) if h.type else "except:", h.lineno, "except"))
                    flatten(h.body, depth + 1, out)
            if getattr(s, "orelse", None):
                out.append((depth, "else", s.orelse[0].lineno, "else:"))
                flatten(s.orelse, depth + 1, out)
            if isinstance(s, ast.FunctionDef):
                pass
        else:
            out.append((depth, ast.dump(s, include_attributes=False), s.lineno, ast.unparse(s).split("\n")[0][:120]))
    return out


def load(path, tag):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    n = Norm(tag)
    n.source = src
    body = n.stmts(tree.body)
    # decorators: keep
    return flatten(body), n.removed


def main(a, b):
    fa, ra = load(a, "v1")
    fb, rb = load(b, "v3")
    ka = [f"{d}|{k}" for d, k, _, _ in fa]
    kb = [f"{d}|{k}" for d, k, _, _ in fb]
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    diffs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        diffs.append({"op": op,
                      "v1": [(fa[i][2], "  " * fa[i][0] + fa[i][3]) for i in range(i1, i2)],
                      "v3": [(fb[j][2], "  " * fb[j][0] + fb[j][3]) for j in range(j1, j2)]})
    print(f"normalised statements: v1={len(fa)} v3={len(fb)}  non-equal blocks={len(diffs)}")
    for d in diffs:
        print("=" * 100)
        print("OP", d["op"])
        for ln, t in d["v1"]:
            print(f"  v1 L{ln:<4} {t}")
        for ln, t in d["v3"]:
            print(f"  v3 L{ln:<4} {t}")
    print("\n#### removed/display-only statements v1")
    for r in ra:
        print("  v1", r)
    print("\n#### removed/display-only statements v3")
    for r in rb:
        print("  v3", r)
    # order of side-effecting helper calls (statically, pre-order)
    def calls(path):
        t = ast.parse(open(path, encoding="utf-8").read())
        seq = []
        for node in ast.walk(t):
            pass
        class V(ast.NodeVisitor):
            def visit_Call(self, n):
                self.generic_visit(n)
                f = n.func
                name = f.id if isinstance(f, ast.Name) else (ast.unparse(f) if isinstance(f, ast.Attribute) else None)
                if name and not name.startswith("st.") and not name.startswith("pd.") and not name.startswith("np.") and name not in ("float","int","list","dict","str","zip","len","range","enumerate","max","open","type"):
                    seq.append((n.lineno, name))
        V().visit(t)
        return seq
    ca = [c for c in calls(a)]
    cb = [c for c in calls(b)]
    na = [n for _, n in ca]
    nb = [n for _, n in cb]
    print("\n#### non-st call sequence identical (source order):", na == nb)
    if na != nb:
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, na, nb, autojunk=False).get_opcodes():
            if op != "equal":
                print(op, ca[i1:i2], cb[j1:j2])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
