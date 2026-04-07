package drop

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
		Use:   "delete <remote_path>",
		Short: "Delete a file from hivo-drop",
		Long: `Delete a file from hivo-drop. Requires confirmation unless --yes is provided.

Examples:
  hivo drop delete docs/old-report.html --yes
  hivo drop delete docs/old-report.html
  hivo drop delete docs/old-report.html --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			remotePath := args[0]

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "path": remotePath})
				return exitcode.DryRunError{Preview: string(out)}
			}

			if !yes {
				fmt.Fprintf(os.Stderr, "Delete %s? [y/N] ", remotePath)
				reader := bufio.NewReader(os.Stdin)
				line, _ := reader.ReadString('\n')
				if !strings.HasPrefix(strings.ToLower(strings.TrimSpace(line)), "y") {
					fmt.Fprintln(os.Stderr, "Aborted.")
					return nil
				}
			}

			token, err := getToken(format)
			if err != nil {
				return err
			}

			result, status, err := doRequest("DELETE", dropURL()+"/files/"+remotePath, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "deleted", "path": remotePath})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Deleted: %s\n", remotePath)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview delete without executing (exit 10)")
	return cmd
}
