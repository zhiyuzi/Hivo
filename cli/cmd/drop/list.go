package drop

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"

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
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, err := getToken(format)
			if err != nil {
				return err
			}

			url := dropURL() + "/list"
			if len(args) == 1 {
				url += "?prefix=" + args[0]
			}

			req, _ := http.NewRequest("GET", url, nil)
			req.Header.Set("Authorization", "Bearer "+token)
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			defer resp.Body.Close()
			raw, _ := io.ReadAll(resp.Body)

			if resp.StatusCode >= 400 {
				var errResult map[string]interface{}
				_ = json.Unmarshal(raw, &errResult)
				return handleAPIError(format, errResult, resp.StatusCode)
			}

			// Server returns a JSON array directly
			var files []map[string]interface{}
			if err := json.Unmarshal(raw, &files); err != nil {
				writeErr(format, "parse_error", "Failed to parse response", "", false)
				return err
			}

			if format == "json" {
				// Wrap in {"files": [...]} for consistent agent consumption
				out, _ := json.Marshal(map[string]interface{}{"files": files})
				fmt.Println(string(out))
			} else {
				if len(files) == 0 {
					fmt.Println("No files.")
					return nil
				}
				fmt.Printf("%-40s  %-12s  %-10s  %s\n", "PATH", "SIZE", "VISIBILITY", "CONTENT_TYPE")
				for _, file := range files {
					fmt.Printf("%-40s  %-12v  %-10v  %v\n",
						file["path"], file["size"], file["visibility"], file["content_type"])
				}
			}
			return nil
		},
	}
	return cmd
}
