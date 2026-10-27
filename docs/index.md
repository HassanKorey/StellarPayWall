# StellarPayWall ⚡

> **High-Throughput HTTP 402 Micropayment API Gateway powered by Stellar & Soroban smart contracts.**

[![CI Build](https://github.com/HassanKorey/StellarPayWall-app/actions/workflows/ci.yml/badge.svg)](https://github.com/HassanKorey/StellarPayWall-app/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/HassanKorey/StellarPayWall-app/blob/main/LICENSE)
[![Stellar Testnet](https://img.shields.io/badge/Stellar-Testnet-success.svg)](https://stellar.expert/explorer/testnet/contract/CA4L7T6R74G3T5F5V7V7RWWUHE2J76Y4WJ3L7C2WJ3L7C2WJ3L7C2WJ3)
[![Soroban SDK v21.0.0](https://img.shields.io/badge/Soroban%20SDK-v21.0.0-blue.svg)](https://soroban.stellar.org)

📖 **Documentation Portal**: [https://HassanKorey.github.io/StellarPayWall-app](https://HassanKorey.github.io/StellarPayWall-app)  
🚀 **Live Merchant Gateway**: [https://stellarpaywall.onrender.com](https://stellarpaywall.onrender.com)  
📚 **Interactive API Docs (Swagger UI)**: [https://stellarpaywall.onrender.com/docs](https://stellarpaywall.onrender.com/docs)  
🩺 **System Health Check**: [https://stellarpaywall.onrender.com/health](https://stellarpaywall.onrender.com/health)

---

## 🌟 Overview

**StellarPayWall** is an open-source, production-ready micropayment API gateway implementing the standard `HTTP 402 Payment Required` protocol over the **Stellar Network** and **Soroban smart contracts**.

It empowers API developers, data providers, and autonomous AI agents (such as LangChain and CrewAI agents) to monetize digital endpoints on a trustless, pay-per-request basis with fractions of a cent per call and sub-5-second finality.

### Key Capabilities
- **Native HTTP 402 Handshake**: Automatically challenges unauthorized API calls with RFC-compliant `WWW-Authenticate` payment instructions.
- **Dual Verification Engines**: Verifies both native Stellar Horizon payments (XLM) and Soroban Asset Contract (SAC / SEP-41 USDC/XLM) token transfers.
- **Atomic Anti-Replay Nonce Ledger**: Built with SQLite WAL journaling and Redis caching, featuring configurable TTL locks to eliminate double-spend race conditions.
- **Dynamic Pricing Engine**: Calculates per-endpoint price tiers based on resource complexity and load.
- **Modern SDKs**: Client libraries for Python and TypeScript/Node.js with automatic 402 response interception and seamless transaction signing.
- **Next.js Merchant Dashboard**: Real-time telemetry, revenue monitoring, and API key management.

---

## 🚀 Quick Start

### 1. Make an Unauthenticated Request
```bash
curl -i https://stellarpaywall.onrender.com/protected-resource
```

### 2. Receive HTTP 402 Challenge
```http
HTTP/1.1 402 Payment Required
WWW-Authenticate: Stellar asset="XLM", amount="0.05", destination="merchant_address", challenge="a4b3c2d1-..."
X-PayWall-Amount: 0.05
X-PayWall-Asset: XLM
X-PayWall-Destination: merchant_address
X-PayWall-Challenge-UUID: a4b3c2d1-...
X-PayWall-Expires-In: 300
```

### 3. Settle On-Chain & Access Resource
Submit a Stellar payment transaction with the challenge UUID set as the transaction `MEMO_TEXT`:
```bash
curl -i https://stellarpaywall.onrender.com/protected-resource \
  -H "X-PayWall-Tx-Hash: <YOUR_STELLAR_TRANSACTION_HASH>" \
  -H "X-PayWall-Challenge-UUID: a4b3c2d1-..."
```
Response:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"message": "Premium content accessed successfully."}
```
