"""Direct Live Test Script for Gnani STT & TTS APIs (Without MCP).

Tests direct HTTP communication to Gnani endpoints to isolate:
- Upstream Gnani API status / credentials validity
- Network connectivity / DNS resolution
- Local wrapper logic vs MCP layer

Does NOT expose credentials in output logs.
"""

from __future__ import annotations

import base64
import io
import math
import os
from pathlib import Path
import struct
import sys
import time
import wave

import httpx

# Ensure local imports work when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.gnani_tools import (
    GNANI_HTTP_TIMEOUT,
    GNANI_STT_URL,
    GNANI_TTS_URL,
    get_credentials_status,
    get_stt_api_key,
    get_tts_api_key,
    mask_key,
)


def generate_test_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate in-memory mono PCM WAV audio bytes for testing."""
    wav_buffer = io.BytesIO()
    num_samples = int(duration_seconds * sample_rate)
    frequency = 440.0

    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        samples = []
        for i in range(num_samples):
            value = int(16000 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            samples.append(struct.pack("<h", value))
        wf.writeframes(b"".join(samples))

    return wav_buffer.getvalue()


def test_live_tts() -> bool:
    """Perform direct live test against official Gnani TTS inference endpoint."""
    print("\n--------------------------------------------------")
    print(" [1/2] Live Gnani TTS API Test")
    print("--------------------------------------------------")

    api_key = get_tts_api_key()
    if not api_key:
        print("  SKIPPED - missing credentials (GNANI_TTS_API_KEY is not configured)")
        return False

    text_to_speak = "Hello from PolicyProof."
    payload = {
        "text": text_to_speak,
        "model": "timbre-v2.5",
        "voice": "Nalini",
        "language": "en-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
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

    print(f"  Endpoint:      POST {GNANI_TTS_URL}")
    print(f"  Auth Header:   X-API-Key-ID: {mask_key(api_key)}")
    print(f"  Input Text:    '{text_to_speak}'")
    print(f"  Model/Voice:   timbre-v2.5 / Nalini (en-IN)")

    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=GNANI_HTTP_TIMEOUT) as client:
            response = client.post(GNANI_TTS_URL, json=payload, headers=headers)
        elapsed = time.perf_counter() - start_time

        print(f"  HTTP Status:   {response.status_code}")
        print(f"  Content-Type:  {response.headers.get('content-type', 'unknown')}")
        print(f"  Response Size: {len(response.content)} bytes")
        print(f"  Elapsed Time:  {elapsed:.3f}s")

        if 200 <= response.status_code < 300 and len(response.content) > 0:
            output_file = Path(__file__).resolve().parent / "test_tts_output.wav"
            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"  SUCCESS: Audio saved to {output_file.name} ({len(response.content)} bytes)")
            return True
        else:
            print(f"  FAILURE: Upstream response: {response.text[:300]}")
            return False

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"  ERROR ({elapsed:.3f}s): {type(e).__name__} - {e}")
        return False


def test_live_stt() -> bool:
    """Perform direct live test against official Gnani STT endpoint."""
    print("\n--------------------------------------------------")
    print(" [2/2] Live Gnani STT API Test")
    print("--------------------------------------------------")

    api_key = get_stt_api_key()
    if not api_key:
        print("  SKIPPED - missing credentials (GNANI_STT_API_KEY is not configured)")
        return False

    # Check if a recorded test audio file exists or generate synthetic wav
    wav_bytes = generate_test_wav(0.5, 16000)
    files = {
        "audio_file": ("test_sample.wav", wav_bytes, "audio/wav"),
    }
    data = {
        "language_code": "en-IN",
        "preferred_language": "en-IN",
        "format": "transcribe",
        "itn_native_numerals": "true",
    }
    headers = {
        "X-API-Key-ID": api_key,
    }

    print(f"  Endpoint:      POST {GNANI_STT_URL}")
    print(f"  Auth Header:   X-API-Key-ID: {mask_key(api_key)}")
    print(f"  Audio Payload: test_sample.wav ({len(wav_bytes)} bytes)")
    print(f"  Language:      en-IN")

    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=GNANI_HTTP_TIMEOUT) as client:
            response = client.post(GNANI_STT_URL, files=files, data=data, headers=headers)
        elapsed = time.perf_counter() - start_time

        print(f"  HTTP Status:   {response.status_code}")
        print(f"  Content-Type:  {response.headers.get('content-type', 'unknown')}")
        print(f"  Response Size: {len(response.content)} bytes")
        print(f"  Elapsed Time:  {elapsed:.3f}s")

        if 200 <= response.status_code < 300:
            try:
                resp_json = response.json()
                print(f"  SUCCESS: Transcript received: {resp_json.get('transcript') or resp_json}")
            except Exception:
                print(f"  SUCCESS: Raw response: {response.text[:200]}")
            return True
        else:
            print(f"  FAILURE: Upstream response: {response.text[:300]}")
            return False

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"  ERROR ({elapsed:.3f}s): {type(e).__name__} - {e}")
        return False


def main():
    print("==================================================")
    print("       Direct Gnani Live API Diagnostics          ")
    print("==================================================")

    cred_status = get_credentials_status()
    print(" Credentials Diagnostic:")
    print(f"  - GNANI_STT_API_KEY configured: {cred_status['GNANI_STT_API_KEY_configured']}")
    print(f"  - GNANI_TTS_API_KEY configured: {cred_status['GNANI_TTS_API_KEY_configured']}")

    tts_ok = test_live_tts()
    stt_ok = test_live_stt()

    print("\n==================================================")
    print(" Summary:")
    print(f"  - TTS Result: {'PASSED' if tts_ok else ('SKIPPED' if not cred_status['GNANI_TTS_API_KEY_configured'] else 'FAILED')}")
    print(f"  - STT Result: {'PASSED' if stt_ok else ('SKIPPED' if not cred_status['GNANI_STT_API_KEY_configured'] else 'FAILED')}")
    print("==================================================")


if __name__ == "__main__":
    main()
