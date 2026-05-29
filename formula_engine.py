import re
import math

_ALLOWED_NAMES = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'int': int,
    'float': float,
    'math': math,
    'ceil': math.ceil,
    'floor': math.floor,
}

def _safe_eval(expr, context):
    safe_names = {**_ALLOWED_NAMES, **context}
    code = compile(expr, '<formula>', 'eval')
    for name in code.co_names:
        if name not in safe_names:
            raise ValueError(f"公式中引用了不允许的标识符: {name}")
    result = eval(code, {"__builtins__": {}}, safe_names)
    return result

def _eval_if_condition(condition_str, context):
    try:
        return bool(_safe_eval(condition_str, context))
    except Exception:
        return False

def _process_if(formula, context):
    pattern = r'if\s*\('
    while re.search(pattern, formula):
        formula = _resolve_one_if(formula, context)
    return formula

def _resolve_one_if(formula, context):
    idx = formula.find('if(')
    if idx == -1:
        idx = formula.find('if (')
    if idx == -1:
        return formula

    start = formula.index('(', idx)
    depth = 0
    end = start
    for i in range(start, len(formula)):
        if formula[i] == '(':
            depth += 1
        elif formula[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break

    inner = formula[start + 1:end]
    parts = _split_if_args(inner)
    if len(parts) < 2:
        return formula

    condition = parts[0].strip()
    true_val = parts[1].strip()
    false_val = parts[2].strip() if len(parts) > 2 else '0'

    cond_result = _eval_if_condition(condition, context)

    if cond_result:
        replacement = true_val
    else:
        replacement = false_val

    result = formula[:idx] + replacement + formula[end + 1:]
    return result

def _split_if_args(s):
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return parts

def evaluate_formula(formula, context):
    if not formula or not formula.strip():
        return 0

    try:
        formula = _process_if(formula, context)
        result = _safe_eval(formula, context)
        if result is None:
            return 0
        return round(float(result), 2)
    except Exception as e:
        return 0

def match_filter_conditions(conditions, context):
    if not conditions:
        return True

    for cond in conditions:
        field = cond.get('field', '')
        op = cond.get('operator', '==')
        value = cond.get('value', '')

        field_val = context.get(field, '')

        if field_val == '' and field not in context:
            return False

        try:
            if op == '==':
                if str(field_val) != str(value):
                    return False
            elif op == '!=':
                if str(field_val) == str(value):
                    return False
            elif op == '>':
                if float(field_val) <= float(value):
                    return False
            elif op == '>=':
                if float(field_val) < float(value):
                    return False
            elif op == '<':
                if float(field_val) >= float(value):
                    return False
            elif op == '<=':
                if float(field_val) > float(value):
                    return False
            elif op == 'contains':
                if str(value) not in str(field_val):
                    return False
            elif op == 'between':
                vals = str(value).split('~')
                if len(vals) == 2:
                    if not (float(vals[0]) <= float(field_val) <= float(vals[1])):
                        return False
        except (ValueError, TypeError):
            return False

    return True
