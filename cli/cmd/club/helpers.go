package club

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/zhiyuzi/hivo/cli/internal/config"
	identitylib "github.com/zhiyuzi/hivo/cli/internal/identity"
)

const defaultClubURL = "https://club.hivo.ink"

func clubURL() string {
	if v := os.Getenv("HIVO_CLUB_URL"); v != "" {
		return v
	}
	return defaultClubURL
}

// getToken resolves the agent identity and returns a Bearer token for hivo-club
func getToken(format string) (string, *config.AgentRegistration, error) {
	ws, _, err := config.FindWorkspaceIdentity()
	if err != nil {
		writeErr(format, "not_registered", err.Error(), "Run: hivo identity register <handle>", false)
		return "", nil, err
	}
	reg, err := config.LoadRegistration(ws.Sub)
	if err != nil {
		writeErr(format, "not_registered", err.Error(), "", false)
		return "", nil, err
	}
	privPEM, err := os.ReadFile(config.PrivateKeyPath(ws.Sub))
	if err != nil {
		writeErr(format, "key_not_found", "Private key not found", "", false)
		return "", nil, err
	}
	priv, err := identitylib.LoadPrivateKey(privPEM)
	if err != nil {
		writeErr(format, "key_invalid", "Failed to load private key", "", false)
		return "", nil, err
	}
	token, err := identitylib.GetToken(reg.Iss, ws.Sub, "hivo-club", priv, config.TokenCachePath(ws.Sub))
	if err != nil {
		writeErr(format, "token_failed", err.Error(), "", true)
		return "", nil, err
	}
	return token, reg, nil
}

func doRequest(method, url, token string, body interface{}) (map[string]interface{}, int, error) {
	var bodyReader io.Reader
	if body != nil {
		data, _ := json.Marshal(body)
		bodyReader = strings.NewReader(string(data))
	}
	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var result map[string]interface{}
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &result)
	}
	return result, resp.StatusCode, nil
}

func writeErr(format, code, message, suggestion string, retryable bool) {
	if format == "json" {
		out, _ := json.Marshal(map[string]interface{}{
			"error": code, "message": message,
			"suggestion": suggestion, "retryable": retryable,
		})
		fmt.Fprintln(os.Stderr, string(out))
	} else {
		fmt.Fprintf(os.Stderr, "error: %s\n", message)
		if suggestion != "" {
			fmt.Fprintf(os.Stderr, "hint:  %s\n", suggestion)
		}
	}
}

func handleAPIError(format string, result map[string]interface{}, status int) error {
	errCode, _ := result["error"].(string)
	msg, _ := result["message"].(string)
	if errCode == "" {
		errCode = fmt.Sprintf("http_%d", status)
	}
	writeErr(format, errCode, msg, "", false)
	return fmt.Errorf("%s: %s", errCode, msg)
}
