package club

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newLeaveCmd() *cobra.Command {
	var yes bool
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "leave <club_id>",
		Short: "Leave a Club",
		Long: `Leave a Club. Requires confirmation unless --yes is provided.

Examples:
  hivo club leave club_abc123 --yes
  hivo club leave club_abc123
  hivo club leave club_abc123 --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			clubID := args[0]

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "club_id": clubID})
				fmt.Println(string(out))
				os.Exit(10)
			}

			if !yes {
				if !exitcode.IsTTY() {
					writeErr(format, "usage_error", "Destructive action requires --yes in non-interactive mode", "", false)
					return fmt.Errorf("usage_error: --yes required in non-interactive mode")
				}
				fmt.Fprintf(os.Stderr, "Leave club %s? [y/N] ", clubID)
				reader := bufio.NewReader(os.Stdin)
				line, _ := reader.ReadString('\n')
				if !strings.HasPrefix(strings.ToLower(strings.TrimSpace(line)), "y") {
					fmt.Fprintln(os.Stderr, "Aborted.")
					return nil
				}
			}

			token, reg, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("DELETE", clubURL()+"/clubs/"+clubID+"/members/"+reg.Sub, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}
			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "left", "club_id": clubID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Left club: %s\n", clubID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview leave without executing (exit 10)")
	return cmd
}
