# PolicyProof Unified MCP Server

Production-ready Model Context Protocol (MCP) server for **AgenticOrg** unifying insurance policy evidence retrieval, Gnani speech intelligence (STT & TTS), and Delhivery logistics execution under a single, unified namespace.

---

## 1. Project Purpose & Architectural Rationale

AgenticOrg's multi-MCP connector previously encountered namespace resolution bugs when communicating across separate microservices for policy evidence, speech APIs, and logistics.

**PolicyProof Unified MCP** resolves this by consolidating all tools onto **ONE single FastMCP instance** operating over HTTP/SSE transport.

### Critical Architectural Boundaries
- **Tool Gateway Only**: This MCP server strictly exposes execution capabilities and factual data retrieval.
- **No LLM or Autonomous Reasoning**: The server contains **NO LLM calls**, **NO autonomous reasoning**, and makes **NO insurance/logistics decisions**.
- **AgenticOrg Decision-Making**: The AgenticOrg orchestrator retains 100% authority for all policy evaluations, claim approvals, comparative determinations, and next-action workflows.

---

## 2. Exposed MCP Tools (Exactly 8)

The unified server registers and exposes exactly 8 production-grade MCP tools:

| # | Tool Name | Domain | Description |
|---|---|---|---|
| 1 | `health_check` | System | Checks server operational health and service identification. |
| 2 | `search_policy_evidence` | PolicyProof | Retrieves factual policy citations, pages, and excerpts from JSON store. |
| 3 | `gnani_speech_to_text` | Gnani AI | Transcribes audio via real Gnani STT REST API (`https://api.vachana.ai/stt/v3`). |
| 4 | `gnani_text_to_speech` | Gnani AI | Synthesizes speech via real Gnani TTS REST API (`https://api.vachana.ai/api/v1/tts/inference`). |
| 5 | `delhivery_pincode_serviceability` | Delhivery | Checks destination pincode serviceability for Prepaid, COD, and Reverse Pickup. |
| 6 | `delhivery_create_shipment` | Delhivery | Manifests packages and books shipments in Delhivery logistics network. |
| 7 | `delhivery_track_shipment` | Delhivery | Tracks parcel lifecycle status and checkpoint scan histories by AWB waybill. |
| 8 | `delhivery_create_pickup_request` | Delhivery | Schedules warehouse pickup appointments for manifested shipments. |

---

## 3. Tool Specifications & Schemas

### 1. `health_check`
- **Inputs**: None (`{}`)
- **Output**:
  ```json
  {
    "status": "ok",
    "service": "PolicyProof Unified MCP"
  }
  ```

### 2. `search_policy_evidence`
- **Inputs**:
  - `policy_id` (string, required): e.g. `"POL-HDFC-TEST"`, `"POL-CARE-TEST"`
  - `query` (string, required): e.g. `"pre-existing disease waiting period"`, `"co-pay"`
- **Output**:
  ```json
  {
    "policy_id": "POL-HDFC-TEST",
    "query": "pre-existing disease waiting period",
    "results": [
      {
        "source": "[TEST DATA] Policy wording",
        "page": 14,
        "excerpt": "[TEST DATA] Pre-existing diseases are subject to a 36-month waiting period.",
        "source_url": "https://example.com/test-data/hdfc.pdf#page=14"
      }
    ]
  }
  ```

### 3. `gnani_speech_to_text` (Audited per https://docs.gnani.ai/)
- **Official Endpoint**: `POST https://api.vachana.ai/stt/v3`
- **Auth Header**: `X-API-Key-ID: <GNANI_STT_API_KEY>`
- **Content-Type**: `multipart/form-data`
- **Inputs**:
  - `audio_base64` (string, required): Base64-encoded audio bytes (WAV, MP3, OGG, FLAC)
  - `filename` (string, default: `"audio.wav"`)
  - `language_code` (string, default: `"en-IN"`)
  - `preferred_language` (string, default: `"en-IN"`)
  - `format` (string, default: `"transcribe"`)
  - `itn_native_numerals` (boolean, default: `true`)
- **Output (Success)**:
  ```json
  {
    "success": true,
    "service": "gnani_stt",
    "request_id": "req-12345",
    "timestamp": "2026-10-04T19:30:00Z",
    "transcript": "Transcribed text from real Gnani STT API",
    "raw_response": { ... }
  }
  ```
