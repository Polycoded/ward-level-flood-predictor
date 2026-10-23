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


@pytest.mark.parametrize("language", ["en", "ta"])
def test_exercise_essential_content_and_multipart(exercise_candidate, language):
    from model.alerts import exercise_message, format_alert_for_channel, sms_info
    result = exercise_message(exercise_candidate, exercise_id="ARTIFICIAL-" + "X" * 300, language=language)
    assert "EXERCISE" in result["text"] and "168" in result["text"]
    assert "100" in result["text"] and "3" in result["text"]
    assert result["instruction"] in result["text"]
    assert result["sms"]["segments"] > 1
    assert format_alert_for_channel(result["text"], "sms", 20) == result["text"]
    assert sms_info("😀")["units"] == 2
    assert sms_info("^" * 80)["units"] == 160
    assert sms_info("^" * 81)["segments"] == 2
    if language == "ta":
        assert result["language_review"] == "pending_native_speaker"


def test_exercise_shelter_is_only_supplied_traceable_info(exercise_candidate):
    from model.alerts import exercise_message
    with pytest.raises(ValueError):
        exercise_message(exercise_candidate, exercise_id="test", shelter={"name": "invented"})
    result = exercise_message(exercise_candidate, exercise_id="test", shelter={
        "name": "ARTIFICIAL supplied hall", "source_ref": "test-only-ref", "url": "https://example.invalid/info"})
    assert "availability/routes unverified" in result["text"]
    assert "ARTIFICIAL supplied hall" in result["text"]
@pytest.mark.parametrize("message,encoding,units,segments", [
    ("^" * 153, "GSM-7", 306, 3),
    ("A" * 152 + "^" + "B" * 152, "GSM-7", 306, 3),
    ("A" * 151 + "^" + "B" * 153, "GSM-7", 306, 2),
    ("A" * 152 + "^" + "B" * 151, "GSM-7", 305, 2),
    ("😀" * 67, "UCS-2", 134, 3),
    ("அ" * 66 + "😀" + "அ" * 66, "UCS-2", 134, 3),
    ("அ" * 65 + "😀" + "அ" * 67, "UCS-2", 134, 2),
    ("^" * 80, "GSM-7", 160, 1),
    ("😀" * 35, "UCS-2", 70, 1),
])
def test_sms_atomic_character_packing(message, encoding, units, segments):
    from model.alerts import sms_info
    assert sms_info(message) == {"encoding": encoding, "units": units,
                                 "segments": segments, "singleLimit": 160 if encoding == "GSM-7" else 70}
