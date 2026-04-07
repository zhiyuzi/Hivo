package drop

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newShareCmd() *cobra.Command {
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "share <remote_path> <public|private>",
		Short: "Set file visibility to public or private",
		Long: `Set a file's visibility. Public files are accessible to anyone via a URL.

Examples:
  hivo drop share docs/report.html public
  hivo drop share docs/report.html private
  hivo drop share docs/report.html public --dry-run`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			remotePath := args[0]
			visibility := args[1]

			if visibility != "public" && visibility != "private" {
				writeErr(format, "usage_error", "visibility must be public or private", "Use: hivo drop share <path> public|private", false)
				return fmt.Errorf("invalid visibility: %s", visibility)
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "path": remotePath, "visibility": visibility})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{"visibility": visibility}
			result, status, err := doRequest("PATCH", dropURL()+"/files/"+remotePath, token, body)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(result)
				fmt.Println(string(out))
			} else {
				if visibility == "public" {
					shareID, _ := result["share_id"].(string)
					fmt.Printf("Public URL: %s/p/%s\n", dropURL(), shareID)
				} else {
					fmt.Println("File is now private. Share link revoked.")
				}
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview share change without executing (exit 10)")
	return cmd
}
