"""Tests for SVG generator functions in fast_mode (no API calls required)."""
from image_generator import _svg_puppet, _svg_background, _clean_svg

def _valid_puppet(svg):
    assert svg.startswith('<svg') and 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert 'width="400"' in svg and 'height="400"' in svg and 'viewBox="0 0 400 400"' in svg

def test_svg_puppet_dragon(): _valid_puppet(_svg_puppet("d1", "a cute dragon"))
def test_svg_puppet_dragon_pink():
    assert "#FF69B4" in _svg_puppet("dp1", "a pink dragon")
def test_svg_puppet_bunny(): _valid_puppet(_svg_puppet("b1", "a fluffy bunny"))
def test_svg_puppet_bunny_white():
    assert "#FFFFFF" in _svg_puppet("bw1", "a white bunny")
def test_svg_puppet_flower(): _valid_puppet(_svg_puppet("f1", "a colorful flower"))
def test_svg_puppet_generic(): _valid_puppet(_svg_puppet("c1", "a friendly character"))

def _valid_bg(svg):
    assert svg.startswith('<svg') and 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert 'width="1200"' in svg and 'height="800"' in svg and 'viewBox="0 0 1200 800"' in svg

def test_svg_background_snow(): _valid_bg(_svg_background("bg1", "snowy mountain"))
def test_svg_background_sunny(): _valid_bg(_svg_background("bg2", "sunny meadow"))

def test_clean_svg_strips_html_comments():
    r = _clean_svg('<svg><!-- x --><r/></svg>')
    assert "<!--" not in r and "<svg>" in r

def test_clean_svg_preserves_valid_content():
    assert _clean_svg('<svg xmlns="http://www.w3.org/2000/svg"><c/></svg>') == \
           '<svg xmlns="http://www.w3.org/2000/svg"><c/></svg>'
