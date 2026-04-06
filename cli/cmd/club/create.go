package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newCreateCmd() *cobra.Command {
	var description string

	cmd := &cobra.Command{
		Use:   "create <name>",
		Short: "Create a new Club",
		Long: `Create a new Club in the Hivo Club service.

Examples:
  hivo club create "My Team"
  hivo club create "My Team" --description "A project team"`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{"name": args[0]}
			if description != "" {
				body["description"] = description
			}

			result, status, err := doRequest("POST", clubURL()+"/clubs", token, body)
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
				id, _ := result["club_id"].(string)
				name, _ := result["name"].(string)
				fmt.Printf("Created: %s — %s\n", id, name)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&description, "description", "", "Club description")
	return cmd
}
