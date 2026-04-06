package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newRevokeLinkCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "revoke-link <club_id> <token>",
		Short: "Revoke an invite link (owner/admin only)",
		Long: `Revoke an invite link for a Club. Requires owner or admin role.

Examples:
  hivo club revoke-link club_abc123 abc123token`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("DELETE", clubURL()+"/clubs/"+args[0]+"/invite-links/"+args[1], token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}
			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "revoked", "token": args[1]})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Revoked invite link: %s\n", args[1])
			}
			return nil
		},
	}
}
