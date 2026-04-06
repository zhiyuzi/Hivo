package drop

import (
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
)

func newListCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "list [prefix]",
		Short: "List files in hivo-drop",
		Long: `List files in hivo-drop, optionally filtered by path prefix.

Examples:
  hivo drop list
  hivo drop list docs/
  hivo drop list --format json`,
		Args: cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			token, err := getToken(format)
			if err != nil {
				return err
			}

			url := defaultDropURL + "/files"
			if len(args) == 1 {
				url += "?prefix=" + args[0]
			}

			result, status, err := doRequest("GET", url, token, nil)
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
				files, _ := result["files"].([]interface{})
				if len(files) == 0 {
					fmt.Println("No files.")
					return nil
				}
				fmt.Printf("%-40s  %-12s  %-10s  %s\n", "PATH", "SIZE", "VISIBILITY", "CONTENT_TYPE")
				for _, f := range files {
					if file, ok := f.(map[string]interface{}); ok {
						fmt.Printf("%-40s  %-12v  %-10v  %v\n",
							file["path"], file["size"], file["visibility"], file["content_type"])
					}
				}
			}
			return nil
		},
	}
	return cmd
}
