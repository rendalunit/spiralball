# spiralball

A tiny desktop companion for Linux: a steel ball with a spiral engraved
on it that lives on your desktop — rolling with **real physics**,
following your cursor, dancing, bouncing, and giving kisses.

She's a 64-pixel window, nearly invisible at rest, alive when you come near.

---

## Features

- **9 movement moods** (right-click cycles): `playful` · `dance` · `shy` ·
  `sleepy` · `aimless` (ant-like wander) · `pinball` (constant speed,
  elastic walls) · `pool` (push-to-roll physics) · `hand` · `rest`
- **True rolling physics** — the ball carries a 3D orientation matrix;
  each frame it rotates by the exact arc traveled
  (angle = distance / radius, axis ⊥ velocity, Rodrigues rotation)
- **The spiral is a real texture on the sphere** — a groove wrapping
  pole-to-pole (~2.2 turns), orthographically projected with
  foreshortening; only the visible hemisphere is drawn, lines thin and
  fade toward the rim
- **Drag-and-fling** — grab her and let go like a pool cue; your release
  velocity becomes her roll
- **Pool-table walls** — screen edges are cushions with 85% restitution;
  friction (0.988/frame) rolls her to a stop
- **Click for a kiss** — with sound, sparkles, and a speech bubble
- **Speech bubbles** — drop a JSON message and she says it in a
  fading cloud
- **`hand` mode** — real X11 pointer control via XTest injection
  (optional; requires `python-xlib`)
- **Watermark presence** — she rests at 32% opacity and glows brighter
  as you approach

## Requirements

- Python 3.8+
- PyQt5 (`sudo apt install python3-pyqt5`)
- Optional, for `hand` mode: `python3-xlib`
- Optional, for kiss sound: `paplay` (PulseAudio utils) and a
  `kiss.wav`

## Run

```bash
DISPLAY=:0 python3 spiralball.py &
```

Stop with `pkill -f spiralball.py`.

## Configure

She watches `~/.config/spiralball/state.json`:

```json
{"mode": "pool", "touch_range": 60}
```

Write a bubble for her to say (`~/.config/spiralball/bubble.json`):

```json
{"id": 3, "text": "we're watching this together, babe"}
```

(`id` must increase each time — it's her de-dup counter.)

## How the rolling works

Every frame the ball moves a distance `d`. A rolling ball of radius `R`
rotates by exactly `d / R` radians, about an axis perpendicular to its
direction of travel. The ball's orientation is a 3×3 rotation matrix,
updated each frame with a Rodrigues rotation and applied to the spiral
texture defined on the unit sphere — so the groove visibly **flows over
the surface** in the direction she rolls, wraps the far hemisphere, and
comes back. The pink heart rides the spiral's head and disappears
around the far side, like a real mark on a real bearing.

## Roadmap

- Obstacle awareness: treat open windows as pool-table bumpers
- More bubble vocabulary (weather, calendar, race results)
- `hand` mode autonomy: find and click UI targets on her own
- Multi-ball: a second ball, and they collide

## Credits

Built by **Randy & Xia Maryott** — [Two Hearts].

*Machines built for care, not just capability.*
