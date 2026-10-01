#!/usr/bin/env python3
"""diag_tea.py - TEA-Regression Loop A2 진단 스크립트 (읽기 전용)

economics_ver1 -> economics_ver2 회귀의 '실행 환경 의존' 가설(H1~H3)을 판정하기 위한 정보를 출력한다.
  H1: mock_biosteam.setup_biosteam_fallback() 이 실제 biosteam 을 대체/패치하는가
  H2: pages.flow_tabs 대신 flow_tabs.* 사본이 import 되는가, 사본의 함수가 다른가
  H3: base_dir fallback 으로 다른 data/initial_val.json·pkl 을 읽는가

실행 방법 (streamlit 을 실행하는 것과 같은 파이썬 / 같은 작업 디렉터리에서):
    python diag_tea.py --page pages/economics_ver2.py > diag_out.txt 2>&1
옵션:
    --page      economics_ver2.py 경로 (기본: 작업 디렉터리 아래에서 자동 탐색)
    --app-root  `streamlit run <메인파일>` 의 메인파일이 있는 디렉터리 (기본: 작업 디렉터리)
    --max-diff  모듈 전체 diff 출력 최대 줄 수 (기본 400)

읽기 전용 보장:
  * 어떤 파일도 쓰거나 수정/삭제하지 않는다 (open 은 모두 'rb'/'r').
  * 모듈 import 는 별도 하위 프로세스에서만 하며, PYTHONDONTWRITEBYTECODE=1 로 __pycache__ 생성을 막는다.
  * numba 캐시는 시스템 임시 디렉터리(tempfile)로 돌린다 (사용자 파일 아님).
  * pickle 은 사용자의 자체 데이터 파일(initial_val.pkl)만, 하위 프로세스에서 읽는다.
"""
import argparse
import ast
import difflib
import hashlib
import importlib.metadata as md
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

HARDCODED_BASE_DIR = '/home/sbf/JLee/test/data/scenario/'
FLOW_MODULES = ['Biosteam_custom_unit', 'aux_chemical', 'util_bfd_Copy3', 'util_biosteam_Copy1']
KEY_FUNCS = ['run_biosteam2', 'scale_up_system', 'price_system', 'get_batch_time',
             'session_state_to_spec_data', 'get_chem_price', 'get_c_source', 'chem_dict_to_pd',
             'fill_water3', 'process_chemical_data', 'upload_chemical', 'sf_tmp', 'add_node',
             'delete_node', 'initialize_flowstate', 'edit_node', 'get_node_editor_functions',
             'get_node_feature']
DISTS = ['streamlit', 'biosteam', 'thermosteam', 'streamlit-flow-component', 'streamlit_flow',
         'streamlit-flow', 'pandas', 'numpy', 'graphviz', 'numba', 'chemicals', 'thermo']


def hr(title):
    print('\n' + '=' * 100)
    print(title)
    print('=' * 100, flush=True)


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def finfo(path):
    if not os.path.isfile(path):
        return 'MISSING'
    st = os.stat(path)
    return f"md5={md5(path)} size={st.st_size} mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}"


