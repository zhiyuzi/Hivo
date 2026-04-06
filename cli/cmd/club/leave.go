package club

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

func newLeaveCmd() *cobra.Command {
	var yes bool

	cmd := &cobra.Command{
		Use:   "leave <club_id>",
		Short: "Leave a Club",
		Long: `Leave a Club. Requires confirmation unless --yes is provided.

Examples:
  hivo club leave club_abc123 --yes
  hivo club leave club_abc123`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			clubID := args[0]

			if !yes {
				fmt.Fprintf(os.Stderr, "Leave club %s? [y/N] ", clubID)
				reader := bufio.NewReader(os.Stdin)
				line, _ := reader.ReadString('\n')
				if !strings.HasPrefix(strings.ToLower(strings.TrimSpace(line)), "y") {
					fmt.Fprintln(os.Stderr, "Aborted.")
					return nil
				}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("DELETE", clubURL()+"/clubs/"+clubID+"/members/me", token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}
			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "left", "club_id": clubID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Left club: %s\n", clubID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	return cmd
}
