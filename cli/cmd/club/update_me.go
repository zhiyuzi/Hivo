package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newUpdateMeCmd() *cobra.Command {
	var displayName, bio string

	cmd := &cobra.Command{
		Use:   "update-me <club_id>",
		Short: "Update your membership profile in a Club",
		Long: `Update your display name or bio within a specific Club.

Examples:
  hivo club update-me club_abc123 --display-name "My Alias"
  hivo club update-me club_abc123 --bio "Team bot"`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			if displayName == "" && bio == "" {
				writeErr(format, "usage_error", "At least one of --display-name or --bio is required", "", false)
				return fmt.Errorf("no fields provided")
			}
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			body := map[string]string{}
			if displayName != "" {
				body["display_name"] = displayName
			}
			if bio != "" {
				body["bio"] = bio
			}
			result, status, err := doRequest("PATCH", clubURL()+"/clubs/"+args[0]+"/me", token, body)
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
				fmt.Printf("Updated membership in: %s\n", args[0])
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&displayName, "display-name", "", "Display name in this club")
	cmd.Flags().StringVar(&bio, "bio", "", "Bio in this club")
	return cmd
}
