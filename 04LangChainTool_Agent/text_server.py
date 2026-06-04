
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("텍스트 처리 서버")

@mcp.tool()
def to_uppercase(text: str) -> str:
    """텍스트를 대문자로 변환합니다. 예: to_uppercase("hello") → "HELLO""""
    return text.upper()

@mcp.tool()
def count_words(text: str) -> int:
    """텍스트의 단어 수를 세어 반환합니다. 예: count_words("hello world") → 2""""
    return len(text.split())

@mcp.tool()
def reverse_text(text: str) -> str:
    """텍스트를 거꾸로 뒤집습니다. 예: reverse_text("hello") → "olleh""""
    return text[::-1]

if __name__ == "__main__":
    mcp.run(transport="stdio")
