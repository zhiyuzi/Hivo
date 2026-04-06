package e2e

import (
	"bytes"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sync"
	"testing"
	"time"
)

// Request encapsulates a CLI invocation
type Request struct {
	Args    []string
	Format  string // "json" or "text" (default: "json")
	WorkDir string // working directory for the command
}

// Result captures execution outcomes
type Result struct {
	ExitCode int
	Stdout   string
	Stderr   string
}

var (
	binaryPath string
	buildOnce  sync.Once
)

// BinaryPath returns the path to the compiled hivo binary, building it once
func BinaryPath(t *testing.T) string {
	t.Helper()
	buildOnce.Do(func() {
		// Find cli/ root (two levels up from tests/e2e/)
		_, file, _, _ := runtime.Caller(0)
		cliRoot := filepath.Join(filepath.Dir(file), "..", "..")

		// Check for explicit binary path override
		if p := os.Getenv("HIVO_BIN"); p != "" {
			binaryPath = p
			return
		}

		// Build the binary
		bin := filepath.Join(t.TempDir(), "hivo")
		if runtime.GOOS == "windows" {
			bin += ".exe"
		}
		cmd := exec.Command("go", "build", "-o", bin, ".")
		cmd.Dir = cliRoot
		var stderr bytes.Buffer
		cmd.Stderr = &stderr
		if err := cmd.Run(); err != nil {
			t.Fatalf("failed to build hivo binary: %v\n%s", err, stderr.String())
		}
		binaryPath = bin
	})
	return binaryPath
}

// RunCmd executes the hivo CLI with the given request
func RunCmd(t *testing.T, r Request) Result {
	t.Helper()
	bin := BinaryPath(t)

	args := r.Args
	format := r.Format
	if format == "" {
		format = "json"
	}
	// Prepend --format flag
	args = append([]string{"--format", format}, args...)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, bin, args...)
	if r.WorkDir != "" {
		cmd.Dir = r.WorkDir
	}

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	exitCode := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			exitCode = 1
		}
	}

	return Result{
		ExitCode: exitCode,
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
	}
}

// WorkDir creates a temp directory and returns its path (auto-cleaned by t.Cleanup)
func WorkDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	return dir
}
