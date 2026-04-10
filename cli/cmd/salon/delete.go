package salon

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newDeleteCmd() *cobra.Command {
	var yes bool
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "delete <salon_id>",
		Short: "Delete a Salon (owner only)",
		Long: `Permanently delete a Salon. Only the salon owner can do this. Requires confirmation unless --yes is provided.

Examples:
  hivo salon delete salon_abc --yes
  hivo salon delete salon_abc
  hivo salon delete salon_abc --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "salon_id": salonID})
				return exitcode.DryRunError{Preview: string(out)}
			}

			if !yes {
				if !exitcode.IsTTY() {
					writeErr(format, "usage_error", "Destructive action requires --yes in non-interactive mode", "", false)
					return &apiError{code: "usage_error", exitCode: exitcode.Usage}
				}
				fmt.Fprintf(os.Stderr, "Delete salon %s? This cannot be undone. [y/N] ", salonID)
				reader := bufio.NewReader(os.Stdin)
				line, _ := reader.ReadString('\n')
				if !strings.HasPrefix(strings.ToLower(strings.TrimSpace(line)), "y") {
					fmt.Fprintln(os.Stderr, "Aborted.")
					return nil
				}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("DELETE", salonURL()+"/salons/"+salonID, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}
			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "deleted", "salon_id": salonID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Deleted salon: %s\n", salonID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview delete without executing (exit 10)")
	return cmd
}
