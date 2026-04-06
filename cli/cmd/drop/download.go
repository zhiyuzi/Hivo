package drop

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/spf13/cobra"
)

func newDownloadCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "download <remote_path> [local_file]",
		Short: "Download a file from hivo-drop",
		Long: `Download a file from hivo-drop. If local_file is omitted, prints to stdout.

Examples:
  hivo drop download docs/report.html report.html
  hivo drop download notes/memo.txt`,
		Args: cobra.RangeArgs(1, 2),
		RunE: func(cmd *cobra.Command, args []string) error {
			format, _ := cmd.Root().PersistentFlags().GetString("format")
			remotePath := args[0]

			token, err := getToken(format)
			if err != nil {
				return err
			}

			req, _ := http.NewRequest("GET", dropURL()+"/files/"+remotePath, nil)
			req.Header.Set("Authorization", "Bearer "+token)
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				writeErr(format, "request_failed", err.Error(), "", true)
				return err
			}
			defer resp.Body.Close()

			if resp.StatusCode >= 400 {
				raw, _ := io.ReadAll(resp.Body)
				var result map[string]interface{}
				_ = json.Unmarshal(raw, &result)
				return handleAPIError(format, result, resp.StatusCode)
			}

			if len(args) == 2 {
				f, err := os.Create(args[1])
				if err != nil {
					writeErr(format, "write_failed", err.Error(), "", false)
					return err
				}
				defer f.Close()
				n, _ := io.Copy(f, resp.Body)
				if format == "json" {
					out, _ := json.Marshal(map[string]interface{}{"path": args[1], "bytes": n})
					fmt.Println(string(out))
				} else {
					fmt.Printf("Downloaded: %s (%d bytes)\n", args[1], n)
				}
			} else {
				io.Copy(os.Stdout, resp.Body)
			}
			return nil
		},
	}
	return cmd
}
