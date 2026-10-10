
import math
from mcp.server.fastmcp import FastMCP

# 입력 절댓값 상한 (비정상적으로 큰 값으로 계산이 깨지는 것을 방지)
LIMIT = 1e12

# MCP 서버 생성 (이름을 붙여줍니다)
mcp = FastMCP("계산기 서버")


def _check(*values: float) -> None:
    """입력이 유한한 수이고 허용 범위 안인지 검증합니다."""
    for v in values:
        if not math.isfinite(v) or abs(v) > LIMIT:
            raise ValueError(f"허용 범위(±{LIMIT:g})를 벗어난 값입니다")


# ---- 도구(Tool) 정의 ----
# @mcp.tool() 데코레이터를 붙이면 AI가 사용할 수 있는 도구가 됩니다
# 함수의 docstring(""" """)이 AI에게 전달되는 도구 설명입니다!

@mcp.tool()
def add(a: float, b: float) -> float:
    """두 숫자를 더합니다. 예: add(3, 5) → 8"""
    _check(a, b)
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """두 숫자를 뺍니다. 예: subtract(10, 3) → 7"""
    _check(a, b)
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """두 숫자를 곱합니다. 예: multiply(4, 5) → 20"""
    _check(a, b)
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """두 숫자를 나눕니다. 예: divide(10, 2) → 5. 단, b가 0이면 에러!"""
    _check(a, b)
    if b == 0:
        raise ValueError("0으로 나눌 수 없습니다!")
    result = a / b
    if not math.isfinite(result):   # 아주 작은 b 로 나누면 결과가 무한대가 될 수 있음
        raise ValueError("결과가 너무 커서 계산할 수 없습니다")
    return result

# 서버 실행 (stdio 방식 = 표준 입출력으로 통신)
if __name__ == "__main__":
    mcp.run(transport="stdio")
