# API Reference Guide 📖

StellarPayWall provides RESTful endpoints documented via OpenAPI 3.1 and Swagger UI.

Interactive API Documentation:
- **Swagger UI**: [https://stellarpaywall.onrender.com/docs](https://stellarpaywall.onrender.com/docs)
- **ReDoc**: [https://stellarpaywall.onrender.com/redoc](https://stellarpaywall.onrender.com/redoc)
- **OpenAPI JSON**: [https://stellarpaywall.onrender.com/openapi.json](https://stellarpaywall.onrender.com/openapi.json)

---

## 📌 Endpoint Summary

| Path | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | No | Serves the Merchant Analytics Dashboard |
| `/dashboard` | `GET` | No | Direct route to Merchant Dashboard |
| `/health` | `GET` | No | Health check probe for gateway uptime |
| `/protected-resource` | `GET` | **HTTP 402** | Sample monetized endpoint requiring Stellar micropayment |
| `/verify-payment` | `POST` | No | Explicit verification endpoint for transaction hashes |

---

## 🔍 Endpoint Details

### 1. Health Check
```http
GET /health HTTP/1.1
Host: stellarpaywall.onrender.com
```

#### Response (`200 OK`)
```json
{
  "status": "ok"
}
```

---

### 2. Protected Resource (Monetized)
```http
GET /protected-resource HTTP/1.1
Host: stellarpaywall.onrender.com
X-PayWall-Tx-Hash: <TRANSACTION_HASH>
X-PayWall-Challenge-UUID: <CHALLENGE_UUID>
```

#### Unpaid Response (`402 Payment Required`)
```http
HTTP/1.1 402 Payment Required
WWW-Authenticate: Stellar asset="XLM", amount="0.05", destination="merchant_address", challenge="b3a9c2..."
X-PayWall-Amount: 0.05
X-PayWall-Asset: XLM
X-PayWall-Destination: merchant_address
X-PayWall-Challenge-UUID: b3a9c2...
X-PayWall-Expires-In: 300
Content-Type: application/json

{
  "detail": "Payment Required"
}
```

#### Success Response (`200 OK`)
```json
{
  "message": "Premium content accessed successfully."
}
```

#### Replayed Transaction Response (`400 Bad Request`)
```json
{
  "detail": "Transaction already spent"
}
```

---

### 3. Explicit Payment Verification
```http
POST /verify-payment?tx_hash=4b29f0e1c2a8d3e... HTTP/1.1
Host: stellarpaywall.onrender.com
```

#### Response (`200 OK`)
```json
{
  "status": "verified",
  "tx_hash": "4b29f0e1c2a8d3e..."
}
```

---

## 🛡️ Standard Error Codes

| Status Code | Reason | Resolution |
| :--- | :--- | :--- |
| `400 Bad Request` | Transaction already spent or invalid hash format | Generate a new transaction with a fresh challenge UUID. |
| `402 Payment Required` | Challenge issued, underpayment, or invalid memo | Sign and submit an on-chain transaction matching the challenge requirements. |
| `500 Internal Server Error` | Transient RPC or network failure | Retry request using exponential backoff. |