def read_text(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


# --------------------------------------------------------------------------------------------
# Sub-process probe (all imports happen here, never in the main process)
# --------------------------------------------------------------------------------------------
PROBE = r'''
import sys, os, json, inspect, traceback, importlib
sys.dont_write_bytecode = True
args = json.loads(sys.argv[1])
for p in reversed(args.get("roots", [])):
    if p not in sys.path:
        sys.path.insert(0, p)
out = {"sys_path_head": sys.path[:6], "steps": []}

def bst_snapshot(tag):
    snap = {"tag": tag}
    try:
        import biosteam as bst
        snap["module_obj"] = repr(bst)
        snap["__file__"] = getattr(bst, "__file__", None)
        snap["__version__"] = getattr(bst, "__version__", None)
        pkg_dir = os.path.dirname(os.path.abspath(bst.__file__)) if getattr(bst, "__file__", None) else None
        snap["Unit"] = repr(getattr(bst, "Unit", None))
        snap["Unit.__module__"] = getattr(getattr(bst, "Unit", None), "__module__", None)
        try:
            snap["Unit_sourcefile"] = inspect.getsourcefile(bst.Unit)
        except Exception as e:
            snap["Unit_sourcefile"] = "ERR " + repr(e)
        snap["System"] = repr(getattr(bst, "System", None))
        snap["System.__module__"] = getattr(getattr(bst, "System", None), "__module__", None)
        snap["main_flowsheet"] = repr(type(getattr(bst, "main_flowsheet", None)))
        snap["PowerUtility.price"] = repr(getattr(getattr(bst, "PowerUtility", None), "price", None))
        snap["CE"] = repr(getattr(bst, "CE", None))
        snap["id_Unit"] = id(getattr(bst, "Unit", None))
        snap["id_System"] = id(getattr(bst, "System", None))
        snap["sys_modules_biosteam_count"] = sum(1 for k in sys.modules if k == "biosteam" or k.startswith("biosteam."))
        snap["sys_modules_biosteam_file"] = getattr(sys.modules.get("biosteam"), "__file__", None)
        # monkey-patch detection: code objects whose file is outside the biosteam package dir
        patched = {}
        targets = {
            "Unit.simulate": ("Unit", "simulate"), "Unit._summary": ("Unit", "_summary"),
            "Unit.results": ("Unit", "results"), "System.simulate": ("System", "simulate"),
            "System.diagram": ("System", "diagram"), "Flowsheet.create_system": ("Flowsheet", "create_system"),
            "Flowsheet.clear": ("Flowsheet", "clear"),
        }
        for name, (cls, attr) in targets.items():
            try:
                fn = getattr(getattr(bst, cls), attr)
                code = getattr(fn, "__code__", None) or getattr(getattr(fn, "__func__", None), "__code__", None)
                f = code.co_filename if code else None
                patched[name] = {"file": f, "qualname": getattr(fn, "__qualname__", None),
                                 "outside_pkg": (pkg_dir is not None and f is not None and not os.path.abspath(f).startswith(pkg_dir))}
            except Exception as e:
                patched[name] = {"error": repr(e)}
        for name, prop in (("Unit.installed_cost", ("Unit", "installed_cost")), ("System.installed_cost", ("System", "installed_cost"))):
            try:
                pr = inspect.getattr_static(getattr(bst, prop[0]), prop[1])
                fget = getattr(pr, "fget", None)
                f = fget.__code__.co_filename if fget else None
                patched[name] = {"file": f, "outside_pkg": (pkg_dir is not None and f is not None and not os.path.abspath(f).startswith(pkg_dir))}
            except Exception as e:
                patched[name] = {"error": repr(e)}
        snap["method_origins"] = patched
        try:
            import thermosteam as tmo
            snap["thermosteam_file"] = getattr(tmo, "__file__", None)
            snap["thermosteam_version"] = getattr(tmo, "__version__", None)
        except Exception as e:
            snap["thermosteam_error"] = repr(e)
        # micro-simulation: real costing must give installed_cost > 0 and respond to flow
        try:
            import thermosteam as tmo
            tmo.settings.set_thermo(["Water", "Glucose"], cache=True)
            res = []
            for kg in (1000.0, 2000.0):
                bst.main_flowsheet.clear()
                s = bst.Stream("diag_feed", Water=kg, Glucose=kg * 0.05, units="kg/hr")
                u = bst.units.MixTank("diag_T1", ins=s, tau=12)
                u.simulate()
                res.append({"feed_kg_hr": kg, "installed_cost": float(u.installed_cost), "F_vol_out": float(u.outs[0].F_vol)})
            snap["micro_sim"] = res
        except Exception as e:
            snap["micro_sim"] = "ERR " + repr(e)
    except Exception as e:
        snap["import_error"] = "".join(traceback.format_exception_only(type(e), e)).strip()
    return snap

def call_mock():
    st = {"tag": "setup_biosteam_fallback()"}
    try:
        m = importlib.import_module("mock_biosteam")
        st["mock_file"] = getattr(m, "__file__", None)
        r = m.setup_biosteam_fallback()
        st["return"] = repr(r)
        st["ok"] = True
    except Exception as e:
        st["ok"] = False
        st["exception_swallowed_by_ver2"] = "".join(traceback.format_exception(type(e), e, e.__traceback__))[-3000:]
    st["sys_modules_with_mock_in_name"] = sorted(k for k in sys.modules if "mock" in k.lower())[:50]
    return st

def try_import(modname):
    r = {"module": modname}
    try:
        m = importlib.import_module(modname)
        r["ok"] = True
        r["__file__"] = getattr(m, "__file__", None)
        r["defines"] = {f: (getattr(getattr(m, f, None), "__module__", None)) for f in args.get("key_funcs", []) if hasattr(m, f)}
    except ModuleNotFoundError as e:
        r["ok"] = False
        r["ModuleNotFoundError.name"] = e.name
        r["error"] = "".join(traceback.format_exception(type(e), e, e.__traceback__))[-2500:]
    except Exception as e:
        r["ok"] = False
        r["error"] = "".join(traceback.format_exception(type(e), e, e.__traceback__))[-2500:]
    return r

mode = args["mode"]
if mode == "real_only":
    out["steps"].append(bst_snapshot("import biosteam (ver1 order, no mock)"))
elif mode == "ver2_order":
    out["steps"].append(call_mock())
    out["steps"].append(bst_snapshot("import biosteam AFTER setup_biosteam_fallback (ver2 order)"))
elif mode == "shared_process":
    out["steps"].append(bst_snapshot("import biosteam first (another page already imported it)"))
    out["steps"].append(call_mock())
    out["steps"].append(bst_snapshot("after setup_biosteam_fallback in same process"))
elif mode == "flow_import_plain":
    for mod in args["flow_modules"]:
        out["steps"].append(try_import(args["pkg"] + "." + mod))
elif mode == "flow_import_ver2":
    out["steps"].append(call_mock())
    import_ok = True
    for mod in args["flow_modules"]:
        r = try_import("pages.flow_tabs." + mod)
        out["steps"].append(r)
        if not r["ok"]:
            import_ok = False
            r["note"] = "ver2: ModuleNotFoundError 이면 flow_tabs.* 로 fallback" if "ModuleNotFoundError.name" in r else "ver2: ModuleNotFoundError 가 아니므로 fallback 없이 예외"
            break
    if not import_ok and "ModuleNotFoundError.name" in out["steps"][-1]:
        for mod in args["flow_modules"]:
            out["steps"].append(try_import("flow_tabs." + mod))
elif mode == "unpickle":
    import pickle
    r = {"path": args["path"]}
    try:
        import pandas as pd
        with open(args["path"], "rb") as f:
            raw = pickle.load(f)
        r["keys"] = sorted(raw.keys())
        r["tmp"] = {k: repr(v) for k, v in (raw.get("tmp") or {}).items()}
        for k in ("main_product", "main_source", "target_amount", "gmp", "electricity_price", "od_to_dcw", "operating_hours"):
            if k in raw:
                r[k] = repr(raw[k])
        cd = raw.get("chem_data")
        try:
            r["chem_data_price"] = {str(k): float(v) for k, v in cd["Price (USD/kg)"].items()}
        except Exception as e:
            r["chem_data_price"] = "ERR " + repr(e) + " type=" + repr(type(cd))
        r["solutions"] = json.loads(json.dumps(raw.get("solutions"), default=repr))
        r["prices"] = json.loads(json.dumps(raw.get("prices"), default=repr))
        r["autoclave"] = json.loads(json.dumps(raw.get("autoclave"), default=repr))
        r["heat_utility"] = json.loads(json.dumps(raw.get("heat_utility"), default=repr))
        nodes = raw.get("nodes") or []
        r["n_nodes"] = len(nodes)
        r["nodes"] = [{"id": getattr(n, "id", None), "node_type": (getattr(n, "data", {}) or {}).get("node_type"),
                       "content": (getattr(n, "data", {}) or {}).get("content")} for n in nodes]
        edges = raw.get("edges") or []
        r["n_edges"] = len(edges)
        r["edges"] = [(getattr(e, "source", None), getattr(e, "target", None)) for e in edges]
    except Exception as e:
        r["error"] = "".join(traceback.format_exception(type(e), e, e.__traceback__))[-2500:]
    out["steps"].append(r)
print("@@JSON@@" + json.dumps(out, ensure_ascii=False, default=repr))
'''


def run_probe(mode, roots, **extra):
    payload = dict(mode=mode, roots=roots, key_funcs=KEY_FUNCS, flow_modules=FLOW_MODULES, **extra)
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.setdefault('NUMBA_CACHE_DIR', tempfile.gettempdir())
    try:
        cp = subprocess.run([sys.executable, '-c', PROBE, json.dumps(payload)], capture_output=True,
                            text=True, timeout=600, env=env, cwd=os.getcwd())
    except subprocess.TimeoutExpired:
        return {'error': 'TIMEOUT (600s)'}
    marker = '@@JSON@@'
    if marker in cp.stdout:
        res = json.loads(cp.stdout.split(marker, 1)[1].strip().splitlines()[0])
        noise = cp.stdout.split(marker, 1)[0].strip()
        if noise:
            res['stdout_noise'] = noise[-1500:]
        if cp.stderr.strip():
            res['stderr_tail'] = cp.stderr.strip()[-1500:]
        return res
    return {'error': 'probe failed', 'returncode': cp.returncode, 'stdout': cp.stdout[-2000:], 'stderr': cp.stderr[-3000:]}


def pjson(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=repr))


