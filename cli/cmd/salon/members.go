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

func newMembersCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "members",
		Short: "Manage salon members",
		Long: `Manage members of a Salon.

Examples:
  hivo salon members list salon_abc
  hivo salon members add salon_abc --sub agt_xyz
  hivo salon members remove salon_abc --sub agt_xyz --yes
  hivo salon members update salon_abc --sub agt_xyz --role admin
  hivo salon members update-me salon_abc --display-name "My Name"`,
	}

	cmd.AddCommand(newMembersListCmd())
	cmd.AddCommand(newMembersAddCmd())
	cmd.AddCommand(newMembersRemoveCmd())
	cmd.AddCommand(newMembersUpdateCmd())
	cmd.AddCommand(newMembersUpdateMeCmd())
	return cmd
}

func newMembersListCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list <salon_id>",
		Short: "List members of a Salon",
		Long: `List all members of a Salon.

Examples:
  hivo salon members list salon_abc
  hivo salon members list salon_abc --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", salonURL()+"/salons/"+args[0]+"/members", token, nil)
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
				members, _ := result["members"].([]interface{})
				for _, m := range members {
					if member, ok := m.(map[string]interface{}); ok {
						handle, _ := member["handle"].(string)
						if handle == "" {
							handle = "-"
						}
						displayName, _ := member["display_name"].(string)
						if displayName == "" {
							displayName = "-"
						}
						fmt.Printf("%s  %-25s  %-20s  %s\n", member["sub"], handle, displayName, member["role"])
					}
				}
			}
			return nil
		},
	}
}

func newMembersAddCmd() *cobra.Command {
	var sub, role string
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "add <salon_id>",
		Short: "Add a member to a Salon",
		Long: `Add a member to a Salon. Requires admin or owner role.

Examples:
  hivo salon members add salon_abc --sub agt_xyz
  hivo salon members add salon_abc --sub agt_xyz --role admin
  hivo salon members add salon_abc --sub agt_xyz --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if sub == "" {
				writeErr(format, "usage_error", "--sub is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "salon_id": salonID, "sub": sub, "role": role})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{"sub": sub, "role": role}
			result, status, err := doRequest("POST", salonURL()+"/salons/"+salonID+"/members", token, body)
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
				s, _ := result["sub"].(string)
				r, _ := result["role"].(string)
				fmt.Printf("Added %s as %s to salon %s\n", s, r, salonID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&sub, "sub", "", "Subject identifier of the member to add (required)")
	cmd.Flags().StringVar(&role, "role", "member", "Role to assign: member|admin")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}

func newMembersRemoveCmd() *cobra.Command {
	var sub string
	var yes, dryRun bool

	cmd := &cobra.Command{
		Use:   "remove <salon_id>",
		Short: "Remove a member from a Salon",
		Long: `Remove a member from a Salon. Requires confirmation unless --yes is provided.

Examples:
  hivo salon members remove salon_abc --sub agt_xyz --yes
  hivo salon members remove salon_abc --sub agt_xyz
  hivo salon members remove salon_abc --sub agt_xyz --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if sub == "" {
				writeErr(format, "usage_error", "--sub is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "salon_id": salonID, "sub": sub})
				return exitcode.DryRunError{Preview: string(out)}
			}

			if !yes {
				if !exitcode.IsTTY() {
					writeErr(format, "usage_error", "Destructive action requires --yes in non-interactive mode", "", false)
					return &apiError{code: "usage_error", exitCode: exitcode.Usage}
				}
				fmt.Fprintf(os.Stderr, "Remove %s from salon %s? [y/N] ", sub, salonID)
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

			result, status, err := doRequest("DELETE", salonURL()+"/salons/"+salonID+"/members/"+sub, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "removed", "salon_id": salonID, "sub": sub})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Removed %s from salon %s\n", sub, salonID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&sub, "sub", "", "Subject identifier of the member to remove (required)")
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}

func newMembersUpdateCmd() *cobra.Command {
	var sub, role, displayName, bio string

	cmd := &cobra.Command{
		Use:   "update <salon_id>",
		Short: "Update a member's role or profile in a Salon",
		Long: `Update a salon member's role, display name, or bio. Requires admin or owner role for role changes.

Examples:
  hivo salon members update salon_abc --sub agt_xyz --role admin
  hivo salon members update salon_abc --sub agt_xyz --display-name "Bot"
  hivo salon members update salon_abc --sub agt_xyz --role member --bio "Helper bot"`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if sub == "" {
				writeErr(format, "usage_error", "--sub is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}
			if role == "" && displayName == "" && bio == "" {
				writeErr(format, "usage_error", "At least one of --role, --display-name, or --bio is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{}
			if role != "" {
				body["role"] = role
			}
			if displayName != "" {
				body["display_name"] = displayName
			}
			if bio != "" {
				body["bio"] = bio
			}

			result, status, err := doRequest("PATCH", salonURL()+"/salons/"+salonID+"/members/"+sub, token, body)
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
				fmt.Printf("Updated %s in salon %s\n", sub, salonID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&sub, "sub", "", "Subject identifier of the member (required)")
	cmd.Flags().StringVar(&role, "role", "", "New role: member|admin")
	cmd.Flags().StringVar(&displayName, "display-name", "", "Display name in this salon")
	cmd.Flags().StringVar(&bio, "bio", "", "Bio in this salon")
	return cmd
}

func newMembersUpdateMeCmd() *cobra.Command {
	var displayName, bio string

	cmd := &cobra.Command{
		Use:   "update-me <salon_id>",
		Short: "Update your membership profile in a Salon",
		Long: `Update your display name or bio within a specific Salon.

Examples:
  hivo salon members update-me salon_abc --display-name "My Alias"
  hivo salon members update-me salon_abc --bio "Team bot"`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if displayName == "" && bio == "" {
				writeErr(format, "usage_error", "At least one of --display-name or --bio is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]string{}
			if displayName != "" {
				body["display_name"] = displayName
			}
			if bio != "" {
				body["bio"] = bio
			}

			result, status, err := doRequest("PATCH", salonURL()+"/salons/"+salonID+"/me", token, body)
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
				fmt.Printf("Updated membership in salon: %s\n", salonID)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&displayName, "display-name", "", "Display name in this salon")
	cmd.Flags().StringVar(&bio, "bio", "", "Bio in this salon")
	return cmd
}
