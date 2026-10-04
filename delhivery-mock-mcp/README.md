# Delhivery Mock MCP Server

A production-ready Python Model Context Protocol (MCP) server providing high-fidelity, deterministic mock implementations of Delhivery Logistics APIs for **The Ken Case Competition / AgenticOrg**.

---

## 📌 Competition Architecture & Compliance

- **Role**: This server acts solely as an external logistics simulation layer. It returns structured logistics facts, standard Delhivery data shapes, and deterministic failure modes.
- **Autonomous Agent**: **AgenticOrg** acts as the autonomous decision-maker consuming these tools.
- **Zero LLM Logic**: This server contains **NO** LLM logic, prompt templates, insurance reasoning, or policy evaluation.
- **No External Calls**: Does **NOT** call real Delhivery production servers.
- **Strictly Deterministic**: No random generators or non-deterministic delays. The same inputs consistently yield the exact same simulation outcomes across all eval runs.

---

## 🛠 Features & Transports

- **Official Python MCP SDK**: Implemented using `FastMCP` (`mcp.server.mcpserver.MCPServer`).
- **Remote SSE Transport**: Full Server-Sent Events (SSE) support (`GET /sse` and `POST /messages`) for remote autonomous agent consumption.
- **Native Health Endpoint**: Dedicated HTTP `GET /health` endpoint for container orchestrators and Render monitoring.
- **CORS & Host Security**: Configurable via `ALLOWED_HOSTS` for deployment on cloud services like Render.

---

## 🚀 Quick Start (Local Setup)

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

---

## ☁️ Render Deployment Configuration

| Setting | Value |
| :--- | :--- |
| **Environment** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python server.py` |
| **Health Check Path** | `/health` |
| **Expected MCP URL** | `https://<service-name>.onrender.com/sse` |

### Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `8000` | Port for HTTP/SSE server (automatically injected by Render) |
| `HOST` | `0.0.0.0` | Host interface to bind |
| `ALLOWED_HOSTS` | `*` | Allowed `Host` headers. Default `*` permits Render dynamic domains |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DELHIVERY_MOCK_AUTH_TOKEN` | *(None)* | Optional token for future authenticated setups |

---

## 🎯 Deterministic Failure Trigger Table

Use these deterministic inputs in AgenticOrg eval cases to trigger exact simulation responses:

| Tool | Field / Parameter | Trigger Value | Simulated Outcome | Response Details |
| :--- | :--- | :--- | :--- | :--- |
| `delhivery_pincode_serviceability` | `pincode` | `"000000"` | **Unserviceable Pincode** | `{"success": true, "serviceable": false, "cod": false, "prepaid": false}` |
| `delhivery_pincode_serviceability` | `pincode` | `"999998"` | **Simulated Timeout** | `{"success": false, "error_type": "TIMEOUT"}` |
| `delhivery_pincode_serviceability` | `pincode` | `"ABC12"` / non-6-digit | **Validation Error** | `{"success": false, "error_type": "VALIDATION_ERROR"}` |
| `delhivery_create_shipment` | `pin` | `"000000"` | **Serviceability Failure** | `{"success": false, "error_type": "UNSERVICEABLE_PINCODE"}` |
| `delhivery_create_shipment` | `order` | `"FAIL-VALIDATION"` | **Validation Error** | `{"success": false, "error_type": "VALIDATION_ERROR"}` |
| `delhivery_create_shipment` | `order` | `"MALFORMED-RESPONSE"`| **Malformed Upstream Payload**| `{"success": false, "error_type": "MALFORMED_RESPONSE", "raw_response": "<html>502...</html>"}` |
| `delhivery_create_shipment` | `order` | `"TIMEOUT-ORDER"` | **Simulated Timeout** | `{"success": false, "error_type": "TIMEOUT"}` |
| `delhivery_track_shipment` | `waybill` | `"NOTFOUND"` | **Shipment Not Found** | `{"success": false, "status": "Not Found", "error_type": "NOT_FOUND"}` |
| `delhivery_track_shipment` | `waybill` | `"TIMEOUT"` | **Simulated Timeout** | `{"success": false, "error_type": "TIMEOUT"}` |
| `delhivery_track_shipment` | `waybill` | `"LOST"` | **Lost Shipment Lifecycle** | `{"success": true, "status": "Lost"}` |
| `delhivery_track_shipment` | `waybill` | `"WB-MANIFESTED"` | **Manifested State** | `{"success": true, "status": "Manifested"}` |
| `delhivery_track_shipment` | `waybill` | `"WB-READY"` | **Ready for Pickup** | `{"success": true, "status": "Ready for Pickup"}` |
| `delhivery_track_shipment` | `waybill` | `"WB-TRANSIT"` | **In Transit State** | `{"success": true, "status": "In Transit"}` |
| `delhivery_track_shipment` | `waybill` | `"WB-OFD"` | **Out for Delivery** | `{"success": true, "status": "Out for Delivery"}` |
| `delhivery_track_shipment` | `waybill` | `"WB-DELIVERED"` | **Delivered State** | `{"success": true, "status": "Delivered"}` |
| `delhivery_track_shipment` | `waybill` | `"WB-CANCELLED"` | **Cancelled / RTO** | `{"success": true, "status": "Cancelled / RTO"}` |
| `delhivery_create_pickup_request` | `pickup_location` | `"NO-CAPACITY"` | **No Pickup Capacity** | `{"success": false, "status": "Unavailable", "error_type": "NO_CAPACITY"}` |
| `delhivery_create_pickup_request` | `pickup_location` | `"TIMEOUT"` | **Simulated Timeout** | `{"success": false, "error_type": "TIMEOUT"}` |
| `delhivery_create_pickup_request` | `pickup_location` | `"BAD-RESPONSE"` | **Malformed Response** | `{"success": false, "error_type": "MALFORMED_RESPONSE"}` |
| `delhivery_create_pickup_request` | `shipment_waybills`| `[]` (empty) | **Validation Error** | `{"success": false, "error_type": "VALIDATION_ERROR"}` |

---

## 📦 MCP Tools Reference

The server exposes 5 tools via MCP:

### 1. `health_check`
No input required.
```json
{
  "status": "ok",
  "service": "Delhivery Mock MCP"
}
```

### 2. `delhivery_pincode_serviceability`
Checks pincode delivery capability (mirrors `GET /c/api/pin-codes/json/?filter_codes={pincode}`).
- **Input**:
  - `pincode` *(string, required)*: 6-digit Indian postal pincode.
- **Example Success Return**:
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
    "state_code": "KA",
    "raw_response": { ... }
  }
  ```

### 3. `delhivery_create_shipment`
Creates a package shipment in Delhivery network (mirrors `POST /api/cmu/create.json`).
- **Required Fields**:
  - `name` *(string)*: Consignee / recipient full name
  - `add` *(string)*: Destination delivery address
  - `pin` *(string)*: 6-digit destination postal code
  - `city` *(string)*: Destination city
  - `state` *(string)*: Destination state
  - `phone` *(string)*: Consignee contact telephone number
  - `order` *(string)*: Unique merchant order ID
- **Optional Fields**:
  - `country` *(string, default "India")*
  - `payment_mode` *(string, default "Prepaid")*: `"Prepaid"` or `"COD"`
  - `return_pin`, `return_city`, `return_phone`, `return_add`, `return_state`, `return_country` *(strings)*
  - `products_desc` *(string, default "Standard Goods")*
  - `hsn_code` *(string)*
  - `cod_amount` *(string, default "0")*
  - `order_date` *(string)*: ISO date/time
  - `total_amount` *(string, default "0.00")*
  - `seller_add`, `seller_name`, `seller_inv` *(strings)*
  - `quantity` *(string, default "1")*
  - `waybill` *(string)*: Pre-allocated AWB number
  - `shipment_width`, `shipment_height` *(string, default "10")*
  - `weight` *(string, default "0.5")*: Dead weight in kg
  - `shipping_mode` *(string, default "Surface")*: `"Surface"` or `"Express"`
  - `address_type` *(string, default "home")*: `"home"` or `"office"`
