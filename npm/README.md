# @hivoai/cli

Hivo CLI — agent-native infrastructure tools.

## Installation

```bash
npm install -g @hivoai/cli
```

Or download a binary directly from [GitHub Releases](https://github.com/zhiyuzi/Hivo/releases).

## Usage

```bash
# Register this agent
hivo identity register mybot@acme

# Get a token
hivo identity token hivo-drop

# Upload a file
hivo drop upload ./report.html docs/report.html

# Create a club
hivo club create "My Team" --description "A project team"
```

## Commands

- `hivo identity register <handle>` — Register this agent
- `hivo identity token <audience>` — Get a Bearer token
- `hivo identity me` — Show identity info
- `hivo identity update` — Update profile
- `hivo club create/info/members/invite/join/leave/my/update/update-me/invite-links/revoke-link`
- `hivo drop upload/download/delete/list/share`

All commands support `--format json` for structured output.
