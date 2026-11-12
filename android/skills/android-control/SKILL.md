---
name: android-control
description: Drive an Android device (a phone or tablet over Tailscale, the local emulator pool, any adb device) like a user, through `ad`: fast adb steps (tap, type, look, user conditions, logs), emulator boot, auto-connect by name, and goal-level checks handed to the `device-checker` subagent. Use when the user asks to run, test or drive an Android app or device, install an APK or a build on a device (installs on a networked phone can go through a drop repo, not adb push), reproduce an Android bug, check or review an app's UI, verify a UI change before they look at it (clipped pills, rough edges, polish), or take an Android screenshot or recording. Don't use for questions about adb or Android development that don't touch a device.
---

# android-control

`ad` is fast adb with no LLM: pick and connect the device, boot the emulator, look at the
screen, tap, type, set user conditions, read logs. To hand a whole device-level goal ("open
Settings, report whether Dark theme is on") to someone, spawn the `device-checker` subagent:
Claude drives `ad`'s plain steps and judges the screen itself.

```bash
A=~/.claude/skills/android-control/ad
$A devices                # connected devices, named targets, emulator state
$A -s NAME status         # model, Android/API, ABI, screen, battery
$A help                   # every subcommand
```

## 1. Pick the device

`-s TARGET` comes first on every call. TARGET is one of:

- a **named target** from `~/.config/ad/targets`, reached over Tailscale. `ad` connects
  it on demand and clears a stale `offline` entry.

  Name each device in `~/.config/ad/targets` (copy `targets.example`); a line may add
  `drop=SSH_ALIAS` for the drop install route (section 5).

- `emu`, `emu2`: the two local Android 16 emulators (`emulator-5554`, `-5556`), each a stock
  Pixel 7-like phone at 1080x2400 and 420 dpi with Google APIs, the a recent Android version, running arm64 apps through translation (install x86_64 builds where an app runs its
  own native binaries). There are only these two; when both are leased, wait for one
  (`--wait`) rather than creating or launching another emulator, since the host's disk and
  memory are sized for two. `emu` (AVD `tl16`) keeps installs and settings between boots;
  `emu2` (AVD `tl16b`) is read-only and resets when stopped. So use `emu` when an install
  must persist, `emu2` for throwaway checks, and both for two checks in parallel. For "any emulator" take `$A lease acquire --any
  "purpose"` (a running slot first, `emu2` before `emu`); two parallel subagents each take their own slot. A
  slot is reachable only while running: with its lease held, run `$A -s emuN emu start`
  (about 80 s, KVM-accelerated, rendered on the CPU; refused under 8 GiB of free memory;
  boots queue 20 s apart). Releasing the lease stops an emulator it started, and
  `emu-reaper.timer` stops one left up 15 min with no live lease.
- an exact serial, or a unique piece of the model or product name.

With no `-s`, `ad` uses `$ANDROID_SERIAL`, then the only connected device. When several are
connected it refuses and lists them. Take the device from the request, and ask the user
when the request leaves it open.

Never start Waydroid on this host, even by hand (`waydroid session start`): running it
next to the emulator panicked the host kernel twice. Use an emulator instead.

Every agent shares one adb server on port 5037. `ad` clears `ANDROID_ADB_SERVER_PORT`; keep
it unset when calling `adb` or Gradle yourself, so all agents see the same
devices. Raw adb goes through `$A -s X adb ...`. To put a build on an emulator, Gradle can
install it directly (`ANDROID_SERIAL=$($A -s X serial) ./gradlew installDebug`). For a named
target, build the APK and hand it to `$A -s X install`, which uses the device-drops route
(section 5); Gradle's install pushes over the Tailscale link.

**Lease the device before you change anything on it.** Sessions from every account share these
devices, so one driver at a time:

```bash
$A -s emu lease acquire "verify palette chips"   # --wait to queue, --for MIN (default 30)
$A lease acquire --any "purpose"                 # first free emulator slot, a running one first
$A -s emu lease status                           # who holds what
$A -s emu lease release                          # when done; stops an emulator your lease started
```

Looking (`status`, `top`, `ui`, `find`, `shot`, `zoom`, `logcat`, getters) needs no lease;
every command that can change the device refuses without one and names the holder. Raw
`adb` and `shell` always need one, reads included, because `ad` cannot tell `getprop` from
`pm clear`: for a lease-free read use the look commands instead. Each command extends your
lease by 10 minutes. Subagents share their session's lease.

**Picking up again after a pause** (a resumed worker, or you after waiting on something): your
lease may have lapsed. Ten idle minutes free it, the reaper stops a slot 15 minutes after that, and
a pool slot comes back empty: no build, no data, no settings. Another session may also have
driven the slot meanwhile. `ad` notices both cases and refuses your first command once, saying
what happened. When that happens, or you get "no lease" or "not running" on a slot you used before,
re-lease it and start it, then reinstall and redo the setup before you carry on. Don't report
anything from before the gap as still true. For work that spans a long pause, take `--for MIN` to
cover it, or use `emu`, which keeps installs. When an orchestrator resumes a worker, its brief
says the slot may have been reset.

## The app's map

Before driving an app, look for `docs/agents/device-map.md` in its repository. It names the
package, how to build and install, how to reach each screen (gestures, element ids, shortcut
commands), and where the app keeps its list of owed device checks. Follow it instead of
exploring; exploring is what makes a check slow. If the app has no map, or the map was wrong or
missing a step, end your report with the lines that should be added, so the next run is faster.

## 2. Whose device it is

- **A personal phone** holds the user's accounts, messages and payment apps.
  - Do only the tasks the user asked for.
  - Ask before you uninstall or clear a package you didn't install, and before you change
    `night`, `font`, `locale`, `airplane`, `size` or `density`. Restore every setting you
    changed.
  - Accounts, payments, messages and contacts are the user's to touch, never yours.
  - Note `$A -s NAME top` first, and leave the same app in front when you finish.
- **An experimental build or tablet** is a shared device (next bullet); its OS may be a test
  build, so separate OS glitches from app bugs before reporting.
- **The emulators belong to the agents.** They hold no user data, so they're the place for
  destructive steps: clearing data, fresh installs, airplane mode, odd sizes. Other agents
  share them, so the shared-device rule below still applies, and so does restoring what you
  change.
- **Shared devices:** run `$A top` before you act. If something other than
  the launcher or your own app is in front, another agent or the user is mid-flow, so ask.
- **A locked screen** needs the user to unlock it.

## 3. Drive: steps, then verify

**Goals.** For a device-level goal where the path through the app doesn't matter, only the end
state does, hand it to the `device-checker` subagent with the end state to report and, for
read-only questions, "do not change anything". It drives `ad`'s steps under the lease and
reports what the screen showed.

**Steps** (`ad`, about 1 s each): the building blocks, and the only route when the exact path
matters, as in tests, bug reproductions and typing into a terminal.

- `$A tap "Sign in"` matches text, desc or id, and prefers a clickable node.
  `$A tap 300 640` taps coordinates, and `$A long ...` long-presses.
- `$A type "hello"` types ASCII only. For a terminal, send one word per call with
  `$A key SPACE` between words, and `$A key ENTER` to run it. On the emulator `input text`
  drops a letter now and then ("Buy mik"), so read the field back with `ui` before `key ENTER`
  and retype if it is wrong.
- `$A swipe up|down|left|right`, `$A key ENTER TAB`, `$A back`, `$A home`.
- `$A launch PKG` starts the app's launcher activity and prints the start time.

**Verify.** A subagent's "done" is its own claim. The step is done when `ad` shows
the end state:

- `$A top` names the focused activity.
- `$A ui` prints the accessibility tree (class, text, desc, id, flags, center `@x,y`).
  `$A find "Sign in"` narrows it.
- `$A shot out.png` saves the full screen. A reader shrinks it to about 1568 px, which
  hides 1–2 px defects, so use it for the overall picture only.
- `$A zoom "Sign in" out.png` crops one element (by text, desc, id or `X1,Y1,X2,Y2`) from
  the full-resolution screenshot and enlarges it so every device pixel shows. `--all`
  crops every match. This is how you see clipping, rough corners and misalignment.
- `$A frames 3 out/dir -- tap "Expand"` records while the action runs, then saves each
  distinct frame plus `sheet.png`, an overview of 12 frames.
- `$A record 10 out.mp4` records the screen. On a device without a video encoder, both
  fall back to about 4 screenshots per second.

If the dump fails mid-animation, retry once, or turn animations off for the session: note
`$A anim`, run `$A anim 0`, and set the noted value back at the end.

## 4. Visual review, scaled to the change

The accessibility tree and `Goal achieved` confirm what is on the screen, not how it looks;
the user keeps finding defects agents called "verified" (a pill clipped flat on one side,
rough corners, text touching an icon). When you check a UI change, look at pixels: `zoom`
the changed element and the sibling it should match.

How far to go depends on the change. A small tweak needs one zoom of the result. A new or
reworked screen also gets light, dark and large font (read each setting first and restore
it), motion frames on the phone when it moves, and, when the user asks for a review, a fresh
reviewer agent judging the crops without the code. The full steps and defect checklist are in
[references/visual-review.md](references/visual-review.md).

**Off-device first for static View layout.** If the project has Roborazzi on Robolectric
(`@GraphicsMode(NATIVE)`), a static layout change to a plain View screen such as a settings
page can be rendered in the worktree first. Add or update a capture there, run
`record<Variant>Roborazzi`, and look at the PNG. It takes seconds, needs no device, and a
builder can run it. Light, dark, width and pane variants come from qualifiers. A long page
needs a taller qualifier. Pause the main looper and idle before you capture.

It doesn't replace the device check. The renderer shows no status bar, insets, elevation or
real device fonts. Recorded `RenderNode`s (live glass), AGSL `RuntimeShader`s and motion don't
render at all. `RenderEffect` blur renders only with `robolectric.pixelCopyRenderMode=hardware`.
Glass, effects, wallpaper, the IME, gestures and anything that moves still go to an emulator
or the phone, and so does the final look of every change.

## 5. Apps, conditions, logs

- **Install:** `$A install app.apk` keeps the app's data, like an update. `--fresh`
  uninstalls first so the first-run flow shows, and `$A clear PKG` resets without
  reinstalling. Check the ABI with `status`: an APK built for another ABI fails with
  `INSTALL_FAILED_NO_MATCHING_ABIS`. Phones are usually arm64. The emulator is x86_64 and also runs
  arm64 builds through translation.
- **Installs on a phone can go through a drop repo.** The Tailscale relay to a phone can crawl
  (11–33 KB/s seen), so a 58 MB `adb install` would have taken an hour and
  dropped when the phone changed network. Both ends reach GitHub fast, though. So for a named
  target whose line in `~/.config/ad/targets` carries `drop=SSH_ALIAS` (for example `drop=termux`),
  `$A -s NAME install app.apk`:
  1. uploads the APK to the private GitHub repo named by `AD_DROP_REPO` (`OWNER/NAME`, release `inbox`);
  2. has the device's Termux `curl` it over ssh, at its own connection's speed, from a short-lived
     signed link resolved on the host (`gh release download` on a phone ran 4–8x slower);
  3. runs `pm install` on it, read back through `run-as com.termux` (a staging or debug build
     of the Termux app) or from `/sdcard` when Termux has storage access;
  4. deletes the asset and the device's copy.

  It prints `Success` like `adb install`; then do the usual launch and crash check. Emulators,
  and targets without a `drop=` field, install over adb as before. `--direct` forces adb for
  one install, and is also how you `--fresh` the Termux app itself (the drop route runs
  through it). When the drop route fails, `ad` says why. The usual causes are no `gh` login on
  the host, Termux's ssh server down (start it with `$A -s NAME runas com.termux /data/data/com.termux/files/usr/bin/sshd` on a staging
  build), or a release build with neither run-as nor storage access. Use the same repo by hand
  for any other large file in either direction. Assets are private and deleted after use;
  GitHub documents no bandwidth cap on release assets (files up to 2 GiB).
