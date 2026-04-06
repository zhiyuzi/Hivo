package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// WorkspaceIdentity is stored in {workdir}/.hivo/identity.json
type WorkspaceIdentity struct {
	Sub string `json:"sub"`
}

// AgentRegistration is stored in ~/.hivo/agents/{sub}/registration.json
type AgentRegistration struct {
	Sub    string `json:"sub"`
	Handle string `json:"handle"`
	Iss    string `json:"iss"`
}

// HivoDir returns the ~/.hivo directory path
func HivoDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".hivo")
}

// AgentDir returns ~/.hivo/agents/{sub}/
func AgentDir(sub string) string {
	return filepath.Join(HivoDir(), "agents", sub)
}

// FindWorkspaceIdentity walks up from cwd looking for .hivo/identity.json
func FindWorkspaceIdentity() (*WorkspaceIdentity, string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return nil, "", err
	}
	for {
		candidate := filepath.Join(dir, ".hivo", "identity.json")
		if data, err := os.ReadFile(candidate); err == nil {
			var id WorkspaceIdentity
			if err := json.Unmarshal(data, &id); err != nil {
				return nil, "", fmt.Errorf("malformed %s: %w", candidate, err)
			}
			return &id, dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return nil, "", fmt.Errorf("no .hivo/identity.json found — run: hivo identity register <handle>")
}

// WriteWorkspaceIdentity writes {workdir}/.hivo/identity.json
func WriteWorkspaceIdentity(workdir string, id WorkspaceIdentity) error {
	dir := filepath.Join(workdir, ".hivo")
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	data, _ := json.MarshalIndent(id, "", "  ")
	return os.WriteFile(filepath.Join(dir, "identity.json"), data, 0600)
}

// LoadRegistration reads ~/.hivo/agents/{sub}/registration.json
func LoadRegistration(sub string) (*AgentRegistration, error) {
	path := filepath.Join(AgentDir(sub), "registration.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("registration not found for %s: %w", sub, err)
	}
	var reg AgentRegistration
	if err := json.Unmarshal(data, &reg); err != nil {
		return nil, err
	}
	return &reg, nil
}

// WriteAgentFiles writes all credential files for an agent under ~/.hivo/agents/{sub}/
func WriteAgentFiles(sub string, files map[string][]byte) error {
	dir := AgentDir(sub)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	for name, data := range files {
		perm := os.FileMode(0600)
		if err := os.WriteFile(filepath.Join(dir, name), data, perm); err != nil {
			return err
		}
	}
	return nil
}

// PrivateKeyPath returns the path to the agent's private key PEM
func PrivateKeyPath(sub string) string {
	return filepath.Join(AgentDir(sub), "private_key.pem")
}

// TokenCachePath returns the path to the agent's token cache
func TokenCachePath(sub string) string {
	return filepath.Join(AgentDir(sub), "token_cache.json")
}
