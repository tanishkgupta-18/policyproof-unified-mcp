"""Gnani Speech-to-Text and Text-to-Speech Tools for PolicyProof Unified MCP.

Audited and aligned with official Gnani API specifications (https://docs.gnani.ai/):
- Official STT REST Endpoint: POST https://api.vachana.ai/stt/v3
- Official TTS REST Endpoint: POST https://api.vachana.ai/api/v1/tts/inference
- Official Auth Header: X-API-Key-ID: <API_KEY>
- Official TTS Model: timbre-v2.5 with audio_config (sample_rate, encoding, container, num_channels, sample_width)
- Returns structured errors with specific failure classes (DNS, timeout, auth, 4xx, 5xx).
- Missing credentials return clean, structured error responses without crashing the server.
- Contains NO LLM reasoning and NEVER invents/fakes transcripts or audio data.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import logging
import os
import socket
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import uuid

import httpx

logger = logging.getLogger("policyproof-unified-mcp.gnani_tools")

# Official Production Gnani API Endpoints (per https://docs.gnani.ai/)
GNANI_STT_URL = "https://api.vachana.ai/stt/v3"
GNANI_TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

# Explicit client timeout configuration
GNANI_HTTP_TIMEOUT = httpx.Timeout(
    connect=10.0,  # 10s connection timeout
    read=30.0,     # 30s read timeout
    write=10.0,    # 10s write timeout
    pool=5.0,      # 5s pool timeout
)


def get_stt_api_key() -> Optional[str]:
    """Retrieve Gnani STT API Key from environment."""
    key = os.environ.get("GNANI_STT_API_KEY") or os.environ.get("GNANI_API_KEY")
    return key.strip() if key else None


def get_tts_api_key() -> Optional[str]:
    """Retrieve Gnani TTS API Key from environment."""
    key = os.environ.get("GNANI_TTS_API_KEY") or os.environ.get("GNANI_API_KEY")
    return key.strip() if key else None


def mask_key(key: Optional[str]) -> str:
    """Safely mask key for display without exposing credentials."""
    if not key:
        return "[NOT CONFIGURED]"
    if len(key) <= 6:
        return "******"
    return f"{key[:3]}...{key[-3:]}"


def get_credentials_status() -> Dict[str, bool]:
    """Safe diagnostic helper reporting credential configuration status without leaking keys."""
    return {
        "GNANI_STT_API_KEY_configured": bool(get_stt_api_key()),
        "GNANI_TTS_API_KEY_configured": bool(get_tts_api_key()),
    }


def _classify_network_exception(e: Exception, service: str, endpoint: str) -> Dict[str, Any]:
    """Classify httpx / network exceptions into distinct structured error payloads."""
    parsed = urlparse(endpoint)
    hostname = parsed.hostname or "api.vachana.ai"

    if isinstance(e, httpx.ConnectTimeout):
        logger.error(f"[{service}] Connect timeout after 10s to {hostname}")
        return {
            "success": False,
            "error_type": "connect_timeout",
            "service": service,
            "status_code": 504,
            "message": f"Connection to {hostname} timed out during TCP/TLS handshake.",
            "raw_response": {"detail": str(e)},
        }

    if isinstance(e, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        logger.error(f"[{service}] Read/Write timeout from {hostname}")
        return {
            "success": False,
            "error_type": "upstream_timeout",
            "service": service,
            "status_code": 504,
            "message": f"Upstream service {hostname} timed out while processing request.",
            "raw_response": {"detail": str(e)},
        }

    if isinstance(e, httpx.ConnectError):
        # Check if root cause is DNS resolution error
        err_str = str(e).lower()
        if "getaddrinfo" in err_str or "name or service not known" in err_str or "nodename nor servname provided" in err_str:
            logger.error(f"[{service}] DNS resolution failure for host: {hostname}")
            return {
                "success": False,
                "error_type": "dns_resolution_failure",
                "service": service,
                "status_code": 502,
                "message": f"DNS resolution failed for hostname '{hostname}'. Check internet connectivity and endpoint configuration.",
                "raw_response": {"detail": str(e), "target_host": hostname},
            }
        logger.error(f"[{service}] Connection refused or failed to connect to {hostname}: {e}")
        return {
            "success": False,
            "error_type": "connection_failure",
            "service": service,
            "status_code": 502,
            "message": f"Failed to establish network connection to {hostname}: {e}",
            "raw_response": {"detail": str(e)},
        }

    logger.error(f"[{service}] Request error: {e}")
    return {
        "success": False,
        "error_type": "network_error",
        "service": service,
        "status_code": None,
        "message": f"Network communication failure with {hostname}: {e}",
        "raw_response": {"detail": str(e)},
    }


# ==============================================================================
# Tool 1: gnani_speech_to_text (Audited against https://docs.gnani.ai/)
# ==============================================================================
async def gnani_speech_to_text(
    audio_base64: str,
    filename: str = "audio.wav",
    language_code: str = "en-IN",
    preferred_language: str = "en-IN",
    format: str = "transcribe",
    itn_native_numerals: bool = True,
) -> Dict[str, Any]:
    """Transcribe audio using Gnani's official REST Speech-to-Text (STT) API (POST https://api.vachana.ai/stt/v3).

    Official Specification:
    - Endpoint: POST https://api.vachana.ai/stt/v3
    - Header: X-API-Key-ID: <API_KEY>
    - Content-Type: multipart/form-data
    - Fields: audio_file (file bytes), language_code, preferred_language, format, itn_native_numerals

    Args:
        audio_base64: Base64-encoded audio data string.
        filename: Name of the audio file (default: 'audio.wav').
        language_code: Target BCP-47 language code (default: 'en-IN').
        preferred_language: Preferred spoken language code (default: 'en-IN').
        format: Transcription format mode (default: 'transcribe').
        itn_native_numerals: Inverse text normalization for native numerals (default: True).

    Returns:
        Structured dictionary with success status, request_id, timestamp, transcript,
        and raw response or error details.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    service_name = "gnani_stt"

    # 1. Validate credentials
    api_key = get_stt_api_key()
    if not api_key:
        logger.warning(f"[{service_name}] Invoked without GNANI_STT_API_KEY configured")
        return {
            "success": False,
            "error_type": "missing_credentials",
            "service": service_name,
            "message": "GNANI_STT_API_KEY environment variable is not configured. Please set GNANI_STT_API_KEY.",
            "request_id": None,
            "timestamp": now_iso,
            "transcript": None,
            "raw_response": {"detail": "Missing GNANI_STT_API_KEY environment variable"},
        }

    # 2. Decode base64 audio
    clean_base64 = audio_base64.strip()
    if "," in clean_base64 and clean_base64.startswith("data:"):
        clean_base64 = clean_base64.split(",", 1)[1]

    try:
        audio_bytes = base64.b64decode(clean_base64)
        if len(audio_bytes) == 0:
            raise ValueError("Decoded audio payload is 0 bytes")
    except Exception as e:
        logger.error(f"[{service_name}] Failed to decode base64 audio: {e}")
        return {
            "success": False,
            "error_type": "invalid_audio_input",
            "service": service_name,
            "status_code": 400,
            "message": f"Invalid base64 audio data: {e}",
            "request_id": None,
            "timestamp": now_iso,
            "transcript": None,
            "raw_response": {"detail": str(e)},
        }

    # 3. Prepare multipart/form-data payload per official docs
    mime_type = "audio/wav"
    lower_fn = (filename or "").lower()
    if lower_fn.endswith(".mp3"):
        mime_type = "audio/mpeg"
    elif lower_fn.endswith(".ogg"):
        mime_type = "audio/ogg"
    elif lower_fn.endswith(".flac"):
        mime_type = "audio/flac"

    files = {
        "audio_file": (filename or "audio.wav", audio_bytes, mime_type),
    }
    data = {
        "language_code": language_code,
        "preferred_language": preferred_language,
        "format": format,
        "itn_native_numerals": "true" if itn_native_numerals else "false",
    }
    headers = {
        "X-API-Key-ID": api_key,
    }

    # 4. Invoke Official Gnani STT API with safe logging and metrics
    logger.info(f"[{service_name}] Sending STT request to {GNANI_STT_URL} (lang={language_code}, size={len(audio_bytes)} bytes)")
    start_time = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=GNANI_HTTP_TIMEOUT) as client:
            response = await client.post(
                GNANI_STT_URL,
                files=files,
                data=data,
                headers=headers,
            )
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(f"[{service_name}] Request failed after {elapsed:.2f}s: {type(e).__name__} - {e}")
        err_result = _classify_network_exception(e, service_name, GNANI_STT_URL)
        err_result["request_id"] = None
        err_result["timestamp"] = now_iso
        err_result["transcript"] = None
        return err_result

    elapsed = time.perf_counter() - start_time
    status_code = response.status_code
    resp_content_type = response.headers.get("content-type", "")
    resp_size = len(response.content)

    logger.info(
        f"[{service_name}] Response received in {elapsed:.2f}s | HTTP {status_code} | "
        f"Content-Type: {resp_content_type} | Size: {resp_size} bytes"
    )

    # 5. Parse response
    try:
        raw_response = response.json()
    except Exception:
        raw_response = {"raw_text": response.text[:2000]}

    request_id = (
        (raw_response.get("request_id") if isinstance(raw_response, dict) else None)
        or (raw_response.get("requestId") if isinstance(raw_response, dict) else None)
        or response.headers.get("x-request-id")
        or str(uuid.uuid4())
    )
    resp_timestamp = (
        (raw_response.get("timestamp") if isinstance(raw_response, dict) else None)
        or (raw_response.get("time") if isinstance(raw_response, dict) else None)
        or now_iso
    )

    if 200 <= status_code < 300:
        # Check if Gnani returned an application-level error inside 2xx
        if isinstance(raw_response, dict) and raw_response.get("success") is False:
            err_msg = raw_response.get("error") or raw_response.get("message") or "STT API reported failure"
            return {
                "success": False,
                "error_type": "api_error",
                "service": service_name,
                "status_code": status_code,
                "message": str(err_msg),
                "request_id": request_id,
                "timestamp": resp_timestamp,
                "transcript": None,
                "raw_response": raw_response,
            }

        # Extract transcript without hallucinating or faking
        transcript = ""
        if isinstance(raw_response, dict):
            if "transcript" in raw_response and isinstance(raw_response["transcript"], str):
                transcript = raw_response["transcript"]
            elif "transcription" in raw_response and isinstance(raw_response["transcription"], str):
                transcript = raw_response["transcription"]
            elif "text" in raw_response and isinstance(raw_response["text"], str):
                transcript = raw_response["text"]
            elif "data" in raw_response and isinstance(raw_response["data"], dict):
                transcript = (
                    raw_response["data"].get("transcript")
                    or raw_response["data"].get("transcription")
                    or raw_response["data"].get("text")
                    or ""
                )
            elif "results" in raw_response:
                transcript = str(raw_response["results"])

        return {
            "success": True,
            "service": service_name,
            "request_id": str(request_id),
            "timestamp": str(resp_timestamp),
            "transcript": transcript,
            "raw_response": raw_response,
        }

    # Error classification for HTTP >= 400
    if status_code in (401, 403):
        error_type = "authentication_error"
    elif status_code == 400:
        error_type = "bad_request"
    elif status_code == 404:
        error_type = "not_found"
    elif status_code == 422:
        error_type = "validation_error"
    elif status_code == 429:
        error_type = "rate_limited"
    elif status_code in (502, 503):
        error_type = "upstream_service_unavailable"
    elif status_code == 504:
        error_type = "upstream_timeout"
    else:
        error_type = f"http_error_{status_code}"

    error_msg = f"Gnani STT API failed with HTTP {status_code}: {error_type}"
    if isinstance(raw_response, dict):
        detail = raw_response.get("message") or raw_response.get("error") or raw_response.get("detail")
        if detail:
            error_msg = f"{error_msg} - {detail}"

    logger.error(f"[{service_name}] STT failed: {error_msg}")
    return {
        "success": False,
        "error_type": error_type,
        "service": service_name,
        "status_code": status_code,
        "message": error_msg,
        "request_id": str(request_id),
        "timestamp": str(resp_timestamp),
        "transcript": None,
        "raw_response": raw_response,
    }


