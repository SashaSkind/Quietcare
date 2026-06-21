# Quietcare — Elder UI Design Options (morning review)

Three design directions for the elder-facing app, **same flow, three visual styles**.
Each lives on its own branch (PR) and has a recorded walkthrough + screenshots here.

## How to review (fastest first)

1. **Screenshots (open instantly in Preview):** each folder has `1-idle → 5-escalated.png`.
2. **Video walkthroughs:** `walkthrough.webm` in each folder. Plays in **Chrome** (double-click)
   or VLC. (QuickTime doesn't do webm — say the word and I'll convert to .mp4.)
3. **Run it live:** `git checkout <branch>` then `cd client && npm run web` → opens at `localhost:8088`.

## The flow you confirmed (same in all three)

`Idle / Listening (orb)` → **Simulate Fall** → `Check-in: "Margaret, are you okay?"`
with a **10s countdown** + big **"I'm OK"** and **"I need help"** buttons →

- **"I'm OK"** → logs silently, returns to idle (caretaker never bothered).
- **"I need help"** OR **countdown expires** → `Escalating` → `Caretaker notified · help on the way`.

Each walkthrough shows **both** the fine path and the auto-escalation path.

## The three options

| Branch | Name | Vibe | Orb |
|---|---|---|---|
| `design-a-aurora` | **Aurora** | Calm, clinical trust | Soft layered-glow sphere, slow breathing (teal/navy) |
| `design-b-pulse` | **Pulse** | High-contrast, accessible | Crisp concentric rings + bold core, electric cyan on black |
| `design-c-halo` | **Halo** | Premium, ambient | Circular audio-reactive waveform around a glowing core (violet) |

### A — Aurora
Softest and most "medical-trust." Reads as calm and reassuring; the blurred glow is gentle on tired eyes.

### B — Pulse
Most **accessible** — highest contrast, biggest shapes, clearest at a glance. Best fit for the doc's
"large text, simple controls, elder-legible" styling note. Strongest for a stage demo (reads from the back).

### C — Halo
Most **premium/modern**. The waveform makes the "it's listening to me" idea literal and feels high-end,
but it's the busiest visually.

## My recommendation
- **For the hero demo:** **Pulse** (B) — reads clearly on a projector, the red escalation is unmistakable.
- **For product polish / "ambient companion" pitch:** **Halo** (C).
- **Aurora** (A) is the safe, calm middle ground.

## Notes
- These are **web previews** (built with React Native primitives, so they drop straight into the native app).
- The native iOS dev build is still pending the EAS cloud build; these design branches are independent of that.
- Whichever you pick, I'll wire the chosen orb + check-in into the real client `App.tsx` and the live
  WebSocket state (`speak` / `listen` / `status`).

_Generated overnight. Pick one in the morning and tell me the branch name — I'll integrate it._
