package club

import "github.com/spf13/cobra"

func newFilesCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "files",
		Short: "Manage club shared files",
		Long: `Manage shared files in a Club.

Examples:
  hivo club files add <club_id> <file_id> --alias docs/report.html
  hivo club files list <club_id>
  hivo club files remove <club_id> <file_id> --yes`,
	}

	cmd.AddCommand(newFilesAddCmd())
	cmd.AddCommand(newFilesListCmd())
	cmd.AddCommand(newFilesRemoveCmd())
	return cmd
}
