import numpy as np, pandas as pd, sys, os, json, copy, string, pickle, math
import streamlit as st

import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
import time

import biosteam as bst
from biosteam import Unit, Stream, settings, main_flowsheet
import thermosteam as tmo

from pages.flow_tabs.Biosteam_custom_unit import *
from pages.flow_tabs.aux_chemical import *
from pages.flow_tabs.util_bfd_Copy3 import *
from pages.flow_tabs.util_biosteam_Copy1 import *
#from pages.flow_tabs.aux_flow import *


st.set_page_config(
    page_title="경제성 평가 자동화 시스템 (TEA-Platform)",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================================
# DESIGN SYSTEM & CUSTOM CSS (Benchmarked from tea-agent-platform-v10)
# ============================================================================
st.markdown(
"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

:root {
    --green-primary: #006600;
    --green-dark: #004d00;
    --green-light: #e8f5e8;
    --green-accent: #15803d;
    --green-border: #bbf7d0;
    --green-hover: #005200;
    --bg-page: #f8fafc;
    --bg-card: #ffffff;
    --border-color: #e2e8f0;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
}

/* Page base background & container */
.stApp {
    background-color: #f8fafc !important;
}

.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 3.5rem;
    max-width: 1440px;
}

/* Top App Header Banner */
.tea-top-banner {
    background: linear-gradient(135deg, #004d00 0%, #006600 55%, #15803d 100%);
    color: #ffffff;
    padding: 24px 30px;
    border-radius: 14px;
    margin-bottom: 24px;
    box-shadow: 0 4px 18px rgba(0, 77, 0, 0.22);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 14px;
}
.tea-top-title {
    font-size: 23px;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    color: #ffffff;
}
.tea-top-sub {
    font-size: 13.5px;
    color: #dcfce7;
    margin-top: 5px;
    font-weight: 400;
    letter-spacing: -0.2px;
}
.tea-badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.35);
    border-radius: 20px;
    font-size: 12.5px;
    font-weight: 600;
    color: #ffffff;
    backdrop-filter: blur(4px);
    transition: all 0.2s ease;
}
.tea-badge-pill:hover {
    background: rgba(255, 255, 255, 0.25);
}

/* Section Header Badges */
.section-header-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}
.section-badge-num {
    background: #e8f5e8;
    color: #006600;
    font-weight: 800;
    font-size: 13px;
    padding: 3px 11px;
    border-radius: 20px;
    border: 1.5px solid #bbf7d0;
}
.section-badge-title {
    font-size: 17px;
    font-weight: 700;
    color: #1e293b;
    letter-spacing: -0.3px;
}

/* Card Containers (st.container border=True) */
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
    padding: 18px 22px !important;
}

/* KPI Summary Cards Grid */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 16px;
    margin-bottom: 22px;
}
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 18px 22px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
    border-left: 5px solid #006600;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 14px rgba(0, 0, 0, 0.07);
}
.kpi-title {
    font-size: 12.5px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-bottom: 8px;
}
.kpi-value {
    font-size: 22px;
    font-weight: 800;
    color: #006600;
    letter-spacing: -0.5px;
}

/* Streamlit Buttons Styling */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #006600, #004d00) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 9px 22px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    box-shadow: 0 2px 8px rgba(0, 102, 0, 0.28) !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #004d00, #003300) !important;
    box-shadow: 0 4px 12px rgba(0, 102, 0, 0.4) !important;
    transform: translateY(-1px) !important;
}

div.stButton > button[kind="secondary"] {
    background: #ffffff !important;
    color: #006600 !important;
    border: 1.5px solid #006600 !important;
    border-radius: 8px !important;
    padding: 8px 18px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}
div.stButton > button[kind="secondary"]:hover {
    background: #e8f5e8 !important;
    border-color: #004d00 !important;
    color: #004d00 !important;
    transform: translateY(-1px) !important;
}

