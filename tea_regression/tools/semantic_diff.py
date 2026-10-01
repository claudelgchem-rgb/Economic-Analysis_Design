"""A1/A5 Semantic Diff: compare the non-UI statement sequence of two Streamlit scripts.

Usage: python semantic_diff.py BASE.py OTHER.py

Normalization rules (what is treated as "UI only" and ignored):
  * Expr statements calling st.markdown / st.divider / st.header / st.subheader /
    st.success / st.info / st.warning / st.caption / st.set_page_config / st.write
    (st.write calls are reported separately so their removal is visible).
  * `with` blocks whose context is pure layout (st.container(...), st.expander(...),
    a Name/Subscript holding columns/containers) are flattened: their body is inlined.
    st.form / st.spinner are NOT layout and are kept as structure.
  * Assignments whose value is st.columns(...) / st.container(...) (layout handles).
  * Widget labels (first positional arg, or label=) and the display-only kwargs
    help, placeholder, use_container_width, type, expanded, width, format, gap,
    vertical_alignment, border are stripped.  key=, value=, options, index, ... are kept.
  * st.column_config.* : label positional, width and format are stripped.
  * String constants inside st.dataframe(...) arguments (styling lambdas) are masked.
  * try-blocks whose body becomes empty after normalization are dropped.
Everything else (imports, assignments, control flow and its nesting depth) is compared.
"""
import ast
import difflib
import sys

UI_EXPR_FUNCS = {"markdown", "divider", "header", "subheader", "success", "info",
                 "warning", "caption", "set_page_config", "write"}
LAYOUT_CALLS = {"container", "expander", "columns"}
LABEL_FIRST_WIDGETS = {"text_input", "button", "selectbox", "number_input", "checkbox",
                       "form_submit_button", "expander", "toggle", "radio", "slider",
                       "text_area", "multiselect"}
DISPLAY_KWARGS = {"help", "placeholder", "use_container_width", "type", "expanded",
                  "width", "format", "gap", "vertical_alignment", "border", "label"}
COLCFG = {"TextColumn", "NumberColumn", "SelectboxColumn"}


def st_attr(node):
    """Return attribute name if node is `st.<name>` or `st.column_config.<name>`."""
    if isinstance(node, ast.Attribute):
        v = node.value
        if isinstance(v, ast.Name) and v.id == "st":
            return node.attr
        if (isinstance(v, ast.Attribute) and v.attr == "column_config"
                and isinstance(v.value, ast.Name) and v.value.id == "st"):
            return "column_config." + node.attr
    return None


def is_st_call(node, names):
    return isinstance(node, ast.Call) and st_attr(node.func) in names


