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

func newFilesRemoveCmd() *cobra.Command {
	var yes bool
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "remove <club_id> <file_id>",
		Short: "Remove a shared file from a club",
		Long: `Remove a file from a Club's shared file space.

This only unregisters the file from the club and revokes the club's ACL grants.
The file itself remains in hivo-drop under the owner's account.

Examples:
  hivo club files remove club_abc123 file_xyz --yes
  hivo club files remove club_abc123 file_xyz
  hivo club files remove club_abc123 file_xyz --dry-run`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			clubID := args[0]
			fileID := args[1]

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "club_id": clubID, "file_id": fileID})
				return exitcode.DryRunError{Preview: string(out)}
			}

			if !yes {
				fmt.Fprintf(os.Stderr, "Remove file %s from club %s? [y/N] ", fileID, clubID)
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

			result, status, err := doRequest("DELETE", clubURL()+"/clubs/"+clubID+"/files/"+fileID, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "removed", "club_id": clubID, "file_id": fileID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Removed file %s from club %s\n", fileID, clubID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}