/* Form Submit Button */
div.stFormSubmitButton > button {
    background: linear-gradient(135deg, #006600, #004d00) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    box-shadow: 0 2px 8px rgba(0, 102, 0, 0.28) !important;
    transition: all 0.2s ease !important;
}
div.stFormSubmitButton > button:hover {
    background: #004d00 !important;
    box-shadow: 0 4px 12px rgba(0, 102, 0, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* Inputs & Selectbox focus highlight */
div[data-baseweb="input"] input:focus,
div[data-baseweb="select"] input:focus {
    border-color: #006600 !important;
    box-shadow: 0 0 0 2px rgba(0, 102, 0, 0.2) !important;
}

/* Streamlit Expander */
div[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    background: #ffffff !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}
div[data-testid="stExpander"] summary {
    font-weight: 700 !important;
    color: #1e293b !important;
    background: #f8fafc !important;
    padding: 10px 16px !important;
}

/* Dataframe and Table styling */
div[data-testid="stDataFrame"] {
    border-radius: 8px !important;
    overflow: hidden !important;
    border: 1px solid #e2e8f0 !important;
}

.dataframe table {
    font-family: 'Noto Sans KR', Consolas, monospace !important;
    border: 1px solid #e2e8f0 !important;
    border-collapse: collapse !important;
    width: 100% !important;
}
.dataframe th {
    background: #006600 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    padding: 9px 14px !important;
}
.dataframe td {
    padding: 7px 14px !important;
    border: 1px solid #e2e8f0 !important;
}
.dataframe tr:hover td {
    background-color: #f0fdf4 !important;
}

/* React Flow / StreamlitFlow canvas styling */
.react-flow__renderer {
    background-color: #fafbfc !important;
    border-radius: 10px !important;
}
.react-flow__controls {
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    overflow: hidden !important;
    border: 1px solid #e2e8f0 !important;
}
.react-flow__controls-button {
    border-bottom: 1px solid #f1f5f9 !important;
    background: #ffffff !important;
}
.react-flow__controls-button:hover {
    background: #e8f5e8 !important;
}

/* Success / Info Alert boxes */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left-width: 4px !important;
}
</style>
""",
unsafe_allow_html=True)

# ── Global App Header ──────────────────────────────────────────
st.markdown("""
<div class="tea-top-banner">
    <div>
        <h1 class="tea-top-title">🧪 경제성 평가 자동화 플랫폼 (TEA-Agent)</h1>
        <div class="tea-top-sub">Bio & Chemical Process Simulation · Techno-Economic Analysis System</div>
    </div>
    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <span class="tea-badge-pill">● Simulation Engine Ready</span>
        <span class="tea-badge-pill">CE Index: 806.7</span>
        <span class="tea-badge-pill">Lang Factor: 3.14</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.session_state.currency = 1500

if 'run_biosteam' not in st.session_state:
    st.session_state.run_biosteam = False
    st.session_state.scaled_system = {}

bst.CE = 806.7
lang_factor = 3.14285714285
base_dir = '/home/sbf/JLee/test/data/scenario/'
hd = ['Name', 'Formula', 'Price (USD/kg)', 'Phase']
@st.cache_resource(ttl=3600)
def load_all_unit_defaults(base_dir):
    with open(base_dir+'initial_val.json', 'r') as f:
        init_value = json.load(f)
    return init_value

#st.cache_resource(ttl=3600)
def load_data(template):
    with open(base_dir+template+'.pkl','rb') as f:
        raw_data = pickle.load(f)
    st.session_state.tmp = raw_data['tmp']
    st.session_state.flow_state = StreamlitFlowState(nodes=raw_data['nodes'], edges=raw_data['edges'])
    st.session_state.selected_id_old = None
    st.session_state.flow_state.timestamp = 0
    st.session_state.flow_rev = 0
    st.session_state.solutions = raw_data.get('solutions', {})
    st.session_state.autoclave = raw_data.get('autoclave', {})
    st.session_state.prices = raw_data.get('prices', {})
    st.session_state.proceed3 = False
    load_chem_data = raw_data['chem_data']
    st.session_state.uploader_key +=1
    st.session_state.chemicals, st.session_state.chem_data = process_chemical_data(load_chem_data)
    st.session_state.heat_utility = raw_data.get('heat_utility', {})
    st.session_state.currency = st.session_state.tmp.get('currency',1500)

    st.session_state.chemical_list = chemical_list = [i.ID for i in st.session_state.chemicals]
    st.session_state.main_product = raw_data.get('main_product', chemical_list[st.session_state.tmp['product_index']])
    st.session_state.main_source = raw_data.get('main_source', chemical_list[st.session_state.tmp['source_index']])
    st.session_state.target_amount = raw_data.get('target_amount', st.session_state.tmp['target_amount'])
    st.session_state.gmp = raw_data.get('gmp', st.session_state.get('gmp',True))

    try:
        st.session_state.electricity_price = st.session_state.tmp['electricity_price']
    except:
        pass

    st.rerun()


if 'gmp' not in st.session_state:
    st.session_state.gmp = True

# --- Session State Initialization ---
# Initialize session state variables if they don't exist.
if 'uploader_key' not in st.session_state:
    with st.spinner("Loading unit default parameters..."):
        # Make sure the path is correct
        st.session_state.all_unit_defaults = load_all_unit_defaults(base_dir)

    st.session_state.uploader_key = 0

    default_chemicals = {
        'Water': {'Price (USD/kg)': 0, 'Phase': 'l','Formula':'H2O'},
        'Biomass': {'Price (USD/kg)': 0, 'Phase': 's','Formula':'CH1.77O0.49N0.24'},
        'Glucose': {'Price (USD/kg)': 1, 'Phase': 'l','Formula':'C6H12O6'},}
    default_chemicals=pd.DataFrame.from_dict(default_chemicals,orient='index')
    default_chemicals['Name']=default_chemicals.index
    st.session_state.chemicals, st.session_state.chem_data = process_chemical_data(default_chemicals)

    st.session_state.proceed = False
    st.session_state.proceed2 = False
    st.session_state.proceed3 = False
    st.session_state.simulation_ran = False
    st.session_state.reactions = {}
    st.session_state.node_select = None
    st.session_state.solutions = {} # Should be in initial_val.pkl but for placeholder
    st.session_state.autoclave = {}
    st.session_state.prices = {}
    st.session_state.flow_state = StreamlitFlowState(nodes=[], edges=[])
    st.session_state.selected_id_old = None
    st.session_state.flow_rev = 0
    st.session_state.flow_state.timestamp = 0
    initialize_flowstate()

    st.session_state.tmp = st.session_state.all_unit_defaults['tmp']
    st.session_state.currency = st.session_state.all_unit_defaults['tmp']['currency']
    st.session_state.operating_hours = st.session_state.all_unit_defaults['tmp']['operating_hours']
    st.session_state.heat_utility = st.session_state.all_unit_defaults['heat_utility']

    load_data('initial_val')

# 화면 배치는 ver2와 동일(📂 저장/불러오기 → ① 화학물질)하게 두되,
# 실행 순서는 ver1과 동일(upload_chemical() → 저장/불러오기)하게 유지하기 위해
# 빈 컨테이너를 먼저 화면 순서대로 만들어 두고, 실행은 ver1 순서로 채운다.
_save_area = st.container()
_upload_area = st.container()

# ── 2. 화학물질 등록 카드 ───────────────────────────────────────
with _upload_area:
    st.markdown("""
    <div class="section-header-badge">
        <span class="section-badge-num">①</span>
        <span class="section-badge-title">화학물질 DB 및 업로드</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        upload_chemical()

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ── 1. 데이터 저장 및 관리 카드 ─────────────────────────────────
with _save_area:
    st.markdown("""
    <div class="section-header-badge">
        <span class="section-badge-num">📂</span>
        <span class="section-badge-title">프로젝트 데이터 관리 (Save & Load)</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        save_col = st.columns([.4, .38, .22], vertical_alignment="bottom")
        with save_col[0]:
            template = st.text_input("저장 파일명", 'Data', help="시나리오 데이터를 저장할 이름을 입력하세요.")
            if st.button("💾 데이터 저장", use_container_width=True, type="secondary"):
                with open(base_dir + template+'.pkl','wb') as f:
                    raw_data = {}

                    #raw_data['chemicals'] = st.session_state.chemicals
                    raw_data['chem_data'] = st.session_state.chem_data
                    raw_data['solutions'] = st.session_state.solutions
                    raw_data['autoclave'] = st.session_state.autoclave
                    raw_data['prices'] = st.session_state.prices
                    raw_data['nodes']= st.session_state.flow_state.nodes
                    raw_data['edges']= st.session_state.flow_state.edges
                    raw_data['tmp'] = st.session_state.tmp
                    raw_data['heat_utility'] = st.session_state.heat_utility

                    raw_data['gmp'] = st.session_state.get('gmp',True)
                    raw_data['electricity_price'] = st.session_state.get('electricity_price',0.128)
                    raw_data['od_to_dcw'] = st.session_state.get('od_to_dcw',0.22)
                    raw_data['operating_hours'] = st.session_state.get('operating_hours',7920)
                    raw_data['target_amount'] = st.session_state.get('target_amount',0.1)
                    raw_data['main_product'] = st.session_state.get('main_product','Collagen')
                    raw_data['main_source'] = st.session_state.get('main_source','Glucose')


                    pickle.dump(raw_data,f)
                st.success(f"'{template}.pkl' 파일로 저장되었습니다.")

        with save_col[1]:
            tmp=[i[:-4] for i in os.listdir(base_dir) if i[-3:]=='pkl']
            map_id = st.selectbox("저장된 데이터 파일 목록", tmp)
            if st.button("📂 데이터 불러오기", use_container_width=True, type="secondary"):
                st.session_state.proceed = True
                st.session_state.proceed2 = True
                load_data(map_id)

        with save_col[2]:
            if st.button("🔄 기본값 초기화", use_container_width=True, type="secondary"):
                with open(base_dir+'initial_val.json', 'r') as f:
                    st.session_state.all_unit_defaults = json.load(f)
                st.info("기본 파라미터가 다시 로드되었습니다.")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ── 3. 기본 조건 & 유틸리티 설정 카드 ──────────────────────────────
if 'chemical_list' not in st.session_state:
    st.header(':red[물질 등록]')
else:
    st.markdown("""
    <div class="section-header-badge">
        <span class="section-badge-num">②</span>
        <span class="section-badge-title">기본 생산 조건 및 유틸리티 설정</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        col1, col2 = st.columns([.65, .35], gap="large")
        with col1:
            chemicals = st.session_state.chemical_list

            c_sub1, c_sub2 = st.columns(2)
            with c_sub1:
                main_product = st.selectbox("🎯 Target Product (목표 제품)", chemicals, index=st.session_state.tmp['product_index'], key='main_product')
            with c_sub2:
                main_source = st.selectbox("🌱 Carbon Source (탄소원)", chemicals, index=st.session_state.tmp['source_index'], key='main_source')

            target_production = st.number_input("📦 연간 목표 생산량 (MT/year)", value=st.session_state.tmp['target_amount'], key='target_amount')

        with col2:
            with st.expander("⚙️ 고급 옵션 (Advanced Options)", expanded=True):
                #operating_hours = st.text_input('Yearly operating hours', value=st.session_state.initial_val['operating_hours'], key="operating_hours")
                operating_hours = st.number_input('연중 운영시간 (hours/year)', value=st.session_state.tmp['operating_hours'], key="operating_hours")
                gmp = st.checkbox('GMP 시설 적용 여부', value = True, key='gmp')
                od_mass = st.number_input('OD별 dry cell weight (g/L/OD)', value=st.session_state.tmp['od_to_dcw'], key="od_to_dcw")

                st.markdown("<div style='font-size: 13px; font-weight: 700; color: #006600; margin-top: 8px;'>유틸리티 단가 테이블 (USD/kg)</div>", unsafe_allow_html=True)
                heat_util = pd.DataFrame.from_dict(st.session_state.heat_utility, orient='index', columns=['price [USD/kg]'])
                heat_util.reset_index(inplace=True,names=['utility'])
                heat_util = st.data_editor(
                    heat_util,
                    num_rows="dynamic",
                    key=f"heat_util",
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        'utility': st.column_config.TextColumn("유틸리티 항목", required=True, width='medium'),
                        'price [USD/kg]': st.column_config.NumberColumn("단가 [USD/kg]", width='small', format="$%.4g", required=True)
                    }
                )

                if 'electricity_price' not in st.session_state.tmp:
                    st.session_state.tmp['electricity_price'] = 0.128
                electricity_price = st.number_input('전력 단가 (USD/kWh)', value=st.session_state.tmp['electricity_price'], key='electricity_price')

        if st.button('다음 단계로 이동 (용액 등록) ➔', type='primary', use_container_width=True):
            st.session_state.tmp['product_index'] = chemicals.index(main_product)
            st.session_state.tmp['source_index'] = chemicals.index(main_source)
            st.session_state.tmp['target_amount'] = target_production
            st.session_state.tmp['electricity_price'] = electricity_price
            st.session_state.tmp['operating_hours'] = operating_hours
            st.session_state.tmp['od_to_dcw'] = od_mass
            st.session_state.proceed = True
            for _,row in heat_util.iterrows():
                st.session_state.heat_utility[row['utility']] = row['price [USD/kg]']
            bst.PowerUtility.price = electricity_price

    # ── 4. 용액 등록 카드 (ver1과 동일하게 else 블록 내부에 위치) ──────────
    if st.session_state.proceed:
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="section-header-badge">
            <span class="section-badge-num">③</span>
            <span class="section-badge-title">용액 관리 및 조성 설정 (Solution Preparation)</span>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            if 'Water' in st.session_state.solutions:
                num_sol = len(st.session_state.solutions)-1
            else:
                num_sol = len(st.session_state.solutions)

            num_sol = st.number_input('등록할 용액 수', min_value=0, step=1, key='num_sol', value=max(num_sol,1))
            sol_list = [f"용액 {i+1}" for i in range(num_sol)]

            with st.expander('🧪 용액별 성분 및 농도 구성 (클릭하여 편집)', expanded=True):
                with st.form("용액 조성"):
                    sol_ui = {str(nn):st.columns(4) for nn in range(num_sol//4+1)}
                    sol_tmp = {}
                    for idx,i in enumerate(sol_list):
                        with sol_ui[str(idx//4)][idx%4]:
                            st.markdown(f"""
                            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 8px;">
                                <div style="font-weight: 700; color: #006600; font-size: 14px; margin-bottom: 6px;">💧 {i}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if i not in st.session_state.solutions:
                                sol_tmp[i] = pd.DataFrame({'Name': [''], 'Concentration [g/L]': [0.0]})
                            else:
                                sol_tmp[i] = pd.DataFrame.from_dict(st.session_state.solutions[i],orient='index').reset_index()
                                sol_tmp[i].columns = ['Name', 'Concentration [g/L]']

                            sol_tmp[i] = st.data_editor(
                                sol_tmp[i],
                                num_rows="dynamic",
                                key=f"{i}_solution",
                                hide_index=True,
                                use_container_width=True,
                                column_config={
                                    'Name': st.column_config.SelectboxColumn("물질", options=st.session_state.chemical_list, required=True),
                                    'Concentration [g/L]': st.column_config.NumberColumn("농도 [g/L]", format="%.2f", required=True)
                                }
                            )
                            st.session_state.autoclave[i] = st.checkbox('멸균 처리 (Autoclave)', value=True, key=f"{i}_autoclave")

                    sol_calc = st.form_submit_button("💾 용액 저장 및 반영", type="primary", use_container_width=True)
                    if sol_calc:
                        st.session_state.solutions = {}
                        for idx,i in enumerate(sol_list):
                            st.session_state.solutions[i] = dict(zip(sol_tmp[i]['Name'], sol_tmp[i]['Concentration [g/L]']))
                            st.session_state.solutions[i] = fill_water3(st.session_state.solutions[i],1)
                            st.session_state.prices[i] = 0
                            for chem,mass in st.session_state.solutions[i].items():
                                st.session_state.prices[i] += mass * st.session_state.chem_data['Price (USD/kg)'][chem]
                            st.session_state.solutions['Water'] = {'Water':1000}
                            st.session_state.autoclave['Water'] = False
                            st.session_state.prices['Water'] = float(st.session_state.chem_data['Price (USD/kg)']['Water'])
                            st.session_state.proceed2 = True
                        st.rerun()

# ── 5. 공정 흐름도 (BFD) 모델링 카드 ──────────────────────────────
if st.session_state.proceed2:
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div class="section-header-badge">
        <span class="section-badge-num">④</span>
        <span class="section-badge-title">공정 흐름도 모델링 (Process Flow Diagram - BFD)</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        # BFD Control Toolbar
        flow_cols = st.columns([.35, .25, .2, .2], vertical_alignment="bottom")
        with flow_cols[0]:
            NODE_TYPES = get_node_feature()
            node_list = list(NODE_TYPES.keys())
            node_in = st.selectbox("추가할 공정 유닛", node_list)
        with flow_cols[1]:
            if st.button("➕ 유닛 노드 추가", use_container_width=True, type="primary"):
                add_node(node_in)
        with flow_cols[2]:
            if st.button('🗑️ 선택 노드/엣지 삭제', use_container_width=True, type="secondary"):
                delete_node(st.session_state.selected_id_old)
        with flow_cols[3]:
            if st.button('🔄 흐름도 리셋', use_container_width=True, type="secondary"):
                initialize_flowstate()

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # BFD Canvas & Sidebar Editor
        main_content, second_sidebar = st.columns([2.2, 1], gap="medium")

        with main_content:
            with st.container(border=True):
                new_state = sf_tmp(str(st.session_state.flow_rev), st.session_state.flow_state)
                st.session_state.flow_state = new_state

                if new_state.selected_id is not None:
                    st.session_state.selected_id_old = new_state.selected_id
                else:
                    st.session_state.selected_id_old = None

        with second_sidebar:
            with st.container(border=True):
                st.markdown("<div style='font-weight: 700; color: #006600; font-size: 15px; margin-bottom: 10px;'>⚙️ 유닛 파라미터 상세 설정</div>", unsafe_allow_html=True)
                # 가독성 위해 node.content로 변경. node 이름 체계 바꿨으니 추후에 다시 변경
                #all_element_ids = [i.id for i in st.session_state.flow_state.nodes]
                all_element_ids = [i.data['content'] for i in st.session_state.flow_state.nodes]
                all_element_ids2 = [i.id for i in st.session_state.flow_state.nodes]

                initial_selectbox_index = None
                try:
                    if st.session_state.selected_id_old is not None:
                        index_by_id = all_element_ids2.index(st.session_state.selected_id_old)
                        st.session_state.node_select = st.session_state.flow_state.nodes[index_by_id].data['content']
                except:
                    initial_selectbox_index = 0

                selected_element_id = st.selectbox('편집 대상 유닛 선택', options=all_element_ids, index=initial_selectbox_index, key='node_select')
                if selected_element_id:
                    selected_idx = all_element_ids.index(selected_element_id)
                    selected_node_id = all_element_ids2[selected_idx]

                    #current_node = copy.deepcopy(st.session_state.flow_state.nodes[selected_idx])
                    current_node = copy.deepcopy(new_state.nodes[selected_idx])
                    with st.form(key=f"edit_node_form_{current_node.id}"):
                        edited_node_data_from_widgets = edit_node(current_node)

                        submit_button = st.form_submit_button("💾 유닛 파라미터 저장", type="primary", use_container_width=True)

                        if submit_button:
                            _, processor = get_node_editor_functions(current_node.data['node_type'])
                            final_node_value = processor(
                                edited_node_data_from_widgets['Value'])
                            st.session_state.flow_state.nodes[selected_idx].data['content'] = edited_node_data_from_widgets['content']
                            st.session_state.flow_state.nodes[selected_idx].data['Value'] = final_node_value
                            st.session_state.flow_state.nodes = st.session_state.flow_state.nodes[:]
                            st.session_state.flow_state.timestamp = time.time()
                            st.session_state.flow_rev +=1
                            st.rerun()

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 경제성 평가 및 시뮬레이션 계산 실행 (Run BioSTEAM)", type='primary', use_container_width=True):
            st.session_state.proceed3 = True
            st.session_state.run_biosteam = True

    # ── 6. 경제성 분석 결과 카드 ────────────────────────────────────
    if st.session_state.proceed3:
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="section-header-badge">
            <span class="section-badge-num">⑤</span>
            <span class="section-badge-title">경제성 분석 및 시뮬레이션 결과 (Techno-Economic Results)</span>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.run_biosteam == True:
            nodes = {}
            edges = {}
            for i in st.session_state.flow_state.nodes:
                nodes[i.id] = i.data
            for i in st.session_state.flow_state.edges:
                if i.source not in edges:
                    edges[i.source]=[i.target]
                else:
                    edges[i.source].append(i.target)

            input_unit = {'배치 피드': {'ID':'',
                                   'T':273.15,
                                   'phases':('s','l','g'),
                                   'P':101325,
                                  },
                 '연속 피드': {'ID':'',
                                  'T':273.15,
                                  'phases':('s','l','g'),
                                  'P':101325,
                                 },
                 'Product Stream': {'ID':'',
                                  'T':273.15,
                                  'phases':('s','l','g'),
                                  'P':101325,
                                 },
                 '폐기물': {'ID':'',
                                  'T':273.15,
                                  'phases':('s','l','g'),
                                  'P':101325,
                                 },
                 '발효/정제 분리선':{},
                 'MVR':{},
                 'HIC column':{},
                 'DiaFiltration':{},
                 'IEX column':{},
                 'gel_filtration':{},
                 'Reaction': {'reaction':'',
                              'reactant':'Glucose',
                              'X':0.8,
                             },
                 '발효기': {
                                    'tau':24,
                                    'tau_cip':3,
                                    'ferm_T':303.15,
                                    'sterilized_T':338.15,
                                    'P':101325,
                                    'init_OD':0.5,
                                    'final_OD':10,
                                    'V_wf':0.7,
                                    'V_max':100,
                                   },
                 'Main Fermenter': {'ID':'',
                                    'ins':[],
                                    'reactions':'',
                                    'tau':24,
                                    'T':303.15,
                                   },
                 '증발기': {
                                'ins':[],
                                'V':0.4,
                                'max_T':338.15,
                                'out_T':298.15,
                                'chemical':'Water',
                               },
                 '동결건조기': {
                                 'ins':[],
                                },
                 'Mix-Tank': {
                              'ins':[],
                             },
                 '원심분리기': {
                                'ins':[],
                                'split':{},
                               },
                 'Chromatography':{'ID':'',
                                   'ins':[],
                                  },
                 'Centrifuge':{},

                }
            session_state_to_spec_data(input_unit, nodes)
            bst.main_flowsheet.clear()
            batch_time = get_batch_time(nodes)
            solutions=[st.session_state.autoclave, st.session_state.solutions, st.session_state.prices]
            ferm_sys = run_biosteam2(nodes, edges, solutions=solutions, feat_data=st.session_state.spec_data, batch_time=batch_time)

            target_amount = float(st.session_state.target_amount) * 1000
            scaled_system  = scale_up_system(ferm_sys,main_product, target_amount, nodes)
            scaled_system = price_system(scaled_system)
            scaled_system.simulate()
            st.session_state.scaled_system = scaled_system


        else:
            target_amount = float(st.session_state.target_amount) * 1000
            scaled_system = st.session_state.scaled_system

        with st.container(border=True):
            st.markdown("<div style='font-weight: 700; color: #006600; font-size: 15px; margin-bottom: 8px;'>📊 BioSTEAM 공정 흐름도 다이어그램</div>", unsafe_allow_html=True)
            st.graphviz_chart(scaled_system.diagram(display=False))
            st.session_state.run_biosteam = False
            total_feed_amount = get_chem_price(scaled_system.ins)
            upstream_amount, upstream_c_amount = get_c_source(total_feed_amount, source=['Glucose','Glycerol','Methanol', st.session_state.main_source])

            #upstream_amount, upstream_c_amount, strictly_upstream_units = get_upstream_feeds(scaled_system)
            downstream_amount = {}

            total_cost = 0
            scaled_system = bst.main_flowsheet.create_system('Ferm_sys')
            scaled_system.simulate()

            with st.expander("🔍 유닛별 출력 스트림 및 결과 상세 보기"):
                for i in scaled_system.units:
                    st.subheader(str(i))
                    for j in i.outs:
                        st.write('Out:', j, f"{j.F_vol * st.session_state.operating_hours:,.2f} kg/year")
                    st.write(i.results())

            etc = {'':[None,None]}


            capex_cost = scaled_system.installed_cost * lang_factor * 1.15
            if st.session_state.currency >1:
                labor_cost= 1440000000/target_amount/st.session_state.currency
            else:
                labor_cost= 1440000000/target_amount
            if st.session_state.gmp:
                capex_cost *=5


            #수선비=(C7*10^6*0.7/10+C7*10^6*0.3/25)/C6
            deprecation_cost = capex_cost*.082 / target_amount
            repair_cost = capex_cost * 0.05 / target_amount


            pd_up_c_feed = chem_dict_to_pd(upstream_c_amount,target_amount)
            pd_up_feed = chem_dict_to_pd(upstream_amount,target_amount)
            pd_down_feed = chem_dict_to_pd(downstream_amount,target_amount)


            utility2 = {}
            utility = {'전기':[scaled_system.power_utility.power * float(st.session_state.operating_hours) / (target_amount), bst.PowerUtility.price, scaled_system.power_utility.cost * float(st.session_state.operating_hours)/target_amount*1000]}
            for hu in scaled_system.heat_utilities:
                if hu.flow>0:
                    if hu.ID in ['low_pressure_steam','medium_pressure_steam','wastewater','sludge','solid_waste','chilled_water','cooling_water','natural_gas']:
                        utility[hu.agent.ID] = [hu.flow * float(st.session_state.operating_hours) / (target_amount), hu.cost/hu.flow, hu.cost * float(st.session_state.operating_hours)/target_amount*1000]
                    elif hu.ID =='cip_water':
                        pd_up_feed['원단위']['Water'] += hu.flow * float(st.session_state.operating_hours) / (target_amount)
                        pd_up_feed['제조원가']['Water'] += hu.flow * float(st.session_state.chem_data['Price (USD/kg)']['Water']) * float(st.session_state.operating_hours)/target_amount*1000

                    else:
                        pd_up_feed.loc[hu.agent.ID]=[hu.flow * float(st.session_state.operating_hours) / (target_amount), hu.cost/hu.flow, hu.cost * float(st.session_state.operating_hours)/target_amount*1000]

            pd_util = pd.DataFrame.from_dict(utility,orient='index',columns=['원단위','단가','제조원가'])
            pd_etc = pd.DataFrame.from_dict(etc,orient='index',columns=['원단위','제조원가'])
            merged_opex_pd = pd.concat([pd_up_c_feed, pd_up_feed, pd_down_feed, pd_util], axis=0, keys = ['발효 원재료','발효 부재료','정제 재료','유틸리티'])


            capex_pd = pd.DataFrame.from_dict({'감가비': [deprecation_cost, deprecation_cost*1000], '인건비': [labor_cost, labor_cost*1000], '수선비': [repair_cost, repair_cost*1000], '기타':[0,0]}, orient='index', columns=['원단위','제조원가'])

            capex_pd['재료'] = ''
            capex_pd = capex_pd.set_index('재료', append=True)

            try:
                currency = st.number_input('환율 [₩/USD]', value=st.session_state.currency, key=st.session_state.currency)
            except:
                currency=st.number_input('환율 [₩/USD]', value=1500, key=st.session_state.currency)
            merge_price_df = pd.concat([merged_opex_pd,capex_pd],axis=0, keys=['변동비','고정비']) * currency
            merge_price_df['원단위'] = merge_price_df['원단위']/currency
            total_sum = np.nansum(merge_price_df['제조원가'])
            merge_price_df['비중'] = merge_price_df['제조원가'] / np.nansum(merge_price_df['제조원가'])
            if currency==1:
                price_hd = [['원단위[kg/kg]','단가[USD/kg]','제조원가[USD]','비중'],[' ',' ','',f"USD {total_sum:,.2f}"],['','',"/톤",'']]
            else:
                price_hd = [['원단위[kg/kg]','단가[₩/kg]','제조원가[₩]','비중'],[' ',' ','',f"₩{total_sum:,.2f}"],['','',"/톤",'']]

            price_hd = pd.MultiIndex.from_tuples(list(zip(*price_hd)), names=["", "총 투자비","capa"])
            merge_price_df.columns=price_hd
            avt_tmp = merge_price_df.groupby(level=1).sum()
            output_index = merge_price_df.index.droplevel(level=2).drop_duplicates()
            avg_price_df = pd.DataFrame(index=output_index, columns=merge_price_df.columns, dtype=float)

            for col in merge_price_df.columns:
            # Get the 'SubCategory' values from the new index and map them to the averages
                avg_price_df[col] = avg_price_df.index.get_level_values(level=1).map(avt_tmp[col])
            columns_to_drop = [col for col in merge_price_df.columns if '단가' in col[0]]

            map_format = {}
            won_format_string = '₩ {:,.3f}' # Example: $12.3k or $12,345
            usd_format_string = 'USD {:,.3f}' # Example: $12.3k or $12,345
            won_format_string2 = '₩ {:,.0f}' # Example: $12.3k or $12,345
            usd_format_string2 = 'USD {:,.0f}' # Example: $12.3k or $12,345
            percentage_format_string = '{:.2%}' # Example: 12.34%
            mass_format_string = '{:,.2f}' # Example: 12.34%

            for col_tuple in merge_price_df.columns:
                if col_tuple[0] == '비중':
                    map_format[col_tuple] = percentage_format_string
                elif col_tuple[0] == '원단위[kg/kg]':
                    map_format[col_tuple] = mass_format_string

                elif col_tuple[0][:4] == '제조원가':
                    if int(currency)==1:
                        map_format[col_tuple] = usd_format_string2
                    else:
                        map_format[col_tuple] = won_format_string2
                elif int(currency) == 1:
                    map_format[col_tuple] = usd_format_string
                else:
                    map_format[col_tuple] = won_format_string

            sum_price = pd.DataFrame(columns=[''])
            sum_price.loc['Capex'] = [float(capex_cost * currency)]
            sum_price.loc['Capacity [MT]'] = [target_amount/1000]
            sum_price.loc[f"{st.session_state.main_source} 단가 [/MT]"] = [float(st.session_state.chem_data['Price (USD/kg)'][f"{st.session_state.main_source}"])*1000 * currency]
            sum_price.loc['제조 원가 [/MT]'] = float(list(avg_price_df.sum(axis=0))[2])

            avg_price_df = avg_price_df.drop(columns=columns_to_drop)

            # KPI Cards Presentation
            # (H4 수정) '단위당 제조원가'는 drop() 이전에 계산되어 sum_price에 저장된 값을 읽는다.
            #           drop() 이후의 avg_price_df.sum(axis=0)[2]는 '비중' 열이므로 사용하지 않는다.
            st.markdown(f"""
            <div class="kpi-container">
                <div class="kpi-card">
                    <div class="kpi-title">총 설비 투자비 (CAPEX)</div>
                    <div class="kpi-value">{"USD " if currency==1 else "₩ "}{float(capex_cost * currency):,.0f}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">연간 생산 용량 (Capacity)</div>
                    <div class="kpi-value">{target_amount/1000:,.1f} MT/yr</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">단위당 제조원가 (/MT)</div>
                    <div class="kpi-value">{"USD " if currency==1 else "₩ "}{float(sum_price.loc['제조 원가 [/MT]', '']):,.0f}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">{st.session_state.main_source} 원료 단가</div>
                    <div class="kpi-value">{"USD " if currency==1 else "₩ "}{float(st.session_state.chem_data['Price (USD/kg)'][f"{st.session_state.main_source}"])*1000 * currency:,.0f} /MT</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            res_col1, res_col2 = st.columns([1, 2], gap="medium")
            with res_col1:
                st.markdown("<div style='font-weight: 700; color: #006600; font-size: 14px; margin-bottom: 6px;'>📌 총괄 요약 지표 (Summary)</div>", unsafe_allow_html=True)
                st.dataframe(sum_price.style.format(usd_format_string2).map(lambda v: 'font-weight: bold; background-color: #f8fafc;'), use_container_width=True)
            with res_col2:
                st.markdown("<div style='font-weight: 700; color: #006600; font-size: 14px; margin-bottom: 6px;'>📋 원가 구성 요약 (Cost Breakdown)</div>", unsafe_allow_html=True)
                st.dataframe(avg_price_df.style.format(map_format), use_container_width=True)

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            st.markdown("<div style='font-weight: 700; color: #006600; font-size: 14px; margin-bottom: 6px;'>🔍 원가 항목별 상세 내역 (Detailed Drill-down)</div>", unsafe_allow_html=True)
            idx = merge_price_df.index.get_level_values(1).unique().tolist()
            detailed_idx = st.selectbox(label='세부 분석 항목 선택', options=idx, index=None, placeholder="상세 확인하고 싶은 항목을 선택하세요")
            if detailed_idx =='감가비':
                installed_cost = {}
                for i in scaled_system.units:
                    if i.installed_cost >0:
                        installed_cost[i.ID] = i.installed_cost
                installed_cost = pd.DataFrame.from_dict(installed_cost,orient='index',columns=['Base Cost USD'])
                detailed_cost = st.dataframe(installed_cost.style.format(usd_format_string), use_container_width=True)
            elif detailed_idx:
                detailed_cost = st.dataframe(merge_price_df.xs(detailed_idx,level=1).style.format(map_format), use_container_width=True)
            else:
                detailed_cost = st.dataframe(merge_price_df.xs('유틸리티',level=1).style.format(map_format), use_container_width=True)
