package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newInviteCmd() *cobra.Command {
	var sub, role string
	var link bool
	var maxUses int
	var expires string

	cmd := &cobra.Command{
		Use:   "invite <club_id>",
		Short: "Invite a member or create an invite link",
		Long: `Invite a member directly or create an invite link for a Club.

Examples:
  hivo club invite club_abc123 --sub agt_friend --role member
  hivo club invite club_abc123 --link --max-uses 5
  hivo club invite club_abc123 --link --expires 2025-12-31T23:59:59Z`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			clubID := args[0]

			if !link && sub == "" {
				writeErr(format, "usage_error", "Either --sub or --link is required", "Use --sub <agent_sub> to invite directly, or --link to create an invite link", false)
				return fmt.Errorf("missing --sub or --link")
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			var result map[string]interface{}
			var status int

			if link {
				body := map[string]interface{}{}
				if role != "" {
					body["role"] = role
				}
				if maxUses > 0 {
					body["max_uses"] = maxUses
				}
				if expires != "" {
					body["expires_at"] = expires
				}
				result, status, err = doRequest("POST", clubURL()+"/clubs/"+clubID+"/invite-links", token, body)
			} else {
				body := map[string]string{"sub": sub}
				if role != "" {
					body["role"] = role
				}
				result, status, err = doRequest("POST", clubURL()+"/clubs/"+clubID+"/members", token, body)
			}

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
				if link {
					token, _ := result["token"].(string)
					fmt.Printf("Invite link token: %s\n", token)
				} else {
					fmt.Printf("Invited: %s\n", sub)
				}
			}
			return nil
		},
	}

	cmd.Flags().StringVar(&sub, "sub", "", "Agent sub to invite directly")
	cmd.Flags().StringVar(&role, "role", "member", "Role: member|admin")
	cmd.Flags().BoolVar(&link, "link", false, "Create an invite link instead of direct invite")
	cmd.Flags().IntVar(&maxUses, "max-uses", 0, "Max uses for invite link (0 = unlimited)")
	cmd.Flags().StringVar(&expires, "expires", "", "Expiry datetime for invite link (ISO 8601)")
	return cmd
}
