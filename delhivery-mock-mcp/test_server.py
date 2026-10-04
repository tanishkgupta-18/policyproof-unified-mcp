"""Test Suite for Delhivery Mock MCP Server.

Validates all 12+ required deterministic scenarios, tool discovery,
HTTP /health endpoint, and remote SSE transport.

Test Cases Covered:
1. Serviceable pincode
2. Unserviceable pincode (000000)
3. Pincode validation failure (malformed pincodes)
4. Pincode timeout (999998)
5. Successful shipment creation
6. Shipment validation failure (FAIL-VALIDATION or missing fields)
7. Shipment timeout (TIMEOUT-ORDER)
8. Shipment malformed upstream response (MALFORMED-RESPONSE)
9. Shipment unserviceable destination pincode (000000)
10. Successful tracking (created shipment and standard waybill)
11. Shipment not found (NOTFOUND)
12. Shipment timeout (TIMEOUT)
13. Lost shipment (LOST)
14. Tracking lifecycle states (Manifested, Ready for Pickup, In Transit, Out for Delivery, Delivered, Cancelled/RTO, Lost)
15. Successful pickup request
16. Pickup no-capacity failure (NO-CAPACITY)
17. Pickup validation failure (empty shipments list)
18. Pickup timeout (TIMEOUT)
19. Pickup malformed upstream response (BAD-RESPONSE)
20. HTTP /health endpoint
21. MCP Tool Discovery (verifies health_check, delhivery_pincode_serviceability, delhivery_create_shipment, delhivery_track_shipment, delhivery_create_pickup_request)
22. Remote SSE transport connection & invocation via MCP ClientSession
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import List

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
    get_health_status,
    track_shipment,
)
from server import create_app, mcp


class TestDelhiveryMockDirect(unittest.TestCase):
    """Direct functional tests of mock_rules business logic."""

    def setUp(self) -> None:
        mock_rules.state_registry.clear()

    # 1. Serviceable pincode
    def test_01_serviceable_pincode(self) -> None:
        res = check_pincode_serviceability("560001")
        self.assertTrue(res["success"])
        self.assertEqual(res["pincode"], "560001")
        self.assertTrue(res["serviceable"])
        self.assertTrue(res["cod"])
        self.assertTrue(res["prepaid"])
        self.assertTrue(res["reverse_pickup"])
        self.assertIn("delivery_codes", res["raw_response"])

    # 2. Unserviceable pincode
    def test_02_unserviceable_pincode(self) -> None:
        res = check_pincode_serviceability(TRIGGER_PINCODE_UNSERVICEABLE)
        self.assertTrue(res["success"])
        self.assertEqual(res["pincode"], "000000")
        self.assertFalse(res["serviceable"])
        self.assertFalse(res["cod"])
        self.assertFalse(res["prepaid"])
        self.assertFalse(res["reverse_pickup"])
        self.assertEqual(res["raw_response"]["delivery_codes"], [])

    # 3. Pincode validation failure (malformed)
    def test_03_malformed_pincode_validation_failure(self) -> None:
        res = check_pincode_serviceability("ABC12")
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "VALIDATION_ERROR")
        self.assertFalse(res["serviceable"])

    # 4. Pincode timeout
    def test_04_pincode_timeout(self) -> None:
        res = check_pincode_serviceability(TRIGGER_PINCODE_TIMEOUT)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "TIMEOUT")
        self.assertIsNone(res["raw_response"])

    # 5. Successful shipment creation
    def test_05_successful_shipment_creation(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Flat 402, Lotus Towers, Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order="ORD-SUCCESS-1001",
            payment_mode="Prepaid",
            total_amount="1499.00",
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["waybill"].startswith("128"))
        self.assertEqual(res["order_id"], "ORD-SUCCESS-1001")
        self.assertEqual(res["status"], "Manifested")
        self.assertIn("packages", res["raw_response"])
        self.assertTrue(res["raw_response"]["success"])

    # 6. Shipment validation failure
    def test_06_shipment_validation_failure(self) -> None:
        # Explicit FAIL-VALIDATION trigger
        res1 = create_shipment(
            name="Rahul Sharma",
            add="Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order=TRIGGER_ORDER_FAIL_VALIDATION,
        )
        self.assertFalse(res1["success"])
        self.assertEqual(res1["error_type"], "VALIDATION_ERROR")

        # Missing required field (name)
        res2 = create_shipment(
            name="",
            add="Indiranagar",
            pin="560038",
            city="Bengaluru",
            state="Karnataka",
            phone="9876543210",
            order="ORD-1002",
        )
        self.assertFalse(res2["success"])
        self.assertEqual(res2["error_type"], "VALIDATION_ERROR")

    # 7. Shipment timeout
    def test_07_shipment_timeout(self) -> None:
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
        self.assertIsNone(res["raw_response"])

    # 8. Shipment malformed upstream response
    def test_08_shipment_malformed_upstream_response(self) -> None:
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
        self.assertIn("<html>", str(res["raw_response"]))

    # 9. Shipment destination unserviceable
    def test_09_shipment_destination_unserviceable(self) -> None:
        res = create_shipment(
            name="Rahul Sharma",
            add="Remote Forest Post",
            pin=TRIGGER_PINCODE_UNSERVICEABLE,
            city="Nowhere",
            state="Unknown",
            phone="9876543210",
            order="ORD-UNSERV-1001",
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "UNSERVICEABLE_PINCODE")
        self.assertEqual(res["destination_pin"], "000000")

    # 10. Successful tracking
    def test_10_successful_tracking(self) -> None:
        # Track manifested order created earlier
        ship = create_shipment(
            name="Priya Patel",
            add="Bandra West",
            pin="400050",
            city="Mumbai",
            state="Maharashtra",
            phone="9820012345",
            order="ORD-TRACK-2001",
        )
        waybill = ship["waybill"]

        res = track_shipment(waybill)
        self.assertTrue(res["success"])
        self.assertEqual(res["waybill"], waybill)
        self.assertEqual(res["status"], "Manifested")
        self.assertGreater(len(res["history"]), 0)

        # Track arbitrary valid waybill (default in-transit)
        res_default = track_shipment("1289998887776")
        self.assertTrue(res_default["success"])
        self.assertEqual(res_default["status"], "In Transit")
        self.assertEqual(len(res_default["history"]), 3)

    # 11. Shipment not found
    def test_11_shipment_not_found(self) -> None:
        res = track_shipment(TRIGGER_WAYBILL_NOTFOUND)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "Not Found")
        self.assertEqual(res["error_type"], "NOT_FOUND")

    # 12. Shipment timeout
    def test_12_shipment_timeout(self) -> None:
        res = track_shipment(TRIGGER_WAYBILL_TIMEOUT)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "TIMEOUT")

    # 13. Lost shipment
    def test_13_lost_shipment(self) -> None:
        res = track_shipment(TRIGGER_WAYBILL_LOST)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "Lost")
        self.assertEqual(res["waybill"], "LOST")
        self.assertTrue(any(h["status"] == "Lost" for h in res["history"]))

    # 14. Tracking lifecycle states
    def test_14_tracking_lifecycle_states(self) -> None:
        states = {
            "WB-MANIFESTED": "Manifested",
            "WB-READY": "Ready for Pickup",
            "WB-TRANSIT": "In Transit",
            "WB-OFD": "Out for Delivery",
            "WB-DELIVERED": "Delivered",
            "WB-CANCELLED": "Cancelled / RTO",
            "LOST": "Lost",
        }
        for wb_key, expected_status in states.items():
            res = track_shipment(wb_key)
            self.assertEqual(res["status"], expected_status, f"Failed for {wb_key}")

    # 15. Successful pickup request
    def test_15_successful_pickup_request(self) -> None:
        res = create_pickup_request(
            pickup_location="WH-Bengaluru-Main",
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001", "1281002"],
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["pickup_request_id"].startswith("PUR-"))
        self.assertEqual(res["status"], "Scheduled")
        self.assertEqual(res["pickup_location"], "WH-Bengaluru-Main")

    # 16. Pickup no-capacity failure
    def test_16_pickup_no_capacity(self) -> None:
        res = create_pickup_request(
            pickup_location=TRIGGER_PICKUP_NO_CAPACITY,
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001"],
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "NO_CAPACITY")
        self.assertEqual(res["status"], "Unavailable")

    # 17. Pickup validation failure (empty shipments list)
    def test_17_pickup_validation_empty_shipments(self) -> None:
        res = create_pickup_request(
            pickup_location="WH-Bengaluru-Main",
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=[],
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "VALIDATION_ERROR")

    # 18. Pickup timeout
    def test_18_pickup_timeout(self) -> None:
        res = create_pickup_request(
            pickup_location=TRIGGER_PICKUP_TIMEOUT,
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001"],
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "TIMEOUT")

    # 19. Pickup malformed upstream response
    def test_19_pickup_malformed_upstream_response(self) -> None:
        res = create_pickup_request(
            pickup_location=TRIGGER_PICKUP_BAD_RESPONSE,
            pickup_date="2026-10-06",
            pickup_slot="14:00 - 18:00",
            shipment_waybills=["1281001"],
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "MALFORMED_RESPONSE")


class TestDelhiveryMockServerAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for FastMCP tools, Tool Discovery, HTTP /health, and SSE transport."""

    async def asyncSetUp(self) -> None:
        mock_rules.state_registry.clear()
        self.app = create_app()

    # 20. Tool Discovery
    async def test_20_mcp_tool_discovery(self) -> None:
        """Verify all 5 required tools are registered and discovered on the MCP server."""
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "health_check",
            "delhivery_pincode_serviceability",
            "delhivery_create_shipment",
            "delhivery_track_shipment",
            "delhivery_create_pickup_request",
        ]

        for expected in expected_tools:
            self.assertIn(expected, tool_names, f"Missing tool: {expected}")
        self.assertEqual(len(tool_names), 5)

    # 21. Tool Call Execution through FastMCP
    async def test_21_mcp_tool_calls_through_server(self) -> None:
        # Call health_check
        res_health = await mcp.call_tool("health_check", {})
        self.assertFalse(res_health.is_error)
        health_data = json.loads(res_health.content[0].text)
        self.assertEqual(health_data["status"], "ok")
        self.assertEqual(health_data["service"], "Delhivery Mock MCP")

        # Call delhivery_pincode_serviceability
        res_pin = await mcp.call_tool("delhivery_pincode_serviceability", {"pincode": "560001"})
        pin_data = json.loads(res_pin.content[0].text)
        self.assertTrue(pin_data["success"])
        self.assertTrue(pin_data["serviceable"])

        # Call delhivery_create_shipment
        res_ship = await mcp.call_tool(
            "delhivery_create_shipment",
            {
                "name": "Ananya Roy",
                "add": "Salt Lake Sector V",
                "pin": "700091",
                "city": "Kolkata",
                "state": "West Bengal",
                "phone": "9830098300",
                "order": "ORD-MCP-3001",
            },
        )
        ship_data = json.loads(res_ship.content[0].text)
        self.assertTrue(ship_data["success"])
        self.assertEqual(ship_data["status"], "Manifested")
        waybill = ship_data["waybill"]

        # Call delhivery_track_shipment
        res_track = await mcp.call_tool("delhivery_track_shipment", {"waybill": waybill})
        track_data = json.loads(res_track.content[0].text)
        self.assertTrue(track_data["success"])
        self.assertEqual(track_data["waybill"], waybill)

        # Call delhivery_create_pickup_request
        res_pickup = await mcp.call_tool(
            "delhivery_create_pickup_request",
            {
                "pickup_location": "CCU-Warehouse-1",
                "pickup_date": "2026-10-07",
                "pickup_slot": "10:00 - 13:00",
                "shipment_waybills": [waybill],
            },
        )
        pickup_data = json.loads(res_pickup.content[0].text)
        self.assertTrue(pickup_data["success"])
        self.assertEqual(pickup_data["status"], "Scheduled")

    # 22. HTTP /health endpoint verification
    async def test_22_http_health_endpoint(self) -> None:
        """Verify Starlette HTTP /health endpoint returns 200 with service JSON."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://127.0.0.1"
        ) as client:
            resp = await client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["service"], "Delhivery Mock MCP")

    # 23. End-to-end SSE Transport with ClientSession
    async def test_23_sse_transport_end_to_end(self) -> None:
        """Verify remote SSE transport connectivity, tool discovery, and tool calling."""
        test_port = 8799
        config = uvicorn.Config(self.app, host="127.0.0.1", port=test_port, log_level="error")
        server_instance = uvicorn.Server(config)
        server_task = asyncio.create_task(server_instance.serve())
        await asyncio.sleep(0.4)

        try:
            sse_url = f"http://127.0.0.1:{test_port}/sse"
            async with sse_client(sse_url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # List tools over SSE
                    tools_result = await session.list_tools()
                    discovered = [t.name for t in tools_result.tools]
                    self.assertIn("health_check", discovered)
                    self.assertIn("delhivery_pincode_serviceability", discovered)
                    self.assertIn("delhivery_create_shipment", discovered)
                    self.assertIn("delhivery_track_shipment", discovered)
                    self.assertIn("delhivery_create_pickup_request", discovered)

                    # Call tool over SSE
                    call_result = await session.call_tool(
                        "delhivery_pincode_serviceability",
                        {"pincode": "560001"},
                    )
                    payload = json.loads(call_result.content[0].text)
                    self.assertTrue(payload["success"])
                    self.assertTrue(payload["serviceable"])
        finally:
            server_instance.should_exit = True
            await server_task


if __name__ == "__main__":
    unittest.main(verbosity=2)
