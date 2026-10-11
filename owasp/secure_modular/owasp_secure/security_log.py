"""보안 이벤트 로그: 격리·차단·거부 이력을 메모리에 기록합니다."""

SECURITY_LOG: list = []   # {"kind": ..., "detail": ...} 목록. 검증 코드에서 읽거나 clear() 할 수 있음
_verbose = True


def set_verbose(value: bool) -> None:
    """True 이면 이벤트를 기록할 때 화면에도 출력합니다."""
    global _verbose
    _verbose = bool(value)


def log_security_event(kind: str, detail: str) -> None:
    """격리·차단·거부 이벤트를 기록합니다. (운영에서는 파일/로그 시스템으로 보내세요)
    TODO: 학습용 메모리 리스트이므로 세션이 끝나면 사라집니다."""
    SECURITY_LOG.append({"kind": kind, "detail": detail})
    if _verbose:
        print(f"[보안] {kind}: {detail}")


def event_kinds() -> set:
    """지금까지 기록된 이벤트 종류의 집합"""
    return {e["kind"] for e in SECURITY_LOG}
