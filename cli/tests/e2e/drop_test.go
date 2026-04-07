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
	reg := RunCmd(t, Request{Args: []string{"identity", "register", UniqueHandle("dropbot")}, WorkDir: dir})
	if reg.ExitCode != 0 {
		t.Fatalf("register failed: %s", reg.Stderr)
	}

	testFile := filepath.Join(dir, "test.txt")
	os.WriteFile(testFile, []byte("hello hivo drop"), 0644)
	remotePath := "e2e/test.txt"

	t.Run("upload file", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "upload", testFile, remotePath},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v\nstdout: %s", err, result.Stdout)
		}
	})

	t.Run("upload dry-run exits 10", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "upload", testFile, "e2e/dry.txt", "--dry-run"},
			WorkDir: dir,
		})
		if result.ExitCode != 10 {
			t.Fatalf("expected exit 10 for dry-run, got %d", result.ExitCode)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("dry-run stdout not valid JSON: %v", err)
		}
		if out["dry_run"] != true {
			t.Fatal("expected dry_run=true in output")
		}
	})

	t.Run("upload conflict without overwrite exits 5", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "upload", testFile, remotePath},
			WorkDir: dir,
		})
		if result.ExitCode != 5 {
			t.Fatalf("expected exit 5 (conflict), got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
	})

	t.Run("upload with overwrite succeeds", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "upload", testFile, remotePath, "--overwrite"},
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
		files, _ := out["files"].([]interface{})
		found := false
		for _, f := range files {
			if file, ok := f.(map[string]interface{}); ok {
				if file["path"] == remotePath {
					found = true
					break
				}
			}
		}
		if !found {
			t.Fatalf("uploaded file %q not found in list: %v", remotePath, out)
		}
	})

	t.Run("download to file", func(t *testing.T) {
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

	t.Run("download to stdout", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "download", remotePath},
			WorkDir: dir,
			Format:  "text",
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		if result.Stdout != "hello hivo drop" {
			t.Fatalf("unexpected stdout content: %q", result.Stdout)
		}
	})

	t.Run("share makes file public and returns share_id", func(t *testing.T) {
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
		if out["share_id"] == nil {
			t.Fatalf("expected share_id in output, got: %v", out)
		}
	})

	t.Run("share dry-run exits 10", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "share", remotePath, "private", "--dry-run"},
			WorkDir: dir,
		})
		if result.ExitCode != 10 {
			t.Fatalf("expected exit 10 for dry-run, got %d", result.ExitCode)
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

	t.Run("delete dry-run exits 10", func(t *testing.T) {
		// Upload first so the path exists
		os.WriteFile(testFile, []byte("dry run test"), 0644)
		RunCmd(t, Request{Args: []string{"drop", "upload", testFile, "e2e/drytest.txt"}, WorkDir: dir})

		result := RunCmd(t, Request{
			Args:    []string{"drop", "delete", "e2e/drytest.txt", "--dry-run"},
			WorkDir: dir,
		})
		if result.ExitCode != 10 {
			t.Fatalf("expected exit 10 for dry-run, got %d", result.ExitCode)
		}
		// Clean up
		RunCmd(t, Request{Args: []string{"drop", "delete", "e2e/drytest.txt", "--yes"}, WorkDir: dir})
	})

	t.Run("download not found exits 3", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"drop", "download", "e2e/nonexistent.txt"},
			WorkDir: dir,
		})
		if result.ExitCode != 3 {
			t.Fatalf("expected exit 3 (not_found), got %d", result.ExitCode)
		}
	})
}
