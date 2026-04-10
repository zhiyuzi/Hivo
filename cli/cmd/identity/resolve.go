package identity

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

func newResolveCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "resolve <handle-or-sub>",
		Short: "Resolve a handle to sub or vice versa",
		Long: `Look up an agent's public identity by handle or sub.

If the argument contains '@', it is treated as a handle.
If it starts with 'agt_', it is treated as a sub.

This is a public endpoint — no registration or token required.

Examples:
  hivo identity resolve writer@acme
  hivo identity resolve agt_01JV8Y...
  hivo identity resolve writer@acme --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			input := args[0]

			baseURL := os.Getenv("HIVO_ISSUER_URL")
			if baseURL == "" {
				baseURL = "https://id.hivo.ink"
			}

			var queryParam string
			if strings.Contains(input, "@") {
				queryParam = "handle=" + input
			} else if strings.HasPrefix(input, "agt_") {
				queryParam = "sub=" + input
			} else {
				return writeError(format, "usage_error",
					"Argument must be a handle (contains @) or a sub (starts with agt_)",
					"Example: hivo identity resolve writer@acme", false,
					fmt.Errorf("unrecognized input format: %s", input))
			}

			req, _ := http.NewRequest("GET", baseURL+"/resolve?"+queryParam, nil)
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				return writeError(format, "request_failed", err.Error(), "", true, err)
			}
			defer resp.Body.Close()
			raw, err := io.ReadAll(resp.Body)
			if err != nil {
				return writeError(format, "read_failed", "Failed to read response body", "", true, err)
			}

			var result map[string]interface{}
			if err := json.Unmarshal(raw, &result); err != nil {
				return writeError(format, "parse_failed", "Failed to parse response", "", false, err)
			}

			if resp.StatusCode >= 400 {
				errCode, _ := result["error"].(string)
				msg, _ := result["message"].(string)
				return writeError(format, errCode, msg, "", false, fmt.Errorf("%s: %s", errCode, msg))
			}

			if format == "json" {
				fmt.Println(string(raw))
			} else {
				fields := []string{"sub", "handle", "display_name"}
				for _, f := range fields {
					if v, ok := result[f]; ok && v != nil {
						fmt.Printf("%-14s %v\n", f+":", v)
					}
				}
			}
			return nil
		},
	}
	return cmd
}
