# Maintainers & Governance

This document outlines the maintainers, domain responsibilities, and review governance for StellarPayWall.

---

## 👥 Core Maintainers

| Name | Role | GitHub | Contact |
| :--- | :--- | :--- | :--- |
| Hassan Akorede (EDUN) | Lead Architect | [@HassanKorey](https://github.com/HassanKorey) | Telegram: `@HassanKorey` |
| Co-Maintainer | Middleware Reviewer | [@CoMaintainer](https://github.com/CoMaintainer) | Discord: `comaintainer#0001` |

---

## 📋 Review & Pull Request Policy

1. **Pull Request Reviews**:
   - Every Pull Request requires review and approval from at least one core maintainer before merging.
   - Core protocol, cryptographic, or ledger modifications require review by the **Lead Architect**.
2. **CI/CD Quality Gates**:
   - Automated GitHub Actions workflows (Ruff linting, Pytest test suite, Cargo tests) must pass cleanly on all pull requests.
3. **Commit & Branching Standards**:
   - Contributions must follow Conventional Commits (`feat:`, `fix:`, `sec:`, `test:`, `docs:`, `chore:`).
   - Work must occur on focused feature branches (`feat/`, `sec/`, `docs/`).
4. **Issue Scoping & Drips Wave Complexity Tiers**:
   - Issues are scoped across standard tiers:
     - **Trivial (100 Points)**: Route metadata, Swagger docs, UI styling.
     - **Medium (150 Points)**: Nonce ledgers, event parsers, SDK wrappers, webhooks.
     - **High (200 Points)**: Smart contract dynamic pricing vaults, AI agent middleware adapters, security attack suites.
