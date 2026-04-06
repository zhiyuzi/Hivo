package club

import "github.com/spf13/cobra"

func NewCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "club",
		Short: "Manage teams and organizations",
		Long: `Manage teams and organizations in the Hivo Club service.

Examples:
  hivo club create "My Team" --description "A project team"
  hivo club my
  hivo club info <club_id>`,
	}

	cmd.AddCommand(newCreateCmd())
	cmd.AddCommand(newInfoCmd())
	cmd.AddCommand(newMembersCmd())
	cmd.AddCommand(newInviteCmd())
	cmd.AddCommand(newJoinCmd())
	cmd.AddCommand(newLeaveCmd())
	cmd.AddCommand(newMyCmd())
	cmd.AddCommand(newUpdateCmd())
	cmd.AddCommand(newUpdateMeCmd())
	cmd.AddCommand(newInviteLinksCmd())
	cmd.AddCommand(newRevokeLinkCmd())
	return cmd
}
