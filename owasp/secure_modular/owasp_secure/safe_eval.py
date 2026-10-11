"""[OWASP LLM10 / ASI05] eval 없이 허용한 pandas 명령만 실행합니다.

원본은 re.match 로 "앞부분"만 검사한 뒤 문자열 전체를 eval 했습니다. 여기서는 ast 로 구조를 분석해
허용한 문법(df, df.shape, df['컬럼'], df.iloc[정수], .mean(), .head(n))만 직접 계산합니다.
"""
import ast

MAX_COMMAND_LEN = 200                  # 명령 길이 상한
MAX_HEAD_ROWS = 100                    # head(n) 의 n 상한
ALLOWED_METHODS = {"mean", "head"}     # 허용할 메서드 이름


class UnsafeCommandError(ValueError):
    """허용되지 않은 명령일 때 발생"""


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _eval_node(node, df):
    """허용한 문법만 계산하고, 그 외는 UnsafeCommandError 를 발생시킵니다. (eval 미사용)"""
    # df
    if isinstance(node, ast.Name) and node.id == "df":
        return df

    # df.shape
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "df" and node.attr == "shape"):
        return df.shape

    # df['컬럼']  /  df.iloc[정수]
    if isinstance(node, ast.Subscript):
        idx = node.slice
        if not isinstance(idx, ast.Constant):
            raise UnsafeCommandError("인덱스는 상수만 허용")
        base = node.value
        if isinstance(base, ast.Name) and base.id == "df":
            if isinstance(idx.value, str) and idx.value in df.columns:
                return df[idx.value]
            raise UnsafeCommandError(f"존재하지 않는 컬럼: {idx.value!r}")
        if (isinstance(base, ast.Attribute) and base.attr == "iloc"
                and isinstance(base.value, ast.Name) and base.value.id == "df"):
            if _is_int(idx.value) and 0 <= idx.value < len(df):
                return df.iloc[idx.value]
            raise UnsafeCommandError("iloc 인덱스는 범위 안의 정수만 허용")

    # <허용된 식>.mean()  /  <허용된 식>.head(n)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr not in ALLOWED_METHODS or node.keywords:
            raise UnsafeCommandError(f"허용되지 않은 메서드/인자: {node.func.attr}")
        target = _eval_node(node.func.value, df)     # 대상도 재귀적으로 검증
        if node.func.attr == "mean" and not node.args:
            return target.mean()
        if node.func.attr == "head" and len(node.args) <= 1:
            n = 5
            if node.args:
                a = node.args[0]
                if not (isinstance(a, ast.Constant) and _is_int(a.value) and 1 <= a.value <= MAX_HEAD_ROWS):
                    raise UnsafeCommandError(f"head 인자는 1~{MAX_HEAD_ROWS} 정수만 허용")
                n = a.value
            return target.head(n)

    raise UnsafeCommandError(f"허용되지 않은 문법: {type(node).__name__}")


def safe_execute_pandas(df, command: str):
    """ast 로 허용 문법만 해석해 실행합니다. 실패하면 이유를 문자열로 돌려줍니다. (예외를 던지지 않음)"""
    command = str(command).strip()
    if len(command) > MAX_COMMAND_LEN:
        return "허용되지 않은 명령어입니다. (너무 김)"
    try:
        tree = ast.parse(command, mode="eval")   # 코드를 실행하지 않고 "구조"만 분석
        return _eval_node(tree.body, df)
    except (SyntaxError, UnsafeCommandError) as e:
        return f"허용되지 않은 명령어입니다. ({e})"
    except Exception as e:                       # 계산 중 일반 오류
        return f"실행 오류: {type(e).__name__}"
