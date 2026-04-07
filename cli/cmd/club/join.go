package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newJoinCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "join <token>",
		Short: "Join a Club via invite link token",
		Long: `Join a Club using an invite link token.

Examples:
  hivo club join abc123token`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("POST", clubURL()+"/join/"+args[0], token, nil)
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
				clubID, _ := result["club_id"].(string)
				fmt.Printf("Joined club: %s\n", clubID)
			}
			return nil
		},
	}
}
