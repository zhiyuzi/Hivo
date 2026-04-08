package drop

import (
	"encoding/json"
	"fmt"
	"io"
	"mime"
	"net/http"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	"github.com/zhiyuzi/hivo/cli/internal/exitcode"
)

func newUploadCmd() *cobra.Command {
	var overwrite bool
	var dryRun bool

	cmd := &cobra.Command{
		Use:   "upload <local_file> <remote_path>",
		Short: "Upload a local file to hivo-drop",
		Long: `Upload a local file to the hivo-drop storage service.

Examples:
  hivo drop upload ./report.html docs/report.html
  hivo drop upload ./data.json results/data.json --overwrite
  hivo drop upload ./file.txt docs/file.txt --dry-run`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format := effectiveFormat(cmd.Root().PersistentFlags().Lookup("format").Value.String())
			localFile := args[0]
			remotePath := args[1]

			f, err := os.Open(localFile)
			if err != nil {
				writeErr(format, "file_not_found", fmt.Sprintf("Cannot open file: %s", localFile), "", false)
				return err
			}
			defer f.Close()

			stat, _ := f.Stat()
			ct := mime.TypeByExtension(filepath.Ext(localFile))
			if ct == "" {
				ct = "application/octet-stream"
			}

			if dryRun {
				out, _ := json.Marshal(map[string]interface{}{
					"dry_run":      true,
					"local_file":   localFile,
					"remote_path":  remotePath,
					"size":         stat.Size(),
					"content_type": ct,
					"overwrite":    overwrite,
				})
				return exitcode.DryRunError{Preview: string(out)}
			}

			token, err := getToken(format)
			if err != nil {
				return err
			}

			url := dropURL() + "/files/" + remotePath
			if overwrite {
				url += "?overwrite=true"
			}

			req, err := http.NewRequest("PUT", url, f)
			if err != nil {
				return err
			}
			req.Header.Set("Authorization", "Bearer "+token)
			req.Header.Set("Content-Type", ct)
			req.ContentLength = stat.Size()

			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				writeErr(format, "upload_failed", err.Error(), "", true)
				return err
			}
			defer resp.Body.Close()
			raw, err := io.ReadAll(resp.Body)
			if err != nil {
				writeErr(format, "read_failed", "Failed to read response body", "", true)
				return err
			}

			var result map[string]interface{}
			if err := json.Unmarshal(raw, &result); err != nil {
				writeErr(format, "parse_failed", "Failed to parse response", "", false)
				return err
			}

			if resp.StatusCode == 409 {
				writeErr(format, "conflict", fmt.Sprintf("File '%s' already exists.", remotePath), "Use --overwrite to replace.", false)
				return &apiError{code: "conflict", exitCode: exitcode.Conflict}
			}
			if resp.StatusCode >= 400 {
				return handleAPIError(format, result, resp.StatusCode)
			}

			if format == "json" {
				fmt.Println(string(raw))
			} else {
				fileID, _ := result["id"].(string)
				fmt.Printf("Uploaded: %s (%d bytes, id: %s)\n", remotePath, stat.Size(), fileID)
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&overwrite, "overwrite", false, "Overwrite existing file")
	cmd.Flags().BoolVar(&dryRun, "dry-run", false, "Preview upload without executing (exit 10)")
	return cmd
}
