package salon

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newListCmd() *cobra.Command {
	var clubID string

	cmd := &cobra.Command{
		Use:   "list --club-id <club_id>",
		Short: "List Salons in a Club",
		Long: `List all Salons in a Club.

Examples:
  hivo salon list --club-id club_abc123
  hivo salon list --club-id club_abc123 --format json`,
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())

			if clubID == "" {
				writeErr(format, "usage_error", "--club-id is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			result, status, err := doRequest("GET", salonURL()+"/salons?club_id="+clubID, token, nil)
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
				salons, _ := result["salons"].([]interface{})
				if len(salons) == 0 {
					fmt.Println("No salons.")
					return nil
				}
				for _, s := range salons {
					sm, _ := s.(map[string]interface{})
					id, _ := sm["id"].(string)
					name, _ := sm["name"].(string)
					fmt.Printf("  %s  %s\n", id, name)
				}
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&clubID, "club-id", "", "Club ID to list salons for (required)")
	return cmd
}
