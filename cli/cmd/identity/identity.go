package identity

import "github.com/spf13/cobra"

func NewCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "identity",
		Short: "Manage this agent's identity credentials",
		Long: `Manage Ed25519 keypair and registration for this agent in the Hivo ecosystem.

Examples:
  hivo identity register mybot@acme
  hivo identity token hivo-drop
  hivo identity me`,
	}

	cmd.AddCommand(newRegisterCmd())
	cmd.AddCommand(newTokenCmd())
	cmd.AddCommand(newMeCmd())
	cmd.AddCommand(newUpdateCmd())
	cmd.AddCommand(newResolveCmd())
	return cmd
}
