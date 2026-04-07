package drop

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

const defaultDropURL = "https://drop.hivo.ink"

func dropURL() string {
	if v := os.Getenv("HIVO_DROP_URL"); v != "" {
		return v
	}
	return defaultDropURL
}

func effectiveFormat(flagVal string) string {
	return exitcode.EffectiveFormat(flagVal)
}

func getToken(format string) (string, error) {
	ws, _, err := config.FindWorkspaceIdentity()
	if err != nil {
		writeErr(format, "not_registered", err.Error(), "Run: hivo identity register <handle>", false)
		return "", err
	}
	reg, err := config.LoadRegistration(ws.Sub)
	if err != nil {
		writeErr(format, "not_registered", err.Error(), "", false)
		return "", err
	}
	privPEM, err := os.ReadFile(config.PrivateKeyPath(ws.Sub))
	if err != nil {
		writeErr(format, "key_not_found", "Private key not found", "", false)
		return "", err
	}
	priv, err := identitylib.LoadPrivateKey(privPEM)
	if err != nil {
		writeErr(format, "key_invalid", "Failed to load private key", "", false)
		return "", err
	}
	token, err := identitylib.GetToken(reg.Iss, ws.Sub, "hivo-drop", priv, config.TokenCachePath(ws.Sub))
	if err != nil {
		writeErr(format, "token_failed", err.Error(), "", true)
		return "", err
	}
	return token, nil
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

func (e *apiError) Error() string    { return e.code }
func (e *apiError) ExitCode() int    { return e.exitCode }

func handleAPIError(format string, result map[string]interface{}, status int) error {
	errCode, _ := result["error"].(string)
	msg, _ := result["message"].(string)
	if errCode == "" {
		errCode = fmt.Sprintf("http_%d", status)
	}
	writeErr(format, errCode, msg, "", false)
	return &apiError{code: fmt.Sprintf("%s: %s", errCode, msg), exitCode: exitCodeForError(errCode, status)}
}