- **Entry points:** `$A open "myapp://path"` fires a deep link. `$A kill PKG` simulates
  process death in the background, and `$A stop PKG` force-stops the app.
- **User conditions** (dark mode, large fonts, Arabic RTL, offline, permissions, process
  death, other screen sizes): the checklist is in
  [references/user-emulation.md](references/user-emulation.md).
- **Inside the app:** `$A runas PKG "command"` runs a shell command as a debuggable app (its uid
  and data dir) and prints the output: read its files, databases and prefs, or run its own
  tools. An app's map can name an env prefix to put in `AD_RUNAS_PRELUDE`.
- **Drag and sliders:** `$A swipe X1 Y1 X2 Y2 MS` drags between two points; a slow drag (600 ms
  or more) moves a slider without flinging.
- **Debugging:** run `$A logclear` before the repro and `$A logcat PKG` during it.
  `$A crash` shows the last crash. Deeper tools are in
  [references/debugging.md](references/debugging.md).

## 6. Finish clean, then report

Before you report, stop everything you started: `record` and `frames` captures, `logcat`
followers, monitor or polling loops, and background shells. Nothing of yours may keep
running against the device after your report: the next driver gets the device, not your leftovers.
Release the device's lease if you took it.

Give the user what they need to replay it without you:

- the device (from `status`)
- the exact `ad` commands
- what `ad` showed at the end, with paths to screenshots, zoom crops and frames
- for a UI change, each checklist finding and the reviewer's, with what you fixed
- any logcat lines
