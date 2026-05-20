# Platform Notes Reference

Load this when diagnosing a platform-specific timezone detection issue.

## Detection Chain

pocket-watch tries IANA timezone detection in this order:

1. `$POCKET_WATCH_TZ` env var — user override, highest priority
2. `datetime.now().astimezone().tzinfo` — Python stdlib, works on most platforms
3. `readlink /etc/localtime` — macOS and most Linux distros
4. `/etc/timezone` — Debian/Ubuntu
5. `timedatectl show --property=Timezone --value` — systemd-based Linux
6. `systemsetup -gettimezone` — macOS alternative
7. `tzutil /g` + Windows→IANA mapping — Windows
8. UTC + warning — final fallback

## macOS

Steps 2, 3, and 6 all typically work. If the user's timezone shows as UTC unexpectedly on macOS, check that System Preferences > Date & Time > Time Zone is set correctly.

## Linux

Steps 2, 3, 4, 5 cover all major distributions. Alpine Linux (no systemd) falls through to UTC; the user should set `POCKET_WATCH_TZ`.

## WSL (Windows Subsystem for Linux)

The WSL instance typically mirrors the Windows host timezone via `/etc/localtime`. If it doesn't, step 2 (Python tzinfo) usually catches it by reading from the Windows registry via Python's OS bindings. If all else fails, `POCKET_WATCH_TZ` is the reliable override.

## Windows (native PowerShell/CMD)

Step 7 (`tzutil /g`) returns Windows timezone names (e.g., "Eastern Standard Time"). pocket-watch includes a mapping table of ~90 Windows → IANA conversions. If the user's zone isn't in the table, it falls back to UTC with a warning.

## SSH / Remote Sessions

When Claude Code runs on a remote host via SSH, the detected timezone is the **remote host's** timezone — not the user's local timezone. Common scenario: the remote server is set to UTC while the user is in New York.

Solution: `export POCKET_WATCH_TZ=America/New_York` in the remote shell's profile (`.bashrc`, `.zshrc`, etc.).

## VPN Sessions

VPN doesn't affect system timezone. The system clock and `/etc/localtime` are unaffected by VPN routing. No special handling needed.

## Docker / Containers

Container timezone depends on the base image and mount configuration. If the container's `/etc/localtime` is not mounted from the host, it may default to UTC. Set `POCKET_WATCH_TZ` in the container's environment.

## Escape Hatch

In all ambiguous cases: `export POCKET_WATCH_TZ=<IANA_name>` before starting Claude Code. This overrides all detection. The IANA name must be a valid zone (e.g., `America/Chicago`, `Europe/London`, `Asia/Tokyo`).

To find your IANA name: `timedatectl show --property=Timezone` (Linux) or check https://en.wikipedia.org/wiki/List_of_tz_database_time_zones.
