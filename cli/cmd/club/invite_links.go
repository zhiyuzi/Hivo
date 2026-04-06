package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newInviteLinksCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "invite-links <club_id>",
		Short: "List all invite links for a Club (owner/admin only)",
		Long: `List all active invite links for a Club. Requires owner or admin role.

Examples:
  hivo club invite-links club_abc123
  hivo club invite-links club_abc123 --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", clubURL()+"/clubs/"+args[0]+"/invite-links", token, nil)
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
				links, _ := result["invite_links"].([]interface{})
				if len(links) == 0 {
					fmt.Println("No invite links.")
					return nil
				}
				for _, l := range links {
					if link, ok := l.(map[string]interface{}); ok {
						fmt.Printf("%s  uses:%v/%v  expires:%v\n",
							link["token"], link["uses"], link["max_uses"], link["expires_at"])
					}
				}
			}
			return nil
		},
	}
}
