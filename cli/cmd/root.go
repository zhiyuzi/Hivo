package cmd

import (
	"errors"
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/cmd/club"
	"github.com/zhiyuzi/hivo/cli/cmd/drop"
	"github.com/zhiyuzi/hivo/cli/cmd/identity"
	"github.com/zhiyuzi/hivo/cli/cmd/salon"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

// ExitCoder is implemented by errors that carry a specific exit code.
type ExitCoder interface {
	ExitCode() int
}

var rootCmd = &cobra.Command{
	Use:   "hivo",
	Short: "Hivo CLI — agent-native infrastructure tools",
	Long: `hivo is the command-line interface for the Hivo ecosystem.

Examples:
  hivo identity register mybot@acme
  hivo drop upload ./file.txt docs/file.txt
  hivo club create "My Team" --description "A project team"`,
	SilenceUsage:  true,
	SilenceErrors: true,
}

// Format is the global --format flag value ("json" or "text")
var Format string

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		code := exitcode.Err
		var ec ExitCoder
		if errors.As(err, &ec) {
			code = ec.ExitCode()
		}
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(code)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(&Format, "format", "text", "Output format: json|text")
	rootCmd.AddCommand(identity.NewCmd())
	rootCmd.AddCommand(club.NewCmd())
	rootCmd.AddCommand(drop.NewCmd())
	rootCmd.AddCommand(salon.NewCmd())
}