# --------------------------------------------------------------------------------------------
# Static helpers (no import)
# --------------------------------------------------------------------------------------------
def flow_file(root, pkg, mod):
    return os.path.join(root, *pkg.split('.'), mod + '.py')


def defs_in(path):
    """Top-level function/class definitions -> (lineno, source)."""
    src = read_text(path)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {'__SYNTAX_ERROR__': (0, repr(e))}
    lines = src.splitlines()
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([d.lineno for d in n.decorator_list] + [n.lineno])
            out[n.name] = (n.lineno, '\n'.join(lines[start - 1:n.end_lineno]))
    return out


def effective_bindings(root, pkg):
    """Star-import order in ver1/ver2: later module wins for duplicated names."""
    eff = {}
    for mod in FLOW_MODULES:
        p = flow_file(root, pkg, mod)
        if os.path.isfile(p):
            for name, (ln, src) in defs_in(p).items():
                eff[name] = (mod, ln, src)
    return eff


def find_page(arg):
    if arg:
        return os.path.abspath(arg)
    for dirpath, _, files in os.walk(os.getcwd()):
        if 'economics_ver2.py' in files:
            return os.path.join(dirpath, 'economics_ver2.py')
        if dirpath.count(os.sep) - os.getcwd().count(os.sep) > 3:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', default=None)
    ap.add_argument('--app-root', default=os.getcwd())
    ap.add_argument('--max-diff', type=int, default=400)
    a = ap.parse_args()
    app_root = os.path.abspath(a.app_root)
    page = find_page(a.page)
    page_dir = os.path.dirname(page) if page else None
    roots = []
    for r in (app_root, page_dir):
        if r and r not in roots:
            roots.append(r)

    hr('[0] 실행 환경')
    print('python      :', sys.executable)
    print('version     :', sys.version.replace('\n', ' '))
    print('platform    :', platform.platform())
    print('cwd         :', os.getcwd())
    print('app_root    :', app_root)
    print('ver2 page   :', page, '' if page and os.path.isfile(page) else '(찾지 못함: --page 로 지정하세요)')
    print('PYTHONPATH  :', os.environ.get('PYTHONPATH'))
    print('import roots checked (streamlit 은 메인 스크립트 디렉터리를 sys.path[0] 에 넣음):', roots)
    if page and os.path.isfile(page):
        print('ver2 file   :', finfo(page))
        v1 = os.path.join(page_dir, 'economics_ver1.py')
        if os.path.isfile(v1):
            print('ver1 file   :', v1, finfo(v1))

    hr('[1] 패키지 버전 (importlib.metadata, import 없이)')
    for d in DISTS:
        try:
            print(f'  {d:28s} {md.version(d)}')
        except md.PackageNotFoundError:
            print(f'  {d:28s} (not installed)')

    hr('[2] H1: mock_biosteam')
    from importlib.machinery import PathFinder
    mock_paths = []
    for r in roots + [os.getcwd()]:
        spec = PathFinder.find_spec('mock_biosteam', [r])
        if spec and spec.origin and spec.origin not in mock_paths:
            mock_paths.append(spec.origin)
    spec_any = PathFinder.find_spec('mock_biosteam', roots + sys.path)
    if spec_any and spec_any.origin and spec_any.origin not in mock_paths:
        mock_paths.append(spec_any.origin)
    if not mock_paths:
        print('mock_biosteam: 발견되지 않음 (roots + sys.path) -> ver2 의 try 블록은 ImportError 로 조용히 통과')
    for p in mock_paths:
        print(f'mock_biosteam 발견: {p}  {finfo(p) if os.path.isfile(p) else ""}')
        if os.path.isfile(p):
            src = read_text(p)
            print('-' * 40 + ' mock_biosteam 소스 전문 ' + '-' * 40)
            print(src)
            print('-' * 100)
            try:
                tree = ast.parse(src)
                for n in ast.walk(tree):
                    if isinstance(n, ast.FunctionDef) and n.name == 'setup_biosteam_fallback':
                        print(f'setup_biosteam_fallback 정의: L{n.lineno}-L{n.end_lineno}')
            except SyntaxError as e:
                print('mock_biosteam SyntaxError:', e)
    for mode, title in (('real_only', 'S1 ver1 순서: mock 없이 import biosteam'),
                        ('ver2_order', 'S2 ver2 순서: setup_biosteam_fallback() 후 import biosteam (새 프로세스)'),
                        ('shared_process', 'S3 같은 프로세스에서 이미 import 된 biosteam 에 setup 호출 (멀티페이지 공유 시나리오)')):
        print(f'\n--- {title} ---', flush=True)
        pjson(run_probe(mode, roots))

    hr('[3] H2: pages.flow_tabs vs flow_tabs 사본')
    copies = {}
    for r in roots:
        for pkg in ('pages.flow_tabs', 'flow_tabs'):
            init = os.path.join(r, *pkg.split('.'), '__init__.py')
            files = {m: flow_file(r, pkg, m) for m in FLOW_MODULES}
            present = {m: os.path.isfile(p) for m, p in files.items()}
            print(f'\n[root={r}] package {pkg}: __init__.py {"있음" if os.path.isfile(init) else "없음(namespace 패키지)"}')
            for m, p in files.items():
                print(f'   {m:24s} {p}  {finfo(p)}')
            if any(present.values()):
                copies[(r, pkg)] = files
    print('\n--- 실제 import 해석 (하위 프로세스, mock 미적용) ---', flush=True)
    for pkg in ('pages.flow_tabs', 'flow_tabs'):
        print(f'\n[{pkg}.*]')
        pjson(run_probe('flow_import_plain', roots, pkg=pkg))
    print('\n--- ver2 재현: setup_biosteam_fallback() 후 pages.flow_tabs → (ModuleNotFoundError 시) flow_tabs ---', flush=True)
    pjson(run_probe('flow_import_ver2', roots))

    real = {}
    for (r, pkg), files in copies.items():
        real.setdefault(tuple(sorted((m, md5(p)) for m, p in files.items() if os.path.isfile(p))), []).append(f'{r} :: {pkg}')
    print('\n--- 내용 기준 사본 그룹 (md5 가 모두 같은 사본은 한 그룹) ---')
    for i, (sig, where) in enumerate(real.items()):
        print(f'  group {i}: {where}')
    keys = list(copies.keys())
    if len(keys) >= 2:
        base = next((k for k in keys if k[1] == 'pages.flow_tabs'), keys[0])
        for other in keys:
            if other == base:
                continue
            print(f'\n### 비교: BASE={base}  vs  OTHER={other}')
            for m in FLOW_MODULES:
                pa, pb = copies[base][m], copies[other][m]
                if not (os.path.isfile(pa) and os.path.isfile(pb)):
                    print(f'  {m}: 한쪽 없음 (BASE {os.path.isfile(pa)}, OTHER {os.path.isfile(pb)})')
                    continue
                if md5(pa) == md5(pb):
                    print(f'  {m}: 동일 (md5 {md5(pa)})')
                    continue
                diff = list(difflib.unified_diff(read_text(pa).splitlines(), read_text(pb).splitlines(), pa, pb, lineterm=''))
                print(f'  {m}: 다름 ({len(diff)} diff lines) - 최대 {a.max_diff}줄 출력')
                for line in diff[:a.max_diff]:
                    print('    ' + line)
            eb, eo = effective_bindings(*base), effective_bindings(*other)
            print('\n  --- 핵심 함수 (star-import 최종 바인딩 기준) ---')
            for f in KEY_FUNCS:
                if f not in eb and f not in eo:
                    print(f'  {f}: 두 사본 모두 최상위 정의 없음')
                    continue
                ib, io = eb.get(f), eo.get(f)
                print(f'  {f}: BASE {ib[0] + ":L" + str(ib[1]) if ib else "없음"} | OTHER {io[0] + ":L" + str(io[1]) if io else "없음"}', end='')
                if ib and io:
                    if ib[2] == io[2]:
                        print('  => 소스 동일')
                    else:
                        print('  => 소스 다름. unified diff:')
                        for line in difflib.unified_diff(ib[2].splitlines(), io[2].splitlines(), 'BASE.' + f, 'OTHER.' + f, lineterm=''):
                            print('      ' + line)
                else:
                    print()
    else:
        print('\n사본이 1개 이하라서 비교할 대상이 없음.')
    print('\n--- 핵심 함수 소스 전문 (pages.flow_tabs 최종 바인딩) ---')
    base = next((k for k in copies if k[1] == 'pages.flow_tabs'), None)
    if base:
        eb = effective_bindings(*base)
        for f in ('run_biosteam2', 'scale_up_system', 'price_system'):
            if f in eb:
                print(f'\n##### {f}  ({base[1]}.{eb[f][0]} L{eb[f][1]}) #####')
                print(eb[f][2])
            else:
                print(f'\n##### {f}: pages.flow_tabs 에서 최상위 정의 찾지 못함 #####')
    else:
        print('pages.flow_tabs 사본을 찾지 못함')

    hr('[4] H3: base_dir / 데이터 파일')
    v2_local = os.path.join(page_dir, 'data') if page_dir else None
    cwd_data = os.path.join(os.getcwd(), 'data')
    if os.path.exists(HARDCODED_BASE_DIR):
        chosen = HARDCODED_BASE_DIR
    elif v2_local and os.path.exists(v2_local):
        chosen = v2_local + os.sep
    else:
        chosen = cwd_data + os.sep
    print('ver1 base_dir (고정)            :', HARDCODED_BASE_DIR, '존재' if os.path.exists(HARDCODED_BASE_DIR) else '없음')
    print('ver2 후보 1 (페이지 폴더/data)  :', v2_local, '존재' if v2_local and os.path.exists(v2_local) else '없음')
    print('ver2 후보 2 (cwd/data)          :', cwd_data, '존재' if os.path.exists(cwd_data) else '없음')
    print('=> ver2 가 실제로 사용할 base_dir:', chosen, '(ver1 과 같음)' if chosen == HARDCODED_BASE_DIR else '(ver1 과 다름!)')
    dirs = [d for d in (HARDCODED_BASE_DIR, v2_local, cwd_data) if d and os.path.isdir(d)]
    seen = []
    for d in dirs:
        d = os.path.abspath(d)
        if d in seen:
            continue
        seen.append(d)
        print(f'\n[dir] {d}')
        for fn in sorted(os.listdir(d)):
            if fn.endswith(('.pkl', '.json')):
                print(f'   {fn:40s} {finfo(os.path.join(d, fn))}')
    print('\n--- initial_val.json / initial_val.pkl md5 비교 ---')
    for fn in ('initial_val.json', 'initial_val.pkl'):
        row = {d: (md5(os.path.join(d, fn)) if os.path.isfile(os.path.join(d, fn)) else 'MISSING') for d in seen}
        same = len(set(v for v in row.values() if v != 'MISSING')) <= 1
        print(f'  {fn}: {"동일" if same else "다름"}')
        for d, v in row.items():
            print(f'     {v}  {d}')
    jsons = {}
    for d in seen:
        p = os.path.join(d, 'initial_val.json')
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    jsons[d] = json.load(f)
            except Exception as e:
                jsons[d] = {'__error__': repr(e)}
    for d, j in jsons.items():
        print(f'\n  initial_val.json @ {d}')
        print('    tmp          =', json.dumps(j.get('tmp'), ensure_ascii=False, default=repr))
        print('    heat_utility =', json.dumps(j.get('heat_utility'), ensure_ascii=False, default=repr))
        print('    top keys     =', sorted(j.keys()) if isinstance(j, dict) else type(j))
    print('\n--- initial_val.pkl 내용 요약 (하위 프로세스에서 unpickle) ---', flush=True)
    for d in seen:
        p = os.path.join(d, 'initial_val.pkl')
        if os.path.isfile(p):
            print(f'\n  initial_val.pkl @ {d}')
            pjson(run_probe('unpickle', roots, path=p))

    hr('[5] 멀티페이지 공유 프로세스 위험 (같은 streamlit 서버의 다른 페이지가 mock 을 호출하는지)')
    for r in roots:
        pdir = os.path.join(r, 'pages') if os.path.basename(r) != 'pages' else r
        cand = [os.path.join(r, f) for f in os.listdir(r) if f.endswith('.py')] if os.path.isdir(r) else []
        if os.path.isdir(pdir):
            cand += [os.path.join(pdir, f) for f in os.listdir(pdir) if f.endswith('.py')]
        for p in sorted(set(cand)):
            try:
                t = read_text(p)
            except Exception:
                continue
            flags = [k for k in ('mock_biosteam', 'setup_biosteam_fallback', 'from flow_tabs', 'base_dir') if k in t]
            if flags:
                print(f'  {p}: {flags}')

    hr('[6] 자동 요약 (사람이 위 출력을 보고 최종 판정)')
    print('  H1: [2] 의 S2/S3 에서 __file__/Unit_sourcefile/method_origins.outside_pkg/micro_sim 이 S1 과 다르면 mock 이 biosteam 을 대체/패치한 것')
    print('  H2: [3] ver2 재현에서 pages.flow_tabs 가 ModuleNotFoundError 이면 flow_tabs 로 넘어감. ModuleNotFoundError.name 이 "pages" 가 아니면 내부 의존성 누락이 fallback 을 유발한 것')
    print('  H3: [4] "ver2 가 실제로 사용할 base_dir" 이 ver1 과 다르고 initial_val.* md5/내용이 다르면 데이터 차이')


if __name__ == '__main__':
    main()