- **Example Success Return**:
  ```json
  {
    "success": true,
    "waybill": "1282796459805",
    "order_id": "ORD-1001",
    "status": "Manifested",
    "destination_pin": "560038",
    "destination_city": "Bengaluru",
    "payment_mode": "Prepaid",
    "shipping_mode": "Surface",
    "raw_response": {
      "cash_pickups_count": 0,
      "package_count": 1,
      "upload_wbn": "UPL-98421",
      "replacement_count": 0,
      "rmk": "Valid",
      "packages": [
        {
          "status": "Success",
          "client": "AGENTIC_ORG",
          "sort_code": "BEN/KAR",
          "remarks": ["Shipment manifested successfully"],
          "waybill": "1282796459805",
          "cod_amount": 0.0,
          "payment": "Prepaid",
          "serviceable": true,
          "refnum": "ORD-1001"
        }
      ],
      "cash_pickups": 0,
      "cod_count": 0,
      "success": true,
      "prepaid_count": 1
    }
  }
  ```

### 4. `delhivery_track_shipment`
Tracks shipment lifecycle status and checkpoint scans (mirrors `GET /api/v1/packages/json/?waybill={waybill}`).
- **Input**:
  - `waybill` *(string, required)*: Delhivery AWB number.
- **Supported Lifecycle States**:
  - `Manifested`
  - `Ready for Pickup`
  - `In Transit`
  - `Out for Delivery`
  - `Delivered`
  - `Cancelled / RTO`
  - `Lost`
- **Example Success Return**:
  ```json
  {
    "success": true,
    "waybill": "1282796459805",
    "status": "In Transit",
    "history": [
      {
        "status": "Manifested",
        "timestamp": "2026-10-04T06:00:00Z",
        "location": "BLR/APL"
      },
      {
        "status": "Ready for Pickup",
        "timestamp": "2026-10-04T08:30:00Z",
        "location": "BLR/APL"
      },
      {
        "status": "In Transit",
        "timestamp": "2026-10-04T12:00:00Z",
        "location": "BLR/HUB",
        "instructions": "Bagged and in transit to sorting center"
      }
    ],
    "raw_response": { ... }
  }
  ```

### 5. `delhivery_create_pickup_request`
Schedules warehouse pickup for packages (mirrors `POST /fm/request/new/`).
- **Input**:
  - `pickup_location` *(string, required)*: Warehouse facility name
  - `pickup_date` *(string, required)*: Pickup date (`YYYY-MM-DD`)
  - `pickup_slot` *(string, required)*: Window (e.g., `"14:00 - 18:00"`)
  - `shipment_waybills` *(array of strings, required)*: List of AWB waybills
- **Supported Pickup Lifecycle States**:
  - `Scheduled`
  - `Out for Pickup`
  - `Picked`
  - `Cancelled`
- **Example Success Return**:
  ```json
  {
    "success": true,
    "pickup_request_id": "PUR-4829103",
    "status": "Scheduled",
    "pickup_location": "WH-Bengaluru-Main",
    "pickup_date": "2026-10-06",
    "pickup_slot": "14:00 - 18:00",
    "raw_response": {
      "pr_id": "PUR-4829103",
      "status": "Scheduled",
      "pickup_id": 829103,
      "pickup_date": "2026-10-06",
      "pickup_time": "14:00 - 18:00",
      "client": "AGENTIC_ORG",
      "incoming_center_name": "WH-/HUB",
      "package_count": 2,
      "message": "Pickup scheduled successfully"
    }
  }
  ```

---

## 🧪 Running Automated Tests

Run the full test suite covering all 23 scenarios:

```bash
python test_server.py
```

All tests execute synchronously and asynchronously, verifying both in-memory logic and the live HTTP / SSE transport.
