package e2e

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestDropLifecycle(t *testing.T) {
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}

	dir := WorkDir(t)
	reg := RunCmd(t, Request{Args: []string{"identity", "register", "dropbot@e2e"}, WorkDir: dir})
	if reg.ExitCode != 0 {
		t.Fatalf("register failed: %s", reg.Stderr)
	}

	// Create a test file
	testFile := filepath.Join(dir, "test.txt")
	os.WriteFile(testFile, []byte("hello hivo drop"), 0644)

	var remotePath = "e2e/test.txt"

	t.Run("upload file", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "upload", testFile, remotePath},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
	})

	t.Run("list shows uploaded file", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "list", "e2e/"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v", err)
		}
	})

	t.Run("download file", func(t *testing.T) {
		localOut := filepath.Join(dir, "downloaded.txt")
		result := RunCmd(t, Request{
			Args:    []string{"drop", "download", remotePath, localOut},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		data, err := os.ReadFile(localOut)
		if err != nil {
			t.Fatalf("downloaded file not found: %v", err)
		}
		if string(data) != "hello hivo drop" {
			t.Fatalf("unexpected content: %s", data)
		}
	})

	t.Run("share makes file public", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "share", remotePath, "public"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v", err)
		}
	})

	t.Run("delete file", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "delete", remotePath, "--yes"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v", err)
		}
		if out["status"] != "deleted" {
			t.Fatalf("expected status=deleted, got: %v", out["status"])
		}
	})
}
