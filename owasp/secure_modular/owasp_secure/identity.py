"""[OWASP ASI03 / LLM03] 호출자 신원과 권한: LLM 이 아니라 서버가 아는 신원으로 권한을 판단합니다.

UserContext 는 서버의 인증 결과(로그인 토큰 검증 등)로만 만들어야 하며, 사용자 메시지에서 읽으면 안 됩니다.
도구는 사번을 인자로 받지 말고 ToolRuntime 의 context 에서 읽어, LLM 이 다른 사람의 사번을 넣을 수 없게 합니다.
"""
from dataclasses import dataclass

from .limits import safe_session_id


@dataclass(frozen=True)
class UserContext:
    """호출자 정보. frozen 이라 실행 중 바꿀 수 없습니다. create_agent(context_schema=UserContext) 로 사용."""
    user_level: str = "user"       # 'user' 또는 'admin'
    user_name: str = ""
    employee_id: str = ""


def scoped_thread_id(ctx: UserContext, session_id: str) -> str:
    """클라이언트가 정한 세션 이름에 서버가 아는 사번을 붙여 사용자별로 분리합니다. (다른 사용자의 대화 기록 접근 방지)"""
    return f"{ctx.employee_id}:{safe_session_id(session_id)}"   # ':' 등으로 다른 사용자 접두어를 흉내 내는 것을 차단
