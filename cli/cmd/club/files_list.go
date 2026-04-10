package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newFilesListCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "list <club_id>",
		Short: "List shared files in a club",
		Long: `List all shared files registered in a Club.

Examples:
  hivo club files list club_abc123`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			clubID := args[0]

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			result, status, err := doRequest("GET", clubURL()+"/clubs/"+clubID+"/files", token, nil)
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
				files, _ := result["files"].([]interface{})
				if len(files) == 0 {
					fmt.Println("No shared files.")
					return nil
				}
				for _, f := range files {
					fm, _ := f.(map[string]interface{})
					alias, _ := fm["alias"].(string)
					fileID, _ := fm["file_id"].(string)
					perms, _ := fm["permissions"].(string)
					owner, _ := fm["owner_sub"].(string)
					ownerHandle, _ := fm["owner_handle"].(string)
					if ownerHandle != "" {
						owner = ownerHandle
					}
					fmt.Printf("  %s  (file_id: %s, permissions: %s, owner: %s)\n", alias, fileID, perms, owner)
				}
			}
			return nil
		},
	}
	return cmd
}
