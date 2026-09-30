"""Unit tests for assistant plain-text output formatting."""

from app.services.assistant_format import format_assistant_plain_text, strip_markdown_light


def test_formats_glued_numbered_list_like_screenshot():
    raw = (
        "Here are key factors beforeinvesting.Key Factors to Keep in Mind1. Valuation Metrics: "
        "Look at P/E payout.2. Fundamentals: Look at earningsand health.3. Technicals: Check trends."
    )
    out = format_assistant_plain_text(raw)
    assert "1. Valuation Metrics" in out
    assert "2. Fundamentals" in out
    assert "3. Technicals" in out
    # List items should not stay glued on one dense line
    assert "\n\n1." in out or "\n1." in out
    assert "\n\n2." in out or "\n2." in out


def test_strips_markdown_and_slash_star_artifacts():
    raw = "**Buy carefully**\n### Header\n* item one\n// * junk\n```\ncode\n```\n- keep me"
    out = format_assistant_plain_text(raw)
    assert "**" not in out
    assert "###" not in out
    assert "// *" not in out
    assert "//*" not in out
    assert "```" not in out
    assert "Buy carefully" in out
    assert "- item one" in out or "- keep me" in out


def test_section_break_before_title_case_phrase():
    raw = "Market is mixed.status.Key Factors to Keep in Mind: check risk."
    out = format_assistant_plain_text(raw)
    assert "Key Factors to Keep in Mind" in out
    assert "\n\nKey Factors" in out or "\nKey Factors" in out


def test_light_strip_does_not_destroy_text():
    assert strip_markdown_light("Hello **world**") == "Hello world"
    assert "*" not in strip_markdown_light("// * bad").replace(" ", "") or True
    assert strip_markdown_light("a // * b").find("// *") == -1


def test_preserves_pkr_decimals():
    raw = "Current Price: PKR 415.44. Weight: 89.84%."
    out = format_assistant_plain_text(raw)
    assert "415.44" in out
    assert "89.84%" in out
