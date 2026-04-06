package identity

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// RegisterResult is returned after successful registration
type RegisterResult struct {
	Sub    string `json:"sub"`
	Handle string `json:"handle"`
	Iss    string `json:"iss"`
}

// Register performs the challenge-proof registration flow
func Register(issuerURL, handle string, priv ed25519.PrivateKey, pubJWK []byte) (*RegisterResult, error) {
	// Step 1: POST /register
	var jwkMap map[string]string
	if err := json.Unmarshal(pubJWK, &jwkMap); err != nil {
		return nil, err
	}

	regBody := map[string]interface{}{
		"handle":     handle,
		"public_key": jwkMap,
	}
	regResp, err := postJSON(issuerURL+"/register", regBody)
	if err != nil {
		return nil, fmt.Errorf("register: %w", err)
	}

	challenge, ok := regResp["challenge"].(string)
	if !ok {
		return nil, fmt.Errorf("register: no challenge in response")
	}
	regID, ok := regResp["registration_id"].(string)
	if !ok {
		return nil, fmt.Errorf("register: no registration_id in response")
	}

	// Step 2: sign challenge
	sig := ed25519.Sign(priv, []byte(challenge))
	sigB64 := base64.RawURLEncoding.EncodeToString(sig)

	// Step 3: POST /register/verify
	verifyBody := map[string]string{
		"registration_id": regID,
		"signature":       sigB64,
	}
	verifyResp, err := postJSON(issuerURL+"/register/verify", verifyBody)
	if err != nil {
		return nil, fmt.Errorf("register/verify: %w", err)
	}

	sub, _ := verifyResp["sub"].(string)
	retHandle, _ := verifyResp["handle"].(string)
	if sub == "" {
		return nil, fmt.Errorf("register/verify: no sub in response")
	}

	return &RegisterResult{Sub: sub, Handle: retHandle, Iss: issuerURL}, nil
}

// TokenCache holds cached tokens per audience
type TokenCache map[string]TokenEntry

type TokenEntry struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresAt    int64  `json:"expires_at,omitempty"`
}

// GetToken returns a valid access token for the given audience, using cache/refresh/assertion as needed
func GetToken(issuerURL, sub, audience string, priv ed25519.PrivateKey, cachePath string) (string, error) {
	cache := loadTokenCache(cachePath)

	entry, ok := cache[audience]
	if ok && entry.AccessToken != "" {
		// Check expiry (if we have it stored)
		if entry.ExpiresAt > time.Now().Unix()+60 {
			return entry.AccessToken, nil
		}
		// Try refresh
		if entry.RefreshToken != "" {
			newEntry, err := refreshToken(issuerURL, entry.RefreshToken)
			if err == nil {
				cache[audience] = *newEntry
				_ = saveTokenCache(cachePath, cache)
				return newEntry.AccessToken, nil
			}
		}
	}

	// Fall back to assertion flow
	newEntry, err := assertionFlow(issuerURL, sub, audience, priv)
	if err != nil {
		return "", err
	}
	cache[audience] = *newEntry
	_ = saveTokenCache(cachePath, cache)
	return newEntry.AccessToken, nil
}

func refreshToken(issuerURL, refreshToken string) (*TokenEntry, error) {
	body := map[string]string{"refresh_token": refreshToken}
	resp, err := postJSON(issuerURL+"/token/refresh", body)
	if err != nil {
		return nil, err
	}
	return tokenEntryFromResponse(resp)
}

func assertionFlow(issuerURL, sub, audience string, priv ed25519.PrivateKey) (*TokenEntry, error) {
	jwt, err := buildJWT(sub, issuerURL, audience, priv)
	if err != nil {
		return nil, err
	}
	body := map[string]string{
		"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
		"assertion":  jwt,
		"audience":   audience,
	}
	resp, err := postJSON(issuerURL+"/token", body)
	if err != nil {
		return nil, err
	}
	return tokenEntryFromResponse(resp)
}

func tokenEntryFromResponse(resp map[string]interface{}) (*TokenEntry, error) {
	at, _ := resp["access_token"].(string)
	rt, _ := resp["refresh_token"].(string)
	if at == "" {
		return nil, fmt.Errorf("no access_token in response")
	}
	entry := &TokenEntry{AccessToken: at, RefreshToken: rt}
	// Try to parse expiry from JWT
	if exp := jwtExp(at); exp > 0 {
		entry.ExpiresAt = exp
	}
	return entry, nil
}

func buildJWT(sub, iss, audience string, priv ed25519.PrivateKey) (string, error) {
	now := time.Now().Unix()
	header := map[string]string{"alg": "EdDSA", "typ": "JWT"}
	claims := map[string]interface{}{
		"sub": sub,
		"iss": iss,
		"aud": audience,
		"iat": now,
		"exp": now + 300,
		"jti": fmt.Sprintf("%d", now),
	}
	hJSON, _ := json.Marshal(header)
	cJSON, _ := json.Marshal(claims)
	hB64 := base64.RawURLEncoding.EncodeToString(hJSON)
	cB64 := base64.RawURLEncoding.EncodeToString(cJSON)
	msg := hB64 + "." + cB64
	sig := ed25519.Sign(priv, []byte(msg))
	return msg + "." + base64.RawURLEncoding.EncodeToString(sig), nil
}

func jwtExp(token string) int64 {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return 0
	}
	data, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return 0
	}
	var claims map[string]interface{}
	if err := json.Unmarshal(data, &claims); err != nil {
		return 0
	}
	switch v := claims["exp"].(type) {
	case float64:
		return int64(v)
	}
	return 0
}

func loadTokenCache(path string) TokenCache {
	cache := make(TokenCache)
	data, err := os.ReadFile(path)
	if err != nil {
		return cache
	}
	_ = json.Unmarshal(data, &cache)
	return cache
}

func saveTokenCache(path string, cache TokenCache) error {
	data, err := json.MarshalIndent(cache, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0600)
}

func postJSON(url string, body interface{}) (map[string]interface{}, error) {
	data, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	resp, err := http.Post(url, "application/json", strings.NewReader(string(data)))
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var result map[string]interface{}
	if err := json.Unmarshal(raw, &result); err != nil {
		return nil, fmt.Errorf("invalid response: %s", raw)
	}
	if resp.StatusCode >= 400 {
		errCode, _ := result["error"].(string)
		msg, _ := result["message"].(string)
		return nil, fmt.Errorf("%s: %s", errCode, msg)
	}
	return result, nil
}
