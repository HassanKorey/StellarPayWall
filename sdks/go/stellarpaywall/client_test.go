package stellarpaywall

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestStandardGetWithout402RemainsUntouched(t *testing.T) {
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		if r.Header.Get("X-PayWall-Tx-Hash") != "" {
			t.Errorf("unexpected payment header on 200 endpoint")
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		SecretKey:   "test-secret",
		OfflineMode: true,
	})

	resp, err := client.Get("/health")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", resp.StatusCode)
	}
	if atomic.LoadInt32(&calls) != 1 {
		t.Fatalf("expected 1 call, got %d", calls)
	}
}

func TestHTTP402ChallengeTriggersPaymentAndRetries(t *testing.T) {
	const (
		expectedAmount      = "0.05"
		expectedAsset       = "XLM"
		expectedDestination = "GBYWLISGOUWQ43VQEGXX6KRGDZ3CKAFFK3JXVLXKDO5TIFJUJ3OHJYOZ"
		expectedUUID        = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
	)

	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempt := atomic.AddInt32(&calls, 1)
		txHash := r.Header.Get("X-PayWall-Tx-Hash")
		stellarTxHash := r.Header.Get("X-Stellar-Tx-Hash")
		challengeUUID := r.Header.Get("X-PayWall-Challenge-UUID")

		if attempt == 1 {
			if txHash != "" {
				t.Errorf("did not expect tx hash on initial request")
			}
			w.Header().Set("X-PayWall-Amount", expectedAmount)
			w.Header().Set("X-PayWall-Asset", expectedAsset)
			w.Header().Set("X-PayWall-Destination", expectedDestination)
			w.Header().Set("X-PayWall-Challenge-UUID", expectedUUID)
			w.WriteHeader(http.StatusPaymentRequired)
			_, _ = w.Write([]byte(`{"detail":"Payment Required"}`))
			return
		}

		if txHash == "" || len(txHash) != 64 {
			t.Errorf("expected 64-char sha256 tx hash, got %q", txHash)
		}
		if stellarTxHash != txHash {
			t.Errorf("expected X-Stellar-Tx-Hash %q to match X-PayWall-Tx-Hash %q", stellarTxHash, txHash)
		}
		if challengeUUID != expectedUUID {
			t.Errorf("expected X-PayWall-Challenge-UUID %q, got %q", expectedUUID, challengeUUID)
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"message":"Premium content accessed successfully."}`))
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		SecretKey:   "payer-secret",
		OfflineMode: true,
	})

	resp, err := client.Get("/protected-resource")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK after 402 retry, got %d", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("reading response body: %v", err)
	}
	if !strings.Contains(string(body), "Premium content accessed successfully.") {
		t.Fatalf("unexpected response body: %s", string(body))
	}
	if atomic.LoadInt32(&calls) != 2 {
		t.Fatalf("expected 2 requests (initial 402 + paid retry), got %d", calls)
	}
}

func TestWWWAuthenticateFallbackAndPostBodyPreservation(t *testing.T) {
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempt := atomic.AddInt32(&calls, 1)
		body, _ := io.ReadAll(r.Body)
		if string(body) != `{"query":"soroban"}` {
			t.Errorf("attempt %d: expected body preserved, got %q", attempt, string(body))
		}

		if attempt == 1 {
			w.Header().Set("WWW-Authenticate", `Stellar asset="USDC", amount="0.25", destination="G_MERCHANT_DEST", challenge="uuid-fallback-123"`)
			w.WriteHeader(http.StatusPaymentRequired)
			return
		}

		if r.Header.Get("X-PayWall-Challenge-UUID") != "uuid-fallback-123" {
			t.Errorf("expected challenge uuid-fallback-123, got %q", r.Header.Get("X-PayWall-Challenge-UUID"))
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"result":"done"}`))
	}))
	defer srv.Close()

	client := NewClient(Config{
		BaseURL:     srv.URL,
		SecretKey:   "secret-seed",
		OfflineMode: true,
	})

	resp, err := client.Post("/api/v1/search", "application/json", strings.NewReader(`{"query":"soroban"}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 OK, got %d", resp.StatusCode)
	}
}
