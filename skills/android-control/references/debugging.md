# Debugging on a device

Start every repro with `ad logclear`, then run `ad logcat PKG` in a background shell, so the
log covers exactly the steps you took. Extra logcat args pass through:
`ad logcat PKG '*:E'`.

| Symptom | Tool | Notes |
|---|---|---|
| Crash / exception | `ad crash` | Crash buffer only. The full stack is in `ad logcat PKG`, around `FATAL EXCEPTION`. |
| App hangs, "isn't responding" | `ad shell cat /data/anr/anr_latest` | Needs root: on `emu`, run `ad -s emu adb root` first. |
| Wrong screen / back stack | `ad top`, `ad shell dumpsys activity activities` | The resumed activity, and the task history. |
| Slow start | `ad stop PKG`, then `ad shell am start -W -n PKG/.Activity` | `TotalTime` is the cold start in ms. |
| Jank | `ad shell dumpsys gfxinfo PKG` | Frame stats since the last reset; add `reset` to zero them. The emulator renders on the CPU, so its numbers are worst-case. |
| Memory | `ad shell dumpsys meminfo PKG` | Run `ad kill PKG`, then relaunch, to check for leaks across process death. |
| Network | `ad airplane enable` | There is no per-app network switch. `ad shell svc wifi disable` also works. |
| Permissions state | `ad perms PKG` | Runtime grants. Change them with `ad perm PKG grant\|revoke android.permission.X`. |
| Files the app wrote | `ad shell run-as PKG ls files/` | Debuggable builds only. Use `ad adb pull` for `/sdcard` paths. |
| Database | `ad shell run-as PKG cat databases/app.db > /tmp/app.db`, then `sqlite3` on the host | |
| Raw UI XML | `ad shell uiautomator dump /sdcard/u.xml && ad adb exec-out cat /sdcard/u.xml` | When `ad ui` hides an attribute you need. |
| What mobilerun did | the `mobilerun run` output, step by step | Add `--save-trajectory step` to keep each step's screen state. |
| Debugger | Android Studio lists the same serial `ad serial` prints | Attach normally. |

Arbitrary shell: `ad shell CMD` runs as the adb shell user. On `emu`, `ad -s emu adb root`
restarts adbd as root (Google APIs image), for setprop, `/data` and system settings that adb refuses.
