from pathlib import Path
import re
import subprocess


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gstack_adapt" / "plan-qa-consumes-fragment.md"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_extract_qa_consumes_section_by_anchor():
    content = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "<!-- #qa-consumes -->" in content
    assert "## QA consumes" in content
    match = re.search(r"<!-- #qa-consumes -->\s*## QA consumes\n(.*?)(?=\n<!-- |\Z)", content, re.DOTALL)
    assert match is not None
    extracted = match.group(1).strip()
    assert "- `memory-bank/back/plan/plan-T-HUB-027.md`" in extracted


def test_review_readiness_exemplar_no_pending_required():
    content = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "<!-- #review-readiness -->" in content
    assert "- [x] Product probe baseline CLEARED" in content
    assert "- [x] Eng review spine CLEARED" in content


def test_plan_template_has_gstack_sections():
    template_path = REPO_ROOT / ".cursor" / "templates" / "plan.md"
    content = template_path.read_text(encoding="utf-8")
    assert "QA consumes" in content
    assert "Review readiness" in content
    assert "Product probe" in content
    assert "Eng review spine" in content


def test_clarify_phase0_grill_pass_intact():
    clarify_path = REPO_ROOT / ".cursor" / "rules" / "shared" / "workflow-clarify-core.mdc"
    content = clarify_path.read_text(encoding="utf-8")
    assert "Phase 0" in content
    assert "Grill" in content
