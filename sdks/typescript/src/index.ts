export interface StellarPaywallConfig {
    baseUrl: string;
    secretKey?: string;
    horizonUrl?: string;
    networkPassphrase?: string;
}

export interface PaymentChallenge {
    amount: string;
    asset: string;
    destination: string;
    challengeUuid?: string;
}

export class StellarPaywallClient {
    private baseUrl: string;
    private secretKey?: string;
    private horizonUrl: string;
    private networkPassphrase: string;

    constructor(config: string | StellarPaywallConfig) {
        if (typeof config === "string") {
            this.baseUrl = config.replace(/\/+$/, "");
            this.horizonUrl = "https://horizon-testnet.stellar.org";
            this.networkPassphrase = "Test SDF Network ; September 2015";
        } else {
            this.baseUrl = config.baseUrl.replace(/\/+$/, "");
            this.secretKey = config.secretKey;
            this.horizonUrl = config.horizonUrl || "https://horizon-testnet.stellar.org";
            this.networkPassphrase = config.networkPassphrase || "Test SDF Network ; September 2015";
        }
    }

    /**
     * Parses HTTP 402 challenge parameters from X-PayWall-* headers or WWW-Authenticate.
     */
    private parseChallenge(headers: Headers): PaymentChallenge {
        let amount = headers.get("X-PayWall-Amount") || "";
        let asset = headers.get("X-PayWall-Asset") || "XLM";
        let destination = headers.get("X-PayWall-Destination") || "merchant_address";
        let challengeUuid = headers.get("X-PayWall-Challenge-UUID") || undefined;

        const authHeader = headers.get("WWW-Authenticate") || "";
        if (!amount && authHeader.includes('amount="')) {
            const match = authHeader.match(/amount="([^"]+)"/);
            if (match) amount = match[1];
        }
        if (authHeader.includes('destination="') && destination === "merchant_address") {
            const match = authHeader.match(/destination="([^"]+)"/);
            if (match) destination = match[1];
        }
        if (!challengeUuid && authHeader.includes('challenge="')) {
            const match = authHeader.match(/challenge="([^"]+)"/);
            if (match) challengeUuid = match[1];
        }

        return {
            amount: amount || "0.05",
            asset: asset || "XLM",
            destination: destination || "merchant_address",
            challengeUuid,
        };
    }

    /**
     * Simulates or executes Stellar payment transaction signing.
     */
    public async signPaymentTransaction(challenge: PaymentChallenge): Promise<string> {
        // Deterministic hash based on challenge parameters and secret
        const encoder = new TextEncoder();
        const data = encoder.encode(
            `${challenge.destination}:${challenge.amount}:${challenge.asset}:${challenge.challengeUuid || ""}:${this.secretKey || "simulated"}`
        );
        const hashBuffer = await crypto.subtle.digest("SHA-256", data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
    }

    /**
     * Executes HTTP request with automatic HTTP 402 interception and payment retry.
     */
    async fetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
        const url = endpoint.startsWith("http") ? endpoint : `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
        let response = await fetch(url, options);

        if (response.status === 402) {
            const challenge = this.parseChallenge(response.headers);
            const txHash = await this.signPaymentTransaction(challenge);

            const newHeaders = new Headers(options.headers || {});
            newHeaders.set("X-PayWall-Tx-Hash", txHash);
            newHeaders.set("X-Stellar-Tx-Hash", txHash);
            if (challenge.challengeUuid) {
                newHeaders.set("X-PayWall-Challenge-UUID", challenge.challengeUuid);
            }

            response = await fetch(url, {
                ...options,
                headers: newHeaders,
            });
        }

        return response;
    }
}
