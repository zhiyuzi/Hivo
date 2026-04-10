package salon

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newCreateCmd() *cobra.Command {
	var clubID, name, bulletin string
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "create --club-id <club_id> --name <name>",
		Short: "Create a new Salon in a Club",
		Long: `Create a new Salon (messaging channel) within a Club.

Examples:
  hivo salon create --club-id club_abc --name "General"
  hivo salon create --club-id club_abc --name "Ops" --bulletin "Ops channel"
  hivo salon create --club-id club_abc --name "Test" --dry-run`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())

			if clubID == "" {
				writeErr(format, "usage_error", "--club-id is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}
			if name == "" {
				writeErr(format, "usage_error", "--name is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "club_id": clubID, "name": name, "bulletin": bulletin})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{"name": name, "club_id": clubID}
			if bulletin != "" {
				body["bulletin"] = bulletin
			}

			result, status, err := doRequest("POST", salonURL()+"/salons", token, body)
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
				id, _ := result["id"].(string)
				n, _ := result["name"].(string)
				fmt.Printf("Created: %s — %s\n", id, n)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&clubID, "club-id", "", "Club ID to create the salon in (required)")
	cmd.Flags().StringVar(&name, "name", "", "Salon name (required)")
	cmd.Flags().StringVar(&bulletin, "bulletin", "", "Salon bulletin text")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview create without executing (exit 10)")
	return cmd
}
