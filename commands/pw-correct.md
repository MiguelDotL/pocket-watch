# /pw-correct

Edit or delete a single estimate entry.

## Usage

```
/pw-correct <id> <field> <value>
/pw-correct <id> --delete
```

## What it does

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/pw correct <id> <field> <value>`.

The log is append-only: corrections write a new entry with the updated field and mark the original `corrected_by`. The calibration engine uses the latest non-deleted version of each entry chain.

## Editable fields

| Field | Example value |
|-------|--------------|
| `category` | `small-fix` |
| `status` | `completed`, `cancelled`, `merged`, `scope-changed` |
| `active_minutes` | `45` |
| `estimate_minutes` | `30` |
| `notes` | `refactor auth module` |
| `audit_result` | `accepted` |

## Deletion

`/pw-correct <id> --delete` marks the entry with `status: "deleted"`. Deleted entries are excluded from calibration and audit. Use this for entries that are clearly wrong or contain sensitive content you want removed from the log.

## Finding entry IDs

Run `/pw-stats` to see recent entries, or inspect `~/.claude/data/pocket-watch/estimates.jsonl` directly. Each entry has an `"id"` field (UUID4).
