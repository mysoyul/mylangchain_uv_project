
from mcp.server.fastmcp import FastMCP

# 입력 길이 상한 (과도하게 긴 입력으로 인한 자원 낭비를 방지)
MAX_TEXT_CHARS = 10_000

mcp = FastMCP("텍스트 처리 서버")


def _check_len(text: str) -> None:
    """입력 길이가 상한을 넘으면 오류를 발생시킵니다."""
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"텍스트가 너무 깁니다 ({len(text):,}자 > {MAX_TEXT_CHARS:,}자)")


@mcp.tool()
def to_uppercase(text: str) -> str:
    """텍스트를 대문자로 변환합니다. 예: to_uppercase('hello') → 'HELLO'"""
    _check_len(text)
    return text.upper()

@mcp.tool()
def count_words(text: str) -> int:
    """텍스트의 단어 수를 세어 반환합니다. 예: count_words('hello world') → 2"""
    _check_len(text)
    return len(text.split())

@mcp.tool()
def reverse_text(text: str) -> str:
    """텍스트를 거꾸로 뒤집습니다. 예: reverse_text('hello') → 'olleh'"""
    _check_len(text)
    return text[::-1]

if __name__ == "__main__":
    mcp.run(transport="stdio")
