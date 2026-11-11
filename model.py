
import json, io
import numpy as np
import openpyxl

book = None
codes = []
names = []
L = M = V = None
sheets = []
valid = False
classification = None


def emit(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def code_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def initialize(raw):
    global book, codes, names, L, M, V, sheets, valid, classification
    valid = False

    wb = openpyxl.load_workbook(
        io.BytesIO(bytes(raw)), read_only=True, data_only=True
    )
    try:
        book = {name: list(wb[name].values) for name in wb.sheetnames}
    finally:
        wb.close()
    sheets = list(book)

    required = [
        '총투입계수(A)', '수입투입계수(Am)', '국산투입계수(Ad)',
        '생산유발계수', '수입유발계수', '부가가치유발계수'
    ]
    missing = [name for name in required if name not in book]
    if missing:
        raise ValueError('필수 시트가 없습니다: ' + ', '.join(missing))

    base = book['국산투입계수(Ad)']
    if len(base) < 7 or len(base[4]) < 3:
        raise ValueError('엑셀 시트 구조를 읽을 수 없습니다.')

    # 9090은 산업부문이 아닌 합계 열이므로 제외
    codes = [
        code_text(x) for x in base[4][2:]
        if x is not None and code_text(x) != '9090'
    ]
    if not codes or len(codes) != len(set(codes)):
        raise ValueError('산업 코드가 없거나 중복되어 있습니다.')

    classification = {
        380: '기본부문',
        33: '대분류',
        83: '중분류',
        165: '소분류'
    }.get(len(codes), str(len(codes)) + '개 부문')

    name_map = {
        code_text(r[0]): str(r[1]).strip()
        for r in base[6:]
        if r and len(r) > 1 and r[0] is not None and r[1] is not None
    }
    if any(c not in name_map for c in codes):
        raise ValueError('일부 산업의 이름을 찾지 못했습니다.')
    names = [name_map[c] for c in codes]

    def matrix(sheet_name):
        rows = book[sheet_name]
        row_index = {
            code_text(r[0]): i
            for i, r in enumerate(rows)
            if r and r[0] is not None
        }
        col_index = {
            code_text(c): i
            for i, c in enumerate(rows[4])
            if c is not None
        }

        if any(c not in row_index for c in codes) or any(
            c not in col_index for c in codes
        ):
            raise ValueError(
                sheet_name + ' 시트의 산업 코드가 일치하지 않습니다.'
            )

        data = np.array([
            [rows[row_index[r]][col_index[c]] for c in codes]
            for r in codes
        ], dtype=float)

        if not np.isfinite(data).all():
            raise ValueError(sheet_name + ' 시트에 숫자가 아닌 값이 있습니다.')
        return data

    L = matrix('생산유발계수')
    M = matrix('수입유발계수')
    V = matrix('부가가치유발계수')
    ad = matrix('국산투입계수(Ad)')
    am = matrix('수입투입계수(Am)')

    total = book['총투입계수(A)']
    col_index = {
        code_text(c): i
        for i, c in enumerate(total[4])
        if c is not None
    }

    va_row = next(
        (r for r in total
         if r and r[0] is not None and code_text(r[0]) == '9690'),
        None
    )
    if va_row is None:
        raise ValueError(
            '총투입계수(A)에서 부가가치계(9690)를 찾지 못했습니다.'
        )

    try:
        va = np.array([va_row[col_index[c]] for c in codes], dtype=float)
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('부가가치계 행을 읽지 못했습니다.')

    eye = np.eye(len(codes))
    residuals = {
        '생산': float(np.max(np.abs((eye - ad) @ L - eye))),
        '수입': float(np.max(np.abs(am @ L - M))),
        '부가가치': float(np.max(np.abs(va[:, None] * L - V)))
    }

    if max(residuals.values()) >= 1e-8:
        raise ValueError('계수 검증 실패: ' + str(residuals))

    valid = True
    return emit({
        'classification': classification,
        'sectorCount': len(codes),
        'sectors': [
            {'code': c, 'name': n}
            for c, n in zip(codes, names)
        ],
        'sheets': sheets,
        'residuals': residuals
    })


def explore(sheet, rowcode):
    if book is None:
        raise ValueError('먼저 엑셀 파일을 불러오세요.')
    if sheet not in book:
        raise ValueError('선택한 시트가 없습니다: ' + str(sheet))

    rows = book[sheet]
    code_set = set(codes)

    choices = [
        {'code': code_text(r[0]), 'name': str(r[1]).strip()}
        for r in rows[6:]
        if r and len(r) > 1
        and r[0] is not None
        and code_text(r[0]) in code_set
        and r[1] is not None
    ]

    chosen = next(
        (r for r in rows[6:]
         if r and r[0] is not None
         and code_text(r[0]) == code_text(rowcode)),
        None
    )

    if chosen is None:
        chosen = next(
            (r for r in rows[6:]
             if r and len(r) > 1
             and r[0] is not None
             and code_text(r[0]) in code_set
             and r[1] is not None),
            None
        )

    if chosen is None:
        raise ValueError('선택할 수 있는 산업 행이 없습니다.')

    header_codes = rows[4]
    header_names = rows[5] if len(rows) > 5 else []
    cells = []

    for i in range(2, len(header_codes)):
        code = code_text(header_codes[i])
        if code not in code_set:
            continue

        value = chosen[i] if i < len(chosen) else None
        if isinstance(value, (int, float)):
            value = float(value)
        elif value is not None:
            value = str(value)

        col_name = (
            str(header_names[i]).strip()
            if i < len(header_names) and header_names[i] is not None
            else ''
        )
        cells.append({
            'code': code,
            'name': col_name,
            'value': value
        })

    unit = rows[3][0] if rows[3] and rows[3][0] else '계수'
    unit = str(unit).replace(
        '係数', '계수 / 비율: 행·열 명칭 확인'
    )

    return emit({
        'rows': choices,
        'selected': code_text(chosen[0]),
        'name': str(chosen[1]).strip(),
        'unit': unit,
        'cells': cells
    })


def simulate(payload):
    if not valid:
        raise ValueError(
            '검증된 데이터가 없습니다. 엑셀 파일을 먼저 불러오세요.'
        )

    demand = np.zeros(len(codes))
    index = {c: i for i, c in enumerate(codes)}

    for item in json.loads(payload):
        code = code_text(item['code'])
        if code not in index:
            raise ValueError('현재 분류에 없는 산업 코드입니다: ' + code)

        amount = float(item['amount'])
        if not np.isfinite(amount) or amount < 0:
            raise ValueError(
                '수요 증가액은 0 이상의 유한한 숫자여야 합니다.'
            )
        demand[index[code]] += amount

    if demand.sum() <= 0:
        raise ValueError(
            '한 산업 이상의 양의 수요 증가액을 입력하세요.'
        )

    production = L @ demand
    imports = M @ demand
    value_added = V @ demand

    result = [
        {
            'code': c,
            'name': n,
            'production': float(p),
            'imports': float(m),
            'valueAdded': float(v)
        }
        for c, n, p, m, v
        in zip(codes, names, production, imports, value_added)
    ]

    result.sort(
        key=lambda r: r['production'],
        reverse=True
    )

    return emit({
        'demand': float(demand.sum()),
        'production': float(production.sum()),
        'imports': float(imports.sum()),
        'valueAdded': float(value_added.sum()),
        'multiplier': float(production.sum() / demand.sum()),
        'rows': result
    })
