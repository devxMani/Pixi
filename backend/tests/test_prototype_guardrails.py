from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def test_prototype_is_branded_as_pixi():
    assert "<title>Pixi —" in HTML
    assert "Pixie" not in HTML
    assert "pixie" not in HTML


def test_prototype_escape_helper_encodes_html_special_characters():
    expected = """const esc=s=>String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");"""
    assert expected in HTML
