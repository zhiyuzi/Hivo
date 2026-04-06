package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newUpdateCmd() *cobra.Command {
	var name, description string

	cmd := &cobra.Command{
		Use:   "update <club_id>",
		Short: "Update a Club's name or description (owner/admin only)",
		Long: `Update a Club's name or description. Requires owner or admin role.

Examples:
  hivo club update club_abc123 --name "New Name"
  hivo club update club_abc123 --description "Updated description"`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			if name == "" && description == "" {
				writeErr(format, "usage_error", "At least one of --name or --description is required", "", false)
				return fmt.Errorf("no fields provided")
			}
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			body := map[string]string{}
			if name != "" {
				body["name"] = name
			}
			if description != "" {
				body["description"] = description
			}
			result, status, err := doRequest("PATCH", clubURL()+"/clubs/"+args[0], token, body)
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
				fmt.Printf("Updated: %s\n", args[0])
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&name, "name", "", "New club name")
	cmd.Flags().StringVar(&description, "description", "", "New club description")
	return cmd
}
