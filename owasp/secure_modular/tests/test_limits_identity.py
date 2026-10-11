"""limits, identity 테스트: 입력 검증, 날짜 범위, 호출 상한 미들웨어, 세션 분리"""
import unittest
from datetime import date

from owasp_secure import identity, limits, security_log
from owasp_secure.identity import UserContext


class LimitsTest(unittest.TestCase):
    def test_validate_question(self):
        self.assertEqual(limits.validate_question("  스테이크 가격은?  "), "스테이크 가격은?")
        for bad in ["", "   ", None, 123, "가" * 10_000]:
            with self.subTest(bad=str(bad)[:10]):
                with self.assertRaises(ValueError):
                    limits.validate_question(bad)
        self.assertEqual(len(limits.validate_question("가" * limits.MAX_QUESTION_CHARS)), limits.MAX_QUESTION_CHARS)

    def test_parse_date(self):
        self.assertEqual(limits.parse_date("2026-04-15"), date(2026, 4, 15))
        for bad in ["내일", "2026-13-01", "2026-04-15 10:00", "", None]:     # 형식만 검증 (기간 상한은 parse_date_range)
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    limits.parse_date(bad)

    def test_parse_date_range(self):
        self.assertEqual(limits.parse_date_range("2026-04-20", "2026-04-24"), (date(2026, 4, 20), date(2026, 4, 24)))
        self.assertEqual(limits.parse_date_range("2026-01-01", "2026-12-31")[1], date(2026, 12, 31))   # 365일: 허용
        for start, end in [("2026-05-10", "2026-05-01"), ("2000-01-01", "2100-12-31"), ("2026-01-01", "2027-12-31")]:
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    limits.parse_date_range(start, end)

    def test_agent_limits_stop_endless_tool_calls(self):
        """recursion_limit 없이 호출 횟수 제한 미들웨어만으로 끝없는 도구 호출이 멈춘다"""
        from langchain.agents import create_agent
        from langchain.tools import tool
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        class EndlessModel(BaseChatModel):
            calls: int = 0

            @property
            def _llm_type(self):
                return "endless"

            def bind_tools(self, tools, **kwargs):
                return self

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                self.calls += 1
                if self.calls > 60:
                    raise RuntimeError("데모 안전장치")
                msg = AIMessage(content="", tool_calls=[{"name": "ping", "args": {}, "id": f"c{self.calls}"}])
                return ChatResult(generations=[ChatGeneration(message=msg)])

        @tool
        def ping() -> str:
            """아무 일도 하지 않는 도구"""
            return "pong"

        model = EndlessModel()
        agent = create_agent(model=model, tools=[ping], middleware=limits.agent_limits())
        agent.invoke({"messages": [("user", "x")]})
        self.assertEqual(model.calls, limits.MAX_MODEL_CALLS)


class IdentityTest(unittest.TestCase):
    USER = UserContext("user", "홍길동", "E12345")
    ADMIN = UserContext("admin", "김부장", "E99999")

    def setUp(self):
        security_log.set_verbose(False)
        security_log.SECURITY_LOG.clear()

    def test_context_is_immutable(self):
        with self.assertRaises(Exception):
            self.USER.user_level = "admin"

    def test_scoped_thread_id(self):
        other = UserContext("user", "고길동", "E67890")
        self.assertNotEqual(identity.scoped_thread_id(self.USER, "session-001"), identity.scoped_thread_id(other, "session-001"))
        self.assertEqual(identity.scoped_thread_id(self.USER, "s_1"), "E12345:s_1")
        for bad in ["x:E12345:session-001", "", "a" * 65, "세션 이름!", None]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    identity.scoped_thread_id(other, bad)


if __name__ == "__main__":
    unittest.main()
