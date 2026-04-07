package identity

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func effectiveFormat(flagVal string) string {
	return exitcode.EffectiveFormat(flagVal)
}

func writeError(format, code, message, suggestion string, retryable bool, err error) error {
	if format == "json" {
		out, _ := json.Marshal(map[string]interface{}{
			"error":      code,
			"message":    message,
			"suggestion": suggestion,
			"retryable":  retryable,
		})
		fmt.Fprintln(os.Stderr, string(out))
	} else {
		fmt.Fprintf(os.Stderr, "error: %s\n", message)
		if suggestion != "" {
			fmt.Fprintf(os.Stderr, "hint:  %s\n", suggestion)
		}
	}
	switch code {
	case "not_found":
		return &identityError{msg: err.Error(), exitCode: exitcode.NotFound}
	case "forbidden":
		return &identityError{msg: err.Error(), exitCode: exitcode.Forbidden}
	case "conflict", "handle_taken":
		return &identityError{msg: err.Error(), exitCode: exitcode.Conflict}
	case "usage_error", "validation_error":
		return &identityError{msg: err.Error(), exitCode: exitcode.Usage}
	}
	return err
}

type identityError struct {
	msg      string
	exitCode int
}

func (e *identityError) Error() string { return e.msg }
func (e *identityError) ExitCode() int { return e.exitCode }
