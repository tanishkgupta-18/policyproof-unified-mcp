"""Comprehensive Test Suite for PolicyProof Unified MCP Server.

Validates:
1. Direct business logic & data store queries across all 3 domains (Policy, Gnani, Delhivery)
2. FastMCP Tool Discovery: EXACTLY the 8 required tools, no duplicates
3. Tool Execution via FastMCP
4. HTTP /health endpoint monitoring
5. Remote SSE Transport end-to-end client connectivity and tool invocation
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import os
from pathlib import Path
import struct
import unittest
import wave

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import uvicorn

import mock_rules
from mock_rules import (
    TRIGGER_ORDER_FAIL_VALIDATION,
    TRIGGER_ORDER_MALFORMED,
    TRIGGER_ORDER_TIMEOUT,
    TRIGGER_PICKUP_BAD_RESPONSE,
    TRIGGER_PICKUP_NO_CAPACITY,
    TRIGGER_PICKUP_TIMEOUT,
    TRIGGER_PINCODE_TIMEOUT,
    TRIGGER_PINCODE_UNSERVICEABLE,
    TRIGGER_WAYBILL_LOST,
    TRIGGER_WAYBILL_NOTFOUND,
    TRIGGER_WAYBILL_TIMEOUT,
    check_pincode_serviceability,
    create_pickup_request,
    create_shipment,
    track_shipment,
)
from server import SERVICE_NAME, create_app, health_check, mcp
from tools.gnani_tools import (
    get_stt_api_key,
    get_tts_api_key,
    gnani_speech_to_text,
    gnani_text_to_speech,
)
from tools.policy_tools import search_evidence_records, search_policy_evidence


def generate_sample_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> str:
    """Generate a clean in-memory PCM 16-bit mono WAV and return as base64."""
    wav_buffer = io.BytesIO()
    num_samples = int(duration_seconds * sample_rate)
    frequency = 440.0

    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        samples = []
        for i in range(num_samples):
            value = int(16000 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            samples.append(struct.pack("<h", value))
        wf.writeframes(b"".join(samples))

    wav_bytes = wav_buffer.getvalue()
    return base64.b64encode(wav_bytes).decode("utf-8")


class TestPolicyEvidence(unittest.TestCase):
    """Test policy evidence retrieval from evidence/policies.json."""

    def test_01_hdfc_waiting_period(self) -> None:
        """Verify POL-HDFC-TEST returns 36-month waiting period excerpt."""
        res = search_policy_evidence(
            policy_id="POL-HDFC-TEST",
            query="pre-existing disease waiting period",
        )
        self.assertEqual(res["policy_id"], "POL-HDFC-TEST")
        self.assertGreater(len(res["results"]), 0)
        excerpts = [r["excerpt"] for r in res["results"]]
        self.assertTrue(
            any("36-month waiting period" in ex for ex in excerpts),
            f"Expected 36-month waiting period in excerpts: {excerpts}",
        )
        self.assertTrue(all(r["page"] > 0 for r in res["results"]))

    def test_02_care_copay(self) -> None:
        """Verify POL-CARE-TEST returns 10 percent co-pay excerpt."""
        res = search_policy_evidence(
            policy_id="POL-CARE-TEST",
            query="co-pay",
        )
        self.assertEqual(res["policy_id"], "POL-CARE-TEST")
        self.assertGreater(len(res["results"]), 0)
        excerpts = [r["excerpt"] for r in res["results"]]
        self.assertTrue(
            any("10 percent co-pay" in ex for ex in excerpts),
            f"Expected 10 percent co-pay in excerpts: {excerpts}",
        )

    def test_03_nonexistent_policy(self) -> None:
        """Verify nonexistent policy returns empty results list."""
        res = search_policy_evidence(
            policy_id="POL-NONEXISTENT",
            query="waiting period",
        )
        self.assertEqual(res["results"], [])


class TestGnaniTools(unittest.IsolatedAsyncioTestCase):
    """Test Gnani STT and TTS tools behavior (credential checks and real calls if available)."""

    async def test_01_stt_missing_or_real_credentials(self) -> None:
        sample_audio = generate_sample_wav(0.2, 16000)
        res = await gnani_speech_to_text(audio_base64=sample_audio)
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)
        if not get_stt_api_key():
            # Missing credentials must return structured error and NOT crash
            self.assertFalse(res["success"])
            self.assertEqual(res["error_type"], "missing_credentials")
            self.assertEqual(res["service"], "gnani_stt")
            self.assertIn("GNANI_STT_API_KEY", res["message"])
        else:
            # If key present, must have timestamp and request_id
            self.assertIn("request_id", res)
            self.assertIn("timestamp", res)

    async def test_02_tts_missing_or_real_credentials(self) -> None:
        res = await gnani_text_to_speech(text="Testing speech synthesis.")
        self.assertIsInstance(res, dict)
        self.assertIn("success", res)
        if not get_tts_api_key():
            # Missing credentials must return structured error and NOT crash
            self.assertFalse(res["success"])
            self.assertEqual(res["error_type"], "missing_credentials")
            self.assertEqual(res["service"], "gnani_tts")
            self.assertIn("GNANI_TTS_API_KEY", res["message"])
        else:
            if res["success"]:
                self.assertIn("audio_base64", res)


class TestDelhiveryLogic(unittest.TestCase):
    """Test deterministic Delhivery logistics rules."""

    def setUp(self) -> None:
        mock_rules.state_registry.clear()

    def test_01_serviceable_pincode(self) -> None:
        res = check_pincode_serviceability("560001")
        self.assertTrue(res["success"])
        self.assertTrue(res["serviceable"])
        self.assertTrue(res["prepaid"])
        self.assertTrue(res["cod"])

    def test_02_unserviceable_pincode(self) -> None:
        res = check_pincode_serviceability(TRIGGER_PINCODE_UNSERVICEABLE)
        self.assertTrue(res["success"])
        self.assertFalse(res["serviceable"])

    def test_03_pincode_timeout(self) -> None:
        res = check_pincode_serviceability(TRIGGER_PINCODE_TIMEOUT)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "TIMEOUT")

    def test_04_pincode_validation_error(self) -> None:
        res = check_pincode_serviceability("INVALID_PIN")
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "VALIDATION_ERROR")

    def test_05_shipment_normal_success(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Flat 402, Lotus Towers, Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order="ORD-SUCCESS-1001",
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "Manifested")
        self.assertTrue(res["waybill"].startswith("128"))

    def test_06_shipment_unserviceable_pin(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Remote Forest",
            pin=TRIGGER_PINCODE_UNSERVICEABLE,
            city="Remote",
            state="Remote",
            phone="9876543210",
            order="ORD-UNSERV-1001",
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "UNSERVICEABLE_PINCODE")

    def test_07_shipment_validation_failure(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order=TRIGGER_ORDER_FAIL_VALIDATION,
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "VALIDATION_ERROR")

    def test_08_shipment_timeout(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order=TRIGGER_ORDER_TIMEOUT,
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "TIMEOUT")

    def test_09_shipment_malformed_response(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order=TRIGGER_ORDER_MALFORMED,
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "MALFORMED_RESPONSE")

    def test_10_tracking_normal_and_special_states(self) -> None:
        # Standard tracking
        res_normal = track_shipment("1281234567890")
        self.assertTrue(res_normal["success"])
        self.assertEqual(res_normal["status"], "In Transit")

        # Not found
        res_nf = track_shipment(TRIGGER_WAYBILL_NOTFOUND)
        self.assertFalse(res_nf["success"])
        self.assertEqual(res_nf["error_type"], "NOT_FOUND")

        # Timeout
        res_to = track_shipment(TRIGGER_WAYBILL_TIMEOUT)
        self.assertFalse(res_to["success"])
        self.assertEqual(res_to["error_type"], "TIMEOUT")

        # Lost
        res_lost = track_shipment(TRIGGER_WAYBILL_LOST)
        self.assertTrue(res_lost["success"])
        self.assertEqual(res_lost["status"], "Lost")

    def test_11_pickup_requests(self) -> None:
        # Normal
        res_ok = create_pickup_request(
            pickup_location="WH-BLR-01",
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001", "1281002"],
        )
        self.assertTrue(res_ok["success"])
        self.assertEqual(res_ok["status"], "Scheduled")

        # No capacity
        res_nocap = create_pickup_request(
            pickup_location=TRIGGER_PICKUP_NO_CAPACITY,
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001"],
        )
        self.assertFalse(res_nocap["success"])
        self.assertEqual(res_nocap["error_type"], "NO_CAPACITY")

        # Timeout
        res_to = create_pickup_request(
            pickup_location=TRIGGER_PICKUP_TIMEOUT,
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001"],
        )
        self.assertFalse(res_to["success"])
        self.assertEqual(res_to["error_type"], "TIMEOUT")

        # Bad response
        res_bad = create_pickup_request(
            pickup_location=TRIGGER_PICKUP_BAD_RESPONSE,
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001"],
        )
        self.assertFalse(res_bad["success"])
        self.assertEqual(res_bad["error_type"], "MALFORMED_RESPONSE")

        # Empty waybills
        res_empty = create_pickup_request(
            pickup_location="WH-BLR-01",
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=[],
        )
        self.assertFalse(res_empty["success"])
        self.assertEqual(res_empty["error_type"], "VALIDATION_ERROR")


class TestMCPServerIntegration(unittest.IsolatedAsyncioTestCase):
    """Test FastMCP tool registration, tool discovery, /health route, and SSE transport."""

    async def asyncSetUp(self) -> None:
        mock_rules.state_registry.clear()
        self.app = create_app()

    async def test_01_mcp_tool_discovery_exact_8_tools(self) -> None:
        """Verify MCP discovery exposes EXACTLY the 8 required tools without duplicates."""
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "health_check",
            "search_policy_evidence",
            "gnani_speech_to_text",
            "gnani_text_to_speech",
            "delhivery_pincode_serviceability",
            "delhivery_create_shipment",
            "delhivery_track_shipment",
            "delhivery_create_pickup_request",
        ]

        self.assertEqual(
            len(tool_names),
            8,
            f"Expected exactly 8 tools, found {len(tool_names)}: {tool_names}",
        )
        self.assertEqual(
            set(tool_names),
            set(expected_tools),
            f"Tools mismatch. Expected: {expected_tools}, Found: {tool_names}",
        )
        # Ensure no duplicate names
        self.assertEqual(len(tool_names), len(set(tool_names)))

    async def test_02_health_check_tool(self) -> None:
        """Verify health_check tool execution."""
        res = await mcp.call_tool("health_check", {})
        self.assertFalse(res.is_error)
        data = json.loads(res.content[0].text)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], SERVICE_NAME)

    async def test_03_search_policy_evidence_tool(self) -> None:
        """Verify search_policy_evidence tool execution through FastMCP."""
        res = await mcp.call_tool(
            "search_policy_evidence",
            {"policy_id": "POL-HDFC-TEST", "query": "waiting period"},
        )
        self.assertFalse(res.is_error)
        data = json.loads(res.content[0].text)
        self.assertEqual(data["policy_id"], "POL-HDFC-TEST")
        self.assertGreater(len(data["results"]), 0)

    async def test_04_http_health_endpoint(self) -> None:
        """Verify Starlette HTTP GET /health endpoint."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://127.0.0.1"
        ) as client:
            resp = await client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["service"], SERVICE_NAME)

    async def test_05_sse_transport_end_to_end(self) -> None:
        """Verify full remote SSE transport connection, tool discovery, and tool invocation."""
        test_port = 8899
        config = uvicorn.Config(self.app, host="127.0.0.1", port=test_port, log_level="error")
        server_instance = uvicorn.Server(config)
        server_task = asyncio.create_task(server_instance.serve())
        await asyncio.sleep(0.4)

        try:
            sse_url = f"http://127.0.0.1:{test_port}/sse"
            async with sse_client(sse_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # List tools over SSE wire
                    tools_result = await session.list_tools()
                    discovered = [t.name for t in tools_result.tools]
                    self.assertEqual(len(discovered), 8)
                    self.assertIn("search_policy_evidence", discovered)
                    self.assertIn("delhivery_pincode_serviceability", discovered)
                    self.assertIn("gnani_speech_to_text", discovered)

                    # Invoke health_check over SSE wire
                    res_hc = await session.call_tool("health_check", arguments={})
                    hc_data = json.loads(res_hc.content[0].text)
                    self.assertEqual(hc_data["status"], "ok")
                    self.assertEqual(hc_data["service"], SERVICE_NAME)

                    # Invoke search_policy_evidence over SSE wire
                    res_pe = await session.call_tool(
                        "search_policy_evidence",
                        {"policy_id": "POL-CARE-TEST", "query": "co-pay"},
                    )
                    pe_data = json.loads(res_pe.content[0].text)
                    self.assertEqual(pe_data["policy_id"], "POL-CARE-TEST")
                    self.assertGreater(len(pe_data["results"]), 0)
        finally:
            server_instance.should_exit = True
            await server_task


if __name__ == "__main__":
    unittest.main(verbosity=2)
