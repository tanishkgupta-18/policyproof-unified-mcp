"""Delhivery Mock MCP - Deterministic Business Logic and Simulation Rules.

This module encapsulates all deterministic simulation rules, failure triggers,
and data models for the Delhivery Mock MCP server.

IMPORTANT:
- This is a mock server for The Ken Case Competition / AgenticOrg simulation.
- It contains NO LLM logic.
- It returns pure logistics facts and responses.
- It is 100% deterministic (no random number generators or non-deterministic time delays).
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


# ==============================================================================
# Deterministic Trigger Constants
# ==============================================================================

# Pincode Serviceability Triggers
TRIGGER_PINCODE_UNSERVICEABLE = "000000"
TRIGGER_PINCODE_TIMEOUT = "999998"

# Shipment Creation Triggers
TRIGGER_ORDER_FAIL_VALIDATION = "FAIL-VALIDATION"
TRIGGER_ORDER_MALFORMED = "MALFORMED-RESPONSE"
TRIGGER_ORDER_TIMEOUT = "TIMEOUT-ORDER"

# Tracking Triggers
TRIGGER_WAYBILL_NOTFOUND = "NOTFOUND"
TRIGGER_WAYBILL_TIMEOUT = "TIMEOUT"
TRIGGER_WAYBILL_LOST = "LOST"
TRIGGER_WAYBILL_MANIFESTED = "WB-MANIFESTED"
TRIGGER_WAYBILL_READY = "WB-READY"
TRIGGER_WAYBILL_TRANSIT = "WB-TRANSIT"
TRIGGER_WAYBILL_OFD = "WB-OFD"
TRIGGER_WAYBILL_DELIVERED = "WB-DELIVERED"
TRIGGER_WAYBILL_CANCELLED = "WB-CANCELLED"

# Pickup Request Triggers
TRIGGER_PICKUP_NO_CAPACITY = "NO-CAPACITY"
TRIGGER_PICKUP_TIMEOUT = "TIMEOUT"
TRIGGER_PICKUP_BAD_RESPONSE = "BAD-RESPONSE"
TRIGGER_PICKUP_OUT_FOR_PICKUP = "OUT-FOR-PICKUP"
TRIGGER_PICKUP_PICKED = "PICKED-LOCATION"
TRIGGER_PICKUP_CANCELLED = "CANCELLED-LOCATION"


# ==============================================================================
# In-Memory State Registry (Deterministic Simulation)
# ==============================================================================

class MockStateRegistry:
    """In-memory registry to retain created shipments and pickups deterministically."""

    def __init__(self) -> None:
        self.shipments: Dict[str, Dict[str, Any]] = {}
        self.pickup_requests: Dict[str, Dict[str, Any]] = {}

    def clear(self) -> None:
        """Reset all in-memory mock state."""
        self.shipments.clear()
        self.pickup_requests.clear()


# Global in-memory registry instance
state_registry = MockStateRegistry()


# ==============================================================================
# Helper Functions
# ==============================================================================

def _deterministic_hash(key: str) -> int:
    """Produce a deterministic positive integer hash independent of Python process salt."""
    h = 0
    for char in key:
        h = (31 * h + ord(char)) & 0xFFFFFFFF
    return h


def _generate_waybill(order_id: str) -> str:
    """Generate a deterministic 13-digit AWB number based on order ID."""
    h = _deterministic_hash(order_id)
    suffix = str(h).zfill(10)[:10]
    return f"128{suffix}"


# ==============================================================================
# Tool 1: Pincode Serviceability Logic
# ==============================================================================

def check_pincode_serviceability(pincode: str) -> Dict[str, Any]:
    """Check whether a destination pincode is serviceable by Delhivery.

    Documented Delhivery endpoint: GET /c/api/pin-codes/json/?filter_codes={pincode}

    Deterministic Scenarios:
    - '999998' or contains 'TIMEOUT' -> Simulated Timeout
    - '000000' or starts with '000' -> Unserviceable
    - Non-6-digit or non-numeric -> Validation Error
    - Any other valid 6-digit pin -> Serviceable with full Prepaid, COD, and Reverse Pickup
    """
    pincode_str = str(pincode).strip()

    # Scenario: Timeout
    if pincode_str == TRIGGER_PINCODE_TIMEOUT or "TIMEOUT" in pincode_str.upper():
        return {
            "success": False,
            "pincode": pincode_str,
            "error": "Upstream timeout: Delhivery serviceability API did not respond within 30000ms",
            "error_type": "TIMEOUT",
            "timeout_seconds": 30.0,
            "raw_response": None,
        }

    # Scenario: Validation Error (malformed pincode)
    if not (pincode_str.isdigit() and len(pincode_str) == 6):
        return {
            "success": False,
            "pincode": pincode_str,
            "serviceable": False,
            "error": f"Validation error: Invalid pincode format '{pincode_str}'. Pincode must be exactly 6 numeric digits.",
            "error_type": "VALIDATION_ERROR",
            "raw_response": {
                "error": "Invalid postal code format",
                "status_code": 400,
            },
        }

    # Scenario: Unserviceable pincode
    if pincode_str == TRIGGER_PINCODE_UNSERVICEABLE or pincode_str.startswith("000"):
        return {
            "success": True,
            "pincode": pincode_str,
            "serviceable": False,
            "cod": False,
            "prepaid": False,
            "reverse_pickup": False,
            "message": f"Pincode {pincode_str} is currently unserviceable by Delhivery",
            "raw_response": {
                "delivery_codes": [],
                "message": f"No delivery service available for pincode {pincode_str}",
            },
        }

    # Scenario: Successful serviceable pincode
    # Derive regional sort code and hub deterministically from pincode
    pin_int = int(pincode_str)
    city_map = {
        "1": ("Delhi", "DL", "DEL/DEL"),
        "2": ("Lucknow", "UP", "LKO/HUB"),
        "3": ("Ahmedabad", "GJ", "AMD/HUB"),
        "4": ("Mumbai", "MH", "BOM/BOM"),
        "5": ("Bengaluru", "KA", "BLR/APL"),
        "6": ("Chennai", "TN", "MAA/HUB"),
        "7": ("Kolkata", "WB", "CCU/HUB"),
        "8": ("Patna", "BR", "PAT/HUB"),
    }
    first_digit = pincode_str[0]
    city_name, state_code, sort_code = city_map.get(first_digit, ("Bengaluru", "KA", "BLR/APL"))

    return {
        "success": True,
        "pincode": pincode_str,
        "serviceable": True,
        "cod": True,
        "prepaid": True,
        "reverse_pickup": True,
        "sort_code": sort_code,
        "city": city_name,
        "state_code": state_code,
        "raw_response": {
            "delivery_codes": [
                {
                    "postal_code": {
                        "pin": pin_int,
                        "pre_paid": "Y",
                        "cod": "Y",
                        "pickup": "Y",
                        "repl": "N",
                        "is_oda": "N",
                        "sort_code": sort_code,
                        "state_code": state_code,
                        "district": city_name,
                        "city": city_name,
                        "center": [
                            {
                                "code": f"{sort_code.split('/')[0]}/HUB",
                                "name": f"{city_name} Central Logistics Hub",
                            }
                        ],
                    }
                }
            ]
        },
    }


# ==============================================================================
# Tool 2: Shipment Creation Logic
# ==============================================================================

def create_shipment(
    name: str,
    add: str,
    pin: str,
    city: str,
    state: str,
    phone: str,
    order: str,
    country: str = "India",
    payment_mode: str = "Prepaid",
    return_pin: Optional[str] = None,
    return_city: Optional[str] = None,
    return_phone: Optional[str] = None,
    return_add: Optional[str] = None,
    return_state: Optional[str] = None,
    return_country: Optional[str] = "India",
    products_desc: Optional[str] = "Standard Goods",
    hsn_code: Optional[str] = None,
    cod_amount: Optional[str] = "0",
    order_date: Optional[str] = None,
    total_amount: Optional[str] = "0.00",
    seller_add: Optional[str] = None,
    seller_name: Optional[str] = None,
    seller_inv: Optional[str] = None,
    quantity: Optional[str] = "1",
    waybill: Optional[str] = "",
    shipment_width: Optional[str] = "10",
    shipment_height: Optional[str] = "10",
    weight: Optional[str] = "0.5",
    shipping_mode: Optional[str] = "Surface",
    address_type: Optional[str] = "home",
) -> Dict[str, Any]:
    """Create a package shipment in Delhivery network.

    Documented Delhivery endpoint: POST /api/cmu/create.json

    Deterministic Scenarios:
    - order == 'TIMEOUT-ORDER' or contains 'TIMEOUT' -> Simulated Timeout
    - order == 'FAIL-VALIDATION' or missing required fields -> Validation Error
    - order == 'MALFORMED-RESPONSE' -> Malformed Upstream Payload
    - pin == '000000' -> Serviceability Failure
    - Otherwise -> Deterministic Successful Shipment Creation
    """
    order_str = str(order or "").strip()
    pin_str = str(pin or "").strip()
    phone_str = str(phone or "").strip()
    name_str = str(name or "").strip()
    add_str = str(add or "").strip()
    city_str = str(city or "").strip()
    state_str = str(state or "").strip()

    # Scenario: Timeout
    if order_str == TRIGGER_ORDER_TIMEOUT or "TIMEOUT" in order_str.upper():
        return {
            "success": False,
            "order_id": order_str,
            "error": "Upstream timeout: POST /api/cmu/create.json timed out after 30000ms",
            "error_type": "TIMEOUT",
            "timeout_seconds": 30.0,
            "raw_response": None,
        }

    # Scenario: Malformed Upstream Response
    if order_str == TRIGGER_ORDER_MALFORMED or "MALFORMED" in order_str.upper():
        return {
            "success": False,
            "order_id": order_str,
            "error": "Simulated upstream response error: malformed HTML returned instead of expected JSON payload from Delhivery CMU gateway",
            "error_type": "MALFORMED_RESPONSE",
            "raw_response": "<html><head><title>502 Bad Gateway</title></head><body><h1>502 Bad Gateway: Upstream CMU microservice returned invalid JSON</h1><hr><i>delhivery-edge-proxy</i></body></html>",
        }

    # Scenario: Validation Failure (Explicit trigger or missing mandatory fields)
    if (
        order_str == TRIGGER_ORDER_FAIL_VALIDATION
        or not order_str
        or not name_str
        or not add_str
        or not pin_str
        or not phone_str
        or not city_str
        or not state_str
        or not (pin_str.isdigit() and len(pin_str) == 6)
        or len(phone_str) < 7
    ):
        missing = []
        if not name_str:
            missing.append("name")
        if not add_str:
            missing.append("add")
        if not pin_str or not (pin_str.isdigit() and len(pin_str) == 6):
            missing.append("pin (must be 6 digits)")
        if not phone_str or len(phone_str) < 7:
            missing.append("phone (valid phone number required)")
        if not city_str:
            missing.append("city")
        if not state_str:
            missing.append("state")
        if not order_str or order_str == TRIGGER_ORDER_FAIL_VALIDATION:
            missing.append("order")

        error_msg = f"Validation error: Invalid or missing mandatory fields: {', '.join(missing)}"
        return {
            "success": False,
            "order_id": order_str,
            "status": "Validation Failed",
            "error": error_msg,
            "error_type": "VALIDATION_ERROR",
            "raw_response": {
                "rmk": error_msg,
                "packages": [],
                "success": False,
                "error_code": "INVALID_INPUT",
            },
        }

    # Scenario: Unserviceable Destination Pincode
    if pin_str == TRIGGER_PINCODE_UNSERVICEABLE or pin_str.startswith("000"):
        return {
            "success": False,
            "order_id": order_str,
            "status": "Failed",
            "error": f"Serviceability error: Destination pincode {pin_str} is not serviceable by Delhivery",
            "error_type": "UNSERVICEABLE_PINCODE",
            "destination_pin": pin_str,
            "raw_response": {
                "cash_pickups_count": 0,
                "package_count": 0,
                "upload_wbn": "",
                "replacement_count": 0,
                "rmk": f"Pincode {pin_str} is not serviceable for client AGENTIC_ORG",
                "packages": [],
                "success": False,
            },
        }

    # Scenario: Deterministic Success
    assigned_waybill = str(waybill).strip() if waybill else _generate_waybill(order_str)
    sort_code = f"{city_str[:3].upper()}/{state_str[:3].upper()}"
    manifest_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    shipment_record = {
        "success": True,
        "waybill": assigned_waybill,
        "order_id": order_str,
        "status": "Manifested",
        "consignee_name": name_str,
        "destination_pin": pin_str,
        "destination_city": city_str,
        "destination_state": state_str,
        "payment_mode": payment_mode,
        "shipping_mode": shipping_mode,
        "weight": weight,
        "manifest_time": manifest_time,
        "history": [
            {
                "status": "Manifested",
                "timestamp": manifest_time,
                "location": sort_code,
                "instructions": "Manifest uploaded and shipment booked via CMU create API",
            }
        ],
        "raw_response": {
            "cash_pickups_count": 0,
            "package_count": 1,
            "upload_wbn": f"UPL-{_deterministic_hash(order_str) % 1000000}",
            "replacement_count": 0,
            "rmk": "Valid",
            "packages": [
                {
                    "status": "Success",
                    "client": "AGENTIC_ORG",
                    "sort_code": sort_code,
                    "remarks": ["Shipment manifested successfully"],
                    "waybill": assigned_waybill,
                    "cod_amount": float(cod_amount) if cod_amount and cod_amount.replace(".", "", 1).isdigit() else 0.0,
                    "payment": payment_mode,
                    "serviceable": True,
                    "refnum": order_str,
                }
            ],
            "cash_pickups": 0,
            "cod_count": 1 if payment_mode.upper() == "COD" else 0,
            "success": True,
            "prepaid_count": 1 if payment_mode.upper() != "COD" else 0,
        },
    }

    # Register in in-memory state for immediate downstream tracking
    state_registry.shipments[assigned_waybill] = shipment_record
    state_registry.shipments[order_str] = shipment_record

    return {
        "success": True,
        "waybill": assigned_waybill,
        "order_id": order_str,
        "status": "Manifested",
        "destination_pin": pin_str,
        "destination_city": city_str,
        "payment_mode": payment_mode,
        "shipping_mode": shipping_mode,
        "raw_response": shipment_record["raw_response"],
    }


# ==============================================================================
# Tool 3: Shipment Tracking Logic
# ==============================================================================

def track_shipment(waybill: str) -> Dict[str, Any]:
    """Track shipment lifecycle and scan history by Delhivery waybill number.

    Documented Delhivery endpoint: GET /api/v1/packages/json/?waybill={waybill}

    Supported Lifecycle States:
    - Manifested
    - Ready for Pickup
    - In Transit
    - Out for Delivery
    - Delivered
    - Cancelled / RTO
    - Lost

    Deterministic Scenarios:
    - waybill == 'NOTFOUND' or contains 'NOTFOUND' -> Shipment Not Found
    - waybill == 'TIMEOUT' or contains 'TIMEOUT' -> Simulated Timeout
    - waybill == 'LOST' or contains 'LOST' -> Status Lost
    - waybill contains 'MANIFESTED' -> Status Manifested
    - waybill contains 'READY' -> Status Ready for Pickup
    - waybill contains 'TRANSIT' -> Status In Transit
    - waybill contains 'OFD' or 'OUT_FOR_DELIVERY' -> Status Out for Delivery
    - waybill contains 'DELIVERED' -> Status Delivered
    - waybill contains 'CANCELLED' or 'RTO' -> Status Cancelled / RTO
    - Waybill exists in state_registry -> Registered status and history
    - Otherwise -> Deterministic standard In Transit lifecycle
    """
    wb = str(waybill or "").strip()

    # Scenario: Timeout
    if wb == TRIGGER_WAYBILL_TIMEOUT or "TIMEOUT" in wb.upper():
        return {
            "success": False,
            "waybill": wb,
            "error": f"Upstream timeout: tracking query for waybill '{wb}' timed out after 30000ms",
            "error_type": "TIMEOUT",
            "timeout_seconds": 30.0,
            "history": [],
            "raw_response": None,
        }

    # Scenario: Not Found
    if wb == TRIGGER_WAYBILL_NOTFOUND or "NOTFOUND" in wb.upper():
        return {
            "success": False,
            "waybill": wb,
            "status": "Not Found",
            "error": f"Shipment not found for waybill: {wb}",
            "error_type": "NOT_FOUND",
            "history": [],
            "raw_response": {
                "ShipmentData": []
            },
        }

    # Scenario: Lost Shipment
    if wb == TRIGGER_WAYBILL_LOST or "LOST" in wb.upper():
        history = [
            {"status": "Manifested", "timestamp": "2026-10-01T09:00:00Z", "location": "BLR/HUB"},
            {"status": "In Transit", "timestamp": "2026-10-02T11:30:00Z", "location": "HYD/HUB"},
            {"status": "Lost", "timestamp": "2026-10-03T18:00:00Z", "location": "HYD/HUB", "instructions": "Shipment declared lost following terminal investigation"},
        ]
        return {
            "success": True,
            "waybill": wb,
            "status": "Lost",
            "history": history,
            "raw_response": {
                "ShipmentData": [
                    {
                        "Shipment": {
                            "AWB": wb,
                            "Status": {
                                "Status": "Lost",
                                "StatusDateTime": "2026-10-03T18:00:00.000Z",
                                "StatusType": "LS",
                                "Instructions": "Shipment declared lost",
                                "StatusLocation": "HYD/HUB",
                            },
                            "Scans": [
                                {"ScanDetail": {"Scan": h["status"], "ScanDateTime": h["timestamp"], "ScannedLocation": h["location"]}}
                                for h in history
                            ],
                        }
                    }
                ]
            },
        }

    # Check state registry first for previously manifested orders
    if wb in state_registry.shipments:
        reg = state_registry.shipments[wb]
        return {
            "success": True,
            "waybill": reg["waybill"],
            "order_id": reg.get("order_id"),
            "status": reg["status"],
            "history": reg["history"],
            "raw_response": reg["raw_response"],
        }

    # Deterministic Lifecycle simulation based on waybill keywords
    wb_upper = wb.upper()
    if "MANIFESTED" in wb_upper or wb == TRIGGER_WAYBILL_MANIFESTED:
        status = "Manifested"
        history = [
            {"status": "Manifested", "timestamp": "2026-10-04T08:00:00Z", "location": "BLR/APL"}
        ]
    elif "READY" in wb_upper or wb == TRIGGER_WAYBILL_READY:
        status = "Ready for Pickup"
        history = [
            {"status": "Manifested", "timestamp": "2026-10-04T08:00:00Z", "location": "BLR/APL"},
            {"status": "Ready for Pickup", "timestamp": "2026-10-04T09:30:00Z", "location": "BLR/APL"}
        ]
    elif "OFD" in wb_upper or "OUT_FOR_DELIVERY" in wb_upper or wb == TRIGGER_WAYBILL_OFD:
        status = "Out for Delivery"
        history = [
            {"status": "Manifested", "timestamp": "2026-10-03T08:00:00Z", "location": "BLR/APL"},
            {"status": "In Transit", "timestamp": "2026-10-03T14:00:00Z", "location": "BOM/HUB"},
            {"status": "Out for Delivery", "timestamp": "2026-10-04T07:30:00Z", "location": "BOM/DC1"}
        ]
    elif "DELIVERED" in wb_upper or wb == TRIGGER_WAYBILL_DELIVERED:
        status = "Delivered"
        history = [
            {"status": "Manifested", "timestamp": "2026-10-02T08:00:00Z", "location": "BLR/APL"},
            {"status": "In Transit", "timestamp": "2026-10-02T16:00:00Z", "location": "BOM/HUB"},
            {"status": "Out for Delivery", "timestamp": "2026-10-03T08:00:00Z", "location": "BOM/DC1"},
            {"status": "Delivered", "timestamp": "2026-10-03T14:45:00Z", "location": "BOM/DC1"}
        ]
    elif "CANCELLED" in wb_upper or "RTO" in wb_upper or wb == TRIGGER_WAYBILL_CANCELLED:
        status = "Cancelled / RTO"
        history = [
            {"status": "Manifested", "timestamp": "2026-10-02T08:00:00Z", "location": "BLR/APL"},
            {"status": "In Transit", "timestamp": "2026-10-02T16:00:00Z", "location": "BOM/HUB"},
            {"status": "Cancelled / RTO", "timestamp": "2026-10-03T10:00:00Z", "location": "BOM/HUB", "instructions": "Consignee cancelled order / Returning to origin"}
        ]
    else:
        # Default standard In Transit lifecycle
        status = "In Transit"
        history = [
            {"status": "Manifested", "timestamp": "2026-10-04T06:00:00Z", "location": "BLR/APL"},
            {"status": "Ready for Pickup", "timestamp": "2026-10-04T08:30:00Z", "location": "BLR/APL"},
            {"status": "In Transit", "timestamp": "2026-10-04T12:00:00Z", "location": "BLR/HUB", "instructions": "Bagged and in transit to sorting center"}
        ]

    return {
        "success": True,
        "waybill": wb,
        "status": status,
        "history": history,
        "raw_response": {
            "ShipmentData": [
                {
                    "Shipment": {
                        "AWB": wb,
                        "Status": {
                            "Status": status,
                            "StatusDateTime": history[-1]["timestamp"],
                            "StatusLocation": history[-1]["location"],
                            "Instructions": history[-1].get("instructions", status),
                        },
                        "Scans": [
                            {"ScanDetail": {"Scan": h["status"], "ScanDateTime": h["timestamp"], "ScannedLocation": h["location"]}}
                            for h in history
                        ],
                    }
                }
            ]
        },
    }


# ==============================================================================
# Tool 4: Pickup Request Creation Logic
# ==============================================================================

def create_pickup_request(
    pickup_location: str,
    pickup_date: str,
    pickup_slot: str,
    shipment_waybills: List[str],
) -> Dict[str, Any]:
    """Create a Delhivery pickup request for manifesting shipments.

    Documented Delhivery endpoint: POST /fm/request/new/

    Supported Pickup Lifecycle States:
    - Scheduled
    - Out for Pickup
    - Picked
    - Cancelled

    Deterministic Scenarios:
    - pickup_location == 'TIMEOUT' or contains 'TIMEOUT' -> Simulated Timeout
    - pickup_location == 'NO-CAPACITY' or contains 'NO-CAPACITY' -> No Capacity Failure
    - pickup_location == 'BAD-RESPONSE' or contains 'BAD-RESPONSE' -> Malformed Upstream Response
    - len(shipment_waybills) == 0 -> Validation Error
    - Otherwise -> Deterministic Successful Pickup Scheduled
    """
    loc = str(pickup_location or "").strip()
    pdate = str(pickup_date or "").strip()
    slot = str(pickup_slot or "").strip()
    waybills = shipment_waybills or []

    # Scenario: Timeout
    if loc == TRIGGER_PICKUP_TIMEOUT or "TIMEOUT" in loc.upper():
        return {
            "success": False,
            "error": "Upstream timeout: POST /fm/request/new/ timed out after 30000ms",
            "error_type": "TIMEOUT",
            "timeout_seconds": 30.0,
            "raw_response": None,
        }

    # Scenario: Malformed Upstream Response
    if loc == TRIGGER_PICKUP_BAD_RESPONSE or "BAD-RESPONSE" in loc.upper():
        return {
            "success": False,
            "error": "Simulated upstream response error: malformed response from Delhivery pickup gateway",
            "error_type": "MALFORMED_RESPONSE",
            "raw_response": "<<INVALID_RESPONSE_HEADER>> 502 Bad Gateway: Upstream Pickup Gateway Disconnected",
        }

    # Scenario: Validation Error (Empty shipment list)
    if not waybills or len(waybills) == 0:
        return {
            "success": False,
            "status": "Validation Failed",
            "error": "Validation error: 'shipment_waybills' cannot be empty. At least one waybill is required to schedule a pickup.",
            "error_type": "VALIDATION_ERROR",
            "raw_response": {
                "pr_id": None,
                "status": "Fail",
                "remarks": ["At least one shipment waybill is required to schedule a pickup"],
            },
        }

    # Scenario: No Pickup Capacity / Slot Unavailable
    if loc == TRIGGER_PICKUP_NO_CAPACITY or "NO-CAPACITY" in loc.upper():
        return {
            "success": False,
            "status": "Unavailable",
            "pickup_location": loc,
            "pickup_date": pdate,
            "pickup_slot": slot,
            "error": f"No pickup capacity available at location '{loc}' for date {pdate} and slot {slot}",
            "error_type": "NO_CAPACITY",
            "raw_response": {
                "pr_id": None,
                "status": "Failed",
                "message": f"No pickup slot/capacity available at center '{loc}' for requested date/time",
            },
        }

    # Determine status (support full pickup lifecycle: Scheduled, Out for Pickup, Picked, Cancelled)
    loc_upper = loc.upper()
    if TRIGGER_PICKUP_PICKED in loc_upper or "PICKED" in loc_upper:
        status = "Picked"
    elif TRIGGER_PICKUP_OUT_FOR_PICKUP in loc_upper or "OUT_FOR_PICKUP" in loc_upper:
        status = "Out for Pickup"
    elif TRIGGER_PICKUP_CANCELLED in loc_upper or "CANCELLED" in loc_upper:
        status = "Cancelled"
    else:
        status = "Scheduled"

    h = _deterministic_hash(f"{loc}:{pdate}:{slot}:{len(waybills)}")
    pickup_request_id = f"PUR-{h % 9000000 + 1000000}"

    pickup_record = {
        "success": True,
        "pickup_request_id": pickup_request_id,
        "status": status,
        "pickup_location": loc,
        "pickup_date": pdate,
        "pickup_slot": slot,
        "package_count": len(waybills),
        "shipment_waybills": waybills,
        "raw_response": {
            "pr_id": pickup_request_id,
            "status": status,
            "pickup_id": h % 1000000,
            "pickup_date": pdate,
            "pickup_time": slot,
            "client": "AGENTIC_ORG",
            "incoming_center_name": f"{loc[:3].upper()}/HUB",
            "package_count": len(waybills),
            "message": "Pickup scheduled successfully",
        },
    }

    state_registry.pickup_requests[pickup_request_id] = pickup_record

    return {
        "success": True,
        "pickup_request_id": pickup_request_id,
        "status": status,
        "pickup_location": loc,
        "pickup_date": pdate,
        "pickup_slot": slot,
        "raw_response": pickup_record["raw_response"],
    }


# ==============================================================================
# Tool 5: Server Health Check Logic
# ==============================================================================

def get_health_status() -> Dict[str, str]:
    """Return health check status for Delhivery Mock MCP."""
    return {
        "status": "ok",
        "service": "Delhivery Mock MCP",
    }
