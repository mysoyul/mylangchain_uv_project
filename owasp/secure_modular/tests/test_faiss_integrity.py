"""faiss_integrity 테스트: 정상은 로드, 변조·서명 없음·다른 키·키 미설정은 거부"""
import os
import secrets
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import DeterministicFakeEmbedding

from owasp_secure import faiss_integrity as fi


class FaissIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="secure_modular_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.emb = DeterministicFakeEmbedding(size=32)
        self.key = secrets.token_hex(32)
        self.good = self.tmp / "good"
        fi.save_faiss_signed(FAISS.from_texts(["시그니처 스테이크 45,000원"], self.emb), self.good, key=self.key)

    def copy_of_good(self, name):
        dst = self.tmp / name
        shutil.copytree(self.good, dst)
        return dst

    def test_signed_index_loads(self):
        db = fi.load_faiss_verified(self.good, self.emb, key=self.key)
        self.assertEqual(db.index.ntotal, 1)

    def test_tampered_pkl_is_rejected(self):
        bad = self.copy_of_good("tampered_pkl")
        with open(bad / "index.pkl", "ab") as f:
            f.write(b"\x00")
        with self.assertRaises(PermissionError):
            fi.load_faiss_verified(bad, self.emb, key=self.key)

    def test_tampered_faiss_is_rejected(self):
        bad = self.copy_of_good("tampered_faiss")
        with open(bad / "index.faiss", "ab") as f:
            f.write(b"\x00")
        with self.assertRaises(PermissionError):
            fi.verify_faiss_dir(bad, key=self.key)

    def test_missing_signature_is_rejected(self):
        bad = self.copy_of_good("unsigned")
        (bad / fi.SIG_NAME).unlink()
        with self.assertRaises(PermissionError):
            fi.load_faiss_verified(bad, self.emb, key=self.key)

    def test_wrong_key_is_rejected(self):
        with self.assertRaises(PermissionError):
            fi.load_faiss_verified(self.good, self.emb, key=secrets.token_hex(32))

    def test_missing_index_file_cannot_be_signed(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(PermissionError):
            fi.sign_faiss_dir(empty, key=self.key)

    def test_missing_key_fails_fast(self):
        with patch.dict(os.environ):
            os.environ.pop(fi.KEY_ENV, None)
            with self.assertRaises(RuntimeError):
                fi.verify_faiss_dir(self.good)

    def test_key_from_environment(self):
        with patch.dict(os.environ, {fi.KEY_ENV: self.key}):
            fi.verify_faiss_dir(self.good)          # 환경 변수 키로도 검증됨

    def test_sign_existing_dir_then_load(self):
        """서명이 없는 기존 저장소에 최초 서명하는 흐름"""
        plain = self.tmp / "plain"
        FAISS.from_texts(["와인 리스트"], self.emb).save_local(str(plain))
        with self.assertRaises(PermissionError):
            fi.load_faiss_verified(plain, self.emb, key=self.key)
        fi.sign_faiss_dir(plain, key=self.key)
        self.assertEqual(fi.load_faiss_verified(plain, self.emb, key=self.key).index.ntotal, 1)


    def test_index_name_is_signed_separately(self):
        """01-0 처럼 index_name 을 쓰는 경우: 같은 폴더의 다른 인덱스와 서명이 분리된다"""
        folder = self.tmp / "named"
        fi.save_faiss_signed(FAISS.from_texts(["사규"], self.emb), folder, key=self.key, index_name="company_manual")
        self.assertTrue((folder / "company_manual.sig").is_file())
        self.assertEqual(fi.load_faiss_verified(folder, self.emb, key=self.key, index_name="company_manual").index.ntotal, 1)
        with self.assertRaises(PermissionError):                      # 기본 이름(index)으로는 서명이 없어 거부
            fi.load_faiss_verified(folder, self.emb, key=self.key)
        with open(folder / "company_manual.pkl", "ab") as f:
            f.write(b"\x00")
        with self.assertRaises(PermissionError):
            fi.load_faiss_verified(folder, self.emb, key=self.key, index_name="company_manual")

    def test_ensure_signed_signs_once_and_never_resigns(self):
        plain = self.tmp / "plain2"
        FAISS.from_texts(["메뉴"], self.emb).save_local(str(plain))
        self.assertFalse(fi.is_signed(plain))
        self.assertTrue(fi.ensure_signed(plain, key=self.key))        # 최초 서명
        self.assertFalse(fi.ensure_signed(plain, key=self.key))       # 이미 있음
        with open(plain / "index.pkl", "ab") as f:                    # 이후 변조
            f.write(b"\x00")
        self.assertFalse(fi.ensure_signed(plain, key=self.key))       # 변조를 덮어써서 재서명하지 않음
        with self.assertRaises(PermissionError):
            fi.load_faiss_verified(plain, self.emb, key=self.key)

    def test_missing_signature_message_has_cli_hint(self):
        bad = self.copy_of_good("hint")
        (bad / fi.SIG_NAME).unlink()
        with self.assertRaises(PermissionError) as ctx:
            fi.verify_faiss_dir(bad, key=self.key)
        self.assertIn("owasp_secure.faiss_integrity sign", str(ctx.exception))

    def test_cli(self):
        plain = self.tmp / "cli"
        FAISS.from_texts(["와인"], self.emb).save_local(str(plain))
        with patch.dict(os.environ, {fi.KEY_ENV: self.key}):
            self.assertEqual(fi.main(["verify", str(plain)]), 1)       # 서명 없음
            self.assertEqual(fi.main(["sign", str(plain)]), 0)
            self.assertEqual(fi.main(["verify", str(plain)]), 0)
            self.assertEqual(fi.main(["sign", str(plain)]), 0)         # 두 번째는 덮어쓰지 않음
            with open(plain / "index.pkl", "ab") as f:
                f.write(b"\x00")
            self.assertEqual(fi.main(["verify", str(plain)]), 1)
        with patch.dict(os.environ):
            os.environ.pop(fi.KEY_ENV, None)
            self.assertEqual(fi.main(["sign", str(self.tmp / "none")]), 1)   # 키 없음


if __name__ == "__main__":
    unittest.main()
