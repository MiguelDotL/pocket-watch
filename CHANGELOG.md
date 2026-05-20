# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pre-v1.0.0: breaking changes are allowed in minor versions (0.X.0). Bug fixes only in patch versions (0.X.Y).

---

## [Unreleased]

---

## [0.1.0] - 2026-05-19

### Added

- **5 hooks**: SessionStart, UserPromptSubmit, PostToolUse, Stop, PreCompact
- **Stop hook**: estimate detection from Claude's natural-language responses via positive-context regex; pivot detection; completion-confidence fusion (verbal + tool signals); active-time accumulation per turn
- **SessionStart hook**: first-run privacy disclosure; stale-open estimate warnings; monthly audit invitation; hook health alerts; habit cache refresh
- **UserPromptSubmit hook**: user-side estimate detection; conversational cue capture (good night, I'm back); /pw-* invocation flag for self-output guard
- **PostToolUse hook**: tool-pattern completion signals (PR created, tests passed, deploy success)
- **PreCompact hook**: preserves open-estimate state across /compact
- **7 slash commands**: /pw-now, /pw-stats, /pw-doctor, /pw-audit, /pw-correct, /pw-done, /pw-estimate
- **pw CLI**: subcommands now, estimate, done, stats, doctor, audit, correct
- **8-step IANA timezone detection chain**: env var → Python tzinfo → /etc/localtime symlink → /etc/timezone → timedatectl → systemsetup → tzutil → UTC fallback
- **Bayesian-blended calibration**: cold/warmup/mature phases with 20% trimmed median; long-running task separate bucket (> 480m)
- **Habit inference** (learn.py): daily-cached aggregation of work patterns; streak, typical hours, category velocity
- **JSONL schema v1**: all fields documented; append-only log; flock concurrency; 0600 permissions
- **Schema fields**: id, _schema, session_id, who, model, project, category, source, confidence, estimated_at, estimate_minutes, started_at, completed_at, active_minutes, elapsed_minutes, completion_signal, completion_confidence, status, notes, audited_at, audit_result, corrected_by, corrects
- **Hook fail-soft**: 3-strike auto-disable with health tracking in hook-health.json; pw doctor --enable-hooks resets
- **POCKET_WATCH_DISABLE=1** kill switch
- **POCKET_WATCH_TZ** override for timezone detection
- **Feature toggles** in config.json: capture_estimates, capture_completions, infer_habits, monthly_audit_enabled, auto_cancel_after_days
- **Bundled holiday data** (US federal + common international, 2024–2026)
- **Makefile** quality gates: lint, typecheck, test, privacy-check, security-check, check-all, release
- **pytest test suite**: test_clock, test_calibrate, test_log, test_parse, test_learn, test_stop_hook
- **Synthetic test fixtures** via gen_fixtures.py (seeded, reproducible)
- **SETUP-FOR-TESTERS.md** for alpha testers
- **Issue templates**: bug, platform-report, feature, pull request template
- **Pre-commit config** for contributor-side enforcement
- Standard OSS files: README, LICENSE (MIT), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CHANGELOG

### Known Limitations

- Cross-timezone display (`pw now --tz <IANA>`) deferred to v1.1
- p25/p75 percentiles in pw stats deferred to v1.1
- Privacy hash mode (HASH_NOTES) deferred to v1.1
- Per-model calibration multipliers deferred to v1.1
- /pw-history, /pw-export, /pw-purge deferred to v1.1
- Sub-agent work attribution is best-effort
- NFS-mounted home directories: flock unreliable
- Windows/WSL: best-effort support; contributions welcome

[Unreleased]: https://github.com/MiguelDotL/pocket-watch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MiguelDotL/pocket-watch/releases/tag/v0.1.0
