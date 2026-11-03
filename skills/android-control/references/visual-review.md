# Visual review: look at it the way the user will

The user keeps finding defects agents reported as "verified": a pill clipped flat on one
side, rough corners, text touching an icon. They come from four gaps:

- **Checking the tree, not pixels.** "The node exists and its text is right" passes even
  when the pill is clipped.
- **Shrunken screenshots.** A reader scales a 1080x2412 screenshot down to about 1568 px
  tall (0.65x), so a 1–2 px clip vanishes. `ad zoom` crops the element from the
  full-resolution screenshot and enlarges it, so every device pixel shows.
- **The emulator isn't the user's screen.** It is close to Pong's size and density
  (1080x2400, 420 dpi) but renders on the CPU. Blur, glass, anti-aliasing and rounded corners can
  look different on Pong's Adreno GPU.
- **The builder grading its own work.** A fresh reviewer that sees only the pixels is harsher.

## Steps

1. **List the surface.** From the diff, write down every element, screen and state the
   change touches: default, pressed or selected, disabled, empty, long text, error.
   Include the existing siblings it has to match.
2. **Pick the device.** Iterate on `emu` (Android 16 like Pong, 420 dpi). It renders on
   the CPU. Do the final look
   on Pong for phones and on
   `surface` (real Mesa GPU, 2736x1824) for tablet or landscape layouts. Run `ad -s X top`
   first. Record or touch a real device only when the user asked for a device check, or
   the launcher or your app is in front.
3. **Zoom every element.** `ad zoom "<text|desc|id>" out/name.png` (`--all` crops every
   match; `X1,Y1,X2,Y2` crops any region). Read each crop and go through the checklist
   below. Zoom the matching sibling too: the existing element is usually the reference
   for "correct".
4. **Repeat under conditions.** First record each setting's current value: `ad night`,
   `ad font`, `ad locale PKG`, `ad size` and `ad density` print it when given no value.
   Then redo step 3 in light and dark (`ad night no|yes`), at `ad font 1.3` (and `1.8` for
   text-heavy screens), and with `ad locale PKG ar-KW` when strings show. Afterwards, set
   each one back to the value you recorded. Don't use `reset` or a guessed default:
   a device may carry a deliberate size, density or theme that `reset` would wipe.
5. **Check motion.** If the change appears, expands, slides or transitions, run
   `ad -s pong frames 3 out/anim -- tap "<trigger>"`. Read `sheet.png` for the
   sequence, then crop the frames where edges move:
   `magick out/anim/f012.png -crop 400x200+80+60 +repage -filter point -resize 400% out/f012-zoom.png`.
   Judge motion on Pong: the emulator renders on the CPU, so its timing isn't real.
6. **Independent review.** This is part of "done", not optional. You built the change,
   so you see what you intended; a fresh agent sees what is there. Give the reviewer only:
   - the crop and full-screen paths, plus the folder's `zoom-index.tsv` (each crop's real
     size on the device and its scale, so touch-target and spacing calls are exact)
   - the device's density (`ad density`): 48dp is 126 px at 420 dpi and 96 px at 320 dpi
   - one sentence on what the user does on this screen
   - the checklist below

   Leave out the code and what you meant the change to do. Ask for every flaw a picky user
   would notice, with the file and the spot. List each image path by name, crops first,
   with the condition it shows (theme, font, locale). Reviewers given only a folder open a
   few full screens and skip the crops. Ask the reviewer to read every listed file and to
   say which ones it read.
   - **If you can spawn agents** (you are the main session), spawn one general-purpose
     agent with that brief.
   - **If you can't** (you are a delegated worker), end your report with a
     `Reviewer brief:` block containing exactly that brief, so the main session can run it.
7. **Done** when all of these hold:
   - every listed element has a crop you read under every relevant condition
   - motion is checked, or listed as owed on a named device
   - the reviewer ran and each finding is fixed or reported, or, as a worker, your report
     ends with the `Reviewer brief:` block
   - every setting reads back the value you recorded in step 4

   Put the crop paths in the report.

## Checklist

- **Clipped edges:** a pill, chip, badge, shadow, ripple or focus ring cut flat by its
  parent, where a straight edge appears that should be a curve. Check all four sides.
- **Corners and seams:** jagged or stair-stepped curves; a nested shape whose radius
  doesn't follow its parent's; hairline gaps or double lines between a fill and its
  border; a background that bleeds past its outline.
- **Text:** truncated or cut glyphs, text touching or overlapping an icon, a baseline off
  from its icon's center, weak contrast on the real background (wallpaper, glass, dark mode).
- **Alignment and spacing:** a few pixels off from siblings; uneven padding inside a pill
  (left vs right, top vs bottom); uneven gaps between repeated items.
- **Icons:** blurry from a scaled bitmap, off-center in their container, a different size
  or weight from their siblings.
- **Touch targets:** smaller than 48dp (126 px at 420 dpi).
- **Colour:** wrong in one theme, hardcoded white or black, invisible on a light wallpaper.
- **Motion:** content clipped mid-animation, a jump at the start or end, flicker, or an
  end state that doesn't match the static layout.
