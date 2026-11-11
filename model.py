        if row and len(row) > 1
        and row[0] is not None and row[1] is not None
    ]

    chosen = next(
        (row for row in rows[6:]
         if row and row[0] is not None and str(row[0]) == str(rowcode)),
        None
    )

    if chosen is None:
        chosen = next(
            (row for row in rows[6:]
             if row and len(row) > 1
             and row[0] is not None and row[1] is not None),
            None
        )

    if chosen is None:
        raise ValueError('선택할 수 있는 산업 행이 없습니다.')

    cells = []
    header_codes = rows[4]
    header_names = rows[5] if len(rows) > 5 else []

    for i in range(2, len(header_codes)):
        if header_codes[i] is None:
            continue

        value = chosen[i] if i < len(chosen) else None
        if isinstance(value, (float, int)):
            value = float(value)
        elif value is not None:
            value = str(value)

        column_name = (
            str(header_names[i])
            if i < len(header_names) and header_names[i] is not None
            else ''
        )

        cells.append({
            'code': str(header_codes[i]),
            'name': column_name,
            'value': value
        })

    unit_value = rows[3][0] if rows[3] and rows[3][0] else '계수'
    unit_value = str(unit_value).replace(
        '係数', '계수 / 비율: 행·열 명칭 확인'
    )

    return emit({
        'rows': choices,
        'selected': str(chosen[0]),
        'name': str(chosen[1]),
        'unit': unit_value,
        'cells': cells
    })


def simulate(payload):
    if not valid:
        raise ValueError('검증된 데이터가 없습니다. 엑셀 파일을 먼저 불러오세요.')

    shocks = json.loads(payload)
    demand = np.zeros(len(codes))

    code_index = {code: i for i, code in enumerate(codes)}

    for shock in shocks:
        code = str(shock['code'])
        if code not in code_index:
            raise ValueError('현재 분류에 없는 산업 코드입니다: ' + code)

        amount = float(shock['amount'])
        if not np.isfinite(amount) or amount < 0:
            raise ValueError('수요 증가액은 0 이상의 유한한 숫자여야 합니다.')

        demand[code_index[code]] += amount

    if not demand.sum() > 0:
        raise ValueError('한 산업 이상의 양의 수요 증가액을 입력하세요.')

    production = L @ demand
    imports = M @ demand
    value_added = V @ demand

    result = [
        {
            'code': code,
            'name': name,
            'production': float(prod),
            'imports': float(imp),
            'valueAdded': float(va)
        }
        for code, name, prod, imp, va
        in zip(codes, names, production, imports, value_added)
    ]

    result.sort(key=lambda row: row['production'], reverse=True)

    return emit({
        'demand': float(demand.sum()),
        'production': float(production.sum()),
        'imports': float(imports.sum()),
        'valueAdded': float(value_added.sum()),
        'multiplier': float(production.sum() / demand.sum()),
        'rows': result
    })
