package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newFilesAddCmd() *cobra.Command {
	var alias string
	var permissions string
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "add <club_id> <file_id>",
		Short: "Register a file to a club",
		Long: `Register a Drop file to a Club's shared file space.

The file must already exist in hivo-drop and you must be its owner.
Other club members will be granted read (default) or read,write access.

Examples:
  hivo club files add club_abc123 file_xyz --alias docs/report.html
  hivo club files add club_abc123 file_xyz --alias notes.md --permissions read,write
  hivo club files add club_abc123 file_xyz --alias notes.md --dry-run`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			clubID := args[0]
			fileID := args[1]

			if alias == "" {
				writeErr(format, "usage_error", "--alias is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{
					"dry_run":     true,
					"club_id":     clubID,
					"file_id":     fileID,
					"alias":       alias,
					"permissions": permissions,
				})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{
				"file_id":     fileID,
				"alias":       alias,
				"permissions": permissions,
			}

			result, status, err := doRequest("POST", clubURL()+"/clubs/"+clubID+"/files", token, body)
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
				a, _ := result["alias"].(string)
				fid, _ := result["file_id"].(string)
				fmt.Printf("Added: %s (file_id: %s)\n", a, fid)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&alias, "alias", "", "Display path in the club file space (required)")
	cmd.Flags().StringVar(&permissions, "permissions", "read", "Permissions to grant: read | read,write")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}
