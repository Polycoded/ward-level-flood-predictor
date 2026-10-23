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
    import dotenv.main

    monkeypatch.chdir(tmp_path)
    # token_server calls load_dotenv(), which searches upward from its own file and
    # would find the developer's real .env. Disable discovery for this test.
    monkeypatch.setattr(dotenv.main, "find_dotenv", lambda *a, **k: "")
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    module = importlib.reload(token_server)
    try:
        assert module.create_access_token("resident", "room") == "mock_token"
    finally:
        importlib.reload(token_server)


def test_token_helper_generates_jwt_with_credentials(monkeypatch, tmp_path):
    import dotenv.main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dotenv.main, "find_dotenv", lambda *a, **k: "")
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


def test_provider_prefers_deepseek_then_openai(monkeypatch):
    import voice.family_agent as fa

    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert fa.provider_name() == "deepseek"

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    assert fa.provider_name() == "openai"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        fa.provider_name()


def test_local_audio_plugins_construct_without_loading_models():
    pytest.importorskip("livekit.agents")
    pytest.importorskip("edge_tts")
    pytest.importorskip("faster_whisper")

    from voice.plugins.edge_tts import EdgeTTS
    from voice.plugins.faster_whisper_stt import FasterWhisperSTT

    tts_impl = EdgeTTS(language="ta")
    assert tts_impl.voice == "ta-IN-PallaviNeural"
    assert tts_impl.sample_rate == 24000
    assert tts_impl.capabilities.streaming is False

    stt_impl = FasterWhisperSTT(language="ta")
    assert stt_impl._engine is None  # lazy: no model download during tests
    assert stt_impl.capabilities.streaming is False