class CallNormalizer(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        # f"abc" without placeholders is the same value as "abc"
        if all(isinstance(v, ast.Constant) for v in node.values):
            return ast.copy_location(ast.Constant("".join(v.value for v in node.values)), node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        self.generic_visit(node)
        name = st_attr(node.func)
        if name is None:
            return node
        if name in LABEL_FIRST_WIDGETS:
            if node.args:
                node.args = [ast.Constant("<LABEL>")] + node.args[1:]
            node.keywords = [k for k in node.keywords if k.arg not in DISPLAY_KWARGS]
        elif name.startswith("column_config.") and name.split(".")[1] in COLCFG:
            node.args = []
            node.keywords = [k for k in node.keywords if k.arg not in ("width", "format", "label")]
        elif name in ("data_editor", "dataframe", "graphviz_chart"):
            node.keywords = [k for k in node.keywords if k.arg not in DISPLAY_KWARGS]
            if name == "dataframe":
                for a in node.args:
                    for sub in ast.walk(a):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            sub.value = "<STYLE>"
        return node


def is_layout_with(item):
    ctx = item.context_expr
    if is_st_call(ctx, LAYOUT_CALLS):
        return True
    if isinstance(ctx, (ast.Name, ast.Subscript)):
        return True
    return False


def normalize_body(stmts, writes, depth_path):
    out = []
    for s in stmts:
        out.extend(normalize_stmt(s, writes, depth_path))
    return out


def normalize_stmt(s, writes, path):
    # UI-only expression statements
    if isinstance(s, ast.Expr):
        if isinstance(s.value, ast.Constant):
            return []
        if is_st_call(s.value, UI_EXPR_FUNCS):
            if st_attr(s.value.func) == "write":
                writes.append((s.lineno, ast.unparse(s)))
            return []
    # layout handle assignments
    if isinstance(s, ast.Assign) and is_st_call(s.value, {"columns", "container"}):
        return []
    if isinstance(s, ast.With):
        if all(is_layout_with(it) for it in s.items):
            return normalize_body(s.body, writes, path)
        s.body = normalize_body(s.body, writes, path) or [ast.Pass()]
        return [s]
    if isinstance(s, (ast.If, ast.For, ast.While)):
        s.body = normalize_body(s.body, writes, path) or [ast.Pass()]
        s.orelse = normalize_body(s.orelse, writes, path)
        return [s]
    if isinstance(s, ast.Try):
        s.body = normalize_body(s.body, writes, path)
        if not s.body:
            return []
        for h in s.handlers:
            h.body = normalize_body(h.body, writes, path) or [ast.Pass()]
        s.orelse = normalize_body(s.orelse, writes, path)
        s.finalbody = normalize_body(s.finalbody, writes, path)
        return [s]
    if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
        s.body = normalize_body(s.body, writes, path) or [ast.Pass()]
        return [s]
    return [s]


def header(s):
    if isinstance(s, ast.If):
        return f"if {ast.unparse(s.test)}:"
    if isinstance(s, ast.For):
        return f"for {ast.unparse(s.target)} in {ast.unparse(s.iter)}:"
    if isinstance(s, ast.While):
        return f"while {ast.unparse(s.test)}:"
    if isinstance(s, ast.With):
        return "with " + ", ".join(ast.unparse(i) for i in s.items) + ":"
    if isinstance(s, ast.Try):
        return "try:"
    if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
        decos = "".join("@" + ast.unparse(d) + " " for d in s.decorator_list)
        return f"{decos}def {s.name}({ast.unparse(s.args)}):"
    return None


def emit(stmts, depth, lines):
    for s in stmts:
        h = header(s)
        if h is None:
            lines.append((getattr(s, "lineno", 0), depth, ast.unparse(s).replace("\n", " ")))
            continue
        lines.append((s.lineno, depth, h))
        emit(s.body, depth + 1, lines)
        if isinstance(s, ast.Try):
            for hd in s.handlers:
                t = "except" + (f" {ast.unparse(hd.type)}" if hd.type else "") + ":"
                lines.append((hd.lineno, depth, t))
                emit(hd.body, depth + 1, lines)
            if s.finalbody:
                lines.append((s.finalbody[0].lineno, depth, "finally:"))
                emit(s.finalbody, depth + 1, lines)
        if getattr(s, "orelse", None):
            first = s.orelse[0]
            if isinstance(s, ast.If) and len(s.orelse) == 1 and isinstance(first, ast.If) \
                    and getattr(first, "_elif", False):
                pass
            lines.append((getattr(first, "lineno", 0), depth, "else:"))
            emit(s.orelse, depth + 1, lines)


def analyze(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    tree = CallNormalizer().visit(tree)
    writes = []
    body = normalize_body(tree.body, writes, [])
    lines = []
    emit(body, 0, lines)
    return lines, writes


def main(a, b):
    la, wa = analyze(a)
    lb, wb = analyze(b)
    ta = [f"{'    ' * d}{t}" for _, d, t in la]
    tb = [f"{'    ' * d}{t}" for _, d, t in lb]
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    n_diff = 0
    print(f"# semantic diff  BASE={a}  OTHER={b}")
    print(f"# normalized non-UI statements: BASE={len(ta)}  OTHER={len(tb)}")
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        n_diff += 1
        print(f"\n## HUNK {n_diff}: {tag}  BASE[{i1}:{i2}]  OTHER[{j1}:{j2}]")
        for k in range(i1, i2):
            print(f"- L{la[k][0]:>4} | {ta[k]}")
        for k in range(j1, j2):
            print(f"+ L{lb[k][0]:>4} | {tb[k]}")
    print(f"\n# TOTAL NON-UI HUNKS: {n_diff}")
    print("\n# st.write calls (reported separately; treated as UI/debug output)")
    sa = [w for _, w in wa]
    sb = [w for _, w in wb]
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=sa, b=sb, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                print(f"  = BASE L{wa[k][0]} / OTHER L{wb[j1 + k - i1][0]} | {sa[k]}")
        else:
            for k in range(i1, i2):
                print(f"  - BASE L{wa[k][0]} | {sa[k]}")
            for k in range(j1, j2):
                print(f"  + OTHER L{wb[k][0]} | {sb[k]}")
    print("\nRESULT:", "PASS (non-UI sequence identical)" if n_diff == 0 else f"DIFF ({n_diff} hunks)")
    return n_diff


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
