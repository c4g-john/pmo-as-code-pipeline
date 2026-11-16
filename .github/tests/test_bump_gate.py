"""Offline regression tests for the actual bump workflow shell bodies.

No package install, GitHub call, repository mutation, or network access.
Run: python3 .github/tests/test_bump_gate.py
"""
import itertools
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows/bump-docassert.yml"


def step(name):
    text = WORKFLOW.read_text()
    block = text.split("      - name: " + name + "\n", 1)[1]
    return block.split("\n      - ", 1)[0]


def body(name):
    return textwrap.dedent(step(name).split("        run: |\n", 1)[1])


class BumpGateTests(unittest.TestCase):
    def test_publish_requires_explicit_success(self):
        self.assertIn(
            "if: success() && steps.v.outputs.latest != steps.v.outputs.current "
            "&& steps.verify.outputs.result == 'PASS'",
            step("Open the bump PR"),
        )
        self.assertNotIn("continue-on-error", step("Verify this repo against the new version"))

    def exercise(self, statuses, missing_command=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = root / "calls"
            output = root / "outputs"
            env = dict(os.environ, GITHUB_OUTPUT=str(output), CALLS=str(calls))
            env["PATH"] = str(root) + os.pathsep + env["PATH"]
            if not missing_command:
                (root / "docassert").write_text(
                    "#!/bin/bash\n"
                    'echo "docassert $*" >> "$CALLS"\n'
                    'echo "diagnostic $1"\n'
                    "case $1 in\n"
                    f"validate) exit {statuses[0]};;\n"
                    f"consistency) exit {statuses[1]};;\n"
                    f"projects) exit {statuses[2]};;\n"
                    "*) exit 99;;\nesac\n"
                )
                (root / "docassert").chmod(0o755)
            for command in ("git", "gh"):
                (root / command).write_text(
                    "#!/bin/bash\n"
                    f'echo "{command} $*" >> "$CALLS"\n'
                    'if [ "$1 $2" = "pr list" ]; then echo 0; fi\n'
                )
                (root / command).chmod(0o755)
            verify = body("Verify this repo against the new version")
            for filename in ("v", "c", "p"):
                verify = verify.replace("/tmp/" + filename + ".txt", str(root / (filename + ".txt")))
            if missing_command:
                # Guaranteed missing executable even if docassert is installed on the host.
                verify = verify.replace("docassert ", str(root / "missing-docassert") + " ")
            publish = body("Open the bump PR")
            publish = publish.replace("${{ steps.v.outputs.latest }}", "1.0.3")
            publish = publish.replace("${{ steps.v.outputs.current }}", "1.0.2")
            publish = publish.replace("${{ steps.verify.outputs.result }}", "PASS")
            # Same -e/pipefail shell semantics as Actions. Static gate assertion
            # above additionally covers its separate-step explicit condition.
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", verify + "\n" + publish],
                cwd=root, env=env, capture_output=True, text=True,
            )
            return result, output.read_text(), calls.read_text() if calls.exists() else ""

    def test_all_pass_and_all_failure_combinations(self):
        for statuses in itertools.product((0, 1), repeat=3):
            with self.subTest(statuses=statuses):
                result, output, calls = self.exercise(statuses)
                self.assertEqual(sum(line.startswith("docassert ") for line in calls.splitlines()), 3, "collect diagnostics for every check")
                for name in ("validate", "consistency", "projects"):
                    self.assertIn("diagnostic " + name, result.stdout)
                if any(statuses):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("result=FAIL", output)
                    self.assertIn("::error::Bump verification failed", result.stdout)
                    self.assertNotIn("git ", calls)
                    self.assertNotIn("gh ", calls)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(output, "result=PASS\n")
                    self.assertIn("git push", calls)
                    self.assertIn("gh pr create", calls)
                    self.assertIn("gh pr merge", calls)

    def test_command_not_found_fails_closed(self):
        result, output, calls = self.exercise((0, 0, 0), missing_command=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validate=127 consistency=127 registry=127", output)
        self.assertNotIn("git ", calls)
        self.assertNotIn("gh ", calls)


if __name__ == "__main__":
    unittest.main()
