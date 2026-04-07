package e2e

import (
	"encoding/json"
	"os"
	"testing"
)

func skipIfNoE2E(t *testing.T) {
	t.Helper()
	if os.Getenv("HIVO_E2E") == "" {
		t.Skip("set HIVO_E2E=1 to run e2e tests")
	}
}

// registerAgent registers a new agent and returns its working directory.
func registerAgent(t *testing.T, base string) string {
	t.Helper()
	dir := WorkDir(t)
	handle := UniqueHandle(base)
	reg := RunCmd(t, Request{Args: []string{"identity", "register", handle}, WorkDir: dir})
	if reg.ExitCode != 0 {
		t.Fatalf("register %s failed: %s", handle, reg.Stderr)
	}
	return dir
}

// createClub creates a club and returns its club_id.
func createClub(t *testing.T, dir, name string) string {
	t.Helper()
	result := RunCmd(t, Request{
		Args:    []string{"club", "create", name, "--description", "e2e test club"},
		WorkDir: dir,
	})
	if result.ExitCode != 0 {
		t.Fatalf("club create failed: %s", result.Stderr)
	}
	var out map[string]interface{}
	if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
		t.Fatalf("club create stdout not valid JSON: %v", err)
	}
	clubID, ok := out["club_id"].(string)
	if !ok || clubID == "" {
		t.Fatalf("no club_id in output: %v", out)
	}
	return clubID
}

func TestClubCreate(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "clubbot")

	t.Run("create returns club_id", func(t *testing.T) {
		clubID := createClub(t, dir, "Test Club")
		if clubID == "" {
			t.Fatal("empty club_id")
		}
	})
}

func TestClubInfo(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "infobot")
	clubID := createClub(t, dir, "Info Club")

	t.Run("info returns club details", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "info", clubID},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
		if out["club_id"] == nil {
			t.Fatal("no club_id in output")
		}
	})
}

func TestClubMembers(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "membersbot")
	clubID := createClub(t, dir, "Members Club")

	t.Run("members returns list", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "members", clubID},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
	})
}

func TestClubInviteAndJoin(t *testing.T) {
	skipIfNoE2E(t)
	ownerDir := registerAgent(t, "inviteowner")
	clubID := createClub(t, ownerDir, "Invite Club")

	// Get owner sub for direct invite test
	meResult := RunCmd(t, Request{Args: []string{"identity", "me"}, WorkDir: ownerDir})
	var meOut map[string]interface{}
	json.Unmarshal([]byte(meResult.Stdout), &meOut)

	t.Run("create invite link", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "invite", clubID, "--link", "--max-uses", "5"},
			WorkDir: ownerDir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
		if out["token"] == nil {
			t.Fatal("no token in output")
		}

		// Join with the link using a new agent
		token := out["token"].(string)
		memberDir := registerAgent(t, "joinbot")
		joinResult := RunCmd(t, Request{
			Args:    []string{"club", "join", token},
			WorkDir: memberDir,
		})
		if joinResult.ExitCode != 0 {
			t.Fatalf("join failed: %s", joinResult.Stderr)
		}
		var joinOut map[string]interface{}
		if err := json.Unmarshal([]byte(joinResult.Stdout), &joinOut); err != nil {
			t.Fatalf("join stdout not valid JSON: %v", err)
		}
		if joinOut["club_id"] == nil {
			t.Fatal("no club_id in join output")
		}
	})

	t.Run("invite direct by sub", func(t *testing.T) {
		// Register a second agent to invite
		inviteeDir := registerAgent(t, "invitee")
		meRes := RunCmd(t, Request{Args: []string{"identity", "me"}, WorkDir: inviteeDir})
		var inviteeMe map[string]interface{}
		json.Unmarshal([]byte(meRes.Stdout), &inviteeMe)
		inviteeSub, ok := inviteeMe["sub"].(string)
		if !ok || inviteeSub == "" {
			t.Fatal("could not get invitee sub")
		}

		result := RunCmd(t, Request{
			Args:    []string{"club", "invite", clubID, "--sub", inviteeSub, "--role", "member"},
			WorkDir: ownerDir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
	})
}

func TestClubInviteLinks(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "linksbot")
	clubID := createClub(t, dir, "Links Club")

	// Create a link first
	RunCmd(t, Request{
		Args:    []string{"club", "invite", clubID, "--link"},
		WorkDir: dir,
	})

	t.Run("invite-links returns list", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "invite-links", clubID},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
	})
}

