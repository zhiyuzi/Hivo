package salon

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/zhiyuzi/hivo/cli/internal/config"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
	identitylib "github.com/zhiyuzi/hivo/cli/internal/identity"
)

const defaultSalonURL = "https://salon.hivo.ink"

func salonURL() string {
	if v := os.Getenv("HIVO_SALON_URL"); v != "" {
		return v
	}
	return defaultSalonURL
}

func effectiveFormat(flagVal string) string {
	return exitcode.EffectiveFormat(flagVal)
}

// getToken resolves the agent identity and returns a Bearer token for hivo-salon
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
	token, err := identitylib.GetToken(reg.Iss, ws.Sub, "hivo-salon", priv, config.TokenCachePath(ws.Sub))
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

// exitCodeForError maps API error codes to CLI exit codes
func exitCodeForError(errCode string, status int) int {
	switch errCode {
	case "not_found":
		return exitcode.NotFound
	case "forbidden", "permission_denied":
		return exitcode.Forbidden
	case "conflict":
		return exitcode.Conflict
	case "usage_error", "validation_error":
		return exitcode.Usage
	}
	if status == 404 {
		return exitcode.NotFound
	}
	if status == 403 {
		return exitcode.Forbidden
	}
	if status == 409 {
		return exitcode.Conflict
	}
	if status == 422 {
		return exitcode.Usage
	}
	return exitcode.Err
}

type apiError struct {
	code     string
	exitCode int
}

func (e *apiError) Error() string { return e.code }
func (e *apiError) ExitCode() int { return e.exitCode }

func handleAPIError(format string, result map[string]interface{}, status int) error {
	errCode, _ := result["error"].(string)
	msg, _ := result["message"].(string)
	if errCode == "" {
		errCode = fmt.Sprintf("http_%d", status)
	}
	writeErr(format, errCode, msg, "", false)
	return &apiError{code: fmt.Sprintf("%s: %s", errCode, msg), exitCode: exitCodeForError(errCode, status)}
}

// resolveHandle calls the identity /resolve endpoint to convert a handle to a sub.
func resolveHandle(handle string) (sub string, err error) {
	baseURL := os.Getenv("HIVO_ISSUER_URL")
	if baseURL == "" {
		baseURL = "https://id.hivo.ink"
	}
	req, _ := http.NewRequest("GET", baseURL+"/resolve?handle="+handle, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("resolve %s: %w", handle, err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("resolve %s: HTTP %d", handle, resp.StatusCode)
	}
	var result map[string]interface{}
	if err := json.Unmarshal(raw, &result); err != nil {
		return "", fmt.Errorf("resolve %s: bad response", handle)
	}
	s, _ := result["sub"].(string)
	if s == "" {
		return "", fmt.Errorf("resolve %s: no sub in response", handle)
	}
	return s, nil
}
