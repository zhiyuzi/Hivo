package e2e

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestIdentityRegister(t *testing.T) {
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}

	dir := WorkDir(t)

	t.Run("register creates identity files", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"identity", "register", "testbot@e2e"},
			WorkDir: dir,
		})

		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}

		// Verify .hivo/identity.json was written
		identityPath := filepath.Join(dir, ".hivo", "identity.json")
		data, err := os.ReadFile(identityPath)
		if err != nil {
			t.Fatalf(".hivo/identity.json not found: %v", err)
		}

		var id map[string]string
		if err := json.Unmarshal(data, &id); err != nil {
			t.Fatalf("invalid identity.json: %v", err)
		}
		if id["sub"] == "" {
			t.Fatal("identity.json missing sub")
		}

		// Verify stdout is valid JSON with sub
		var out map[string]string
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v\nstdout: %s", err, result.Stdout)
		}
		if out["sub"] == "" {
			t.Fatal("stdout JSON missing sub")
		}
	})

	t.Run("register fails with invalid handle", func(t *testing.T) {
		dir2 := WorkDir(t)
		result := RunCmd(t, Request{
			Args:    []string{"identity", "register", "invalid-handle"},
			WorkDir: dir2,
		})
		if result.ExitCode == 0 {
			t.Fatal("expected non-zero exit for invalid handle")
		}
	})
}

func TestIdentityToken(t *testing.T) {
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}

	dir := WorkDir(t)

	// Register first
	reg := RunCmd(t, Request{
		Args:    []string{"identity", "register", "tokenbot@e2e"},
		WorkDir: dir,
	})
	if reg.ExitCode != 0 {
		t.Fatalf("register failed: %s", reg.Stderr)
	}

	t.Run("token returns JWT", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"identity", "token", "hivo-drop"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}

		var out map[string]string
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v", err)
		}
		if out["access_token"] == "" {
			t.Fatal("no access_token in output")
		}
	})
}

func TestIdentityMe(t *testing.T) {
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}

	dir := WorkDir(t)
	reg := RunCmd(t, Request{
		Args:    []string{"identity", "register", "mebot@e2e"},
		WorkDir: dir,
	})
	if reg.ExitCode != 0 {
		t.Fatalf("register failed: %s", reg.Stderr)
	}

	t.Run("me returns identity info", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"identity", "me"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v", err)
		}
		if out["sub"] == nil {
			t.Fatal("no sub in output")
		}
	})
}

func TestNoIdentity(t *testing.T) {
	dir := WorkDir(t)

	t.Run("me without registration returns error", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"identity", "me"},
			WorkDir: dir,
		})
		if result.ExitCode == 0 {
			t.Fatal("expected non-zero exit when not registered")
		}
	})
}
