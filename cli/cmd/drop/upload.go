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
)

func newUploadCmd() *cobra.Command {
	var overwrite bool

	cmd := &cobra.Command{
		Use:   "upload <local_file> <remote_path>",
		Short: "Upload a local file to hivo-drop",
		Long: `Upload a local file to the hivo-drop storage service.

Examples:
  hivo drop upload ./report.html docs/report.html
  hivo drop upload ./data.json results/data.json --overwrite`,
		Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			localFile := args[0]
			remotePath := args[1]

			token, err := getToken(format)
			if err != nil {
				return err
			}

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

			url := defaultDropURL + "/files/" + remotePath
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
			raw, _ := io.ReadAll(resp.Body)

			var result map[string]interface{}
			_ = json.Unmarshal(raw, &result)

			if resp.StatusCode >= 400 {
				return handleAPIError(format, result, resp.StatusCode)
			}

			if format == "json" {
				fmt.Println(string(raw))
			} else {
				fmt.Printf("Uploaded: %s (%d bytes)\n", remotePath, stat.Size())
			}
			return nil
		},
	}
	cmd.Flags().BoolVar(&overwrite, "overwrite", false, "Overwrite existing file")
	return cmd
}
