package stellarpaywall

import (
	"net/http"
	"regexp"
	"strings"
)

const (
	DefaultAmount      = "0.05"
	DefaultAsset       = "XLM"
	DefaultDestination = "merchant_address"
)

var (
	reAmount      = regexp.MustCompile(`amount="([^"]+)"`)
	reAsset       = regexp.MustCompile(`asset="([^"]+)"`)
	reDestination = regexp.MustCompile(`destination="([^"]+)"`)
	reChallenge   = regexp.MustCompile(`challenge="([^"]+)"`)
)

// Challenge represents the parsed HTTP 402 Payment Required challenge parameters.
type Challenge struct {
	Amount        string
	Asset         string
	Destination   string
	ChallengeUUID string
}

// ParseChallenge extracts Stellar micropayment challenge parameters from
// X-PayWall-* headers or falls back to parsing the WWW-Authenticate header.
func ParseChallenge(header http.Header) Challenge {
	amount := strings.TrimSpace(header.Get("X-PayWall-Amount"))
	asset := strings.TrimSpace(header.Get("X-PayWall-Asset"))
	destination := strings.TrimSpace(header.Get("X-PayWall-Destination"))
	challengeUUID := strings.TrimSpace(header.Get("X-PayWall-Challenge-UUID"))

	authHeader := header.Get("WWW-Authenticate")
	if authHeader != "" {
		if amount == "" {
			if m := reAmount.FindStringSubmatch(authHeader); len(m) == 2 {
				amount = m[1]
			}
		}
		if asset == "" {
			if m := reAsset.FindStringSubmatch(authHeader); len(m) == 2 {
				asset = m[1]
			}
		}
		if destination == "" {
			if m := reDestination.FindStringSubmatch(authHeader); len(m) == 2 {
				destination = m[1]
			}
		}
		if challengeUUID == "" {
			if m := reChallenge.FindStringSubmatch(authHeader); len(m) == 2 {
				challengeUUID = m[1]
			}
		}
	}

	if amount == "" {
		amount = DefaultAmount
	}
	if asset == "" {
		asset = DefaultAsset
	}
	if destination == "" {
		destination = DefaultDestination
	}

	return Challenge{
		Amount:        amount,
		Asset:         asset,
		Destination:   destination,
		ChallengeUUID: challengeUUID,
	}
}
