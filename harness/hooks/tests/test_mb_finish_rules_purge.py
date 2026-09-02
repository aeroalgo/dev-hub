import subprocess
import pytest

def test_no_live_implement_finish_block_calls():
    # Check that _implement_finish_block is not called as a live prompt injector in loop/context_loop.py
    res = subprocess.run(
        "rg '_implement_finish_block\\s*\\(' loop/context_loop.py | grep -v '^.*def _implement_finish_block'",
        shell=True,
        capture_output=True,
        text=True
    )
    assert res.returncode != 0, f"Found live calls to _implement_finish_block:\n{res.stdout}"

def test_no_live_qa_finish_block_calls():
    # Check that _qa_finish_block is not called as a live prompt injector in loop/context_loop.py
    res = subprocess.run(
        "rg '_qa_finish_block\\s*\\(' loop/context_loop.py | grep -v '^.*def _qa_finish_block'",
        shell=True,
        capture_output=True,
        text=True
    )
    assert res.returncode != 0, f"Found live calls to _qa_finish_block:\n{res.stdout}"

def test_context_loop_imports_clean():
    import loop.context_loop
    assert loop.context_loop is not None
