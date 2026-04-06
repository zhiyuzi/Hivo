package drop

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newShareCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "share <remote_path> <public|private>",
		Short: "Set file visibility to public or private",
		Long: `Set a file's visibility. Public files are accessible to anyone via a URL.

Examples:
  hivo drop share docs/report.html public
  hivo drop share docs/report.html private`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			remotePath := args[0]
			visibility := args[1]

			if visibility != "public" && visibility != "private" {
				writeErr(format, "usage_error", "visibility must be public or private", "Use: hivo drop share <path> public|private", false)
				return fmt.Errorf("invalid visibility: %s", visibility)
			}

			token, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{"visibility": visibility}
			result, status, err := doRequest("PATCH", dropURL()+"/files/"+remotePath+"/visibility", token, body)
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
	return cmd
}
