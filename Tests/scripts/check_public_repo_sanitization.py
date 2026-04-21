#!/usr/bin/env python3
"""Lightweight guardrail for making the repository public.

This check intentionally avoids external dependencies so it can run in a bare
local shell before publishing the repo.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

FILES_TO_SCAN = [
    ".gitignore",
    "Tests/.gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "HANDOFF.md",
    "Tests/README.md",
    "Tests/e2e/global-setup.js",
    "Tests/e2e/playwright.config.js",
    "Tests/e2e/tests/auth.spec.js",
    "Tests/e2e/tests/projects.spec.js",
    "Tests/e2e/tests/site_edit.spec.js",
    "vba/modConfig.bas",
    "vba/SETUP.md",
]

FORBIDDEN_PATTERNS = [
    "168.222.140.39",
    "Admin123456",
    "1q2w3e4R",
    "vblyakherov",
    "ssh vps",
    "viktorblya-vps-1",
]

REQUIRED_E2E_PATTERNS = [
    "E2E_BASE_URL",
    "E2E_ADMIN_USERNAME",
    "E2E_ADMIN_PASSWORD",
    "E2E_USER_USERNAME",
    "E2E_USER_PASSWORD",
]

REQUIRED_GITIGNORE_PATTERNS = [
    ".agents/",
    "Tests/e2e/.auth/",
    "Tests/e2e/node_modules/",
    "Tests/e2e/playwright-report/",
    "Tests/e2e/test-results/",
]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    scanned_files = {path: read_text(path) for path in FILES_TO_SCAN}

    for path, content in scanned_files.items():
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in content:
                errors.append(f"{path}: found forbidden pattern {pattern!r}")

    e2e_setup = scanned_files["Tests/e2e/global-setup.js"]
    e2e_config = scanned_files["Tests/e2e/playwright.config.js"]
    e2e_auth = scanned_files["Tests/e2e/tests/auth.spec.js"]
    e2e_bundle = "\n".join((e2e_setup, e2e_config, e2e_auth))
    for pattern in REQUIRED_E2E_PATTERNS:
        if pattern not in e2e_bundle:
            errors.append(f"E2E config: missing required env-driven pattern {pattern!r}")

    gitignore_text = "\n".join((scanned_files[".gitignore"], scanned_files["Tests/.gitignore"]))
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in gitignore_text:
            errors.append(f"gitignore: missing ignore rule {pattern!r}")

    if errors:
        print("Repository sanitization check failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Repository sanitization check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
