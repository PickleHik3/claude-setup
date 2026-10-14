# Emulating end users

Each row is a user the app will meet. Before setting a condition, record its current value
(`ad night`, `ad font`, `ad size`, `ad density` and `ad locale PKG` print it with no value).
Run the flow under test as that user (`ad run` for the flow, `ad` to verify), then set the
recorded value back. The deliverable is
a screenshot at each condition; the finding is the difference between them.

| User | Set it | Reset | Watch for |
|---|---|---|---|
| First-time user | `ad install app.apk --fresh` or `ad clear PKG`, then `ad launch PKG` | — | onboarding shown once, empty states, no stale data, permission prompts in the right order |
| Returning user after update | `ad install new.apk` over the old build | — | migrations, login kept, no forced re-onboarding |
| Denies a permission | `ad perm PKG revoke android.permission.CAMERA` (see `ad perms PKG`) | `grant` | rationale, graceful fallback, no crash, a way to ask again |
| Dark mode | `ad night yes` (or `no` if it was already on) | the recorded value | unreadable text, hardcoded white cards, icons that vanish |
| Large fonts | `ad font 1.3`, then `1.8` | the recorded value | clipped labels, overlapping buttons, truncated `...`, buttons pushed off-screen |
| Arabic / RTL (Kuwait) | `ad locale PKG ar-KW` (per app, no restart) | `ad locale PKG ""` | mirrored layout, untranslated strings, numerals, date and currency formats, text direction in inputs |
| Offline / flaky | `ad airplane enable` before or during the flow | `ad airplane disable` | spinners that never end, error copy, retry, cached content, queued writes |
| Different phone | `ad size 1080x2340` + `ad density 420`; for a real tablet use `-s surface` | the recorded values (`reset` would wipe a deliberate override) | breakpoints, tablet two-pane layout, overflow on small screens |
| Backgrounded, then killed | `ad home`, `ad kill PKG`, `ad launch PKG` | — | state restored, form contents kept, login kept, no blank screen |
| Impatient tapper | `ad run "tap Submit twice quickly"`, or two quick `ad tap` calls | — | duplicate submissions, double navigation, crash on back |
| Screen-reader user | `ad ui`, and read the `desc` fields | — | icon buttons with no description, unlabeled inputs, tap targets under 48dp (bounds) |
| Chaos | `ad shell monkey -p PKG --throttle 300 --pct-syskeys 0 -v 500` | — | crashes in `ad crash`, ANRs (see debugging.md) |

Deep links and notifications: run `ad open "https://app.example/x"` or `ad open "myapp://x"`
three ways: with the app cold, backgrounded, and already on that screen. Real users arrive
from all three.

Back navigation: after any flow, run `ad back` until the launcher shows, and note
every screen you pass. Loops, skipped screens and an exit that lands somewhere unexpected
are bugs.
