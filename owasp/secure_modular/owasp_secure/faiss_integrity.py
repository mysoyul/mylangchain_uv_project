"""[OWASP LLM04 / ASI04] FAISS 인덱스 무결성: 저장 시 HMAC-SHA256 서명, 로드 전 검증.

FAISS.load_local 은 pickle 을 읽으므로, 변조된 index.pkl 을 로드하면 임의 코드가 실행될 수 있습니다.
서명이 일치할 때만 allow_dangerous_deserialization=True 로 로드하도록 감쌉니다.

명령줄 사용 (서명이 없는 기존 저장소에 최초 1회 서명 / 검증):
    python -m owasp_secure.faiss_integrity sign   ../db/menu_db
    python -m owasp_secure.faiss_integrity verify ../db/menu_db --index-name company_manual
"""
import argparse
import hashlib
import hmac
import os
from pathlib import Path

KEY_ENV = "FAISS_INTEGRITY_KEY"                # 서명 키를 담는 환경 변수 이름
DEFAULT_INDEX_NAME = "index"                   # FAISS.save_local 의 기본 index_name
SIGN_FILES = ("index.faiss", "index.pkl")      # 기본 index_name 의 서명 대상 파일
SIG_NAME = "index.sig"                         # 기본 index_name 의 서명 저장 파일
_CLI_HINT = "서명이 없는 기존 저장소라면 직접 만든 파일이 확실할 때만 `python -m owasp_secure.faiss_integrity sign <폴더>` 로 최초 1회 서명하세요."


def _files(index_name: str) -> tuple:
    """index_name 에 대응하는 서명 대상 파일 이름. (index_name='company_manual' -> company_manual.faiss/.pkl)"""
    return f"{index_name}.faiss", f"{index_name}.pkl"


def _sig_path(db_path, index_name: str) -> Path:
    return Path(db_path) / f"{index_name}.sig"


def get_integrity_key(key=None) -> bytes:
    """서명 키를 반환합니다. key 가 없으면 환경 변수에서 읽고, 그것도 없으면 임시 키를 만들지 않고 즉시 실패합니다.
    (임시 키로 서명하면 다음 실행에서 검증이 항상 실패하기 때문)"""
    if key is None:
        key = os.getenv(KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{KEY_ENV} 가 설정되지 않았습니다. .env 에 추가하세요. "
            "생성: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return key if isinstance(key, bytes) else str(key).encode()


def signature(db_path, key=None, index_name: str = DEFAULT_INDEX_NAME) -> str:
    """인덱스 폴더의 두 파일 이름과 내용을 이어서 HMAC-SHA256 서명(16진수)을 계산합니다."""
    p = Path(db_path)
    mac = hmac.new(get_integrity_key(key), digestmod=hashlib.sha256)
    for name in _files(index_name):
        f = p / name
        if not f.is_file():
            raise PermissionError(f"필수 파일이 없어 서명할 수 없습니다: {f}")
        mac.update(name.encode())              # 파일 이름도 포함 (파일 바꿔치기 방지)
        mac.update(f.read_bytes())
    return mac.hexdigest()


def sign_faiss_dir(db_path, key=None, index_name: str = DEFAULT_INDEX_NAME) -> None:
    """이미 저장된 인덱스에 서명 파일을 만듭니다. (지금 파일을 신뢰한다는 선언이므로 직접 만든 파일일 때만)"""
    _sig_path(db_path, index_name).write_text(signature(db_path, key, index_name), encoding="utf-8")


def is_signed(db_path, index_name: str = DEFAULT_INDEX_NAME) -> bool:
    """서명 파일이 있는지 확인합니다. (일치 여부는 verify_faiss_dir 로 확인)"""
    return _sig_path(db_path, index_name).is_file()


def ensure_signed(db_path, key=None, index_name: str = DEFAULT_INDEX_NAME) -> bool:
    """서명이 없을 때만 최초 1회 서명합니다. 새로 서명했으면 True, 이미 서명이 있으면 False 를 반환합니다.
    이미 서명이 있으면 내용이 바뀌었어도 다시 서명하지 않습니다. (변조를 덮어쓰지 않음)
    주의: 서명이 없는 시점의 파일을 신뢰한다는 선언(TOFU)입니다. 서명 파일을 지우고 변조하는 공격은 막지 못합니다."""
    if is_signed(db_path, index_name):
        return False
    sign_faiss_dir(db_path, key, index_name)
    return True


def save_faiss_signed(db, db_path, key=None, index_name: str = DEFAULT_INDEX_NAME) -> None:
    """FAISS 인덱스를 저장하고 서명을 함께 기록합니다."""
    db.save_local(str(db_path), index_name=index_name)
    sign_faiss_dir(db_path, key, index_name)


def verify_faiss_dir(db_path, key=None, index_name: str = DEFAULT_INDEX_NAME) -> None:
    """서명이 없거나 일치하지 않으면 PermissionError, 키가 없으면 RuntimeError."""
    sig_file = _sig_path(db_path, index_name)
    if not sig_file.is_file():
        raise PermissionError(f"서명 파일이 없어 로드를 거부합니다: {db_path} ({_CLI_HINT})")
    if not hmac.compare_digest(sig_file.read_text(encoding="utf-8").strip(), signature(db_path, key, index_name)):
        raise PermissionError(f"서명이 일치하지 않아 로드를 거부합니다 (파일 변조 가능성): {db_path}")


def load_faiss_verified(db_path, embeddings, key=None, index_name: str = DEFAULT_INDEX_NAME):
    """서명을 검증한 뒤에만 FAISS.load_local 을 호출합니다."""
    verify_faiss_dir(db_path, key, index_name)
    from langchain_community.vectorstores import FAISS    # 무거운 import 는 필요할 때만
    # 검증을 통과한 파일만 pickle 역직렬화를 허용
    return FAISS.load_local(str(db_path), embeddings, index_name=index_name, allow_dangerous_deserialization=True)


def main(argv=None) -> int:
    """명령줄 진입점: sign / verify. 성공 0, 실패 1 을 반환합니다."""
    parser = argparse.ArgumentParser(prog="python -m owasp_secure.faiss_integrity", description="FAISS 인덱스 서명/검증")
    parser.add_argument("command", choices=["sign", "verify"])
    parser.add_argument("db_path", help="index.faiss/index.pkl 이 있는 폴더")
    parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME)
    args = parser.parse_args(argv)
    try:
        if args.command == "sign":
            if ensure_signed(args.db_path, index_name=args.index_name):
                print(f"[서명 생성] {args.db_path} ({args.index_name})")
            else:
                print(f"[이미 서명됨] {args.db_path} ({args.index_name}) - 덮어쓰지 않았습니다")
        else:
            verify_faiss_dir(args.db_path, index_name=args.index_name)
            print(f"[검증 통과] {args.db_path} ({args.index_name})")
    except (PermissionError, RuntimeError) as e:
        print(f"[실패] {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