# ==============================================================================
# Tool 2: gnani_text_to_speech (Audited against https://docs.gnani.ai/)
# ==============================================================================
async def gnani_text_to_speech(
    text: str,
    language: str = "en-IN",
    voice: str = "Nalini",
    speed: float = 1.0,
    sample_rate: int = 48000,
) -> Dict[str, Any]:
    """Synthesize speech from text using Gnani's official REST Text-to-Speech (TTS) API (POST https://api.vachana.ai/api/v1/tts/inference).

    Official Specification:
    - Endpoint: POST https://api.vachana.ai/api/v1/tts/inference
    - Header: X-API-Key-ID: <API_KEY>
    - Content-Type: application/json
    - Request Body Schema:
      {
        "text": string,
        "model": "timbre-v2.5",
        "voice": string (e.g. "Nalini", "Arjun", "Yashvi"),
        "language": string (e.g. "en-IN", "hi-IN"),
        "speed": float (0.85 - 1.15),
        "audio_config": {
          "sample_rate": int (8000, 16000, 22050, 24000, 44100, 48000),
          "encoding": "linear_pcm",
          "container": "wav",
          "num_channels": 1,
          "sample_width": 2
        }
      }
    - Success Response: Raw binary audio bytes (audio/wav or application/octet-stream)
    - Error Response: JSON {"success": false, "error": {"type": "...", "message": "..."}}

    Args:
        text: Text string to synthesize.
        language: Language code (default: 'en-IN').
        voice: Voice name (default: 'Nalini').
        speed: Playback speed multiplier (default: 1.0, range 0.85 - 1.15).
        sample_rate: Audio sample rate in Hz (default: 48000).

    Returns:
        Structured dictionary with success status, base64-encoded audio,
        content_type, sample_rate, and raw metadata or error details.
    """
    service_name = "gnani_tts"

    # 1. Validate credentials
    api_key = get_tts_api_key()
    if not api_key:
        logger.warning(f"[{service_name}] Invoked without GNANI_TTS_API_KEY configured")
        return {
            "success": False,
            "error_type": "missing_credentials",
            "service": service_name,
            "message": "GNANI_TTS_API_KEY environment variable is not configured. Please set GNANI_TTS_API_KEY.",
            "raw_metadata": {"detail": "Missing GNANI_TTS_API_KEY environment variable"},
        }

    # 2. Validate input text
    clean_text = (text or "").strip()
    if not clean_text:
        return {
            "success": False,
            "error_type": "validation_error",
            "service": service_name,
            "status_code": 400,
            "message": "Input text cannot be empty for text-to-speech synthesis.",
            "raw_metadata": {"detail": "Empty text provided"},
        }

    # Clamp speed to valid documented range
    clamped_speed = max(0.85, min(1.15, float(speed)))

    # 3. Construct official payload matching timbre-v2.5 documentation
    payload = {
        "text": clean_text,
        "model": "timbre-v2.5",
        "voice": voice or "Nalini",
        "language": language or "en-IN",
        "speed": clamped_speed,
        "audio_config": {
            "sample_rate": sample_rate,
            "encoding": "linear_pcm",
            "container": "wav",
            "num_channels": 1,
            "sample_width": 2,
        },
    }
    headers = {
        "X-API-Key-ID": api_key,
        "Content-Type": "application/json",
    }

    # 4. Invoke Official Gnani TTS API with safe logging and metrics
    logger.info(
        f"[{service_name}] Sending TTS request to {GNANI_TTS_URL} (model=timbre-v2.5, voice={voice}, "
        f"lang={language}, text_len={len(clean_text)})"
    )
    start_time = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=GNANI_HTTP_TIMEOUT) as client:
            response = await client.post(
                GNANI_TTS_URL,
                json=payload,
                headers=headers,
            )
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(f"[{service_name}] Request failed after {elapsed:.2f}s: {type(e).__name__} - {e}")
        return _classify_network_exception(e, service_name, GNANI_TTS_URL)

    elapsed = time.perf_counter() - start_time
    status_code = response.status_code
    content_type_header = response.headers.get("content-type", "").lower()
    resp_size = len(response.content)

    logger.info(
        f"[{service_name}] Response received in {elapsed:.2f}s | HTTP {status_code} | "
        f"Content-Type: {content_type_header} | Size: {resp_size} bytes"
    )

    if 200 <= status_code < 300:
        # Success returns raw binary audio data
        if "audio" in content_type_header or "octet-stream" in content_type_header or resp_size > 0:
            audio_bytes = response.content
            if len(audio_bytes) == 0:
                return {
                    "success": False,
                    "error_type": "empty_audio",
                    "service": service_name,
                    "status_code": status_code,
                    "message": "Gnani TTS API returned 200 OK but the audio stream was 0 bytes.",
                    "raw_metadata": {"headers": dict(response.headers)},
                }
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            return {
                "success": True,
                "service": service_name,
                "audio_base64": audio_base64,
                "content_type": response.headers.get("content-type", "audio/wav"),
                "sample_rate": sample_rate,
                "raw_metadata": {
                    "size_bytes": len(audio_bytes),
                    "model": "timbre-v2.5",
                    "voice": voice,
                    "language": language,
                    "headers": {k: v for k, v in response.headers.items() if k.lower() != "x-api-key-id"},
                },
            }

        # Status 200 with unexpected empty response
        return {
            "success": False,
            "error_type": "missing_audio_payload",
            "service": service_name,
            "status_code": status_code,
            "message": "Gnani TTS API returned 200 OK but no audio stream was received.",
            "raw_metadata": {"headers": dict(response.headers)},
        }

    # Error handling for HTTP >= 400
    if status_code in (401, 403):
        error_type = "authentication_error"
    elif status_code == 400:
        error_type = "bad_request"
    elif status_code == 404:
        error_type = "not_found"
    elif status_code == 422:
        error_type = "validation_error"
    elif status_code == 429:
        error_type = "rate_limited"
    elif status_code in (502, 503):
        error_type = "upstream_service_unavailable"
    elif status_code == 504:
        error_type = "upstream_timeout"
    else:
        error_type = f"http_error_{status_code}"

    try:
        raw_metadata = response.json()
    except Exception:
        raw_metadata = {"raw_text": response.text[:2000]}

    error_msg = f"Gnani TTS API failed with HTTP {status_code}: {error_type}"
    if isinstance(raw_metadata, dict):
        detail = raw_metadata.get("message") or raw_metadata.get("error") or raw_metadata.get("detail")
        if detail:
            error_msg = f"{error_msg} - {detail}"

    logger.error(f"[{service_name}] TTS failed: {error_msg}")
    return {
        "success": False,
        "error_type": error_type,
        "service": service_name,
        "status_code": status_code,
        "message": error_msg,
        "raw_metadata": raw_metadata,
    }
