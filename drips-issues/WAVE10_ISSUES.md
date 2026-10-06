# Drips Wave 10 - StellarPayWall Maintainer Backlog

## Issue #1: [Trivial (100 Points)] Add OpenAPI / FastAPI Metadata Tags & Detailed Docstrings to Paywall Routes
**Target File**: `stellarpaywall/routers/paywall.py`
**Requirements**: Enhance OpenAPI documentation with tags, summary descriptions, and response examples for HTTP 402, 200, and 422 codes.
**Acceptance Criteria**: All endpoints in `paywall.py` display structured documentation at `/docs`, with zero missing query parameter descriptions.

## Issue #2: [Trivial (100 Points)] Implement Exponential Backoff & Retry Logic for Horizon RPC Client
**Target File**: `stellarpaywall/services/horizon_client.py`
**Requirements**: Wrap Horizon HTTP calls with an async retry policy handling 429 (Rate Limit) and 503 errors using `tenacity`.
**Acceptance Criteria**: Client retries up to 4 times with exponential jitter before raising a typed `HorizonConnectionError`. Unit tests verify retry counts.

## Issue #3: [Medium (150 Points)] Build Async Horizon Path Payment & Token Transfer Verifier
**Target File**: `stellarpaywall/services/payment_verifier.py`
**Requirements**: Create an async verification module that verifies payment transactions against source accounts, asset trustlines, and destination addresses.
**Acceptance Criteria**: `verify_payment(tx_hash, expected_amount, destination)` correctly returns `True` for valid Horizon payments and `False` for invalid/unconfirmed transactions.

## Issue #4: [Medium (150 Points)] Develop Redis Nonce Ledger & Replay Prevention Middleware
**Target File**: `stellarpaywall/middleware/replay_guard.py`
**Requirements**: Build Redis caching layer that logs used Stellar transaction hashes with configurable TTLs to prevent transaction replay attacks.
**Acceptance Criteria**: Submitting the same transaction hash twice returns an HTTP 400 'Transaction already spent' error. Test coverage > 95%.

## Issue #5: [Medium (150 Points)] Build Pytest Async Integration Test Suite for Paywall Gateway
**Target File**: `tests/test_paywall_gateway.py`
**Requirements**: Implement comprehensive async pytest suite covering HTTP 402 challenges, valid payment responses, and invalid transaction edge cases.
**Acceptance Criteria**: `pytest` executes cleanly with > 90% code coverage across all core routers and middleware.

## Issue #6: [Medium (150 Points)] Build Next.js Tailwind Merchant API Key & Paywall Analytics Component
**Target File**: `frontend/components/MerchantAnalytics.tsx`
**Requirements**: Create a responsive React component displaying total revenue (XLM/USDC), active API keys, and endpoint call volumes.
**Acceptance Criteria**: Component renders clean Tailwind charts with mock/live API data and zero console warnings.

## Issue #7: [High (200 Points)] Implement HTTP 402 Protocol Negotiator & Dynamic Price Estimator
**Target File**: `stellarpaywall/core/http402.py`
**Requirements**: Develop dynamic pricing logic that calculates endpoint costs based on compute load, payload size, or query complexity.
**Acceptance Criteria**: Middleware attaches dynamic `WWW-Authenticate: Stellar asset="XLM", amount="0.05"` headers based on route decorators.

## Issue #8: [High (200 Points)] Develop Soroban Asset Contract (SAC) Token Payment Verifier
**Target File**: `stellarpaywall/services/soroban_verifier.py`
**Requirements**: Extend payment verifier to validate Soroban smart contract invocations and SAC token transfers via Soroban RPC `getTransaction`.
**Acceptance Criteria**: Gateway successfully verifies SAC USDC transfers on Soroban testnet/mainnet with full event log parsing.

## Issue #9: [High (200 Points)] Develop Multi-Language Client SDK Packages (TypeScript & Python)
**Target File**: `sdks/typescript/` & `sdks/python/`
**Requirements**: Build client SDKs that wrap standard `fetch`/`requests` calls, intercept HTTP 402 responses, auto-sign Stellar payments, and retry transparently.
**Acceptance Criteria**: TypeScript SDK compiles clean `.d.ts` types; Python SDK passes `mypy --strict`. Both publish cleanly to mock registries.

## Issue #10: [High (200 Points)] Implement Automated GitHub Actions CI/CD Pipeline with Coverage Enforcement
**Target File**: `.github/workflows/ci.yml`
**Requirements**: Configure GitHub Actions workflow to run `ruff` linting, `mypy` type checks, and `pytest` with 90% coverage enforcement on push/PR.
**Acceptance Criteria**: CI workflow passes consistently on GitHub, blocking unformatted or untested PRs automatically.
