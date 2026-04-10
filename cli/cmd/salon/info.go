package salon

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newInfoCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "info <salon_id>",
		Short: "View Salon info",
		Long: `View details of a Salon.

Examples:
  hivo salon info salon_abc123
  hivo salon info salon_abc123 --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", salonURL()+"/salons/"+args[0], token, nil)
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
				for _, f := range []string{"id", "club_id", "name", "bulletin", "owner_sub", "owner_handle", "created_at", "updated_at"} {
					if v, ok := result[f]; ok && v != nil {
						fmt.Printf("%-14s %v\n", f+":", v)
					}
				}
			}
			return nil
		},
	}
}
