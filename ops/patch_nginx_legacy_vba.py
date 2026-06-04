#!/usr/bin/env python3
"""Insert legacy Excel/VBA proxy routes into the production nginx config.

The production server keeps a local SSL-enabled nginx/nginx.conf that differs
from the public repository. This script patches that local file in place without
replacing the rest of the SSL configuration.
"""

from __future__ import annotations

import argparse
import difflib
import shutil
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory


MARKER = "Legacy XLSM/VBA compatibility"

LEGACY_BLOCK = r'''
    # Legacy XLSM/VBA compatibility.
    # Older macro containers call /auth/* and /sync* directly, without /api/v1.
    location = /auth/me {
        proxy_pass http://backend:8000/api/v1/sync/columns;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /auth/ {
        proxy_pass http://backend:8000/api/v1/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /sync {
        proxy_pass http://backend:8000/api/v1/sync;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
    }

    location /sync/ {
        proxy_pass http://backend:8000/api/v1/sync/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
    }

'''


def insert_legacy_block(text: str) -> tuple[str, bool]:
    """Return patched nginx config text and whether it changed."""
    if MARKER in text:
        return text, False

    ssl_pos = text.find("listen 443 ssl")
    if ssl_pos == -1:
        raise ValueError("Could not find HTTPS server block: expected 'listen 443 ssl'")

    location_marker = "    location / {\n"
    insert_pos = text.find(location_marker, ssl_pos)
    if insert_pos == -1:
        raise ValueError("Could not find 'location /' inside the HTTPS server block")

    return text[:insert_pos] + LEGACY_BLOCK + text[insert_pos:], True


def patch_file(path: Path, *, dry_run: bool = False, backup: bool = True) -> bool:
    text = path.read_text(encoding="utf-8")
    patched, changed = insert_legacy_block(text)

    if not changed:
        print(f"{path}: legacy VBA block already exists; no changes made.")
        return False

    if dry_run:
        diff = difflib.unified_diff(
            text.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (patched)",
        )
        sys.stdout.writelines(diff)
        return True

    if backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_name(f"{path.name}.bak_excel_legacy_{stamp}")
        shutil.copy2(path, backup_path)
        print(f"Backup written: {backup_path}")

    path.write_text(patched, encoding="utf-8")
    print(f"Patched: {path}")
    return True


def run_self_test() -> None:
    sample = """server {
    listen 80;
    server_name tracker.rtk-service.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name tracker.rtk-service.ru;

    ssl_certificate /etc/ssl/localcerts/tracker.rtk-service.ru.crt;
    ssl_certificate_key /etc/ssl/localcerts/tracker.rtk-service.ru.key;

    location / {
        root /usr/share/nginx/html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
    }
}
"""
    patched, changed = insert_legacy_block(sample)
    assert changed is True
    assert MARKER in patched
    assert "proxy_pass http://backend:8000/api/v1/sync/columns;" in patched
    assert patched.index(MARKER) < patched.index("    location / {")

    patched_again, changed_again = insert_legacy_block(patched)
    assert changed_again is False
    assert patched_again == patched

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "nginx.conf"
        path.write_text(sample, encoding="utf-8")
        assert patch_file(path, dry_run=False, backup=True) is True
        assert MARKER in path.read_text(encoding="utf-8")
        assert list(path.parent.glob("nginx.conf.bak_excel_legacy_*"))

    print("self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch nginx.conf with legacy Excel/VBA routes.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="nginx/nginx.conf",
        help="Path to nginx.conf (default: nginx/nginx.conf)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the diff without writing.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create a .bak file.")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests and exit.")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    path = Path(args.path)
    if not path.exists():
        parser.error(f"File not found: {path}")

    try:
        patch_file(path, dry_run=args.dry_run, backup=not args.no_backup)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
