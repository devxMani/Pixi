"""Static smoke checks for the preserved HTML prototype."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / "index.html"


def main() -> int:
    if not HTML_FILE.exists():
        raise SystemExit(f"Prototype file missing: {HTML_FILE}")
    html = HTML_FILE.read_text(encoding="utf-8")

    scripts = re.findall(
        r"<script\b(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script\s*>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not scripts:
        raise SystemExit("No inline JavaScript found in the prototype.")

    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required to syntax-check the prototype JavaScript.")

    with tempfile.TemporaryDirectory(prefix="pixi-prototype-check-") as temp_dir:
        for index, source in enumerate(scripts):
            script_file = Path(temp_dir) / f"inline-{index}.js"
            script_file.write_text(source, encoding="utf-8")
            subprocess.run([node, "--check", str(script_file)], check=True)

    print(f"Prototype JavaScript syntax valid ({len(scripts)} inline script(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
