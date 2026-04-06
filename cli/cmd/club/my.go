package club

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newMyCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "my",
		Short: "List all Clubs you belong to",
		Long: `List all Clubs the current agent belongs to.

Examples:
  hivo club my
  hivo club my --format json`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", clubURL()+"/clubs/my", token, nil)
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
				clubs, _ := result["clubs"].([]interface{})
				if len(clubs) == 0 {
					fmt.Println("No clubs.")
					return nil
				}
				for _, c := range clubs {
					if club, ok := c.(map[string]interface{}); ok {
						fmt.Printf("%s  %s  (%s)\n", club["club_id"], club["name"], club["role"])
					}
				}
			}
			return nil
		},
	}
}
