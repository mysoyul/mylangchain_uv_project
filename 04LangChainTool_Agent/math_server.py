
from mcp.server.fastmcp import FastMCP

# MCP 서버 생성 (이름을 붙여줍니다)
mcp = FastMCP("계산기 서버")

# ---- 도구(Tool) 정의 ----
# @mcp.tool() 데코레이터를 붙이면 AI가 사용할 수 있는 도구가 됩니다
# 함수의 docstring(""" """)이 AI에게 전달되는 도구 설명입니다!

@mcp.tool()
def add(a: float, b: float) -> float:
    """두 숫자를 더합니다. 예: add(3, 5) → 8"""
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """두 숫자를 뺍니다. 예: subtract(10, 3) → 7"""
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """두 숫자를 곱합니다. 예: multiply(4, 5) → 20"""
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """두 숫자를 나눕니다. 예: divide(10, 2) → 5. 단, b가 0이면 에러!"""
    if b == 0:
        raise ValueError("0으로 나눌 수 없습니다!")
    return a / b

# 서버 실행 (stdio 방식 = 표준 입출력으로 통신)
if __name__ == "__main__":
    mcp.run(transport="stdio")
