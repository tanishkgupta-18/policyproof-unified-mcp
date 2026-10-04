"""PolicyProof Unified MCP Server.

A production-ready FastMCP server unifying insurance policy evidence retrieval,
Gnani speech processing (STT & TTS), and Delhivery logistics simulation for AgenticOrg.

Architecture:
- Single MCP Server Instance: 'PolicyProof Unified MCP'
- Tool Gateway Only: No LLM logic, no autonomous decisions, no policy recommendations.
- Transports: Remote SSE transport (/sse, /messages) and HTTP Health check (/health).

Exposed Tools (Exactly 8):
1. health_check
2. search_policy_evidence
3. gnani_speech_to_text
4. gnani_text_to_speech
5. delhivery_pincode_serviceability
6. delhivery_create_shipment
7. delhivery_track_shipment
8. delhivery_create_pickup_request
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except (ImportError, ModuleNotFoundError):
    pass

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("policyproof-unified-mcp")

# MCP Server imports with backward/forward compatibility (mcp 2.x and 1.x)
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP  # type: ignore

try:
    from mcp.server.transport_security import TransportSecuritySettings
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.sse import TransportSecuritySettings  # type: ignore
    except (ImportError, ModuleNotFoundError):
        TransportSecuritySettings = None  # type: ignore

# Import tool handlers from modular tools package
from tools.delhivery_tools import (
    delhivery_create_pickup_request as _delhivery_create_pickup_request,
    delhivery_create_shipment as _delhivery_create_shipment,
    delhivery_pincode_serviceability as _delhivery_pincode_serviceability,
    delhivery_track_shipment as _delhivery_track_shipment,
)
from tools.gnani_tools import (
    get_stt_api_key,
    get_tts_api_key,
    gnani_speech_to_text as _gnani_speech_to_text,
    gnani_text_to_speech as _gnani_text_to_speech,
    mask_key,
)
from tools.policy_tools import (
    search_policy_evidence as _search_policy_evidence,
)

# ==============================================================================
# Unified MCP Server Instance
# ==============================================================================

SERVICE_NAME = "PolicyProof Unified MCP"

mcp = FastMCP(
    name=SERVICE_NAME,
    instructions=(
        "Production-ready unified tool gateway for AgenticOrg. "
        "Provides insurance policy evidence retrieval, Gnani speech transcription (STT) "
        "and synthesis (TTS), and Delhivery logistics lifecycle management."
    ),
)


# ==============================================================================
# Tool 1: health_check
# ==============================================================================

@mcp.tool(
    name="health_check",
    description="Check the operational health status of the PolicyProof Unified MCP service.",
)
def health_check() -> Dict[str, str]:
    """MCP health check tool returning server status and service name."""
    logger.debug("Executing health_check tool")
    return {
        "status": "ok",
        "service": SERVICE_NAME,
    }


# ==============================================================================
# Tool 2: search_policy_evidence
# ==============================================================================

@mcp.tool(
    name="search_policy_evidence",
    description=(
        "Searches the policy evidence store for citations, pages, and excerpts matching "
        "a specific policy ID and query terms. Returns factual evidence excerpts only."
    ),
)
def search_policy_evidence(policy_id: str, query: str) -> Dict[str, Any]:
    """Search policy evidence records for a given policy ID and query terms.

    Args:
        policy_id: The unique identifier of the policy (e.g. 'POL-HDFC-TEST', 'POL-CARE-TEST').
        query: Keywords or question phrase to match within policy evidence excerpts.

    Returns:
        Structured dictionary with policy_id, query, and matching factual results.
    """
    logger.info("Searching policy evidence for policy_id='%s', query='%s'", policy_id, query)
    return _search_policy_evidence(policy_id=policy_id, query=query)


# ==============================================================================
# Tool 3: gnani_speech_to_text
# ==============================================================================

@mcp.tool(
    name="gnani_speech_to_text",
    description=(
        "Transcribe audio using Gnani's real Speech-to-Text (STT) API (https://api.vachana.ai/stt/v3). "
        "Decodes base64-encoded audio and returns a structured transcription response."
    ),
)
async def gnani_speech_to_text(
    audio_base64: str,
    filename: str = "audio.wav",
    language_code: str = "en-IN",
    preferred_language: str = "en-IN",
    format: str = "transcribe",
    itn_native_numerals: bool = True,
) -> Dict[str, Any]:
    """Transcribe audio bytes using Gnani Vachana STT v3 API.

    Args:
        audio_base64: Base64-encoded audio data string.
        filename: Name of the audio file (default: 'audio.wav').
        language_code: Target language code (default: 'en-IN').
        preferred_language: Preferred spoken language code (default: 'en-IN').
        format: Transcription format mode (default: 'transcribe').
        itn_native_numerals: Inverse text normalization for native numerals (default: True).

    Returns:
        Structured dictionary with success status, request_id, timestamp, transcript,
        and raw response or error details.
    """
    logger.info("Invoking Gnani STT API (lang=%s, format=%s)", language_code, format)
    return await _gnani_speech_to_text(
        audio_base64=audio_base64,
        filename=filename,
        language_code=language_code,
        preferred_language=preferred_language,
        format=format,
        itn_native_numerals=itn_native_numerals,
    )


# ==============================================================================
# Tool 4: gnani_text_to_speech
# ==============================================================================

@mcp.tool(
    name="gnani_text_to_speech",
    description=(
        "Synthesize speech from text using Gnani's real Text-to-Speech (TTS) API (https://api.vachana.ai/api/v1/tts/inference). "
        "Returns synthesized audio as base64 without writing permanently to disk."
    ),
)
async def gnani_text_to_speech(
    text: str,
    language: str = "en-IN",
    voice: str = "Nalini",
    speed: float = 1.0,
    sample_rate: int = 48000,
) -> Dict[str, Any]:
    """Convert text into speech using Gnani TTS API.

    Args:
        text: Text string to synthesize into speech.
        language: Language code (default: 'en-IN').
        voice: Voice name (default: 'Nalini').
        speed: Playback speed multiplier (default: 1.0, range 0.85 - 1.15).
        sample_rate: Audio sample rate in Hz (default: 48000).

    Returns:
        Structured dictionary with success status, base64-encoded audio,
        content_type, sample_rate, and raw metadata or error details.
    """
    logger.info("Invoking Gnani TTS API (lang=%s, voice=%s, text_len=%d)", language, voice, len(text))
    return await _gnani_text_to_speech(
        text=text,
        language=language,
        voice=voice,
        speed=speed,
        sample_rate=sample_rate,
    )


# ==============================================================================
# Tool 5: delhivery_pincode_serviceability
# ==============================================================================

@mcp.tool(
    name="delhivery_pincode_serviceability",
    description=(
        "Check whether a destination pincode is serviceable by Delhivery for Prepaid, COD, and Reverse Pickup. "
        "Mirrors GET /c/api/pin-codes/json/?filter_codes={pincode}."
    ),
)
def delhivery_pincode_serviceability(pincode: str) -> Dict[str, Any]:
    """Check whether a destination pincode is serviceable by Delhivery.

    Args:
        pincode: 6-digit Indian postal code to check (e.g. '560001', '110001', '400001').
    """
    return _delhivery_pincode_serviceability(pincode=pincode)


# ==============================================================================
# Tool 6: delhivery_create_shipment
# ==============================================================================

@mcp.tool(
    name="delhivery_create_shipment",
    description=(
        "Create a package shipment in Delhivery network. "
        "Mirrors POST /api/cmu/create.json."
    ),
)
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

    Required Fields:
        name: Consignee / recipient full name
        add: Consignee destination delivery address
        pin: Destination 6-digit postal pincode
        city: Destination city name
        state: Destination state name
        phone: Consignee contact telephone number
        order: Merchant unique order reference ID
    """
    return _delhivery_create_shipment(
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
# Tool 7: delhivery_track_shipment
# ==============================================================================

@mcp.tool(
    name="delhivery_track_shipment",
    description=(
        "Track shipment lifecycle status and checkpoint scan history by Delhivery waybill number. "
        "Mirrors GET /api/v1/packages/json/?waybill={waybill}."
    ),
)
def delhivery_track_shipment(waybill: str) -> Dict[str, Any]:
    """Track shipment lifecycle status and checkpoint scan history by Delhivery waybill number.

    Args:
        waybill: 13-digit Delhivery AWB waybill tracking number or test trigger.
    """
    return _delhivery_track_shipment(waybill=waybill)


# ==============================================================================
# Tool 8: delhivery_create_pickup_request
# ==============================================================================

@mcp.tool(
    name="delhivery_create_pickup_request",
    description=(
        "Create a Delhivery pickup request for manifesting shipments. "
        "Mirrors POST /fm/request/new/."
    ),
)
def delhivery_create_pickup_request(
    pickup_location: str,
    pickup_date: str,
    pickup_slot: str,
    shipment_waybills: List[str],
) -> Dict[str, Any]:
    """Create a Delhivery pickup request for manifesting shipments.

    Args:
        pickup_location: Registered pickup warehouse/facility location name (Required)
        pickup_date: Scheduled pickup date in YYYY-MM-DD format (Required)
        pickup_slot: Preferred pickup window slot (e.g. '14:00 - 18:00') (Required)
        shipment_waybills: List of Delhivery waybills to be handed over (Required)
    """
    return _delhivery_create_pickup_request(
        pickup_location=pickup_location,
        pickup_date=pickup_date,
        pickup_slot=pickup_slot,
        shipment_waybills=shipment_waybills,
    )


# ==============================================================================
# HTTP Route: /health
# ==============================================================================

@mcp.custom_route("/health", methods=["GET"])
async def http_health_endpoint(request: Request) -> JSONResponse:
    """HTTP GET /health endpoint for Render health checks and container monitoring."""
    return JSONResponse({
        "status": "ok",
        "service": SERVICE_NAME,
    }, status_code=200)


# ==============================================================================
# Application Factory
# ==============================================================================

def create_app() -> Any:
    """Build and configure the production Starlette ASGI app with MCP SSE transport."""
    allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "*").strip()

    if TransportSecuritySettings is not None:
        if allowed_hosts_env == "*" or not allowed_hosts_env:
            # Allow all hosts (standard for cloud environments like Render with dynamic routing)
            transport_sec = TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
                allowed_hosts=[],
                allowed_origins=[],
            )
            logger.info("Host security: DNS rebinding protection disabled (ALLOWED_HOSTS='*')")
        else:
            raw_hosts = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
            expanded_hosts: List[str] = []
            expanded_origins: List[str] = []
            for h in raw_hosts:
                expanded_hosts.append(h)
                if not h.endswith(":*") and ":" not in h:
                    expanded_hosts.append(f"{h}:*")
                expanded_origins.extend([f"http://{h}", f"https://{h}", f"http://{h}:*", f"https://{h}:*"])

            # Always include localhost and loopback for local development and tests
            for local in ("localhost", "127.0.0.1", "[::1]", "0.0.0.0"):
                if local not in expanded_hosts:
                    expanded_hosts.extend([local, f"{local}:*"])
                    expanded_origins.extend([f"http://{local}", f"http://{local}:*", f"https://{local}:*"])

            # Also incorporate ALLOWED_ORIGINS if configured
            env_origins = os.environ.get("ALLOWED_ORIGINS")
            if env_origins:
                for orig in env_origins.split(","):
                    orig = orig.strip()
                    if orig and orig not in expanded_origins:
                        expanded_origins.append(orig)

            transport_sec = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=expanded_hosts,
                allowed_origins=expanded_origins,
            )
            logger.info(f"Host security: DNS rebinding enabled with allowed hosts: {expanded_hosts}")

        app = mcp.sse_app(transport_security=transport_sec)
    else:
        app = mcp.sse_app()

    # Add CORS middleware for browser-based inspection or AgenticOrg UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


# Module-level ASGI app for ASGI runners (uvicorn unified.server:app)
app = create_app()


# ==============================================================================
# Server Entrypoint
# ==============================================================================

def main() -> None:
    """Start the PolicyProof Unified MCP server via Uvicorn."""
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")

    print("==================================================")
    print("           PolicyProof Unified MCP Server         ")
    print("==================================================")
    print(f" Service:              {SERVICE_NAME}")
    print(f" Binding:              http://{host}:{port}")
    print(f" Health Check URL:     http://{host}:{port}/health")
    print(f" MCP SSE Endpoint:     http://{host}:{port}/sse")
    print(f" MCP Messages:         http://{host}:{port}/messages/")
    print(f" STT API Key:          {mask_key(get_stt_api_key())}")
    print(f" TTS API Key:          {mask_key(get_tts_api_key())}")
    print(f" Allowed Hosts:        {os.environ.get('ALLOWED_HOSTS', '*')}")
    print("==================================================")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
