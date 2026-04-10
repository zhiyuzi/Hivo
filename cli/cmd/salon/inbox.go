package salon

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newInboxCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "inbox",
		Short: "View your unread salon messages",
		Long: `View your inbox — a summary of unread messages across all salons you belong to.

Examples:
  hivo salon inbox
  hivo salon inbox --format json`,
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", salonURL()+"/inbox", token, nil)
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
				entries, _ := result["inbox"].([]interface{})
				if len(entries) == 0 {
					fmt.Println("No unread messages.")
					return nil
				}
				for _, e := range entries {
					entry, _ := e.(map[string]interface{})
					salonID, _ := entry["salon_id"].(string)
					salonName, _ := entry["salon_name"].(string)
					clubID, _ := entry["club_id"].(string)
					unread, _ := entry["unread_count"].(float64)
					hasMention, _ := entry["has_mention"].(bool)
					lastMsg, _ := entry["last_message_at"].(string)
					mentionTag := ""
					if hasMention {
						mentionTag = " [mentioned]"
					}
					fmt.Printf("  %s (%s)  club:%s  unread:%d  last:%s%s\n", salonName, salonID, clubID, int(unread), lastMsg, mentionTag)
				}
			}
			return nil
		},
	}
}
