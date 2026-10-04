"""Delhivery Mock MCP Server.

A production-ready Python MCP server providing mock Delhivery logistics tools
for The Ken Case Competition / AgenticOrg simulation.

Endpoints:
- GET  /health   -> HTTP health check for Render / monitoring
- GET  /sse      -> Remote SSE transport for MCP clients
- POST /messages -> MCP JSON-RPC message endpoint

Tools exposed:
- health_check
- delhivery_pincode_serviceability
- delhivery_create_shipment
- delhivery_track_shipment
- delhivery_create_pickup_request
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

import uvicorn
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# MCP Server imports with backward/forward compatibility
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP

from mcp.server.transport_security import TransportSecuritySettings

from mock_rules import (
    check_pincode_serviceability,
    create_pickup_request,
    create_shipment,
    get_health_status,
    track_shipment,
)

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("delhivery-mock-mcp")

# ==============================================================================
# MCP Server Instance
# ==============================================================================

mcp = FastMCP(
    name="Delhivery Mock MCP",
    instructions=(
        "Production-ready Delhivery logistics simulation server for AgenticOrg. "
        "Provides realistic, deterministic mock implementations of Delhivery APIs: "
        "pincode serviceability, package shipment creation, shipment tracking, "
        "and pickup scheduling."
    ),
)


# ==============================================================================
# Tool 1: health_check
# ==============================================================================

@mcp.tool()
def health_check() -> Dict[str, str]:
    """Check health status of the Delhivery Mock MCP server."""
    logger.debug("Executing health_check tool")
    return get_health_status()


# ==============================================================================
# Tool 2: delhivery_pincode_serviceability
# ==============================================================================

@mcp.tool()
def delhivery_pincode_serviceability(pincode: str) -> Dict[str, Any]:
    """Check whether a destination pincode is serviceable by Delhivery for Prepaid, COD, and Reverse Pickup.

    Mirrors documented endpoint: GET /c/api/pin-codes/json/?filter_codes={pincode}

    Args:
        pincode: 6-digit Indian postal code to check (e.g. '560001', '110001', '400001').
    """
    logger.info("Checking pincode serviceability for: %s", pincode)
    return check_pincode_serviceability(pincode=pincode)


# ==============================================================================
# Tool 3: delhivery_create_shipment
# ==============================================================================

@mcp.tool()
def delhivery_create_shipment(
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

    Mirrors documented endpoint: POST /api/cmu/create.json

    Required Fields:
        name: Consignee / recipient full name
        add: Consignee destination delivery address
        pin: Destination 6-digit postal pincode
        city: Destination city name
        state: Destination state name
        phone: Consignee contact telephone number
        order: Merchant unique order reference ID

    Optional Fields:
        country: Destination country (default 'India')
        payment_mode: Payment type: 'Prepaid' or 'COD' (default 'Prepaid')
        return_pin: Return warehouse 6-digit pincode in case of RTO
        return_city: Return warehouse city
        return_phone: Return contact telephone
        return_add: Return warehouse full address
        return_state: Return warehouse state
        return_country: Return warehouse country (default 'India')
        products_desc: Description of package products (default 'Standard Goods')
        hsn_code: Harmonized System of Nomenclature code
        cod_amount: Cash-on-delivery amount to collect (default '0')
        order_date: Order placement ISO date/time string
        total_amount: Total declared invoice amount (default '0.00')
        seller_add: Registered seller warehouse address
        seller_name: Registered seller trade name
        seller_inv: Merchant invoice number
        quantity: Number of product pieces (default '1')
        waybill: Pre-allocated AWB waybill number if available
        shipment_width: Package width in cm (default '10')
        shipment_height: Package height in cm (default '10')
        weight: Package gross dead weight in kg (default '0.5')
        shipping_mode: Shipping mode: 'Surface' or 'Express' (default 'Surface')
        address_type: Destination address classification: 'home' or 'office' (default 'home')
    """
    logger.info("Creating shipment for order: %s, pin: %s (POST /api/cmu/create.json)", order, pin)
    return create_shipment(
        name=name,
        add=add,
        pin=pin,
        city=city,
        state=state,
        phone=phone,
        order=order,
        country=country,
        payment_mode=payment_mode,
        return_pin=return_pin,
        return_city=return_city,
        return_phone=return_phone,
        return_add=return_add,
        return_state=return_state,
        return_country=return_country,
        products_desc=products_desc,
        hsn_code=hsn_code,
        cod_amount=cod_amount,
        order_date=order_date,
        total_amount=total_amount,
        seller_add=seller_add,
        seller_name=seller_name,
        seller_inv=seller_inv,
        quantity=quantity,
        waybill=waybill,
        shipment_width=shipment_width,
        shipment_height=shipment_height,
        weight=weight,
        shipping_mode=shipping_mode,
        address_type=address_type,
    )


