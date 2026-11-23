"""Acceptance checks for the repository's GitHub Actions workflow policy."""

import os
import re
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("CI_CONFIG_ROOT", Path(__file__).resolve().parents[1]))
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_all_external_actions_are_full_sha_pinned_with_version_comments(self):
        references = re.findall(
            r"^\s*-?\s*uses:\s*([^\s#]+)(?:\s+#\s*(.*))?$",
            self.workflow_text,
            flags=re.MULTILINE,
        )
        self.assertTrue(references, "workflow must use external actions")
        for reference, comment in references:
            if reference.startswith("./"):
                continue
            self.assertRegex(
                reference,
                r"^[^@]+@[0-9a-f]{40}$",
                f"action must use an immutable 40-character SHA: {reference}",
            )
            self.assertRegex(
                comment or "",
                r"^v\d+\.\d+\.\d+$",
                f"pinned action needs a version comment: {reference}",
            )

    def test_dependabot_updates_github_actions_pins(self):
        self.assertTrue(
            DEPENDABOT_PATH.is_file(),
            "Dependabot must periodically update GitHub Actions references",
        )
        config = DEPENDABOT_PATH.read_text(encoding="utf-8")
        self.assertRegex(
            config,
            r"(?m)^\s*-\s*package-ecosystem:\s*['\"]?github-actions['\"]?\s*$"
            r"(?s:.*?)^\s*directory:\s*['\"]?/['\"]?\s*$"
            r"(?s:.*?)^\s*schedule:\s*$"
            r"(?s:.*?)^\s*interval:\s*['\"]?(?:weekly|monthly)['\"]?\s*$",
            "Dependabot must periodically update GitHub Actions references",
        )

    def test_pr_runs_cancel_superseded_runs_by_workflow_and_ref(self):
        self.assertRegex(
            self.workflow_text,
            r"(?m)^concurrency:\s*\n  group: (.+)\n  cancel-in-progress: true$",
        )
        group = re.search(r"(?m)^  group: (.+)$", self.workflow_text).group(1)
        self.assertIn("${{ github.workflow }}", group)
        self.assertIn("${{ github.ref }}", group)

    def test_existing_ci_jobs_matrix_permissions_and_timeouts_remain(self):
        self.assertRegex(
            self.workflow_text, r"(?m)^permissions:\s*\n\s+contents:\s*read\s*$"
        )
        self.assertRegex(self.workflow_text, r"(?m)^  checks:\s*$")
        self.assertRegex(self.workflow_text, r"(?m)^  measurements:\s*$")
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', self.workflow_text)
        self.assertRegex(self.workflow_text, r"(?m)^    timeout-minutes: 20\s*$")
        self.assertRegex(self.workflow_text, r"(?m)^    timeout-minutes: 30\s*$")
        self.assertIn("python build.py check", self.workflow_text)
        self.assertIn("python -m unittest discover -s tests -v", self.workflow_text)
        self.assertIn(
            'python docs/measurements/score_bank.py --guide ../guide --workspace "$RUNNER_TEMP/readiness-bank" --compare',
            self.workflow_text,
        )


if __name__ == "__main__":
    unittest.main()
