# Security Policy

## Supported Versions

Security patches are provided for the latest minor version only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (current) |
| < 0.1   | No |

Once v1.0.0 is released, patches will apply to the latest minor version only.

## Security Model

pocket-watch hooks execute Python code with your user privileges. By installing this plugin, you are trusting the source code to run in your Claude Code environment.

Mitigations:
- **Stdlib only** — no third-party runtime dependencies that could be compromised
- **Small surface area** — the entire codebase is reviewable in a single sitting
- **No network calls** — zero outbound connections; all data stays on disk
- **Local state only** — data in `~/.claude/data/pocket-watch/` (chmod 0600)
- **Fail-soft design** — hooks fail silently and auto-disable after 3 consecutive errors; they never block your session

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public issue**.

Instead, report the issue privately via the [private security advisory](https://github.com/MiguelDotL/pocket-watch/security/advisories/new) feature of this repository.

- Response SLA: best-effort, 7-day acknowledgment target
- Patch target: best-effort for high-severity issues; coordinated disclosure preferred

We are a solo project with no bug bounty program. We take security seriously and will work to address valid findings promptly.

## Known Limitations

- **Hook code execution**: All hooks run as Python scripts with full user privileges. Review the hook code before installing any plugin.
- **NFS home directories**: `fcntl.flock` is unreliable on NFS — concurrent writes may interleave. Documented; not patched.
- **System clock trust**: pocket-watch trusts the OS system clock. A compromised or misconfigured system clock produces incorrect output.
