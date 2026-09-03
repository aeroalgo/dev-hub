import importlib
import pytest
import warnings


def test_formula_render_emits_deprecation_warning():
    with pytest.deprecated_call(match="layout_v1_deprecated"):
        import loop.formula_render
        importlib.reload(loop.formula_render)