func TestClubRevokeLink(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "revokebot")
	clubID := createClub(t, dir, "Revoke Club")

	// Create a link to revoke
	linkResult := RunCmd(t, Request{
		Args:    []string{"club", "invite", clubID, "--link"},
		WorkDir: dir,
	})
	if linkResult.ExitCode != 0 {
		t.Fatalf("invite --link failed: %s", linkResult.Stderr)
	}
	var linkOut map[string]interface{}
	json.Unmarshal([]byte(linkResult.Stdout), &linkOut)
	token, ok := linkOut["token"].(string)
	if !ok || token == "" {
		t.Fatal("no token in invite-link output")
	}

	t.Run("revoke-link succeeds", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "revoke-link", clubID, token},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
	})
}

func TestClubUpdate(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "updateclubbot")
	clubID := createClub(t, dir, "Update Club")

	t.Run("update club name", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "update", clubID, "--name", "Updated Club Name"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
	})
}

func TestClubUpdateMe(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "updatemebotclub")
	clubID := createClub(t, dir, "UpdateMe Club")

	t.Run("update-me sets display-name", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "update-me", clubID, "--display-name", "My Display Name"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
	})
}

func TestClubUpdateMember(t *testing.T) {
	skipIfNoE2E(t)
	ownerDir := registerAgent(t, "roleowner")
	clubID := createClub(t, ownerDir, "Role Club")

	// Invite a member via link and have them join
	linkResult := RunCmd(t, Request{
		Args:    []string{"club", "invite", clubID, "--link", "--role", "member"},
		WorkDir: ownerDir,
	})
	if linkResult.ExitCode != 0 {
		t.Fatalf("invite --link failed: %s", linkResult.Stderr)
	}
	var linkOut map[string]interface{}
	json.Unmarshal([]byte(linkResult.Stdout), &linkOut)
	token := linkOut["token"].(string)

	memberDir := registerAgent(t, "rolemember")
	RunCmd(t, Request{Args: []string{"club", "join", token}, WorkDir: memberDir})

	// Get member sub
	meRes := RunCmd(t, Request{Args: []string{"identity", "me"}, WorkDir: memberDir})
	var meOut map[string]interface{}
	json.Unmarshal([]byte(meRes.Stdout), &meOut)
	memberSub := meOut["sub"].(string)

	t.Run("update-member role to admin", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "update-member", clubID, memberSub, "--role", "admin"},
			WorkDir: ownerDir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
		if out["role"] != "admin" {
			t.Fatalf("expected role=admin, got: %v", out["role"])
		}
	})
}

func TestClubLeave(t *testing.T) {
	skipIfNoE2E(t)
	ownerDir := registerAgent(t, "leaveowner")
	clubID := createClub(t, ownerDir, "Leave Club")

	linkResult := RunCmd(t, Request{
		Args:    []string{"club", "invite", clubID, "--link"},
		WorkDir: ownerDir,
	})
	var linkOut map[string]interface{}
	json.Unmarshal([]byte(linkResult.Stdout), &linkOut)
	token := linkOut["token"].(string)

	memberDir := registerAgent(t, "leavebot")
	RunCmd(t, Request{Args: []string{"club", "join", token}, WorkDir: memberDir})

	t.Run("leave club", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "leave", clubID, "--yes"},
			WorkDir: memberDir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
	})
}

func TestClubMy(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "mybot")
	createClub(t, dir, "My Club")

	t.Run("my returns clubs list", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "my"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
	})
}

func TestClubDelete(t *testing.T) {
	skipIfNoE2E(t)
	dir := registerAgent(t, "deletebot")
	clubID := createClub(t, dir, "Delete Club")

	t.Run("delete club", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "delete", clubID, "--yes"},
			WorkDir: dir,
		})
		if result.ExitCode != 0 {
			t.Fatalf("expected exit 0, got %d\nstderr: %s", result.ExitCode, result.Stderr)
		}
		var out map[string]interface{}
		if err := json.Unmarshal([]byte(result.Stdout), &out); err != nil {
			t.Fatalf("stdout not valid JSON: %v", err)
		}
		if out["status"] != "deleted" {
			t.Fatalf("expected status=deleted, got: %v", out["status"])
		}
	})

	t.Run("info after delete returns error", func(t *testing.T) {
		result := RunCmd(t, Request{
			Args:    []string{"club", "info", clubID},
			WorkDir: dir,
		})
		if result.ExitCode == 0 {
			t.Fatal("expected non-zero exit for deleted club")
		}
	})
}
