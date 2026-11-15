# Docker socket startup ordering

> For agentic workers, execute this approved change inline with `superpowers:executing-plans`.

**Goal** — Start Docker after its default socket symlink is ready, avoiding the observed startup authorization request.

**Architecture** — Docker's existing `com.docker.socket` LaunchDaemon creates the system symlink. A user LaunchAgent waits for that symlink to point to the current user's Docker socket, then opens Docker once and exits.

**Tech Stack** — POSIX shell, launchd property lists, Python standard-library regression tests.

**Spec** — The user approved the three-step proposal in this conversation on November 16, 2026.

## Constraints

- Set Docker's built-in `AutoStart` to false through its own settings interface.
- Enable the default Docker socket integration and reuse the installed official service.
- Check the symlink and its target path every two seconds. A dangling but correct symlink is ready.
- Log waiting periodically and continue waiting when the helper is slow.
- Exit after opening Docker so manually quitting Docker does not reopen it.
- Back up the Mac configuration on Windows before installation.
- A physical reboot and authorization-dialog check remain user-controlled verification.

## Task 1

- [x] Add regression tests covering missing, wrong, regular-file, and dangling-correct socket paths and opener failures.
- [x] Run against the previous direct-open behavior and observe early-start failures.
- [x] Add the waiting script and LaunchAgent, then run the full regression suite on macOS.
- [x] Document installation, logs, and rollback in the existing Docker instructions.
- [x] Review the complete change and commit using the repository's existing style.
- [x] Back up, install, disable native autostart, and verify Docker and the installed job.

## Review focus

- Waiting for the actual socket would deadlock startup.
- A wrong symlink or regular file must keep Docker gated.
- Paths containing spaces must work.
- An opener failure must be visible to launchd.
- Updating autostart must preserve unrelated Docker settings.

## Verification

The previous direct-open behavior failed all three waiting cases. The new implementation passed all five regression tests on macOS, shell syntax validation, and plist validation. Independent review found no blocking issues.

Installed on November 16, 2026. Both Docker's running settings interface and its saved configuration report native autostart disabled and default socket integration enabled. Only the autostart setting changed. The installed LaunchAgent ran once and exited successfully. The existing `keepalive-test` container retained its ID and start time.

The original configuration is backed up on Windows under `F:\300u-hackintosh-workspace\backups\docker-startup-order-20261116-005954`. Installed script and plist hashes match the reviewed source. Docker's official socket LaunchDaemon remains installed and its plist hash matches the backup.

Physical reboot verification remains pending. The user will check whether Docker starts automatically and whether the authorization dialog reappears.
