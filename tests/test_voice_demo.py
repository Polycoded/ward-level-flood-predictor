"""Voice demo: scripts, TwiML and token helpers (no network calls)."""

from __future__ import annotations

import importlib
import xml.etree.ElementTree as ET

import pytest

from voice import token_server
from voice.scripts import get_twiml_script, get_voice_script

# Substrings from earlier corrupted Tamil/English translations that must never return.
GARBLED = ["IVAL", "mahdoll", "palacio", "palace", "Seigneur", "võimal", "v\u00f5imal", "final"]


def test_english_script_has_ward_rain_and_helpline():
    script = get_voice_script("Ward 168", "high", "0.5-1.0m", 120, "en", 6)
    assert "Ward 168" in script
    assert "120 millimetres" in script
    assert "1077" in script
    assert "Exercise only" in script


def test_tamil_script_is_clean_and_has_tamil_text():
    script = get_voice_script("Ward 168", "very_high", "1.0m+", 200, "ta", 6)
    assert any("\u0b80" <= ch <= "\u0bff" for ch in script)
    assert "1077" in script
    for bad in GARBLED:
        assert bad not in script


def test_unknown_levels_fall_back_safely():
    script = get_voice_script("Ward 1", "nonsense", "weird", 10, "en")
    assert "Ward 1" in script


def test_twiml_is_valid_xml_and_uses_tamil_voice():
    xml = get_twiml_script("Ward 168", "high", "0.5-1.0m", 120, "ta", 6)
    root = ET.fromstring(xml)
    says = root.findall("Say")
    assert says and says[0].attrib["language"] == "ta-IN"
    assert "1077" in "".join(says[0].itertext())


def test_token_helpers_simulate_without_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # ensure no local .env supplies credentials
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    module = importlib.reload(token_server)
    try:
        assert module.create_access_token("resident", "room") == "mock_token"
    finally:
        importlib.reload(token_server)


def test_token_helper_generates_jwt_with_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s" * 40)
    module = importlib.reload(token_server)
    try:
        token = module.create_access_token("resident", "room-1", '{"a": 1}')
        assert token.count(".") == 2 and len(token) > 50
    finally:
        monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
        monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
        importlib.reload(token_server)


def test_demo_metadata_and_meet_url():
    from types import SimpleNamespace

    from voice import demo

    args = SimpleNamespace(ward_name="Ward 9", risk_level="moderate",
                           depth_band="0.15-0.5m", rainfall=55.0,
                           duration=6.0, language="ta", identity="resident",
                           room="demo")
    metadata = demo.build_metadata(args)
    assert '"ward_name": "Ward 9"' in metadata
    assert '"exercise": true' in metadata

    url = demo.meet_url("wss://x.livekit.cloud", "abc.def.ghi")
    assert url.startswith("https://meet.livekit.io/?")
    assert "token=abc.def.ghi" in url


def test_voice_agent_builds_script_when_agents_installed():
    pytest.importorskip("livekit.agents")
    from voice.family_agent import FloodAlertAgent

    agent = FloodAlertAgent("Ward 168", "high", "0.5-1.0m", 120, "en", 6)
    assert "Ward 168" in agent.script()
    assert "flood-alert voice assistant" in agent.instructions()
    assert "EXERCISE" in agent.instructions()
