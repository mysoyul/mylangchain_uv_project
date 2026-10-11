"""[OWASP LLM01 / ASI06] 검색 문서·웹 결과를 '지시'가 아닌 '데이터'로 다루기 위한 도구 모음.

L1 문서 스캔·격리 -> L2 프롬프트 구조화(길이 상한, 꺾쇠 무력화) -> L3 출력 검사.
정규식 스캔은 알려진 표현만 잡으므로, 마지막 방어선으로 출력 검사를 함께 씁니다.
문서 객체는 page_content 와 metadata 속성을 가진 것(langchain Document)을 기대합니다.
"""
import re
import unicodedata
from urllib.parse import urlparse

from .security_log import log_security_event

# ---- 기본값 ----
MAX_DOC_CHARS = 2000          # 문서 1건당 프롬프트에 넣는 최대 길이
FALLBACK_ANSWER = "죄송합니다. 안전하게 답변을 생성하지 못했습니다. 다시 질문해 주세요."
NO_SAFE_DOCS_ANSWER = "검색된 문서가 안전 검사를 통과하지 못해 답변을 생성하지 않았습니다. 질문을 바꿔 다시 시도해 주세요."

# 지시문 패턴. 너무 넓게 잡으면 정상 문서가 격리되므로 "지시 + 무시/출력" 조합만 봅니다.
# 공백 제거본에도 적용하므로 공백은 \s* 로 느슨하게 씁니다.
INJECTION_PATTERNS = [
    (r"(이전|위의|앞의|기존).{0,8}(지시|명령|규칙|프롬프트).{0,8}(무시|잊)", "이전 지시 무시 요구"),
    (r"ignore\s*(all\s*)?(the\s*)?(previous|prior|above)\s*(instructions|rules|prompts?)", "ignore previous instructions"),
    (r"\[?\s*(시스템|system)\s*(지시|메시지|prompt|message)\s*\]?", "가짜 시스템 지시 표지"),
    (r"(시스템\s*프롬프트|system\s*prompt).{0,20}(출력|보여|알려|print|reveal|show)", "시스템 프롬프트 노출 요구"),
]
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")        # 마크다운 이미지 = 자동 요청으로 데이터가 새는 통로
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
# 시스템 프롬프트에 심어 둔 탐지용 표식(카나리). 답변에 나오면 시스템 프롬프트가 그대로 출력(유출)된 것이다.
# 운영자만 아는 업무 정보를 프롬프트에 넣지 않는 것이 근본 대책이며, 이 검사는 유출을 알아채는 보조 장치다.
SECRET_PATTERNS = [
    (r"CANARY-[0-9a-f]{4}", "내부 탐지 토큰(프롬프트 유출)"),
]


# ================= L1: 스캔·격리 =================
def _normalize(text: str) -> str:
    """NFKC 정규화 + 제로폭 문자 제거 + 소문자화"""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"[​-‏﻿]", "", text).lower()


def scan_text(text: str) -> list:
    """텍스트에서 발견된 지시문 패턴의 사유 목록을 반환합니다. (일반본과 공백 제거본을 모두 검사)"""
    plain = _normalize(text)
    squashed = re.sub(r"\s+", "", plain)     # 글자 사이에 공백을 끼운 난독화 대비
    return [label for pat, label in INJECTION_PATTERNS if re.search(pat, plain) or re.search(pat, squashed)]


def doc_label(doc) -> str:
    """로그·화면 표시용 문서 이름 (url > source > 출처 없음)"""
    return next((str(doc.metadata[k]) for k in ("url", "source") if doc.metadata.get(k)), "(출처 없음)")


def scan_documents(docs: list) -> tuple:
    """문서 목록을 검사해 (통과 목록, 격리 목록[{'doc','reasons'}]) 을 반환합니다. 메타데이터도 함께 검사합니다."""
    clean, quarantined = [], []
    for doc in docs:
        text = doc.page_content + "\n" + " ".join(str(v) for v in doc.metadata.values())
        reasons = scan_text(text)
        if reasons:
            quarantined.append({"doc": doc, "reasons": reasons})
            log_security_event("문서 격리", f"{doc_label(doc)} | {reasons}")
        else:
            clean.append(doc)
    return clean, quarantined


# ================= L2: 구조화 =================
def neutralize(text: str) -> str:
    """꺾쇠를 전각 문자로 바꿔, 문서가 태그를 닫거나 위조하지 못하게 합니다."""
    return text.replace("<", "＜").replace(">", "＞")


def build_context(docs: list, max_chars: int = MAX_DOC_CHARS) -> str:
    """통과한 문서를 '출처 + 본문(길이 상한)' 형태로 조립합니다. (전체 메타데이터는 넣지 않음)"""
    parts = []
    for doc in docs:
        source = neutralize(str(doc.metadata.get("url") or doc.metadata.get("source") or "unknown"))
        body = neutralize(doc.page_content)[:max_chars]
        parts.append(f"---\n[출처: {source}]\n{body}\n---")
    return "\n\n".join(parts)


# ================= L3: 출력 검사 =================
def guard_output(answer, allowed_hosts=frozenset(), check_links: bool = True) -> tuple:
    """답변을 검사해 (사용자에게 보낼 답변, 발견 사항) 을 반환합니다. 문제가 있으면 대체 문구로 교체합니다.
    allowed_hosts: 링크로 허용할 도메인 (예: 이번 검색 결과에 실제로 있던 URL 의 도메인)."""
    answer = answer if isinstance(answer, str) else str(answer)
    findings = []
    if IMAGE_RE.search(answer):
        findings.append("마크다운 이미지 삽입")
    if check_links:
        allowed = {h.lower() for h in allowed_hosts}
        for url in URL_RE.findall(answer):
            host = (urlparse(url).hostname or "").lower()
            if host not in allowed:
                findings.append(f"허용되지 않은 도메인: {host}")
    for pat, label in SECRET_PATTERNS:
        if re.search(pat, answer):
            findings.append(label)
    if findings:
        log_security_event("출력 차단", str(findings))
    return (FALLBACK_ANSWER if findings else answer), findings


def hosts_of(docs: list) -> set:
    """문서 메타데이터의 url 에서 도메인 집합을 만듭니다. (출력 검사의 링크 허용 목록용)"""
    return {(urlparse(str(d.metadata["url"])).hostname or "").lower() for d in docs if d.metadata.get("url")}
