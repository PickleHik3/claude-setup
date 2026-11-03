---
name: android-control
description: Drive an Android device (the Pong phone and the Surface tablet over Tailscale, the local Android 16 emulator, any adb device) like a user, through `ad`: fast adb steps (tap, type, look, user conditions, logs), emulator boot, auto-connect by name, and `ad run` to hand a goal to the mobilerun LLM agent. Use when the user asks to run, test or drive an Android app or device, install an APK or a build on a device (installs on Pong go through the private device-drops repo, not adb push), reproduce an Android bug, check or review an app's UI, verify a UI change before they look at it (clipped pills, rough edges, polish), or take an Android screenshot or recording. Don't use for questions about adb or Android development that don't touch a device.
---

# android-control

`ad` drives the device; mobilerun is the agent it hands goals to.

- **`ad run "goal"`** hands a whole goal to mobilerun's LLM agent, which reads the screen
  and plans its own taps.
- **The rest of `ad`** is fast adb with no LLM: pick and connect the device, boot the
  emulator, look at the screen, tap, type, set user conditions, read logs.

```bash
A=~/.claude/skills/android-control/ad
$A devices                # connected devices, named targets, emulator state
$A -s pong status         # model, Android/API, ABI, screen, battery, Portal installed?
$A help                   # every subcommand
```

## 1. Pick the device

`-s TARGET` comes first on every call. TARGET is one of:

- a **named target** from `~/.config/ad/targets`, reached over Tailscale. `ad` connects
  it on demand and clears a stale `offline` entry.

  | Target | Device | Use it for |
  |---|---|---|
  | `pong` | the user's Nothing Phone 2: Android 16 (API 36), arm64, 1080x2412 at 420 dpi, Adreno GPU | phone sign-off; what the user actually sees |
  | `surface` | Surface Pro 7 on Bliss OS 18.8 (the user's experimental Android 15 build): x86_64, 2736x1824 at 320 dpi, Mesa GPU | tablet and landscape layouts; Android 15 behavior |

- `emu`, `emu2`, `emu3`, `emu4`: the local Android 16 emulators (`emulator-5554`, `-5556`,
  `-5558`, `-5560`), each a stock Pixel 7-like phone at 1080x2400 and 420 dpi with Google
  APIs, the same Android version as Pong, running arm64 apps through translation (install
  x86_64 builds where an app runs its own native binaries). 3 at once is the working limit;
  start the 4th (`$A -s emu4 emu start --allow-4th`) only after asking the user. `emu` (AVD
  `tl16`) keeps installs and settings between boots; `emu2`-`emu4` (AVD `tl16b`) are
  read-only and reset when stopped. So use `emu` when an install must persist, a pool slot
  for parallel or throwaway checks. For "any emulator" take `$A lease acquire --any
  "purpose"` (a running slot first, pool slots before `emu`); parallel subagents each take their own slot. A
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
it unset when calling `adb`, `mobilerun` or Gradle yourself, so all agents see the same
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

The device is ready when `$A -s X status` prints `portal: installed`. If it says missing,
run `mobilerun setup -d $($A -s X serial)`. That installs the Mobilerun Portal app and
enables its accessibility service, so on Pong, ask the user first.

## The app's map

Before driving an app, look for `docs/agents/device-map.md` in its repository. It names the
package, how to build and install, how to reach each screen (gestures, element ids, shortcut
commands), and where the app keeps its list of owed device checks. Follow it instead of
exploring; exploring is what makes a check slow. If the app has no map, or the map was wrong or
missing a step, end your report with the lines that should be added, so the next run is faster.

## 2. Whose device it is

- **Pong is the user's own phone**, with their accounts, messages and payment apps.
  - Run goals only for tasks the user asked for. Every mobilerun step sends the screen's
    text to the LLM provider.
  - Ask before you uninstall or clear a package you didn't install, and before you change
    `night`, `font`, `locale`, `airplane`, `size` or `density`. Restore every setting you
    changed.
  - Accounts, payments, messages and contacts are the user's to touch, never yours.
  - Note `$A -s pong top` first, and leave the same app in front when you finish.
- **Surface is the user's experimental Bliss OS build.** Treat it like a shared device (next
  bullet). Its OS is a test build, so separate OS glitches from app bugs before reporting.
- **The emulators belong to the agents.** They hold no user data, so they're the place for
  destructive steps: clearing data, fresh installs, airplane mode, odd sizes. Other agents
  share them, so the shared-device rule below still applies, and so does restoring what you
  change.
- **Shared devices:** run `$A top` before you act. If something other than
  the launcher or your own app is in front, another agent or the user is mid-flow, so ask.
- **A locked screen** needs the user to unlock it.

## 3. Drive: goal or steps, then verify

**Goal** (`ad run` for mobilerun, `ad codex` for Codex): use it when the path through the app doesn't matter, only the end
state does. `$A -s X run "Open Settings, go to Display and report whether Dark theme is on"`.
Describe the end state and what to report, and add "do not change anything" for
read-only questions. Options pass through to `mobilerun run`:

