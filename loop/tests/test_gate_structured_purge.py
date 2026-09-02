import re
from pathlib import Path


def test_sc001_no_verdict_regex_in_extract_verdict():
    lib_path = Path(".claude/hooks/_lib.py")
    content = lib_path.read_text(encoding="utf-8")

    match = re.search(
        r"def extract_verdict\(.*?\):\n(.*?)(?=\n[a-zA-Z0-9_]+\s*=|\ndef |\Z)",
        content,
        re.DOTALL,
    )
    assert match is not None, "extract_verdict not found in _lib.py"
    func_code = match.group(1)

    assert "VERDICT:" not in func_code
    assert "re.search" not in func_code
    assert "re.finditer" not in func_code


def test_sc005_agents_have_json_contract():
    # T-HUB-039 s10 deleted verify.md / reviewer.md; phase agents are SoT.
    agents_dir = Path(".claude/agents")
    verify_md = (agents_dir / "verify-implement.md").read_text(encoding="utf-8")
    reviewer_md = (agents_dir / "verify-qa.md").read_text(encoding="utf-8")

    assert "loop-gate-verdict/v1" in verify_md
    assert "loop-gate-verdict/v1" in reviewer_md


def test_sc006_context_loop_no_verdict_machine_instruction():
    context_loop = Path("loop/context_loop.py").read_text(encoding="utf-8")
    assert "loop-gate-verdict/v1" in context_loop
    assert "`VERDICT: PASS`" not in context_loop
    assert "`VERDICT: FAIL`" not in context_loop


def test_sc007_contracts_no_verdict_first_line():
    # T-HUB-023 s07: HARD VERDICT-first purged from CONTRACTS.
    lib = Path(".claude/hooks/_lib.py").read_text(encoding="utf-8")
    assert "loop-gate-verdict" in lib
    assert not re.search(r'CONTRACTS[\s\S]*?первая строка.*VERDICT', lib)