- **Output (Missing Credentials)**:
  ```json
  {
    "success": false,
    "error_type": "missing_credentials",
    "service": "gnani_stt",
    "message": "GNANI_STT_API_KEY environment variable is not configured. Please set GNANI_STT_API_KEY."
  }
  ```

### 4. `gnani_text_to_speech` (Audited per https://docs.gnani.ai/)
- **Official Endpoint**: `POST https://api.vachana.ai/api/v1/tts/inference`
- **Auth Header**: `X-API-Key-ID: <GNANI_TTS_API_KEY>`
- **Content-Type**: `application/json`
- **Official Model**: `timbre-v2.5`
- **Inputs**:
  - `text` (string, required): Text to synthesize
  - `language` (string, default: `"en-IN"`)
  - `voice` (string, default: `"Nalini"`)
  - `speed` (float, default: `1.0`, range `0.85` - `1.15`)
  - `sample_rate` (integer, default: `48000`)
- **Payload Schema**:
  ```json
  {
    "text": "Hello from PolicyProof.",
    "model": "timbre-v2.5",
    "voice": "Nalini",
    "language": "en-IN",
    "speed": 1.0,
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "container": "wav",
      "num_channels": 1,
      "sample_width": 2
    }
  }
  ```
- **Output (Success)**:
  ```json
  {
    "success": true,
    "service": "gnani_tts",
    "audio_base64": "<base64-encoded-audio>",
    "content_type": "audio/wav",
    "sample_rate": 48000,
    "raw_metadata": { ... }
  }
  ```
- **Output (Missing Credentials)**:
  ```json
  {
    "success": false,
    "error_type": "missing_credentials",
    "service": "gnani_tts",
    "message": "GNANI_TTS_API_KEY environment variable is not configured. Please set GNANI_TTS_API_KEY."
  }
  ```

### 5. `delhivery_pincode_serviceability`
- **Inputs**:
  - `pincode` (string, required): 6-digit postal code (e.g. `"560001"`)
- **Output**:
  ```json
  {
    "success": true,
    "pincode": "560001",
    "serviceable": true,
    "cod": true,
    "prepaid": true,
    "reverse_pickup": true,
    "sort_code": "BLR/APL",
    "city": "Bengaluru",
    "state_code": "KA"
  }
  ```

### 6. `delhivery_create_shipment`
- **Inputs**:
  - `name`, `add`, `pin`, `city`, `state`, `phone`, `order` (required)
  - `country`, `payment_mode`, `return_*`, `products_desc`, `hsn_code`, `cod_amount`, `order_date`, `total_amount`, `seller_*`, `quantity`, `waybill`, `shipment_width`, `shipment_height`, `weight`, `shipping_mode`, `address_type` (optional)
- **Output**:
  ```json
  {
    "success": true,
    "waybill": "1282796459805",
    "order_id": "ORD-1001",
    "status": "Manifested",
    "destination_pin": "560038",
    "destination_city": "Bengaluru",
    "payment_mode": "Prepaid",
    "shipping_mode": "Surface"
  }
  ```

### 7. `delhivery_track_shipment`
- **Inputs**:
  - `waybill` (string, required): 13-digit AWB or deterministic trigger
- **Output**:
  ```json
  {
    "success": true,
    "waybill": "1282796459805",
    "status": "In Transit",
    "history": [
      { "status": "Manifested", "timestamp": "...", "location": "BLR/APL" },
      { "status": "Ready for Pickup", "timestamp": "...", "location": "BLR/APL" },
      { "status": "In Transit", "timestamp": "...", "location": "BLR/HUB" }
    ]
  }
  ```

### 8. `delhivery_create_pickup_request`
- **Inputs**:
  - `pickup_location` (string, required)
  - `pickup_date` (string, required, YYYY-MM-DD)
  - `pickup_slot` (string, required, e.g. `"14:00 - 18:00"`)
  - `shipment_waybills` (array of strings, required)
- **Output**:
  ```json
  {
    "success": true,
    "pickup_request_id": "PUR-5892104",
    "status": "Scheduled",
    "pickup_location": "WH-Bengaluru-Main",
    "pickup_date": "2026-10-06",
    "pickup_slot": "14:00 - 18:00"
  }
  ```

---

## 4. Local Setup & Execution

### 1. Create and Activate Virtual Environment

