"""Tests aligning py-xiaozhi with xiaozhi-esp32 OTA, MCP 2026-07-28, WebSocket and UDP probe specs."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.activation.ota import OtaConfigClient
from src.activation.service import ActivationService
from src.mcp.mcp_server import McpServer
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType
from src.mcp.tools.camera.normal_camera import NormalCamera
from src.mcp.tools.camera.register import register_camera_tools
from src.protocols.mqtt_crypto import (
    PROBE_TYPE_PING,
    PROBE_TYPE_PONG,
    decode_probe_credentials,
    encode_probe,
    matches_pending_pong,
)
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.mqtt_udp import MqttUdpChannel, UdpProbeState
from src.protocols.protocol import build_client_protocol_features
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# 1. OTA & WebSocket & MQTT keepalive alignment (docs/ota_zh.md, websocket_zh.md)
# ---------------------------------------------------------------------------


def test_ota_headers_and_payload_match_spec():
    cfg = ConfigManager.from_dict(
        {
            "SYSTEM_OPTIONS": {
                "DEVICE_ID": "02:00:00:00:00:01",
                "CLIENT_ID": "11111111-2222-4333-8444-555555555555",
                "NETWORK": {"ACTIVATION_VERSION": "v2"},
            }
        }
    )
    identity = SimpleNamespace(
        get_serial_number=lambda: "SN-TEST-0001",
        load_efuse_data=lambda: {"hmac_key": "abc123"},
    )
    client = OtaConfigClient(cfg, identity)
    client._local_ip = "192.168.1.10"

    headers = client._build_ota_headers()
    assert headers["Activation-Version"] == "2"
    assert headers["Serial-Number"] == "SN-TEST-0001"
    assert headers["Device-Id"] == "02:00:00:00:00:01"
    assert headers["Client-Id"] == "11111111-2222-4333-8444-555555555555"

    payload = client._build_ota_payload()
    assert payload["version"] == 2
    assert payload["language"] == "zh-CN"
    assert payload["mac_address"] == "02:00:00:00:00:01"
    assert payload["uuid"] == "11111111-2222-4333-8444-555555555555"
    assert payload["application"]["name"]
    assert payload["protocol"]["features"] == build_client_protocol_features()

    # v1 or missing serial number -> Activation-Version: 1, no Serial-Number
    cfg_v1 = ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"NETWORK": {"ACTIVATION_VERSION": "v1"}}}
    )
    headers_v1 = OtaConfigClient(cfg_v1, identity)._build_ota_headers()
    assert headers_v1["Activation-Version"] == "1"
    assert "Serial-Number" not in headers_v1


@pytest.mark.asyncio
async def test_activation_service_refreshes_ota_after_success(monkeypatch):
    cfg = ConfigManager.from_dict()
    service = ActivationService(config=cfg)
    monkeypatch.setattr(
        "src.activation.service.apply_code_side_effects", lambda code, msg: None
    )
    service._http.activate = AsyncMock(return_value=True)
    service._ota.fetch_ota_config = AsyncMock(return_value={"mqtt": {"endpoint": "e"}})

    ok = await service.activate({"challenge": "c", "code": "123456"})
    assert ok is True
    service._ota.fetch_ota_config.assert_awaited_once()

    # Post-activation OTA refresh failure must not fail already-activated startup
    service._ota.fetch_ota_config = AsyncMock(side_effect=OSError("offline"))
    ok2 = await service.activate({"challenge": "c", "code": "123456"})
    assert ok2 is True


@pytest.mark.asyncio
async def test_websocket_token_prefix_and_session_id():
    cfg_prefixed = ConfigManager.from_dict(
        {
            "SYSTEM_OPTIONS": {
                "NETWORK": {
                    "WEBSOCKET_URL": "wss://example.com",
                    "WEBSOCKET_ACCESS_TOKEN": "Bearer already-prefixed",
                }
            }
        }
    )
    ws = WebsocketProtocol(config=cfg_prefixed)
    assert ws.HEADERS["Authorization"] == "Bearer already-prefixed"

    ws.hello_received = asyncio.Event()
    await ws._handle_server_hello({"transport": "websocket", "session_id": "sess-42"})
    assert ws.session_id == "sess-42"

    await ws._do_cleanup()
    assert ws.session_id == ""


def test_mqtt_reads_ota_keepalive_and_keeps_default():
    loop = asyncio.new_event_loop()
    try:
        cfg_custom = ConfigManager.from_dict(
            {"SYSTEM_OPTIONS": {"NETWORK": {"MQTT_INFO": {"keepalive": 240}}}}
        )
        proto_custom = MqttProtocol(loop, config=cfg_custom)
        assert proto_custom._read_control_config()["keepalive"] == 240

        cfg_default = ConfigManager.from_dict(
            {"SYSTEM_OPTIONS": {"NETWORK": {"MQTT_INFO": {}}}}
        )
        proto_default = MqttProtocol(loop, config=cfg_default)
        assert proto_default._read_control_config()["keepalive"] is None
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# 2. Dual-version MCP 2026-07-28 + 2024-11-05 (docs/mcp-protocol_zh.md)
# ---------------------------------------------------------------------------


def _modern_meta(version="2026-07-28", capabilities=None):
    return {
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientCapabilities": (
            {} if capabilities is None else capabilities
        ),
        "io.modelcontextprotocol/clientInfo": {
            "name": "xiaozhi-backend",
            "version": "1.0.0",
        },
    }


async def _send_mcp(server: McpServer, message) -> list[dict]:
    replies: list[dict] = []

    async def capture(raw: str):
        replies.append(json.loads(raw))

    server.set_send_callback(capture)
    await server.parse_message(message)
    return replies


@pytest.mark.asyncio
async def test_mcp_unknown_method_returns_32601_and_invalid_json_32700():
    server = McpServer()
    replies = await _send_mcp(
        server, {"jsonrpc": "2.0", "id": 10000, "method": "unknown/method"}
    )
    assert len(replies) == 1
    assert replies[0]["id"] == 10000
    assert replies[0]["error"]["code"] == -32601

    bad_json = await _send_mcp(server, "{not valid json")
    assert bad_json[0]["error"]["code"] == -32700

    bad_id = await _send_mcp(
        server, {"jsonrpc": "2.0", "id": True, "method": "tools/list"}
    )
    assert bad_id[0]["error"]["code"] == -32600

    # Notification (no id) must never reply
    notif = await _send_mcp(
        server, {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert notif == []


@pytest.mark.asyncio
async def test_mcp_modern_discover_list_and_unsupported_version():
    server = McpServer()
    server.add_tool(
        McpTool(
            "self.echo",
            "echo",
            PropertyList([Property("text", PropertyType.STRING)]),
            lambda args: args["text"],
        )
    )

    # Without vision tools: no me.xiaozhi/vision extension
    replies = await _send_mcp(
        server,
        {
            "jsonrpc": "2.0",
            "id": "disc-1",
            "method": "server/discover",
            "params": {"_meta": _modern_meta()},
        },
    )
    res = replies[0]["result"]
    assert replies[0]["id"] == "disc-1"
    assert res["resultType"] == "complete"
    assert res["supportedVersions"] == ["2026-07-28", "2024-11-05"]
    assert res["capabilities"] == {"tools": {}}
    assert res["ttlMs"] == 60000
    assert res["cacheScope"] == "private"
    assert "io.modelcontextprotocol/serverInfo" in res["_meta"]

    # Register vision tool -> advertises me.xiaozhi/vision
    cam = NormalCamera(ConfigManager.from_dict())
    register_camera_tools(server.add_tool, cam)
    replies2 = await _send_mcp(
        server,
        {
            "jsonrpc": "2.0",
            "id": 10000,
            "method": "server/discover",
            "params": {"_meta": _modern_meta()},
        },
    )
    assert replies2[0]["result"]["capabilities"]["extensions"] == {
        "me.xiaozhi/vision": {}
    }

    # Unsupported version (including 2024-11-05 inside modern _meta) -> -32022
    for bad_ver in ("2099-01-01", "2024-11-05"):
        err = await _send_mcp(
            server,
            {
                "jsonrpc": "2.0",
                "id": "ver-1",
                "method": "server/discover",
                "params": {"_meta": _modern_meta(version=bad_ver)},
            },
        )
        assert err[0]["error"]["code"] == -32022
        assert err[0]["error"]["data"]["requested"] == bad_ver
        assert "2026-07-28" in err[0]["error"]["data"]["supported"]

    # Modern tools/list includes resultType, ttlMs, cacheScope, _meta
    listed = await _send_mcp(
        server,
        {
            "jsonrpc": "2.0",
            "id": "list-1",
            "method": "tools/list",
            "params": {"withUserTools": False, "_meta": _modern_meta()},
        },
    )
    page = listed[0]["result"]
    assert page["resultType"] == "complete"
    assert page["ttlMs"] == 60000
    assert page["cacheScope"] == "private"
    assert "_meta" in page
    assert {t["name"] for t in page["tools"]} == {"self.echo", "take_photo"}


@pytest.mark.asyncio
async def test_mcp_modern_per_call_vision_isolation(monkeypatch):
    server = McpServer()
    cam = NormalCamera(ConfigManager.from_dict())
    cam.set_explain_url("https://legacy.example.com/vision")
    cam.set_explain_token("legacy-secret")
    cam.capture = lambda: (cam.set_jpeg_data(b"\xff\xd8fake"), True)[1]

    posted: list[tuple[str, dict]] = []

    def fake_post(url, headers=None, files=None, timeout=10):
        posted.append((url, dict(headers or {})))
        return SimpleNamespace(status_code=200, text="red cup")

    monkeypatch.setattr("src.mcp.tools.camera.normal_camera.requests.post", fake_post)
    register_camera_tools(server.add_tool, cam)

    # 1. Missing me.xiaozhi/vision -> -32021 with requiredCapabilities
    missing = await _send_mcp(
        server,
        {
            "jsonrpc": "2.0",
            "id": "photo-missing",
            "method": "tools/call",
            "params": {
                "name": "take_photo",
                "arguments": {"question": "what?"},
                "_meta": _modern_meta(capabilities={}),
            },
        },
    )
    assert missing[0]["error"]["code"] == -32021
    assert missing[0]["error"]["data"]["requiredCapabilities"] == {
        "extensions": {"me.xiaozhi/vision": {}}
    }
    assert posted == []

    # 2. Modern call without token -> uses per-call URL, MUST NOT leak legacy token
    ok_no_token = await _send_mcp(
        server,
        {
            "jsonrpc": "2.0",
            "id": "photo-1",
            "method": "tools/call",
            "params": {
                "name": "take_photo",
                "arguments": {"question": "what?"},
                "_meta": _modern_meta(
                    capabilities={
                        "extensions": {
                            "me.xiaozhi/vision": {
                                "url": "https://modern.example.com/analyze"
                            }
                        }
                    }
                ),
            },
        },
    )
    res = ok_no_token[0]["result"]
    assert res["resultType"] == "complete"
    assert res["isError"] is False
    assert res["content"] == [{"type": "text", "text": "red cup"}]
    assert posted[-1][0] == "https://modern.example.com/analyze"
    assert "Authorization" not in posted[-1][1]
    # Legacy saved config must remain untouched
    assert cam.explain_url == "https://legacy.example.com/vision"
    assert cam.explain_token == "legacy-secret"

    # 3. Modern call with invalid arguments -> -32602 before execution
    bad_args = await _send_mcp(
        server,
        {
            "jsonrpc": "2.0",
            "id": "photo-bad-args",
            "method": "tools/call",
            "params": {
                "name": "take_photo",
                "arguments": {},
                "_meta": _modern_meta(
                    capabilities={
                        "extensions": {
                            "me.xiaozhi/vision": {
                                "url": "https://modern.example.com/analyze",
                                "token": "modern-tok",
                            }
                        }
                    }
                ),
            },
        },
    )
    assert bad_args[0]["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# 3. MQTT/UDP authenticated udp_probe (docs/mqtt-udp-probe_zh.md)
# ---------------------------------------------------------------------------


def test_udp_probe_matches_official_spec_vectors():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    ssrc = bytes.fromhex("11223344")

    ping = encode_probe(PROBE_TYPE_PING, key, ssrc, 1)
    assert ping.hex() == (
        "02000010112233440000000000000001" "daef4dd63a34feb152d16095500e9506"
    )

    pong = encode_probe(PROBE_TYPE_PONG, key, ssrc, 1)
    assert pong.hex() == (
        "03000010112233440000000000000001" "7cd8501761355f1009447bad2c4f8a56"
    )

    assert matches_pending_pong(pong, ping, key) is True

    # Any tampered byte must be rejected
    for index in (0, 1, 2, 4, 8, 12, 16, 31):
        bad = bytearray(pong)
        bad[index] ^= 0x01
        assert matches_pending_pong(bytes(bad), ping, key) is False

    # Wrong length rejected
    assert matches_pending_pong(pong[:-1], ping, key) is False

    decoded_key, decoded_ssrc = decode_probe_credentials(
        "000102030405060708090a0b0c0d0e0f",
        "01000000112233440000000000000000",
    )
    assert decoded_key == key
    assert decoded_ssrc == ssrc


@pytest.mark.asyncio
async def test_udp_probe_retransmit_and_pong_marks_healthy(caplog):
    loop = asyncio.get_running_loop()
    channel = MqttUdpChannel(loop)
    channel._probe_retry_offsets = (0.04, 0.09)
    channel._probe_budget_s = 0.25
    channel._probe_interval_s = 10.0

    key_hex = "000102030405060708090a0b0c0d0e0f"
    nonce_hex = "01000000112233440000000000000000"
    channel.configure("127.0.0.1", 8888, key_hex, nonce_hex, probe_enabled=True)

    sent: list[bytes] = []

    class FakeSocket:
        def sendto(self, data, addr):
            sent.append(data)

        def close(self):
            pass

    channel.socket = FakeSocket()
    channel.running = True

    failures: list[str] = []
    channel.start_probe(on_failure=failures.append)
    assert len(sent) == 1
    assert channel.probe_state == UdpProbeState.VERIFYING

    # Wait for first retransmission (attempt 2 -> SUSPECT, identical datagram)
    await asyncio.sleep(0.06)
    assert len(sent) >= 2
    assert sent[1] == sent[0]
    assert channel.probe_state == UdpProbeState.SUSPECT

    # Deliver matching PONG -> HEALTHY, does NOT touch audio sequence counters
    key = bytes.fromhex(key_hex)
    ssrc = bytes.fromhex("11223344")
    pong = encode_probe(PROBE_TYPE_PONG, key, ssrc, 1)
    with caplog.at_level("INFO"):
        channel._handle_packet(pong, 1)

    await asyncio.sleep(0.02)
    assert channel.probe_state == UdpProbeState.HEALTHY
    assert channel.local_sequence == 0
    assert channel.remote_sequence == 0
    assert failures == []
    assert any("unknown after retransmission" in r.message for r in caplog.records)

    channel.reset_session()


@pytest.mark.asyncio
async def test_udp_probe_timeout_fails_without_downgrade():
    loop = asyncio.get_running_loop()
    channel = MqttUdpChannel(loop)
    channel._probe_retry_offsets = (0.02, 0.04)
    channel._probe_budget_s = 0.07
    channel._probe_interval_s = 10.0

    channel.configure(
        "127.0.0.1",
        8888,
        "000102030405060708090a0b0c0d0e0f",
        "01000000112233440000000000000000",
        probe_enabled=True,
    )
    sent: list[bytes] = []
    channel.socket = SimpleNamespace(
        sendto=lambda data, addr: sent.append(data), close=lambda: None
    )
    channel.running = True

    failed = asyncio.Event()
    reasons: list[str] = []

    def on_fail(reason: str):
        reasons.append(reason)
        failed.set()

    channel.start_probe(on_failure=on_fail)
    await asyncio.wait_for(failed.wait(), timeout=1.0)

    assert reasons == ["udp_probe_timeout"]
    assert channel.probe_state == UdpProbeState.FAILED
    assert channel.is_ready() is False
    assert len(sent) == 3  # initial + 2 retries
    channel.reset_session()


@pytest.mark.asyncio
async def test_mqtt_protocol_hello_negotiates_probe_and_rejects_bad_types():
    loop = asyncio.get_running_loop()
    protocol = MqttProtocol(loop, config=ConfigManager.from_dict())
    protocol._udp.start = Mock()

    # Valid legacy hello (no features.udp_probe) -> LEGACY_UNVERIFIED
    protocol._handle_mqtt_message(
        json.dumps(
            {
                "type": "hello",
                "transport": "udp",
                "session_id": "s1",
                "udp": {
                    "server": "127.0.0.1",
                    "port": 8888,
                    "key": "000102030405060708090a0b0c0d0e0f",
                    "nonce": "01000000112233440000000000000000",
                },
            }
        )
    )
    assert protocol._udp.probe_enabled is False
    assert protocol._udp.probe_state == UdpProbeState.LEGACY_UNVERIFIED

    # Invalid features.udp_probe type -> sets _hello_error
    protocol.server_hello_event = asyncio.Event()
    protocol._hello_error = None
    protocol._handle_mqtt_message(
        json.dumps(
            {
                "type": "hello",
                "transport": "udp",
                "session_id": "s2",
                "features": {"udp_probe": "yes"},
                "udp": {
                    "server": "127.0.0.1",
                    "port": 8888,
                    "key": "000102030405060708090a0b0c0d0e0f",
                    "nonce": "01000000112233440000000000000000",
                },
            }
        )
    )
    assert protocol._hello_error is not None
    assert protocol.server_hello_event.is_set()
