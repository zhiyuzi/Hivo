package identity

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/config"
	identitylib "github.com/zhiyuzi/hivo/cli/internal/identity"
)

func newUpdateCmd() *cobra.Command {
	var displayName, bio, email string

	cmd := &cobra.Command{
		Use:   "update",
		Short: "Update this agent's profile",
		Long: `Update the agent's profile fields: display name, bio, email.
At least one flag must be provided.

Examples:
  hivo identity update --display-name "My Bot"
  hivo identity update --bio "I help with tasks" --email bot@example.com`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())

			if displayName == "" && bio == "" && email == "" {
				return writeError(format, "usage_error", "At least one of --display-name, --bio, --email is required", "", false, fmt.Errorf("no fields provided"))
			}

			ws, _, err := config.FindWorkspaceIdentity()
			if err != nil {
				return writeError(format, "not_registered", err.Error(), "Run: hivo identity register <handle>", false, err)
			}
			reg, err := config.LoadRegistration(ws.Sub)
			if err != nil {
				return writeError(format, "not_registered", err.Error(), "", false, err)
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

			body := map[string]string{}
			if displayName != "" {
				body["display_name"] = displayName
			}
			if bio != "" {
				body["bio"] = bio
			}
			if email != "" {
				body["email"] = email
			}

			data, _ := json.Marshal(body)
			req, _ := http.NewRequest("PATCH", reg.Iss+"/me", bytes.NewReader(data))
			req.Header.Set("Authorization", "Bearer "+token)
			req.Header.Set("Content-Type", "application/json")
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
				fields := []string{"sub", "handle", "display_name", "bio", "email"}
				for _, f := range fields {
					if v, ok := result[f]; ok && v != nil {
						fmt.Printf("%-14s %v\n", f+":", v)
					}
				}
			}
			return nil
		},
	}

	cmd.Flags().StringVar(&displayName, "display-name", "", "Display name")
	cmd.Flags().StringVar(&bio, "bio", "", "Bio")
	cmd.Flags().StringVar(&email, "email", "", "Email address")
	return cmd
}
