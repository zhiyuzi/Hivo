package identity

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/config"
	identitylib "github.com/zhiyuzi/hivo/cli/internal/identity"
)

func newRegisterCmd() *cobra.Command {
	var issuer string

	cmd := &cobra.Command{
		Use:   "register <handle>",
		Short: "Register this agent with hivo-identity",
		Long: `Generate an Ed25519 keypair and register with the hivo-identity service.

Examples:
  hivo identity register mybot@acme
  hivo identity register mybot@acme --issuer https://id.hivo.ink

Writes to:
  .hivo/identity.json              (current directory — contains sub only)
  ~/.hivo/agents/{sub}/            (private key, registration, token cache)`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			handle := args[0]
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())

			if issuer == "" {
				if v := os.Getenv("HIVO_ISSUER_URL"); v != "" {
					issuer = v
				} else {
					issuer = "https://id.hivo.ink"
				}
			}

			// Generate keypair
			pemBytes, jwkBytes, priv, err := identitylib.GenerateKeypair()
			if err != nil {
				return writeError(format, "keygen_failed", "Failed to generate keypair", "", false, err)
			}

			// Register
			result, err := identitylib.Register(issuer, handle, priv, jwkBytes)
			if err != nil {
				return writeError(format, "register_failed", err.Error(), "Check handle format: name@namespace, 2-32 chars each", false, err)
			}

			// Write ~/.hivo/agents/{sub}/
			regJSON, _ := json.MarshalIndent(result, "", "  ")
			err = config.WriteAgentFiles(result.Sub, map[string][]byte{
				"private_key.pem":   pemBytes,
				"public_key.jwk":    jwkBytes,
				"registration.json": regJSON,
			})
			if err != nil {
				return writeError(format, "write_failed", "Failed to write credentials", "", false, err)
			}

			// Write .hivo/identity.json in cwd
			cwd, _ := os.Getwd()
			err = config.WriteWorkspaceIdentity(cwd, config.WorkspaceIdentity{Sub: result.Sub})
			if err != nil {
				return writeError(format, "write_failed", "Failed to write .hivo/identity.json", "", false, err)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{
					"sub":    result.Sub,
					"handle": result.Handle,
					"iss":    result.Iss,
				})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Registered: %s (%s)\n", result.Handle, result.Sub)
				fmt.Printf("Credentials written to ~/.hivo/agents/%s/\n", result.Sub)
				fmt.Printf("Workspace identity written to .hivo/identity.json\n")
			}
			return nil
		},
	}

	cmd.Flags().StringVar(&issuer, "issuer", "", "Identity service URL (default: https://id.hivo.ink)")
	return cmd
}
