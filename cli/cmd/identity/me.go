package identity

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/config"
	identitylib "github.com/zhiyuzi/hivo/cli/internal/identity"
)

func newMeCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "me",
		Short: "Show this agent's identity info",
		Long: `Show the current agent's identity info from the identity service.

Examples:
  hivo identity me
  hivo identity me --format json`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())

			ws, _, err := config.FindWorkspaceIdentity()
			if err != nil {
				return writeError(format, "not_registered", err.Error(), "Run: hivo identity register <handle>", false, err)
			}

			reg, err := config.LoadRegistration(ws.Sub)
			if err != nil {
				return writeError(format, "not_registered", err.Error(), "Run: hivo identity register <handle>", false, err)
			}

			privPEM, err := os.ReadFile(config.PrivateKeyPath(ws.Sub))
			if err != nil {
				return writeError(format, "key_not_found", "Private key not found", "", false, err)
			}
			priv, err := identitylib.LoadPrivateKey(privPEM)
			if err != nil {
				return writeError(format, "key_invalid", "Failed to load private key", "", false, err)
			}

			token, err := identitylib.GetToken(reg.Iss, ws.Sub, "hivo-identity", priv, config.TokenCachePath(ws.Sub))
			if err != nil {
				return writeError(format, "token_failed", err.Error(), "", true, err)
			}

			req, _ := http.NewRequest("GET", reg.Iss+"/me", nil)
			req.Header.Set("Authorization", "Bearer "+token)
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
				fields := []string{"sub", "handle", "display_name", "bio", "email", "status", "created_at"}
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
