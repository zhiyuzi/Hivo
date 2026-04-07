package exitcode

import (
	"os"

	"golang.org/x/term"
)

// Exit codes
const (
	OK        = 0
	Err       = 1
	Usage     = 2
	NotFound  = 3
	Forbidden = 4
	Conflict  = 5
	DryRun    = 10
)

// IsTTY returns true if stdout is a terminal
func IsTTY() bool {
	return term.IsTerminal(int(os.Stdout.Fd()))
}

// EffectiveFormat returns "json" when not in a TTY, otherwise the user-specified format
func EffectiveFormat(flagVal string) string {
	if !IsTTY() && flagVal == "text" {
		return "json"
	}
	return flagVal
}
