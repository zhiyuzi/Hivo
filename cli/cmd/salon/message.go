package salon

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newMessageCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "message",
		Short: "Manage salon messages",
		Long: `Send, list, get, and delete messages in a Salon.

Examples:
  hivo salon message send salon_abc --text "Hello"
  hivo salon message list salon_abc
  hivo salon message get msg_abc
  hivo salon message delete msg_abc --yes`,
	}

	cmd.AddCommand(newMessageSendCmd())
	cmd.AddCommand(newMessageListCmd())
	cmd.AddCommand(newMessageGetCmd())
	cmd.AddCommand(newMessageDeleteCmd())
	return cmd
}

func newMessageSendCmd() *cobra.Command {
	var text string
	var mentions []string
	var files []string
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "send <salon_id>",
		Short: "Send a message to a Salon",
		Long: `Send a message to a Salon. Build content blocks from --text, --mention, and --file flags.

--mention accepts a handle (prefixed with @) or a sub identifier.
--mention and --file can be specified multiple times.

Examples:
  hivo salon message send salon_abc --text "Hello everyone"
  hivo salon message send salon_abc --text "Check this" --file file_xyz
  hivo salon message send salon_abc --text "Hey" --mention @alice --mention agt_bob
  hivo salon message send salon_abc --text "Draft" --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			if text == "" {
				writeErr(format, "usage_error", "--text is required", "", false)
				return &apiError{code: "usage_error", exitCode: exitcode.Usage}
			}

			// Build content blocks
			var content []map[string]interface{}
			content = append(content, map[string]interface{}{"type": "text", "text": text})

			for _, m := range mentions {
				block := map[string]interface{}{"type": "mention"}
				raw := strings.TrimPrefix(m, "@")
				if strings.Contains(raw, "@") {
					// It's a handle — resolve to sub
					resolved, err := resolveHandle(raw)
					if err != nil {
						writeErr(format, "resolve_failed", err.Error(), "Check the handle is correct", false)
						return &apiError{code: "resolve_failed", exitCode: exitcode.Err}
					}
					block["sub"] = resolved
					block["handle"] = raw
				} else if strings.HasPrefix(raw, "agt_") {
					block["sub"] = raw
				} else {
					writeErr(format, "usage_error", fmt.Sprintf("mention %q: must be a handle (contains @) or sub (starts with agt_)", m), "", false)
					return &apiError{code: "usage_error", exitCode: exitcode.Usage}
				}
				content = append(content, block)
			}

			for _, f := range files {
				content = append(content, map[string]interface{}{"type": "file", "file_id": f})
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "salon_id": salonID, "content": content})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			body := map[string]interface{}{"content": content}
			result, status, err := doRequest("POST", salonURL()+"/salons/"+salonID+"/messages", token, body)
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
				id, _ := result["id"].(string)
				fmt.Printf("Sent: %s\n", id)
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&text, "text", "", "Message text (required)")
	cmd.Flags().StringArrayVar(&mentions, "mention", nil, "Mention a user by @handle or sub (repeatable)")
	cmd.Flags().StringArrayVar(&files, "file", nil, "Attach a file by file_id (repeatable)")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}

func newMessageListCmd() *cobra.Command {
	var since, before, sender string
	var mentionMe bool
	var limit int

	cmd := &cobra.Command{
		Use:   "list <salon_id>",
		Short: "List messages in a Salon",
		Long: `List messages in a Salon with optional filters.

Examples:
  hivo salon message list salon_abc
  hivo salon message list salon_abc --limit 20
  hivo salon message list salon_abc --since 2025-01-01T00:00:00Z
  hivo salon message list salon_abc --sender @alice
  hivo salon message list salon_abc --mention-me`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			salonID := args[0]

			token, _, err := getToken(format)
			if err != nil {
				return err
			}

			params := url.Values{}
			if since != "" {
				params.Set("since", since)
			}
			if before != "" {
				params.Set("before", before)
			}
			if sender != "" {
				params.Set("sender", sender)
			}
			if mentionMe {
				params.Set("mention_me", "true")
			}
			if limit > 0 {
				params.Set("limit", fmt.Sprintf("%d", limit))
			}

			reqURL := salonURL() + "/salons/" + salonID + "/messages"
			if len(params) > 0 {
				reqURL += "?" + params.Encode()
			}

			result, status, err := doRequest("GET", reqURL, token, nil)
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
				messages, _ := result["messages"].([]interface{})
				if len(messages) == 0 {
					fmt.Println("No messages.")
					return nil
				}
				for _, m := range messages {
					msg, _ := m.(map[string]interface{})
					id, _ := msg["id"].(string)
					senderHandle, _ := msg["sender_handle"].(string)
					senderSub, _ := msg["sender_sub"].(string)
					who := senderHandle
					if who == "" {
						who = senderSub
					}
					createdAt, _ := msg["created_at"].(string)
					// Extract text from content blocks
					textContent := ""
					if contentBlocks, ok := msg["content"].([]interface{}); ok {
						for _, b := range contentBlocks {
							if block, ok := b.(map[string]interface{}); ok {
								if block["type"] == "text" {
									if t, ok := block["text"].(string); ok {
										textContent = t
									}
								}
							}
						}
					}
					fmt.Printf("[%s] %s (%s): %s\n", createdAt, who, id, textContent)
				}
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&since, "since", "", "Filter messages after this datetime (ISO 8601)")
	cmd.Flags().StringVar(&before, "before", "", "Filter messages before this datetime (ISO 8601)")
	cmd.Flags().StringVar(&sender, "sender", "", "Filter by sender handle or sub")
	cmd.Flags().BoolVar(&mentionMe, "mention-me", false, "Only show messages that mention me")
	cmd.Flags().IntVar(&limit, "limit", 0, "Maximum number of messages to return")
	return cmd
}

func newMessageGetCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "get <message_id>",
		Short: "Get a single message",
		Long: `Get details of a single message by ID.

Examples:
  hivo salon message get msg_abc
  hivo salon message get msg_abc --format json`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			token, _, err := getToken(format)
			if err != nil {
				return err
			}
			result, status, err := doRequest("GET", salonURL()+"/messages/"+args[0], token, nil)
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
				for _, f := range []string{"id", "salon_id", "sender_sub", "sender_handle", "created_at"} {
					if v, ok := result[f]; ok && v != nil {
						fmt.Printf("%-16s %v\n", f+":", v)
					}
				}
				if contentBlocks, ok := result["content"].([]interface{}); ok {
					fmt.Println("content:")
					for _, b := range contentBlocks {
						if block, ok := b.(map[string]interface{}); ok {
							btype, _ := block["type"].(string)
							switch btype {
							case "text":
								t, _ := block["text"].(string)
								fmt.Printf("  [text] %s\n", t)
							case "mention":
								h, _ := block["handle"].(string)
								s, _ := block["sub"].(string)
								if h != "" {
									fmt.Printf("  [mention] @%s\n", h)
								} else {
									fmt.Printf("  [mention] %s\n", s)
								}
							case "file":
								fid, _ := block["file_id"].(string)
								fmt.Printf("  [file] %s\n", fid)
							}
						}
					}
				}
			}
			return nil
		},
	}
}

func newMessageDeleteCmd() *cobra.Command {
	var yes, dryRun bool

	cmd := &cobra.Command{
		Use:   "delete <message_id>",
		Short: "Delete a message",
		Long: `Delete a message. Requires confirmation unless --yes is provided.

Examples:
  hivo salon message delete msg_abc --yes
  hivo salon message delete msg_abc
  hivo salon message delete msg_abc --dry-run`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			msgID := args[0]

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{"dry_run": true, "message_id": msgID})
				return exitcode.DryRunError{Preview: string(out)}
			}

			if !yes {
				if !exitcode.IsTTY() {
					writeErr(format, "usage_error", "Destructive action requires --yes in non-interactive mode", "", false)
					return &apiError{code: "usage_error", exitCode: exitcode.Usage}
				}
				fmt.Fprintf(os.Stderr, "Delete message %s? [y/N] ", msgID)
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

			result, status, err := doRequest("DELETE", salonURL()+"/messages/"+msgID, token, nil)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			if status >= 400 {
				return handleAPIError(format, result, status)
			}

			if format == "json" {
				out, _ := json.Marshal(map[string]string{"status": "deleted", "message_id": msgID})
				fmt.Println(string(out))
			} else {
				fmt.Printf("Deleted message: %s\n", msgID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompt")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview without executing (exit 10)")
	return cmd
}