```bash
# Navigate to unified project directory
cd policyproof-unified-mcp/unified

# Create Python virtual environment
python -m venv .venv

# Activate on Windows (PowerShell / Command Prompt):
.venv\Scripts\activate

# Activate on Linux / macOS:
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy template
cp .env.example .env
```

### 4. Run the Server

```bash
python server.py
```

Server starts on `http://0.0.0.0:8000`.

### 5. Run Automated Verification Tests

```bash
# Full server and MCP tests
python test_server.py

# Direct Gnani live diagnostics (non-MCP)
python test_gnani_live.py
```

---

## 5. Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `GNANI_STT_API_KEY` | None | API Key for Gnani Speech-to-Text (`X-API-Key-ID`) |
| `GNANI_TTS_API_KEY` | None | API Key for Gnani Text-to-Speech (`X-API-Key-ID`) |
| `HOST` | `0.0.0.0` | Host IP binding |
| `PORT` | `8000` | Port binding |
| `ALLOWED_HOSTS` | `*` | Comma-separated list of allowed host header patterns |
| `ALLOWED_ORIGINS` | None | Comma-separated list of allowed CORS / SSE origins |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 6. Render / Cloud Deployment

- **Environment**: Python 3.11+
- **Root Directory**: `policyproof-unified-mcp/unified`
- **Build Command**:
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```bash
  python server.py
  ```
- **Health Check Path**: `/health`
- **MCP SSE Transport Path**: `/sse`

---

## 7. Delhivery Deterministic Simulation Triggers

| Domain | Trigger Value | Behavior |
|---|---|---|
| **Pincode Serviceability** | `560001` | Serviceable (Prepaid, COD, Reverse Pickup) |
| | `000000` or `000*` | Unserviceable |
| | `999998` or `*TIMEOUT*` | Simulated Upstream Timeout |
| | Non-6-digit / non-numeric | Validation Error |
| **Shipment Creation** | Normal fields | Manifested with deterministic 13-digit AWB `128...` |
| | `pin="000000"` | Destination Unserviceable Failure |
| | `order="FAIL-VALIDATION"` | Validation Failure |
| | `order="TIMEOUT-ORDER"` | Simulated Upstream Timeout |
| | `order="MALFORMED-RESPONSE"`| Malformed Upstream Gateway Response |
| **Tracking** | Normal AWB | Standard Lifecycle / Checkpoint scans |
| | `waybill="NOTFOUND"` | 404 Shipment Not Found |
| | `waybill="TIMEOUT"` | Simulated Upstream Timeout |
| | `waybill="LOST"` | Lost Status |
| | `WB-MANIFESTED`, `WB-READY`, `WB-TRANSIT`, `WB-OFD`, `WB-DELIVERED`, `WB-CANCELLED` | Deterministic specific lifecycle stage |
| **Pickup Request** | Normal fields | Scheduled with deterministic ID `PUR-...` |
| | `pickup_location="NO-CAPACITY"` | No Pickup Capacity / Unavailable |
| | `pickup_location="TIMEOUT"` | Simulated Upstream Timeout |
| | `pickup_location="BAD-RESPONSE"` | Malformed Upstream Response |
| | `shipment_waybills=[]` | Validation Error (empty list) |

---

## 8. Gnani Real API Integration & Audited Behavior

- **STT Endpoint**: `POST https://api.vachana.ai/stt/v3`
- **TTS Endpoint**: `POST https://api.vachana.ai/api/v1/tts/inference`
- **Authentication**: `X-API-Key-ID: <API_KEY>`
- **TTS Model**: `timbre-v2.5` with structured `audio_config`
- **Missing Credentials Resilience**: If `GNANI_STT_API_KEY` or `GNANI_TTS_API_KEY` are unset, server starts normally, MCP discovery succeeds, and calling tools returns structured `error_type: "missing_credentials"` responses.
- **Direct Live Diagnostics**: `python test_gnani_live.py` executes standalone tests to separate upstream credentials issues from MCP protocol issues.

---

## 9. Policy Evidence Store Behavior

- Structured local test evidence store located at `evidence/policies.json`.
- Supports test policy datasets:
  - `POL-HDFC-TEST`: HDFC ERGO Optima Secure (e.g. 36-month waiting period, room rent, restoration).
  - `POL-CARE-TEST`: Care Supreme (e.g. 24-month waiting period, 10% co-pay, single private room).
- Pure factual retrieval with citations, page numbers, and source excerpts without LLM reasoning.
