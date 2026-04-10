package salon

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newFilesCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "files",
		Short: "Manage salon shared files",
		Long: `Manage shared files in a Salon.

Examples:
  hivo salon files add salon_abc file_xyz --alias docs/report.html
  hivo salon files list salon_abc
  hivo salon files remove salon_abc file_xyz --yes`,
	}

	cmd.AddCommand(newFilesAddCmd())
	cmd.AddCommand(newFilesListCmd())
	cmd.AddCommand(newFilesRemoveCmd())
	return cmd
}

func newFilesAddCmd() *cobra.Command {
	var alias, permissions string
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "add <salon_id> <file_id>",
		Short: "Register a file to a Salon",
		Long: `Register a Drop file to a Salon's shared file space.

The file must already exist in hivo-drop and you must be its owner.

Examples:
  hivo salon files add salon_abc file_xyz --alias docs/report.html
  hivo salon files add salon_abc file_xyz --alias notes.md --permissions read,write
  hivo salon files add salon_abc file_xyz --alias notes.md --dry-run`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]
			fileID := args[1]

			if alias == "" {
				writeErr(format, "usage_error", "--alias is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{
					"dry_run":     true,
					"salon_id":    salonID,
					"file_id":     fileID,
					"alias":       alias,
					"permissions": permissions,
				})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{
				"file_id":     fileID,
				"alias":       alias,
				"permissions": permissions,
			}

			result, status, err := doRequest("POST", salonURL()+"/salons/"+salonID+"/files", token, body)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(result)
				fmt.Println(string(out))
			} else {
				a, _ := result["alias"].(string)
				fid, _ := result["file_id"].(string)
				fmt.Printf("Added: %s (file_id: %s)\n", a, fid)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&alias, "alias", "", "Display path in the salon file space (required)")
	cmd.Flags().StringVar(&permissions, "permissions", "read", "Permissions to grant: read | read,write")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}

func newFilesListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list <salon_id>",
		Short: "List shared files in a Salon",
		Long: `List all shared files registered in a Salon.

Examples:
  hivo salon files list salon_abc
  hivo salon files list salon_abc --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			result, status, err := doRequest("GET", salonURL()+"/salons/"+salonID+"/files", token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(result)
				fmt.Println(string(out))
			} else {
				files, _ := result["files"].([]interface{})
				if len(files) == 0 {
					fmt.Println("No shared files.")
					return nil
				}
				for _, f := range files {
					fm, _ := f.(map[string]interface{})
					a, _ := fm["alias"].(string)
					fid, _ := fm["file_id"].(string)
					perms, _ := fm["permissions"].(string)
					owner, _ := fm["owner_sub"].(string)
					ownerHandle, _ := fm["owner_handle"].(string)
					if ownerHandle != "" {
						owner = ownerHandle
					}
					fmt.Printf("  %s  (file_id: %s, permissions: %s, owner: %s)\n", a, fid, perms, owner)
				}
			}
			return nil
		},
	}
}

func newFilesRemoveCmd() *cobra.Command {
	var yes, dryRun bool

	cmd := &cobra.Command{
		Use:   "remove <salon_id> <file_id>",
		Short: "Remove a shared file from a Salon",
		Long: `Remove a file from a Salon's shared file space.

This only unregisters the file from the salon and revokes the salon's ACL grants.
The file itself remains in hivo-drop under the owner's account.

Examples:
  hivo salon files remove salon_abc file_xyz --yes
  hivo salon files remove salon_abc file_xyz
  hivo salon files remove salon_abc file_xyz --dry-run`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]
			fileID := args[1]

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "salon_id": salonID, "file_id": fileID})
				return exitcode.DryRunError{Preview: string(out)}
			}

			if !yes {
				if !exitcode.IsTTY() {
					writeErr(format, "usage_error", "Destructive action requires --yes in non-interactive mode", "", false)
					return &apiError{code: "usage_error", exitCode: exitcode.Usage}
				}
				fmt.Fprintf(os.Stderr, "Remove file %s from salon %s? [y/N] ", fileID, salonID)
				reader := bufio.NewReader(os.Stdin)
				line, _ := reader.ReadString('\n')
				if !strings.HasPrefix(strings.ToLower(strings.TrimSpace(line)), "y") {
					fmt.Fprintln(os.Stderr, "Aborted.")
					return nil
				}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			result, status, err := doRequest("DELETE", salonURL()+"/salons/"+salonID+"/files/"+fileID, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "removed", "salon_id": salonID, "file_id": fileID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Removed file %s from salon %s\n", fileID, salonID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}
