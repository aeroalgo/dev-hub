import pytest
from pathlib import Path
from loop.formula_render import list_formulas
from loop.schemas.formula import DecomposeFormula

def test_list_formulas_returns_all():
    formulas = list_formulas()
    assert len(formulas) == 3
    ids = [f.id for f in formulas]
    assert "hooks-epic" in ids
    assert "loop-runtime-epic" in ids
    assert "cli-validate-epic" in ids
    assert sorted(ids) == ids

def test_formula_list_shows_all(capsys):
    import sys
    from pathlib import Path
    hooks_dir = str(Path(__file__).resolve().parents[2] / ".claude" / "hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    from epic_resolve import main
    orig_argv = sys.argv
    try:
        sys.argv = ["epic_resolve.py", "formula-list"]
        code = main()
        assert code == 0
        captured = capsys.readouterr()
        assert "hooks-epic" in captured.out
        assert "loop-runtime-epic" in captured.out
        assert "cli-validate-epic" in captured.out
    finally:
        sys.argv = orig_argv

def test_formula_list_table_columns(capsys):
    import sys
    from pathlib import Path
    hooks_dir = str(Path(__file__).resolve().parents[2] / ".claude" / "hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    from epic_resolve import main
    orig_argv = sys.argv
    try:
        sys.argv = ["epic_resolve.py", "formula-list"]
        main()
        captured = capsys.readouterr()
        assert "ID" in captured.out
        assert "DESCRIPTION" in captured.out
        assert "LEVEL" in captured.out
        assert "STEPS" in captured.out
    finally:
        sys.argv = orig_argv
