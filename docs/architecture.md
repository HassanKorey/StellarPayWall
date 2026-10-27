# System Architecture 🏛️

StellarPayWall is designed for high throughput, sub-second latency, and uncompromising cryptographic security. It bridges standard RESTful HTTP clients and autonomous AI agents with the high-speed Stellar blockchain and Soroban smart contract runtime.

---

## 📐 High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Clients["Consumers & Autonomous Agents"]
        Agent["Autonomous AI Agent (LangChain / CrewAI)"]
        WebBrowser["Web App / dApp Consumer"]
        PyClient["Python Client SDK"]
        TSClient["TypeScript / Node.js SDK"]
    end

    subgraph Gateway["StellarPayWall Gateway (FastAPI Core)"]
        Middleware["HTTP 402 Middleware\n(Intercepts request & checks headers)"]
        ReplayGuard["Replay Guard Middleware\n(Checks in-flight & spent hashes)"]
        
        subgraph CoreServices["Internal Gateway Services"]
            DynamicPrice["Dynamic Pricing Engine"]
            HorizonVerifier["Horizon Payment Verifier"]
            SorobanVerifier["Soroban SAC Event Verifier"]
        end
        
        subgraph LedgerLayer["Anti-Replay Nonce Ledger"]
            Mutex["Asyncio Key-Level Mutex"]
            Storage["SQLite (WAL) / Redis Backend\n(TTL Auto-Expiration)"]
        end
    end

    subgraph StellarNetwork["Stellar Distributed Ledger"]
        HorizonNode["Stellar Horizon RPC Node"]
        SorobanRPC["Soroban RPC getTransaction Endpoint"]
        PaywallVault["paywall_vault Smart Contract\n(SEP-41 Soroban Asset Contract)"]
    end

    Clients -->|1. Initial Request (Unpaid)| Middleware
    Middleware -->|2. Returns 402 + Challenge UUID| Clients
    Clients -->|3. Submits Micropayment Tx| StellarNetwork
    Clients -->|4. Retries Request + Tx Hash| Middleware

    Middleware --> ReplayGuard
    ReplayGuard --> Mutex
    Mutex --> Storage

    Middleware --> HorizonVerifier
    Middleware --> SorobanVerifier

    HorizonVerifier --> HorizonNode
    SorobanVerifier --> SorobanRPC
    SorobanRPC --> PaywallVault

    Storage -->|Verified Nonce Stored with TTL| Middleware
    Middleware -->|5. Grants 200 OK + Payload| Clients
```

---

## 🗂️ Dual-Repository Workspace Split

Following the **Stellar Wave Builder Maintainer Playbook**, StellarPayWall is architecturally divided into two specialized workspaces:

### 1. `HassanKorey/StellarPayWall-contract`
- **Language**: `#![no_std]` Rust with `soroban-sdk` v21.0.0.
- **Components**:
  - `paywall_vault`: Smart contract handling SAC (USDC/XLM) deposit escrow, merchant claims, and `PaymentVerified` event emission.
  - Verification getters: `get_admin`, `get_token`, `get_payment_status`, and `verify_payment_memo`.
  - Comprehensive unit test suite with mock auths and asset contracts (`cargo test`).

### 2. `HassanKorey/StellarPayWall-app`
- **Language & Frameworks**: Python 3.12 (FastAPI, Uvicorn, Pydantic v2), Next.js 14, Tailwind CSS.
- **Components**:
  - `stellarpaywall/middleware/`: ASGI middleware for HTTP 402 challenge negotiation and replay protection.
  - `stellarpaywall/services/`: Horizon RPC client with exponential backoff and Soroban RPC `getTransaction` event parser for SEP-41 token transfers.
  - `stellarpaywall/ledger.py`: Nonce ledger featuring atomic key-level locks, SQLite WAL journaling, Redis distributed caching, and TTL auto-expiration.
  - `frontend/`: Next.js merchant dashboard for revenue metrics and API key controls.
  - `sdks/`: Python and TypeScript SDKs.
  - `docs/`: MkDocs documentation portal deployed to GitHub Pages.

---

## 🛡️ Nonce Ledger & Replay Prevention

Transaction replay attacks represent the primary vulnerability in HTTP micropayment architectures. StellarPayWall mitigates this via a three-tier defense:

1. **In-Flight Mutex (`asyncio.Lock`)**:
   When a request arrives with an `X-PayWall-Tx-Hash`, the ledger locks that specific hash key. Concurrent requests attempting to use the same hash simultaneously are serialized and blocked.
2. **Atomic Ledger Commitment**:
   Transactions are recorded inside an atomic database transaction. If an attacker attempts to reuse an existing hash, the SQLite `UNIQUE(tx_hash)` constraint or Redis `SETNX` immediately aborts the verification.
3. **Configurable TTL Rent / Expiration**:
   Nonces expire after a configurable TTL (default: 3600 seconds), ensuring database pruning while maintaining complete double-spend resistance during the challenge validity window.
