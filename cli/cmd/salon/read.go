package salon

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newReadCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "read <salon_id>",
		Short: "Mark a Salon as read",
		Long: `Mark all messages in a Salon as read (updates your read cursor).

Returns last_read_at, which can be used as --since in "message list" for incremental fetching.

Examples:
  hivo salon read salon_abc
  hivo salon read salon_abc --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			result, status, err := doRequest("POST", salonURL()+"/salons/"+salonID+"/read", token, nil)
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
				lastRead, _ := result["last_read_at"].(string)
				fmt.Printf("Marked %s as read at %s\n", salonID, lastRead)
			}
			return nil
		},
	}
}
