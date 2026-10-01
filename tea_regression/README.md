# TEA-Regression Loop (economics_ver1 → ver2 회귀 수정)

| 파일 | 설명 |
|---|---|
| `economics_ver1.py` | 기준본 (계산 정상, 사용자 제공 원문) |
| `economics_ver2.py` | 디자인 변경본 (계산 깨짐, 사용자 제공 원문) |
| `economics_ver3.py` | **수정본**: ver1 로직 + ver2 디자인 |
| `diag_tea.py` | 서버에서 실행하는 읽기 전용 진단 스크립트 (H1~H3 판정) |
| `tools/semantic_diff.py` | A1/A5: AST 정규화 후 비-UI 문 시퀀스 diff |
| `tools/design_check.py` | A6: ver2 디자인 요소가 ver3에 모두 있는지 대조 |
| `reports/` | A1/A5/A6 실행 출력, ver2→ver3 unified diff |
| `a7_harness/` | A7 독립 검증 하네스 (스텁 + AppTest 차등 실행) |

재현:
```
python3 tools/semantic_diff.py economics_ver1.py economics_ver2.py   # A1 (10 hunks)
python3 tools/semantic_diff.py economics_ver1.py economics_ver3.py   # A5 (PASS, 0 hunks)
python3 tools/design_check.py  economics_ver2.py economics_ver3.py   # A6 (PASS)
```
