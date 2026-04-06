package drop

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

	cmd := &cobra.Command{
		Use:   "delete <remote_path>",
		Short: "Delete a file from hivo-drop",
		Long: `Delete a file from hivo-drop. Requires confirmation unless --yes is provided.

Examples:
  hivo drop delete docs/old-report.html --yes
  hivo drop delete docs/old-report.html`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			remotePath := args[0]

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
	return cmd
}
