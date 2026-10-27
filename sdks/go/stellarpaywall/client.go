package stellarpaywall

import (
	"bytes"
	"io"
	"net/http"
	"strings"
)

// Config holds configuration for the StellarPayWall Go client SDK and RoundTripper.
type Config struct {
	BaseURL           string
	SecretKey         string
	HorizonURL        string
	NetworkPassphrase string
	OfflineMode       bool
	BaseTransport     http.RoundTripper
}

// Transport implements http.RoundTripper to transparently intercept HTTP 402
// Payment Required challenges, construct/sign Stellar micropayments, and retry
// the original HTTP request with payment verification headers.
type Transport struct {
	Config Config
}

// NewTransport constructs an HTTP 402 intercepting RoundTripper.
func NewTransport(cfg Config) *Transport {
	if cfg.HorizonURL == "" {
		cfg.HorizonURL = DefaultHorizonURL
	}
	if cfg.NetworkPassphrase == "" {
		cfg.NetworkPassphrase = DefaultNetworkPassphrase
	}
	if cfg.BaseTransport == nil {
		cfg.BaseTransport = http.DefaultTransport
	}
	return &Transport{Config: cfg}
}

// RoundTrip executes a single HTTP transaction, automatically negotiating HTTP 402 challenges.
func (t *Transport) RoundTrip(req *http.Request) (*http.Response, error) {
	base := t.Config.BaseTransport
	if base == nil {
		base = http.DefaultTransport
	}

	var bodyBytes []byte
	if req.Body != nil && req.Body != http.NoBody {
		var err error
		bodyBytes, err = io.ReadAll(req.Body)
		if err != nil {
			return nil, err
		}
		_ = req.Body.Close()
		req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
	}

	resp, err := base.RoundTrip(req)
	if err != nil || resp.StatusCode != http.StatusPaymentRequired {
		return resp, err
	}

	challenge := ParseChallenge(resp.Header)
	_, _ = io.Copy(io.Discard, resp.Body)
	_ = resp.Body.Close()

	txHash, err := SignPaymentTransaction(PaymentParams{
		Destination:   challenge.Destination,
		Amount:        challenge.Amount,
		AssetCode:     challenge.Asset,
		MemoText:      challenge.ChallengeUUID,
		SecretKey:     t.Config.SecretKey,
		HorizonURL:    t.Config.HorizonURL,
		Passphrase:    t.Config.NetworkPassphrase,
		OfflineMode:   t.Config.OfflineMode,
		HTTPTransport: base,
	})
	if err != nil {
		return nil, err
	}

	retryReq := req.Clone(req.Context())
	if bodyBytes != nil {
		retryReq.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		retryReq.ContentLength = int64(len(bodyBytes))
	}
	retryReq.Header.Set("X-PayWall-Tx-Hash", txHash)
	retryReq.Header.Set("X-Stellar-Tx-Hash", txHash)
	if challenge.ChallengeUUID != "" {
		retryReq.Header.Set("X-PayWall-Challenge-UUID", challenge.ChallengeUUID)
	}

	return base.RoundTrip(retryReq)
}

// Client wraps a standard *http.Client configured with the HTTP 402 Transport.
type Client struct {
	BaseURL    string
	HTTPClient *http.Client
	Transport  *Transport
}

// NewClient creates a new StellarPayWall Go client.
func NewClient(cfg Config) *Client {
	transport := NewTransport(cfg)
	return &Client{
		BaseURL: strings.TrimRight(cfg.BaseURL, "/"),
		HTTPClient: &http.Client{
			Transport: transport,
		},
		Transport: transport,
	}
}

// Do sends an HTTP request using the underlying 402-intercepting HTTP client.
func (c *Client) Do(req *http.Request) (*http.Response, error) {
	return c.HTTPClient.Do(req)
}

// Get performs a GET request against the given endpoint or full URL.
func (c *Client) Get(endpoint string) (*http.Response, error) {
	req, err := http.NewRequest(http.MethodGet, c.resolveURL(endpoint), nil)
	if err != nil {
		return nil, err
	}
	return c.HTTPClient.Do(req)
}

// Post performs a POST request against the given endpoint or full URL.
func (c *Client) Post(endpoint, contentType string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequest(http.MethodPost, c.resolveURL(endpoint), body)
	if err != nil {
		return nil, err
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	return c.HTTPClient.Do(req)
}

func (c *Client) resolveURL(endpoint string) string {
	if strings.HasPrefix(endpoint, "http://") || strings.HasPrefix(endpoint, "https://") {
		return endpoint
	}
	if strings.HasPrefix(endpoint, "/") {
		return c.BaseURL + endpoint
	}
	return c.BaseURL + "/" + endpoint
}
