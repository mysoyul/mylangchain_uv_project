"""owasp_secure — OWASP LLM/Agentic Top 10 대응 공통 모듈.

모듈별 역할
- faiss_integrity : FAISS 인덱스 서명·검증 로드 (LLM04)
- safe_eval       : eval 없는 pandas 명령 실행 (LLM10)
- doc_guard       : 문서 스캔·구조화·출력 검사 (LLM01)
- limits          : 입력 검증·호출 상한 (LLM06)
- identity        : 호출자 신원·권한·세션 분리 (ASI03)
- security_log    : 보안 이벤트 기록
"""
from . import doc_guard, faiss_integrity, identity, limits, safe_eval, security_log
from .doc_guard import build_context, guard_output, scan_documents, scan_text
from .faiss_integrity import ensure_signed, is_signed, load_faiss_verified, save_faiss_signed, sign_faiss_dir, verify_faiss_dir
from .identity import UserContext, scoped_thread_id
from .limits import agent_limits, parse_date, parse_date_range, validate_question
from .safe_eval import UnsafeCommandError, safe_execute_pandas
from .security_log import SECURITY_LOG, log_security_event, set_verbose

__all__ = [
    "doc_guard", "faiss_integrity", "identity", "limits", "safe_eval", "security_log",
    "build_context", "guard_output", "scan_documents", "scan_text",
    "ensure_signed", "is_signed", "load_faiss_verified", "save_faiss_signed", "sign_faiss_dir", "verify_faiss_dir",
    "UserContext", "scoped_thread_id",
    "agent_limits", "parse_date", "parse_date_range", "validate_question",
    "UnsafeCommandError", "safe_execute_pandas",
    "SECURITY_LOG", "log_security_event", "set_verbose",
]
