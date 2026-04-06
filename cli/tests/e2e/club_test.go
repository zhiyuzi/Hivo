package e2e

import (
	"encoding/json"
	"os"
	"testing"
)

func TestClubCreate(t *testing.T) {
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}

	dir := WorkDir(t)
	reg := RunCmd(t, Request{Args: []string{"identity", "register", "clubbot@e2e"}, WorkDir: dir})
	if reg.ExitCode != 0 {
		t.Fatalf("register failed: %s", reg.Stderr)
	}

	t.Run("create returns club_id", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "create", "Test Club", "--description", "e2e test club"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout is not valid JSON: %v\nstdout: %s", err, result.Stdout)
		}
		if out["club_id"] == nil {
			t.Fatal("no club_id in output")
		}
	})
}

func TestClubMy(t *testing.T) {
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}

	dir := WorkDir(t)
	reg := RunCmd(t, Request{Args: []string{"identity", "register", "mybot@e2e"}, WorkDir: dir})
	if reg.ExitCode != 0 {
		t.Fatalf("register failed: %s", reg.Stderr)
	}

	t.Run("my returns clubs list", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "my"},
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
}
