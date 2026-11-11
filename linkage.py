# 연쇄효과(영향력계수·감응도계수) 계산 — model.py 뒤에 실행되어 같은 전역변수(L, codes, names, valid, emit)를 사용함
import numpy as np

def linkage():
    if not valid:
        raise ValueError('검증된 데이터가 없습니다. 엑셀 파일을 먼저 불러오세요.')
    col = L.sum(axis=0)   # 열합계: 후방연쇄
    row = L.sum(axis=1)   # 행합계: 전방연쇄
    back = col / col.mean()
    fwd = row / row.mean()
    out = []
    for c, n, b, f in zip(codes, names, back, fwd):
        b = float(b)
        f = float(f)
        if b >= 1 and f >= 1:
            t = 'key'
        elif b >= 1:
            t = 'back'
        elif f >= 1:
            t = 'fwd'
        else:
            t = 'low'
        out.append({'code': c, 'name': n, 'backward': b, 'forward': f, 'type': t})
    return emit({'rows': out})
