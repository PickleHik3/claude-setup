---
name: android-control
description: Drive an Android device (the Pong phone and the Surface tablet over Tailscale, the local Android 16 emulator, any adb device) like a user, through `ad`: fast adb steps (tap, type, look, user conditions, logs), emulator boot, auto-connect by name, and `ad run` to hand a goal to the mobilerun LLM agent. Use when the user asks to run, test or drive an Android app or device, reproduce an Android bug, check or review an app's UI, verify a UI change before they look at it (clipped pills, rough edges, polish), or take an Android screenshot or recording. Don't use for questions about adb or Android development that don't touch a device.
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
  "purpose"` (prefers one already running); parallel subagents each take their own slot. A
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
devices. Raw adb goes through `$A -s X adb ...`, and builds through
`ANDROID_SERIAL=$($A -s X serial) ./gradlew installDebug`.

**Lease the device before you change anything on it.** Sessions from every account share these
devices, so one driver at a time:

```bash
$A -s emu lease acquire "verify palette chips"   # --wait to queue, --for MIN (default 30)
$A lease acquire --any "purpose"                 # first free emulator slot, a running one first
$A -s emu lease status                           # who holds what
$A -s emu lease release                          # when done; stops an emulator your lease started
```

Looking (`status`, `top`, `ui`, `find`, `shot`, `zoom`, `logcat`, getters) needs no lease;
every command that can change the device refuses without one and names the holder. Each
command extends your lease by 10 minutes. Subagents share their session's lease.

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

`$A -s X codex "goal"` hands the same kind of goal to the Codex CLI, which drives the device
through `ad` (so the lease holds) and lists the commands it ran. On a Settings read it took
47 s against mobilerun's 81 s. Both bill their own provider, not Claude: let them navigate
and keep your own tokens for judging what they found.
Each mobilerun run selects its own keyboard, then `ime disable`s it at the end. That
leaves Android on whatever keyboard comes next (voice typing on Pong), not the user's.
`ad run` puts back both the selected keyboard and the enabled list, so launch mobilerun
only through `ad run`.

**Steps** (`ad`, about 1 s each): use them when the exact path matters, as in tests,
bug reproductions and typing into a terminal.

- `$A tap "Sign in"` matches text, desc or id, and prefers a clickable node.
  `$A tap 300 640` taps coordinates, and `$A long ...` long-presses.
- `$A type "hello"` types ASCII only. For a terminal, send one word per call with
  `$A key SPACE` between words, and `$A key ENTER` to run it.
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

## 4. Visual review: required for any UI change

The user looks at the result on Pong with their own eyes, and they keep finding what
agents called "verified": a pill clipped flat on one side, rough corners, text touching
an icon. A UI change is done only when you've reviewed it the way the user will:

- zoom every changed element and the sibling it should match, under light, dark, large
  font and RTL. Read each setting first (`$A night`, `$A font` with no argument) and
  restore that value.
- check its motion frames on Pong, and on `surface` when the layout differs on tablets
- have a fresh reviewer agent judge the crops without seeing the code. This step isn't
  optional: you built the change, so your eye forgives exactly what the user's won't.

Follow [references/visual-review.md](references/visual-review.md) for the steps and the
defect checklist. The accessibility tree and `Goal achieved` can confirm what is on the
screen, but not how it looks.

## 5. Apps, conditions, logs

- **Install:** `$A install app.apk` keeps the app's data, like an update. `--fresh`
  uninstalls first so the first-run flow shows, and `$A clear PKG` resets without
  reinstalling. Check the ABI with `status`: an APK built for another ABI fails with
  `INSTALL_FAILED_NO_MATCHING_ABIS`. Pong is arm64. The emulator is x86_64 and also runs
  arm64 builds through translation. Surface is x86_64 only.
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
