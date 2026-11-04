# Android add-on to CLAUDE.md

Loaded as a user-level rule when Android work is installed. It adds to the delegation rules; it
does not replace them.

- `device-checker` (Sonnet) runs batched functional checks on a device from a user-facing summary
  of the change. About 8 items per run; name the surface to look at. It never edits code. Use it
  after a change is merged and built, or for a batch of owed checks.
- Tagged logging: when a worker commits temporary logging under one tag, build and install that
  branch, reproduce once, and capture with `adb logcat -s <tag>`; send the lines back.
- A real device is the truth for layout and motion. Emulators differ in width, font scale,
  wallpaper and permissions, so an emulator pass is a claim, not proof.
- When the user has allowed their device for a piece of work, a build goes on it after each wave,
  not only at the end.
- Fixers never touch devices or emulators; anything that needs one goes to `device-checker` or
  back to the main session.