- default: the fast single agent, best for short tasks inside one app.
- `--reasoning`: adds a planner, for long tasks or tasks across several apps.
- `--vision`: sends screenshots too, for screens with a poor accessibility tree (Flutter
  apps, games, WebViews, canvases).
- `--steps N`: the step budget, 15 by default.

Expect about 20 s for a one-step read and a few minutes for an 8-step task.

`$A -s X codex "goal" [--map FILE] [codex exec flags]` hands the same kind of goal to the Codex
CLI, which drives the device through `ad` (so the lease holds) and lists the commands it ran.
On a Settings read it took 47 s against mobilerun's 81 s (one sample each). Both bill their own
provider, not Claude: let them navigate and keep your own tokens for judging what they found.

- **Model:** `-m gpt-6.1-sol` or `-m gpt-6.1-terra` after the goal; with no `-m`, Codex's own
  default applies. Reasoning effort is fixed at low; Codex runs ephemeral, with the `ad`
  command set and the lease directory as its whole world.
- **The app's map:** `--map docs/agents/device-map.md` appends the map to Codex's prompt, so it
  follows routes and ids instead of tapping around. With no flag, `$AD_MAP` or
  `./docs/agents/device-map.md` (when it exists) is used, so run it from the app's repository.
- **Output:** the answer prints to stdout; the log, prompt and screenshots stay in the
  `/tmp/ad-codex.*` directory named on stderr. `--json` makes the log JSONL with a
  `turn.completed` usage record, which is how to count steps and tokens for a benchmark.
Each mobilerun run selects its own keyboard, then `ime disable`s it at the end. That
leaves Android on whatever keyboard comes next (voice typing on Pong), not the user's.
`ad run` puts back both the selected keyboard and the enabled list, so launch mobilerun
only through `ad run`.

**Steps** (`ad`, about 1 s each): use them when the exact path matters, as in tests,
bug reproductions and typing into a terminal.

- `$A tap "Sign in"` matches text, desc or id, and prefers a clickable node.
  `$A tap 300 640` taps coordinates, and `$A long ...` long-presses.
- `$A type "hello"` types ASCII only. For a terminal, send one word per call with
  `$A key SPACE` between words, and `$A key ENTER` to run it. On the emulator `input text`
  drops a letter now and then ("Buy mik"), so read the field back with `ui` before `key ENTER`
  and retype if it is wrong.
- `$A swipe up|down|left|right`, `$A key ENTER TAB`, `$A back`, `$A home`.
- `$A launch PKG` starts the app's launcher activity and prints the start time.

**Verify.** A goal agent's "Goal achieved" is its own claim. The step is done when `ad` shows
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
it), motion frames on Pong when it moves, and, when the user asks for a review, a fresh
reviewer agent judging the crops without the code. The full steps and defect checklist are in
[references/visual-review.md](references/visual-review.md).

## 5. Apps, conditions, logs

- **Install:** `$A install app.apk` keeps the app's data, like an update. `--fresh`
  uninstalls first so the first-run flow shows, and `$A clear PKG` resets without
  reinstalling. Check the ABI with `status`: an APK built for another ABI fails with
  `INSTALL_FAILED_NO_MATCHING_ABIS`. Pong is arm64. The emulator is x86_64 and also runs
  arm64 builds through translation. Surface is x86_64 only.
- **Installs on a phone go through device-drops.** The Tailscale relay to a phone can crawl:
  on 2026-11-01 it ran at 11–33 KB/s, so a 58 MB `adb install` would have taken an hour and
  dropped when the phone changed network. Both ends reach GitHub fast, though. So for a named
  target whose line in `~/.config/ad/targets` carries `drop=SSH_ALIAS` (Pong: `drop=termux`),
  `$A -s pong install app.apk`:
  1. uploads the APK to the private repo `PickleHik3/device-drops` (release `inbox`);
  2. has the device's Termux download it over ssh, at its own connection's speed;
  3. runs `pm install` on it, read back through `run-as com.termux` (a staging or debug build
     of the Termux app) or from `/sdcard` when Termux has storage access;
  4. deletes the asset and the device's copy.

  It prints `Success` like `adb install`; then do the usual launch and crash check. Emulators,
  and targets without a `drop=` field, install over adb as before. `--direct` forces adb for
  one install, and is also how you `--fresh` the Termux app itself (the drop route runs
  through it). When the drop route fails, `ad` says why. The usual causes are no `gh` login in
  Termux, its ssh server down (start it with `$A -s pong runas com.termux /data/data/com.termux/files/usr/bin/sshd` on a staging
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
followers, monitor or polling loops, background shells and goal agents. Nothing of yours may keep
running against the device after your report: the next driver gets the device, not your leftovers.
Release the device's lease if you took it.

Give the user what they need to replay it without you:

- the device (from `status`)
- the exact `ad` and `ad run` commands
- what `ad` showed at the end, with paths to screenshots, zoom crops and frames
- for a UI change, each checklist finding and the reviewer's, with what you fixed
- any logcat lines
