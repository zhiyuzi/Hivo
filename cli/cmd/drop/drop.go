package drop

import "github.com/spf13/cobra"

func NewCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "drop",
		Short: "Manage files in Hivo Drop storage",
		Long: `Manage files in the Hivo Drop storage service.

Examples:
  hivo drop upload ./report.html docs/report.html
  hivo drop list docs/
  hivo drop share docs/report.html public`,
	}

	cmd.AddCommand(newUploadCmd())
	cmd.AddCommand(newDownloadCmd())
	cmd.AddCommand(newDeleteCmd())
	cmd.AddCommand(newListCmd())
	cmd.AddCommand(newShareCmd())
	return cmd
}
