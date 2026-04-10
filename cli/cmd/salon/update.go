package salon

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newUpdateCmd() *cobra.Command {
	var name, bulletin string
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "update <salon_id>",
		Short: "Update a Salon's name or bulletin",
		Long: `Update a Salon's name or bulletin. Requires owner or admin role.

Examples:
  hivo salon update salon_abc --name "New Name"
  hivo salon update salon_abc --bulletin "Updated bulletin"
  hivo salon update salon_abc --name "New" --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if name == "" && bulletin == "" {
				writeErr(format, "usage_error", "At least one of --name or --bulletin is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			if dryRun {
				preview := map[string]interface{}{"dry_run": true, "salon_id": salonID}
				if name != "" {
					preview["name"] = name
				}
				if bulletin != "" {
					preview["bulletin"] = bulletin
				}
				out, _ := json.Marshal(preview)
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{}
			if name != "" {
				body["name"] = name
			}
			if bulletin != "" {
				body["bulletin"] = bulletin
			}

			result, status, err := doRequest("PATCH", salonURL()+"/salons/"+salonID, token, body)
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
				fmt.Printf("Updated: %s\n", salonID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&name, "name", "", "New salon name")
	cmd.Flags().StringVar(&bulletin, "bulletin", "", "New salon bulletin")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview update without executing (exit 10)")
	return cmd
}
