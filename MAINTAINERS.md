# Project Maintainers & Governance

This document outlines the maintainers, domain responsibilities, and review governance for `HassanKorey/StellarPayWall`.

---

## 👥 Core Maintainers

| Name / GitHub Handle | Role | Domain Responsibilities |
| :--- | :--- | :--- |
| **Hassan Akorede Edun** ([@HassanKorey](https://github.com/HassanKorey) / [@hedun](https://github.com/hedun)) | **Lead Maintainer & Architect** | Core architecture, Soroban contracts, security model, and production releases |
| **Stellar Protocol Maintainer** | **Co-Maintainer** | HTTP 402 middleware, Horizon RPC client, dynamic pricing, and SAC token verification |
| **Smart Contracts & Vault Maintainer** | **Co-Maintainer** | Soroban Rust SDK (`paywall_vault`), contract auditing, and on-chain event schemas |
| **Client SDKs & Tooling Maintainer** | **Co-Maintainer** | Python & TypeScript SDKs, autonomous agent adapters (LangChain/CrewAI), and merchant UI |
| **Quality & Security Maintainer** | **Co-Maintainer** | Pytest security vectors, anti-replay ledgers, TTL pruning, and CI/CD coverage enforcement |

---

## 📋 Review & Pull Request Policy

To maintain high code quality, security standards, and rapid development cycles:

1. **Pull Request Reviews**:
   - Every Pull Request requires at least **one approving review** from a maintainer prior to merge.
   - Core protocol, cryptographic, or ledger modifications require review by the **Lead Maintainer** or designated security maintainer.
2. **CI/CD Checks**:
   - All automated GitHub Actions workflows (Ruff linting, Pytest test suite, Cargo tests, Cargo Clippy) must pass cleanly.
3. **Branching & Commit Standard**:
   - Contributions must follow Conventional Commits (`feat:`, `fix:`, `sec:`, `test:`, `docs:`, `chore:`).
   - Separate atomic branches must be used for distinct feature scopes.
4. **Issue Backlog & Scoring**:
   - Issue scoping and prioritization follows the Drips Wave complexity taxonomy:
     - **Trivial (100 Points)**: Documentation, OpenAPI metadata, minor helper utilities.
     - **Medium (150 Points)**: Nonce ledgers, integration test suites, UI components.
     - **High (200 Points)**: Soroban SAC verifiers, dynamic price estimators, multi-language SDKs.
