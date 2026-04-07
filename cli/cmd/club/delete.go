package club

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

func newDeleteCmd() *cobra.Command {
	var yes bool
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "delete <club_id>",
		Short: "Delete a Club (owner only)",
		Long: `Permanently delete a Club. Only the owner can do this. Requires confirmation unless --yes is provided.

Examples:
  hivo club delete club_abc123 --yes
  hivo club delete club_abc123
  hivo club delete club_abc123 --dry-run`,
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
				fmt.Fprintf(os.Stderr, "Delete club %s? This cannot be undone. [y/N] ", clubID)
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
			result, status, err := doRequest("DELETE", clubURL()+"/clubs/"+clubID, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}
			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "deleted", "club_id": clubID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Deleted club: %s\n", clubID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview delete without executing (exit 10)")
	return cmd
}
