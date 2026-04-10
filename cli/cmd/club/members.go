package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newMembersCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "members <club_id>",
		Short: "List members of a Club",
		Long: `List all members of a Club.

Examples:
  hivo club members club_abc123
  hivo club members club_abc123 --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", clubURL()+"/clubs/"+args[0]+"/members", token, nil)
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
				members, _ := result["members"].([]interface{})
				for _, m := range members {
					if member, ok := m.(map[string]interface{}); ok {
						handle, _ := member["handle"].(string)
						if handle == "" {
							handle = "-"
						}
						displayName, _ := member["display_name"].(string)
						if displayName == "" {
							displayName = "-"
						}
						fmt.Printf("%s  %-25s  %-20s  %s\n", member["sub"], handle, displayName, member["role"])
					}
				}
			}
			return nil
		},
	}
}
