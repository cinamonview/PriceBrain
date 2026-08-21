"""Firestore Security Rules tests — Node @firebase/rules-unit-testing harness."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pricebrain_app.tests.emulator_utils import requires_emulator

NODE_TEST_DIR = Path(__file__).with_name("node")
RULES_RUNNER = NODE_TEST_DIR / "run_rules_tests.mjs"


def _node_executable() -> str | None:
    return shutil.which("node")


def _ensure_node_dependencies() -> None:
    node_modules = NODE_TEST_DIR / "node_modules"
    if node_modules.exists():
        return
    npm_cli = Path(_node_executable() or "").parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not npm_cli.exists():
        pytest.skip("SKIPPED — npm CLI not found for Firestore Rules test dependencies")
    install = subprocess.run(
        [_node_executable(), str(npm_cli), "install", "--no-audit", "--no-fund"],
        cwd=NODE_TEST_DIR,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if install.returncode != 0:
        pytest.fail(f"npm install failed for rules tests:\n{install.stdout}\n{install.stderr}")


@requires_emulator
def test_firestore_security_rules_via_node_runner() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("SKIPPED — Node.js not available for Firestore Rules tests")

    _ensure_node_dependencies()
    result = subprocess.run(
        [node, str(RULES_RUNNER)],
        cwd=NODE_TEST_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        message = result.stdout + result.stderr
        pytest.fail(f"Firestore Rules runner failed:\n{message}")
