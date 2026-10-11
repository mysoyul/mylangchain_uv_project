"""safe_eval 테스트: 허용 문법은 계산, 그 외(원본의 re.match 우회 입력 포함)는 거부"""
import unittest

import pandas as pd

from owasp_secure.safe_eval import MAX_COMMAND_LEN, safe_execute_pandas

DF = pd.DataFrame({"Age": [20, 30, 40], "Name": ["a", "b", "c"]})
REFUSED = "허용되지 않은 명령어입니다"


class SafeEvalTest(unittest.TestCase):
    def test_allowed_commands(self):
        self.assertEqual(safe_execute_pandas(DF, "df.shape"), (3, 2))
        self.assertEqual(safe_execute_pandas(DF, "df['Age'].mean()"), 30)
        self.assertEqual(safe_execute_pandas(DF, 'df["Age"].mean()'), 30)
        self.assertEqual(len(safe_execute_pandas(DF, "df.head()")), 3)
        self.assertEqual(len(safe_execute_pandas(DF, "df.head(2)")), 2)
        self.assertEqual(safe_execute_pandas(DF, "df.iloc[1]")["Age"], 30)
        self.assertEqual(list(safe_execute_pandas(DF, "df['Name']")), ["a", "b", "c"])

    def test_original_prefix_bypass_is_refused(self):
        """원본은 re.match 가 앞부분만 보고 통과시킨 뒤 전체를 eval 했다 -> 뒤에 붙인 코드가 실행됨"""
        payloads = [
            "df['Age'].mean() + len(__import__('os').getcwd())",
            "df.head() or __import__('os').getcwd()",
            "df.shape and __import__('os').system('echo x')",
            "df.iloc[0] if open('marker.txt', 'w') else 0",
            "[c for c in ().__class__.__mro__]",
        ]
        for p in payloads:
            with self.subTest(payload=p):
                self.assertTrue(str(safe_execute_pandas(DF, p)).startswith(REFUSED))

    def test_disallowed_syntax(self):
        for p in ["__import__('os')", "df.to_csv('x.csv')", "df['Age'].sum()", "df.eval('Age + 1')",
                  "df.head(n=2)", "df.head(0)", "df.head(1000)", "df.head(True)", "df.iloc[-1]", "df.iloc[99]",
                  "df['없는컬럼']", "df[df['Age'] > 20]", "df.__class__", "lambda: 1", "df; df", ""]:
            with self.subTest(payload=p):
                self.assertTrue(str(safe_execute_pandas(DF, p)).startswith(REFUSED))

    def test_too_long_command(self):
        long_command = "df['Age']" + ".mean()" * 40
        self.assertGreater(len(long_command), MAX_COMMAND_LEN)
        self.assertTrue(safe_execute_pandas(DF, long_command).startswith(REFUSED))
        # 앞뒤 공백은 strip 되므로 길이 계산에 포함되지 않는다
        self.assertEqual(safe_execute_pandas(DF, "df.shape" + " " * MAX_COMMAND_LEN), (3, 2))

    def test_non_string_input_does_not_raise(self):
        self.assertTrue(str(safe_execute_pandas(DF, None)).startswith(REFUSED))


if __name__ == "__main__":
    unittest.main()
