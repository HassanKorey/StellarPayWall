# TypeScript / JavaScript Client SDK 🌐

The StellarPayWall TypeScript SDK (`@stellarpaywall/sdk`) provides a modern, typed client library for Node.js, Next.js, and browser environments. It includes an automatic `Axios` / `fetch` interceptor for HTTP 402 micro-transactions on Stellar and Soroban.

---

## 📦 Installation

```bash
npm install @stellarpaywall/sdk @stellar/stellar-sdk
# or via pnpm / yarn:
pnpm add @stellarpaywall/sdk @stellar/stellar-sdk
```

---

## ⚡ Quick Start: Node.js Backend Client

```typescript
import { StellarPayWallClient } from '@stellarpaywall/sdk';
import { Keypair, Networks } from '@stellar/stellar-sdk';

const signerKeypair = Keypair.fromSecret('S...');

const client = new StellarPayWallClient({
  baseUrl: 'https://stellarpaywall.onrender.com',
  networkPassphrase: Networks.TESTNET,
  horizonUrl: 'https://horizon-testnet.stellar.org',
  keypair: signerKeypair,
});

async function run() {
  // Requests to protected endpoints automatically negotiate 402 challenge
  const response = await client.get('/protected-resource');
  console.log('Status:', response.status);
  console.log('Payload:', response.data);
}

run().catch(console.error);
```

---

## 🔌 Axios Interceptor Plug-in

If you already use an existing `axios` instance in your application, you can attach the StellarPayWall 402 interceptor directly:

```typescript
import axios from 'axios';
import { attachPayWallInterceptor } from '@stellarpaywall/sdk';
import { Keypair, Networks } from '@stellar/stellar-sdk';

const api = axios.create({
  baseURL: 'https://stellarpaywall.onrender.com',
});

const keypair = Keypair.fromSecret('S...');

attachPayWallInterceptor(api, {
  keypair,
  networkPassphrase: Networks.TESTNET,
  maxPriceLimit: '0.10', // Max XLM willing to pay per request
});

// All API calls now automatically pay the 402 challenge:
const res = await api.get('/protected-resource');
console.log(res.data);
```

---

## 👛 Browser / Freighter Wallet Integration

For frontend web applications, you can connect the Freighter browser wallet to sign 402 transactions on behalf of the user:

```typescript
import { StellarPayWallBrowserClient } from '@stellarpaywall/sdk';
import { isConnected, signTransaction } from '@stellar/freighter-api';

const browserClient = new StellarPayWallBrowserClient({
  baseUrl: 'https://stellarpaywall.onrender.com',
  signTransaction: async (xdr: string) => {
    return await signTransaction(xdr, { network: 'TESTNET' });
  },
});
```