# ==============================================================================
# Tool 4: delhivery_track_shipment
# ==============================================================================

@mcp.tool()
def delhivery_track_shipment(waybill: str) -> Dict[str, Any]:
    """Track shipment lifecycle status and checkpoint scan history by Delhivery waybill number.

    Mirrors documented endpoint: GET /api/v1/packages/json/?waybill={waybill}

    Supported Lifecycle States:
        Manifested, Ready for Pickup, In Transit, Out for Delivery,
        Delivered, Cancelled / RTO, Lost.

    Args:
        waybill: 13-digit Delhivery AWB waybill tracking number or test trigger.
    """
    logger.info("Tracking shipment for waybill: %s (GET /api/v1/packages/json/)", waybill)
    return track_shipment(waybill=waybill)


# ==============================================================================
# Tool 5: delhivery_create_pickup_request
# ==============================================================================

@mcp.tool()
def delhivery_create_pickup_request(
    pickup_location: str,
    pickup_date: str,
    pickup_slot: str,
    shipment_waybills: List[str],
) -> Dict[str, Any]:
    """Create a Delhivery pickup request for manifesting shipments.

    Mirrors documented endpoint: POST /fm/request/new/

    Supported Pickup Lifecycle States:
        Scheduled, Out for Pickup, Picked, Cancelled.

    Args:
        pickup_location: Registered pickup warehouse/facility location name (Required)
        pickup_date: Scheduled pickup date in YYYY-MM-DD format (Required)
        pickup_slot: Preferred pickup window slot (e.g. '14:00 - 18:00') (Required)
        shipment_waybills: List of Delhivery waybills to be handed over (Required)
    """
    logger.info("Creating pickup request at '%s' on %s (POST /fm/request/new/)", pickup_location, pickup_date)
    return create_pickup_request(
        pickup_location=pickup_location,
        pickup_date=pickup_date,
        pickup_slot=pickup_slot,
        shipment_waybills=shipment_waybills,
    )


# ==============================================================================
# HTTP Endpoints (Starlette / Render Health Check)
# ==============================================================================

@mcp.custom_route("/health", methods=["GET"])
async def http_health_endpoint(request: Request) -> JSONResponse:
    """HTTP GET /health endpoint for Render health checks and container monitoring."""
    return JSONResponse(get_health_status(), status_code=200)


# Extensible Authentication Hook
# In this simulation server, authentication is not enforced by default.
# If DELHIVERY_AUTH_KEY is set in the environment, you can enable token validation:
AUTH_TOKEN = os.environ.get("DELHIVERY_MOCK_AUTH_TOKEN")


# ==============================================================================
# Application Factory
# ==============================================================================

def create_app() -> Any:
    """Create and configure the Starlette application with MCP SSE transport."""
    allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "*").strip()

    # Configure DNS rebinding / host validation protection
    if allowed_hosts_env == "*" or not allowed_hosts_env:
        # Allow all hosts (standard for cloud environments like Render with dynamic routing)
        transport_sec = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
            allowed_hosts=[],
            allowed_origins=[],
        )
    else:
        # Restrict to specified hosts
        raw_hosts = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
        expanded_hosts: List[str] = []
        expanded_origins: List[str] = []
        for h in raw_hosts:
            expanded_hosts.append(h)
            if not h.endswith(":*") and ":" not in h:
                expanded_hosts.append(f"{h}:*")
            expanded_origins.extend([f"http://{h}", f"https://{h}", f"http://{h}:*", f"https://{h}:*"])

        transport_sec = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=expanded_hosts,
            allowed_origins=expanded_origins,
        )

    # Build Starlette app using FastMCP's built-in SSE app generator
    app = mcp.sse_app(transport_security=transport_sec)

    # Add CORS middleware for browser-based inspection or AgenticOrg UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


# ==============================================================================
# Server Entrypoint
# ==============================================================================

def main() -> None:
    """Start the Uvicorn web server."""
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info("Starting Delhivery Mock MCP server on %s:%d", host, port)
    logger.info("Endpoints available:")
    logger.info("  - Health Check: http://%s:%d/health", host, port)
    logger.info("  - MCP SSE Transport: http://%s:%d/sse", host, port)
    logger.info("  - MCP Messages: http://%s:%d/messages", host, port)

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
