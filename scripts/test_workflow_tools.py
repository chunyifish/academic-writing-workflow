"""Offline regression tests for observable helper behavior; all data synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import workflow_tools as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def record(self, **overrides):
        value = {"schema_version": 1, "mode": "draft", "sources": [], "results": [],
                 "claims": [], "decisions": [], "issues": [], "terms": [], "artifacts": []}
        value.update(overrides)
        path = self.root / "research.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def codes(self, report):
        return {row["code"] for row in report["findings"]}

    def source(self, **overrides):
        value = {"id": "S1", "key": "Synthetic2026", "title": "Synthetic citation only",
                 "access": "full", "read_locator": "all sections", "metadata_status": "verified",
                 "version_status": "synthetic_checked", "retraction_status": "synthetic_checked"}
        value.update(overrides)
        return value

    def test_init_creates_templates_without_overwrite(self):
        project = self.root / "new"
        result = w.new_project(project, "合成案例")
        self.assertEqual(len(result["files_created"]), 6)
        original = (project / "research.json").read_bytes()
        with self.assertRaises(ValueError):
            w.new_project(project, "不可覆蓋")
        self.assertEqual(original, (project / "research.json").read_bytes())

    def test_balanced_registered_keys_still_no_semantic_verification(self):
        path = self.record(sources=[self.source()])
        manuscript = self.root / "稿件.md"
        manuscript.write_text("僅為合成格式測試 [@Synthetic2026]。", encoding="utf-8")
        report = w.check_project(path, manuscript)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["coverage"]["semantic_claim_support"], "not_checked_by_program")

    def test_missing_and_unused_keys(self):
        path = self.record(sources=[self.source()])
        draft = self.root / "draft.md"
        draft.write_text("[@Unknown2026]", encoding="utf-8")
        self.assertTrue({"CITED_KEY_UNREGISTERED", "REGISTERED_KEY_UNUSED"} <= self.codes(w.check_project(path, draft)))

    def test_duplicate_doi_case_and_url(self):
        path = self.record(sources=[self.source(doi="https://doi.org/10.0000/TEST"),
                                  self.source(id="S2", key="Other", doi="doi:10.0000/test")])
        self.assertIn("DUPLICATE_IDENTIFIER", self.codes(w.check_project(path)))

    def test_abstract_support_requires_reading_review(self):
        path = self.record(sources=[self.source(access="abstract", read_locator="abstract")],
                           claims=[{"id": "C1", "text": "synthetic methods claim", "strength": "descriptive",
                                    "evidence": [{"kind": "source", "id": "S1", "locator": "abstract", "relation": "supporting"}]}])
        self.assertIn("LIMITED_READING_SCOPE", self.codes(w.check_project(path)))

    def test_no_evidence_and_causal_basis_missing(self):
        path = self.record(claims=[{"id": "C1", "text": "x causes y", "strength": "causal", "evidence": []},
                                   {"id": "C2", "text": "a causes b", "strength": "causal",
                                    "evidence": [{"kind": "result", "id": "missing", "relation": "not_checked"}]}])
        self.assertTrue({"EVIDENCE_MISSING", "EVIDENCE_TARGET_MISSING", "CAUSAL_BASIS_MISSING"} <= self.codes(w.check_project(path)))

    def test_mixed_and_contradicting_not_promoted(self):
        path = self.record(results=[{"id": "R1", "text": "null result", "locator": "table 1"}],
                           claims=[{"id": "C1", "text": "improvement", "strength": "associational",
                                    "evidence": [{"kind": "result", "id": "R1", "locator": "table 1", "relation": "contradicting"}]}])
        self.assertIn("SUPPORT_UNRESOLVED", self.codes(w.check_project(path)))

    def test_ai_proposal_cannot_stand_for_author_decision(self):
        path = self.record(decisions=[{"id": "D1", "text": "accept", "origin": "ai_proposal", "provenance": "synthetic"}],
                           issues=[{"id": "I1", "disposition": "accept", "status": "resolved", "decision_id": "D1",
                                    "response": "changed", "change_locator": "p2"}])
        self.assertIn("AUTHOR_DECISION_MISSING", self.codes(w.check_project(path)))

    def test_resolved_requires_actual_change(self):
        path = self.record(decisions=[{"id": "D1", "text": "accept", "origin": "author", "provenance": "synthetic author message"}],
                           issues=[{"id": "I1", "disposition": "accept", "status": "resolved", "decision_id": "D1", "response": "planned"}])
        self.assertIn("CHANGE_LOCATOR_MISSING", self.codes(w.check_project(path)))

    def test_stale_artifact_detected_read_only(self):
        draft = self.root / "data.txt"
        draft.write_text("old", encoding="utf-8")
        path = self.record(artifacts=[{"path": "data.txt", "sha256": w.digest(draft)}])
        draft.write_text("new", encoding="utf-8")
        self.assertIn("ARTIFACT_CHANGED", self.codes(w.check_project(path)))
        self.assertEqual(draft.read_text(encoding="utf-8"), "new")

    def test_natural_apa_is_not_claimed_as_parsed(self):
        path = self.record()
        draft = self.root / "apa.md"
        draft.write_text("王大明（2026）與 Smith (2025)。", encoding="utf-8")
        self.assertIn("NO_EXPLICIT_KEYS", self.codes(w.check_project(path, draft)))

    def test_citation_code_examples_ignored(self):
        self.assertEqual(w.citation_keys("```text\n[@Fake]\n```\n`[@Fake2]`\n[@A; @B, p. 2]"), ["A", "B"])

    def test_synthetic_results_never_unmarked(self):
        path = self.record(results=[{"id": "R1", "text": "fiction", "locator": "demo", "synthetic": True}])
        self.assertIn("SYNTHETIC_RESULT", self.codes(w.check_project(path)))

    def test_scope_allows_length_change_inside_only(self):
        old, new = self.root / "old.md", self.root / "new.md"
        old.write_text("head\nold\ntail\n", encoding="utf-8")
        new.write_text("head\nnew\nextra\ntail\n", encoding="utf-8")
        self.assertEqual(w.compare_text(old, new, 2, 2)["scope"]["status"], "preserved")
        new.write_text("changed head\nnew\ntail\n", encoding="utf-8")
        self.assertEqual(w.compare_text(old, new, 2, 2)["scope"]["status"], "outside_scope_changed")

    def test_numeric_and_citation_inventory(self):
        old, new = self.root / "old.md", self.root / "new.md"
        old.write_text("n=32, p=0.08 [@A]", encoding="utf-8")
        new.write_text("n=34, p=0.03 [@B]", encoding="utf-8")
        result = w.compare_text(old, new)
        self.assertEqual(result["numbers_removed"], {"32": 1, "0.08": 1})
        self.assertEqual(result["citations_added"], {"B": 1})

    def test_numbers_preserve_leading_decimal_and_scientific_notation(self):
        self.assertEqual(w.numeric_tokens("r=.42 p=.018 CI −.50 to 1.20 n=1,200 2.5e-3"),
                         {".42": 1, ".018": 1, "−.50": 1, "1.20": 1, "1,200": 1, "2.5e-3": 1})

    def test_semantic_change_not_certified_by_inventory(self):
        old, new = self.root / "old.md", self.root / "new.md"
        old.write_text("x is associated with y", encoding="utf-8")
        new.write_text("x causes y", encoding="utf-8")
        result = w.compare_text(old, new)
        self.assertTrue(result["text_changed"])
        self.assertEqual(result["status"], "no_tracked_difference")
        self.assertIn("meaning", result["limitation"])

    def test_invalid_record_does_not_return_clean(self):
        path = self.record(schema_version=True, sources="broken", claims=[None])
        report = w.check_project(path)
        self.assertEqual(report["status"], "findings")
        self.assertTrue({"SCHEMA_VERSION", "INVALID_TABLE"} <= self.codes(report))

    def test_registered_term_variant(self):
        path = self.record(terms=[{"canonical": "生成式人工智慧", "variants": ["生成型人工智慧"]}])
        draft = self.root / "draft.md"
        draft.write_text("生成型人工智慧", encoding="utf-8")
        self.assertIn("TERM_VARIANT", self.codes(w.check_project(path, draft)))

    def test_cli_refuses_report_over_input(self):
        path = self.record()
        before = path.read_bytes()
        result = subprocess.run([sys.executable, "-X", "utf8", w.__file__, "check", str(path),
                                 "--output", str(path)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(json.loads(result.stderr)["status"], "error")

    def test_cli_invalid_json_never_clean(self):
        path = self.root / "壞資料.json"
        path.write_text("{broken", encoding="utf-8")
        result = subprocess.run([sys.executable, "-X", "utf8", w.__file__, "check", str(path)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
