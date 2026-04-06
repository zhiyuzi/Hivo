package httpclient

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// Client is an HTTP client that injects a Bearer token
type Client struct {
	BaseURL string
	Token   string
}

// New creates a new Client
func New(baseURL, token string) *Client {
	return &Client{BaseURL: baseURL, Token: token}
}

// Do performs an HTTP request with Bearer auth, returns parsed JSON body
func (c *Client) Do(method, path string, body interface{}) (map[string]interface{}, int, error) {
	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, 0, err
		}
		bodyReader = strings.NewReader(string(data))
	}

	req, err := http.NewRequest(method, c.BaseURL+path, bodyReader)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("request failed (retryable): %w", err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)

	var result map[string]interface{}
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &result)
	}

	if resp.StatusCode >= 400 {
		errCode, _ := result["error"].(string)
		msg, _ := result["message"].(string)
		if errCode == "" {
			errCode = fmt.Sprintf("http_%d", resp.StatusCode)
		}
		return nil, resp.StatusCode, &APIError{Code: errCode, Message: msg, Status: resp.StatusCode}
	}

	return result, resp.StatusCode, nil
}

// DoRaw performs an HTTP request and returns raw bytes (for file download)
func (c *Client) DoRaw(method, path string) ([]byte, int, error) {
	req, err := http.NewRequest(method, c.BaseURL+path, nil)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("request failed (retryable): %w", err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	return raw, resp.StatusCode, nil
}

// DoUpload uploads a file with multipart form
func (c *Client) DoUpload(path string, body io.Reader, contentType string, extraFields map[string]string) (map[string]interface{}, int, error) {
	req, err := http.NewRequest("POST", c.BaseURL+path, body)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Content-Type", contentType)
	for k, v := range extraFields {
		req.Header.Set(k, v)
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("upload failed (retryable): %w", err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)

	var result map[string]interface{}
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &result)
	}
	if resp.StatusCode >= 400 {
		errCode, _ := result["error"].(string)
		msg, _ := result["message"].(string)
		return nil, resp.StatusCode, &APIError{Code: errCode, Message: msg, Status: resp.StatusCode}
	}
	return result, resp.StatusCode, nil
}

// APIError is a structured error from the Hivo API
type APIError struct {
	Code    string
	Message string
	Status  int
}

func (e *APIError) Error() string {
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// IsNotFound returns true if the error is a 404
func IsNotFound(err error) bool {
	if e, ok := err.(*APIError); ok {
		return e.Status == 404
	}
	return false
}

// IsConflict returns true if the error is a 409
func IsConflict(err error) bool {
	if e, ok := err.(*APIError); ok {
		return e.Status == 409
	}
	return false
}

// PrintError prints a structured error to stderr in JSON or text format
func PrintError(format, errCode, message, suggestion string, retryable bool) {
	if format == "json" {
		data, _ := json.Marshal(map[string]interface{}{
			"error":      errCode,
			"message":    message,
			"suggestion": suggestion,
			"retryable":  retryable,
		})
		fmt.Println(string(data))
	} else {
		fmt.Printf("error: %s\n", message)
		if suggestion != "" {
			fmt.Printf("hint:  %s\n", suggestion)
		}
	}
}
