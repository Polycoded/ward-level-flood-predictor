"""Compatibility proxies must not become public alert predictions."""

import pytest

from model.alerts import generate_alert_messages


@pytest.mark.parametrize("language", ["en", "ta"])
@pytest.mark.parametrize("level", ["very_low", "low", "moderate", "high", "very_high"])
@pytest.mark.parametrize("channel", ["sms", "whatsapp", "voice"])
def test_alerts_ignore_physical_proxy(language, level, channel):
    first, link = generate_alert_messages("Artificial ward", level, "1.0m+", 100, language, channel)
    second, _ = generate_alert_messages("Artificial ward", level, "unsupported-secret-proxy", 100, language, channel)
    assert first == second
    assert "1.0m" not in first and "deep" not in first and "peak" not in first.lower()
    assert ("Uncalibrated index" if language == "en" else "அளவுத்திருத்தம்") in first
    assert (link is not None) == (channel == "whatsapp")
