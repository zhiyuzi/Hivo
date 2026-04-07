package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newUpdateMemberCmd() *cobra.Command {
	var role string

	cmd := &cobra.Command{
		Use:   "update-member <club_id> <sub>",
		Short: "Change a member's role (owner/admin only)",
		Long: `Change the role of a club member. Only owner or admin can do this.
Role must be 'member' or 'admin'. Cannot change the owner's role or your own role.

Examples:
  hivo club update-member club_abc123 agt_xyz --role admin
  hivo club update-member club_abc123 agt_xyz --role member`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			clubID := args[0]
			targetSub := args[1]

			if role != "member" && role != "admin" {
				writeErr(format, "usage_error", "role must be 'member' or 'admin'", "Use: --role member|admin", false)
				return fmt.Errorf("invalid role: %s", role)
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{"role": role}
			result, status, err := doRequest("PATCH", clubURL()+"/clubs/"+clubID+"/members/"+targetSub, token, body)
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
				fmt.Printf("Updated %s role to %s in club %s\n", targetSub, role, clubID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&role, "role", "", "New role: member or admin (required)")
	cmd.MarkFlagRequired("role")
	return cmd
}
