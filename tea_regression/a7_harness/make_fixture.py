import json, pickle, sys, pandas as pd
sys.path.insert(0, '/tmp/claude-0/a7/env')
from streamlit_flow.elements import StreamlitFlowNode as N, StreamlitFlowEdge as E
base = '/home/sbf/JLee/test/data/scenario/'
tmp = {'currency': 1500, 'operating_hours': 7920, 'product_index': 2, 'source_index': 1,
       'target_amount': 100.0, 'od_to_dcw': 0.22, 'electricity_price': 0.128}
heat = {'low_pressure_steam': 0.0123, 'cooling_water': 0.00005}
json.dump({'tmp': tmp, 'heat_utility': heat}, open(base + 'initial_val.json', 'w'), ensure_ascii=False)
chem = pd.DataFrame({'Name': ['Water', 'Glucose', 'Ethanol'], 'Formula': ['H2O', 'C6H12O6', 'C2H6O'],
                     'Price (USD/kg)': [0.001, 0.5, 3.0], 'Phase': ['l', 'l', 'l']})
spec = [('feed', '배치 피드', {'solution': '용액 1'}), ('R1', '발효기', {}), ('S1', '분배기', {}),
        ('CA', '원심분리기', {}), ('CB', '원심분리기', {}), ('M1', 'Mix-Tank', {}), ('prod', 'Product Stream', {})]
nodes = [N(i, (k * 100, 0), {'content': f'{t}_{i}', 'node_type': t, 'Value': v}) for k, (i, t, v) in enumerate(spec)]
ed = [('feed', 'R1'), ('R1', 'S1'), ('S1', 'CA'), ('S1', 'CB'), ('CA', 'M1'), ('CB', 'M1'), ('M1', 'prod')]
edges = [E(f'e{k}', s, t) for k, (s, t) in enumerate(ed)]
raw = {'tmp': tmp, 'nodes': nodes, 'edges': edges, 'chem_data': chem,
       'solutions': {'용액 1': {'Glucose': 50.0, 'Ethanol': 20.0, 'Water': 930.0}, 'Water': {'Water': 1000}},
       'autoclave': {'용액 1': True, 'Water': False}, 'prices': {}, 'heat_utility': heat}
pickle.dump(raw, open(base + 'initial_val.pkl', 'wb'))
print('ok')
