package identity

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/config"
	identitylib "github.com/zhiyuzi/hivo/cli/internal/identity"
)

func newTokenCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "token <audience>",
		Short: "Get a Bearer access token for a target service",
		Long: `Get a Bearer access token for the specified audience service.
Handles caching, refresh, and assertion flow automatically.

Examples:
  hivo identity token hivo-drop
  hivo identity token hivo-club`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			audience := args[0]
			format, _ := cmd.Root().PersistentFlags().GetString("format")

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
				return writeError(format, "key_not_found", "Private key not found", "Run: hivo identity register <handle>", false, err)
			}

			priv, err := identitylib.LoadPrivateKey(privPEM)
			if err != nil {
				return writeError(format, "key_invalid", "Failed to load private key", "", false, err)
			}

			token, err := identitylib.GetToken(reg.Iss, ws.Sub, audience, priv, config.TokenCachePath(ws.Sub))
			if err != nil {
				return writeError(format, "token_failed", err.Error(), "", true, err)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{"access_token": token})
				fmt.Println(string(out))
			} else {
				fmt.Println(token)
			}
			return nil
		},
	}
	return cmd
}
