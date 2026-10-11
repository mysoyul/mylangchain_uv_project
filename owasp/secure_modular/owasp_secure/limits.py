"""[OWASP LLM06] 입력 검증과 호출 상한: 질문 길이, 날짜 범위, 모델·도구 호출 횟수."""
import re
from datetime import date, datetime

MAX_QUESTION_CHARS = 500           # 사용자 질문 최대 길이
MAX_SPAN_DAYS = 366                # 날짜 범위 계산 상한
MAX_MODEL_CALLS = 8                # 질문 1회당 모델 호출 상한
MAX_TOOL_CALLS = 6                 # 질문 1회당 도구 호출 상한
LLM_MAX_TOKENS = 1024              # 응답 길이 상한
LLM_TIMEOUT = 60                   # 응답 대기 상한(초)
LLM_MAX_RETRIES = 3                # 재시도는 비용을 곱하므로 작게


def validate_question(question, max_chars: int = MAX_QUESTION_CHARS) -> str:
    """사용자 질문을 검증해 정리된 문자열을 반환합니다. 문제가 있으면 ValueError."""
    if not isinstance(question, str):
        raise ValueError("질문은 문자열이어야 합니다")
    question = question.strip()
    if not question:
        raise ValueError("질문이 비어 있습니다")
    if len(question) > max_chars:
        raise ValueError(f"질문이 너무 깁니다 ({len(question)}자 > {max_chars}자)")
    return question


def parse_date(value) -> date:
    """YYYY-MM-DD 형식만 검증합니다. 문제가 있으면 ValueError. (기간 상한은 parse_date_range 가 담당)"""
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"날짜 형식이 올바르지 않습니다 (YYYY-MM-DD): {str(value)[:30]!r}") from None


def parse_date_range(start, end, max_span_days: int = MAX_SPAN_DAYS) -> tuple:
    """시작일·종료일을 검증하고 (시작, 종료) date 를 반환합니다. 순서 오류·기간 초과는 ValueError."""
    d1, d2 = parse_date(start), parse_date(end)
    if d2 < d1:
        raise ValueError("종료일이 시작일보다 빠릅니다")
    if (d2 - d1).days + 1 > max_span_days:
        raise ValueError(f"기간은 최대 {max_span_days}일까지 계산할 수 있습니다")
    return d1, d2


def agent_limits(max_model_calls: int = MAX_MODEL_CALLS, max_tool_calls: int = MAX_TOOL_CALLS) -> list:
    """create_agent(middleware=...) 에 넣을 호출 횟수 제한 미들웨어 목록을 만듭니다.
    모델은 한도에서 종료하고, 도구는 초과분만 오류 메시지로 대체합니다."""
    from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware   # 필요할 때만 import
    return [
        ModelCallLimitMiddleware(run_limit=max_model_calls, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=max_tool_calls, exit_behavior="continue"),
    ]


def safe_session_id(session_id: str) -> str:
    """세션 이름을 검증합니다. (영문·숫자·_·- 64자 이내)"""
    if not isinstance(session_id, str) or not re.fullmatch(r"[\w\-]{1,64}", session_id):
        raise ValueError("세션 이름은 영문·숫자·_·- 64자 이내여야 합니다")
    return session_id
