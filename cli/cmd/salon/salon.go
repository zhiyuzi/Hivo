package salon

import "github.com/spf13/cobra"

func NewCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "salon",
		Short: "Salon management commands",
		Long: `Manage salons (group messaging channels) within Hivo clubs.

Examples:
  hivo salon create --club-id club_abc --name "General"
  hivo salon list --club-id club_abc
  hivo salon info salon_abc
  hivo salon message send salon_abc --text "Hello"
  hivo salon inbox`,
	}

	cmd.AddCommand(newCreateCmd())
	cmd.AddCommand(newInfoCmd())
	cmd.AddCommand(newListCmd())
	cmd.AddCommand(newUpdateCmd())
	cmd.AddCommand(newDeleteCmd())
	cmd.AddCommand(newMembersCmd())
	cmd.AddCommand(newMessageCmd())
	cmd.AddCommand(newInboxCmd())
	cmd.AddCommand(newReadCmd())
	cmd.AddCommand(newFilesCmd())
	return cmd
}
