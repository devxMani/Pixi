"""Syntax-check inline scripts in Pixi's browser interfaces."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = (ROOT / "index.html", ROOT / "console.html")


def main() -> int:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required to syntax-check Pixi JavaScript.")

    total_scripts = 0
    with tempfile.TemporaryDirectory(prefix="pixi-js-check-") as temp_dir:
        for html_file in HTML_FILES:
            if not html_file.exists():
                raise SystemExit(f"Required HTML interface missing: {html_file}")
            html = html_file.read_text(encoding="utf-8")
            scripts = re.findall(
                r"<script\b(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script\s*>",
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not scripts:
                raise SystemExit(f"No inline JavaScript found in {html_file.name}.")
            for index, source in enumerate(scripts):
                script_file = Path(temp_dir) / f"{html_file.stem}-{index}.js"
                script_file.write_text(source, encoding="utf-8")
                subprocess.run([node, "--check", str(script_file)], check=True)
            total_scripts += len(scripts)

    print(
        f"Pixi JavaScript syntax valid: {total_scripts} inline script(s) across "
        f"{len(HTML_FILES)} HTML interfaces."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
