#!/usr/bin/env python3
"""
GitHub Contribution Space Invaders
Usage:
    python generate_readme.py --demo
    python generate_readme.py --username USER --token ghp_xxx
"""

import sys, random, argparse
from pathlib import Path
from datetime import date, timedelta

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

# ─────────────────────────────────────────────────────────────────────────────
# GitHub API
# ─────────────────────────────────────────────────────────────────────────────

GQL = """
query {
  viewer {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""
LEVELS = {
    "NONE": "c0", "FIRST_QUARTILE": "c1",
    "SECOND_QUARTILE": "c2", "THIRD_QUARTILE": "c3", "FOURTH_QUARTILE": "c4",
}

def fetch(username, token):
    r = requests.post("https://api.github.com/graphql",
        json={"query": GQL},
        headers={"Authorization": f"bearer {token}"}, timeout=15)
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(body["errors"])
    cal = body["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]
    return cal["weeks"], cal["totalContributions"]

def make_demo(seed=0):
    rng = random.Random(seed)
    cur = date.today() - timedelta(weeks=52)
    cur -= timedelta(days=cur.weekday())
    weeks, total = [], 0
    for _ in range(52):
        days = []
        for _ in range(7):
            p = 0.12 if cur.weekday() >= 5 else 0.60
            v = rng.random()
            if   v > p + 0.35: lvl, n = "NONE", 0
            elif v > p + 0.20: lvl, n = "FIRST_QUARTILE",  rng.randint(1,2)
            elif v > p + 0.08: lvl, n = "SECOND_QUARTILE", rng.randint(2,4)
            elif v > p - 0.05: lvl, n = "THIRD_QUARTILE",  rng.randint(4,7)
            else:               lvl, n = "FOURTH_QUARTILE", rng.randint(7,15)
            days.append({"date": str(cur), "contributionCount": n, "contributionLevel": lvl})
            total += n
            cur += timedelta(days=1)
        weeks.append({"contributionDays": days})
    return weeks, total

# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────

SVG_W       = 800
SVG_H       = 440       # tall enough for grid at top, invaders at bottom

GX          = 14        # grid left
GY          = 38        # grid top  (just below score bar)
CELL        = 14        # 11px square + 3px gap
COLS        = 52
ROWS        = 7

N_INV_COLS  = 11
N_INV_ROWS  = 5
INV_SX      = 44        # horiz slot per invader  (11 × 44 = 484px)
INV_SY      = 28        # vert  slot per invader  (5  × 28 = 140px)

# Anchor from the bottom: player at bottom, formation just above it
PLAYER_Y    = SVG_H - 52
FORM_Y      = PLAYER_Y - N_INV_ROWS * INV_SY - 10   # formation top ≈ 248

FORM_X_MIN  = GX                                        # = 14
FORM_X_MAX  = GX + COLS * CELL - N_INV_COLS * INV_SX   # = 742 - 484 = 258

def sx(col): return GX + col * CELL
def sy(row): return GY + row * CELL

# ─────────────────────────────────────────────────────────────────────────────
# Animation timing
# ─────────────────────────────────────────────────────────────────────────────

CYCLE        = 16.0   # seconds – total loop
MARCH_DUR    = 7.0    # seconds per left→right leg  (formation)
PAUSE_DUR    = 1.0    # pause at each end

# Cannon fire positions (pixel x) — evenly spread across the screen
CANNON_X_MIN   = 30
CANNON_X_MAX   = SVG_W - 60        # = 740
RIGHT_FIRE_X   = [110, 240, 370, 500, 630]   # fires during left→right sweep
LEFT_FIRE_X    = [660, 530, 400, 270, 140]   # fires during right→left sweep
CANNON_SWEEP_T  = 5.0    # seconds of pure movement per direction
PAUSE_BEFORE    = 0.02   # stop before firing
PAUSE_AFTER     = 0.09   # stop after firing
PAUSE_FIRE      = PAUSE_BEFORE + PAUSE_AFTER   # = 0.35s total stop per shot
PAUSE_END       = 0.5    # brief pause at each edge

CYCLE = 2 * (CANNON_SWEEP_T + len(RIGHT_FIRE_X) * PAUSE_FIRE + PAUSE_END)  # ≈ 14.5s

LASER_SPEED = 350.0


def form_x_at(t: float) -> float:
    """Formation left-edge x — mirrors CSS @keyframes."""
    t %= CYCLE
    if t <= MARCH_DUR:
        return FORM_X_MIN + (FORM_X_MAX - FORM_X_MIN) * t / MARCH_DUR
    t -= MARCH_DUR
    if t <= PAUSE_DUR:
        return FORM_X_MAX
    t -= PAUSE_DUR
    if t <= MARCH_DUR:
        return FORM_X_MAX - (FORM_X_MAX - FORM_X_MIN) * t / MARCH_DUR
    return FORM_X_MIN


def build_cannon_trajectory():
    """
    Cannon moves left→right pausing at each RIGHT_FIRE_X, then right→left
    pausing at each LEFT_FIRE_X.  Returns:
      smil_times : list of floats (absolute seconds within CYCLE)
      smil_xs    : list of ints   (cannon center x)
      fire_events: list of (fire_t, lx)  — moment cannon stops & fires
    """
    total_range = CANNON_X_MAX - CANNON_X_MIN   # 710 px

    def seg_t(dist):
        return CANNON_SWEEP_T * abs(dist) / total_range

    times, xs, fires = [0.0], [CANNON_X_MIN], []
    t = 0.0

    for sweep_xs, x_start, x_end in [
        (RIGHT_FIRE_X, CANNON_X_MIN, CANNON_X_MAX),
        (LEFT_FIRE_X,  CANNON_X_MAX, CANNON_X_MIN),
    ]:
        positions = [x_start] + sweep_xs + [x_end]
        for i in range(1, len(positions)):
            t += seg_t(positions[i] - positions[i - 1])
            times.append(t); xs.append(positions[i])
            if i < len(positions) - 1:          # fire position
                fires.append((t + PAUSE_BEFORE, positions[i]))  # fire after 0.25s stop
                t += PAUSE_FIRE
                times.append(t); xs.append(positions[i])
        # pause at edge
        t += PAUSE_END
        times.append(t); xs.append(x_end)

    return times, xs, fires


def plan_events(weeks, seed=42):
    rng = random.Random(seed)
    active: dict[int, list[int]] = {}
    for w, week in enumerate(weeks[:COLS]):
        for d, day in enumerate(week["contributionDays"][:ROWS]):
            if LEVELS.get(day["contributionLevel"], "c0") != "c0":
                active.setdefault(w, []).append(d)

    used: set = set()

    def pick(col):
        for off in [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]:
            c = col + off
            if 0 <= c < COLS and c in active:
                cands = [d for d in active[c] if (c, d) not in used]
                if cands:
                    d = rng.choice(cands)
                    used.add((c, d))
                    return c, d
        return None

    _, _, fire_events = build_cannon_trajectory()
    events = []
    for fire_t, lx in fire_events:
        gc = max(0, min(COLS - 1, round((lx - GX) / CELL)))
        result = pick(gc)
        if result:
            tc, tr = result
            events.append((fire_t, lx, tc, tr))
    return events

# ─────────────────────────────────────────────────────────────────────────────
# SMIL key-time helper  — keyTimes MUST start at 0 and end at 1
# ─────────────────────────────────────────────────────────────────────────────

def kts(*times) -> str:
    """Convert absolute times (seconds) to keyTimes fractions.
    Forces the last entry to exactly '1'."""
    fracs = []
    for i, t in enumerate(times):
        if i == len(times) - 1:
            fracs.append("1")
        else:
            fracs.append(f"{min(t / CYCLE, 0.9998):.4f}")
    return "; ".join(fracs)

# ─────────────────────────────────────────────────────────────────────────────
# CSS for the formation march
# ─────────────────────────────────────────────────────────────────────────────

def march_css() -> str:
    p1 = MARCH_DUR / CYCLE * 100
    p2 = (MARCH_DUR + PAUSE_DUR) / CYCLE * 100
    p3 = (MARCH_DUR * 2 + PAUSE_DUR) / CYCLE * 100

    return f"""\
    .formation {{
      animation: march {CYCLE}s steps(15, end) infinite;
    }}
    @keyframes march {{
      0%       {{ transform: translate({FORM_X_MIN}px, {FORM_Y}px);
                 animation-timing-function: steps(15, end); }}
      {p1:.2f}%  {{ transform: translate({FORM_X_MAX}px, {FORM_Y}px);
                 animation-timing-function: step-end; }}
      {p2:.2f}%  {{ transform: translate({FORM_X_MAX}px, {FORM_Y}px);
                 animation-timing-function: steps(15, end); }}
      {p3:.2f}%  {{ transform: translate({FORM_X_MIN}px, {FORM_Y}px);
                 animation-timing-function: step-end; }}
      100%     {{ transform: translate({FORM_X_MIN}px, {FORM_Y}px); }}
    }}"""

# ─────────────────────────────────────────────────────────────────────────────
# SVG generation
# ─────────────────────────────────────────────────────────────────────────────

def gen_svg(weeks, total, events, label):

    # ── contribution grid ────────────────────────────────────────────────────
    grid = []
    for w, week in enumerate(weeks[:COLS]):
        for d, day in enumerate(week["contributionDays"][:ROWS]):
            cls = LEVELS.get(day["contributionLevel"], "c0")
            grid.append(f'  <rect id="s{w}-{d}" x="{sx(w)}" y="{sy(d)}" '
                        f'width="11" height="11" rx="2" class="{cls}"/>')
    grid_str = "\n".join(grid)

    # ── invader formation ────────────────────────────────────────────────────
    row_types = ["squid", "crab", "crab", "octopus", "octopus"]
    inv_uses = []
    for r in range(N_INV_ROWS):
        for c in range(N_INV_COLS):
            cx = c * INV_SX + (INV_SX - 27) // 2   # center 27px sprite in slot
            cy = r * INV_SY + (INV_SY - 18) // 2
            inv_uses.append(f'    <use href="#inv-{row_types[r]}" '
                            f'transform="translate({cx},{cy})"/>')
    inv_str = "\n".join(inv_uses)

    # ── laser + explosion + square-kill animations ───────────────────────────
    # Laser fires from the cannon tip upward
    # Subtract laser height so the bolt's bottom edge sits flush at the barrel tip
    LASER_H      = 18
    cannon_tip_y = PLAYER_Y - LASER_H

    anims = []
    for fire_t, lx, tc, tr in events:
        tgt_y    = sy(tr) + 5
        travel   = (cannon_tip_y - tgt_y) / LASER_SPEED   # positive = upward

        t0       = fire_t                   # laser fires
        t1       = fire_t + travel          # laser hits square
        t_exp    = t1 + 0.10               # explosion peak
        t_fade   = t1 + 0.35               # explosion fades out
        t_resp   = min(CYCLE * 0.93, t1 + 2.5)  # square respawns near end

        anims.append(f"""\
  <!-- fire@{fire_t:.1f}s x={lx} → sq({tc},{tr}) -->
  <rect x="{lx - 1}" y="{cannon_tip_y}" width="3" height="{LASER_H}" rx="1"
        fill="#ff0000" opacity="0">
    <animate attributeName="opacity"
      values="0; 0; 1; 1; 0; 0"
      keyTimes="{kts(0, t0, t0+0.01, t1, t1+0.01, CYCLE)}"
      dur="{CYCLE}s" repeatCount="indefinite"/>
    <animate attributeName="y"
      values="{cannon_tip_y}; {cannon_tip_y}; {cannon_tip_y}; {tgt_y}; {tgt_y}"
      keyTimes="{kts(0, t0, t0+0.01, t1, CYCLE)}"
      dur="{CYCLE}s" repeatCount="indefinite"/>
  </rect>
  <rect x="{sx(tc) - 4}" y="{sy(tr) - 4}" width="19" height="19" rx="3"
        fill="#ff6600" opacity="0">
    <animate attributeName="opacity"
      values="0; 0; 1; 0.4; 0; 0"
      keyTimes="{kts(0, t1, t_exp, t_fade, t_fade+0.15, CYCLE)}"
      dur="{CYCLE}s" repeatCount="indefinite"/>
  </rect>
  <rect x="{sx(tc)}" y="{sy(tr)}" width="11" height="11" rx="2"
        fill="#0d1117" opacity="0">
    <animate attributeName="opacity"
      values="0; 0; 1; 1; 0; 0"
      keyTimes="{kts(0, t1, t1+0.02, t_resp, t_resp+0.1, CYCLE)}"
      dur="{CYCLE}s" repeatCount="indefinite"/>
  </rect>""")

    anim_str = "\n".join(anims)

    # Cannon SMIL — moves to each fire position, pauses 0.5s, then continues
    c_times, c_xs, _ = build_cannon_trajectory()
    _cts = ["0"] + [f"{t/CYCLE:.4f}" for t in c_times[1:]]
    _cts[-1] = "1"
    cannon_kt = "; ".join(_cts)
    cannon_val = "; ".join(f"{x - 15},{PLAYER_Y}" for x in c_xs)  # -15 centers 30px sprite on fire x

    hi  = str(total * 10).zfill(6)
    sc  = str(total).zfill(6)

    css = march_css()

    return f"""\

<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {SVG_W} {SVG_H}" width="{SVG_W}" height="{SVG_H}">
  <defs>
    <style>
      /* Contribution square colours */
      .c0 {{ fill: #161b22; }}
      .c1 {{ fill: #0e4429; }}
      .c2 {{ fill: #006d32; }}
      .c3 {{ fill: #26a641; }}
      .c4 {{ fill: #39d353; }}
      /* Sprites */
      .inv  {{ fill: #ffffff; }}
      .inv2 {{ fill: #000000; }}   /* eye holes */
      /* UI text */
      .ui  {{ font-family: "Courier New", monospace; fill: #ffffff; font-size: 11px; }}
      .ui2 {{ font-family: "Courier New", monospace; fill: #39d353; font-size: 11px; }}
{css}
    </style>

    <!-- Squid (top row) 27×18 -->
    <g id="inv-squid">
      <rect x="9"  y="0"  width="9"  height="3" class="inv"/>
      <rect x="3"  y="3"  width="21" height="3" class="inv"/>
      <rect x="0"  y="6"  width="27" height="3" class="inv"/>
      <rect x="3"  y="6"  width="3"  height="3" class="inv2"/>
      <rect x="21" y="6"  width="3"  height="3" class="inv2"/>
      <rect x="0"  y="9"  width="27" height="3" class="inv"/>
      <rect x="6"  y="12" width="6"  height="3" class="inv"/>
      <rect x="15" y="12" width="6"  height="3" class="inv"/>
      <rect x="0"  y="15" width="3"  height="3" class="inv"/>
      <rect x="24" y="15" width="3"  height="3" class="inv"/>
    </g>

    <!-- Crab (middle rows) 27×18 -->
    <g id="inv-crab">
      <rect x="3"  y="0"  width="3"  height="3" class="inv"/>
      <rect x="21" y="0"  width="3"  height="3" class="inv"/>
      <rect x="6"  y="3"  width="15" height="3" class="inv"/>
      <rect x="0"  y="6"  width="27" height="3" class="inv"/>
      <rect x="6"  y="6"  width="3"  height="3" class="inv2"/>
      <rect x="18" y="6"  width="3"  height="3" class="inv2"/>
      <rect x="3"  y="9"  width="21" height="3" class="inv"/>
      <rect x="0"  y="12" width="9"  height="3" class="inv"/>
      <rect x="18" y="12" width="9"  height="3" class="inv"/>
      <rect x="0"  y="15" width="3"  height="3" class="inv"/>
      <rect x="9"  y="15" width="3"  height="3" class="inv"/>
      <rect x="15" y="15" width="3"  height="3" class="inv"/>
      <rect x="24" y="15" width="3"  height="3" class="inv"/>
    </g>

    <!-- Octopus (bottom rows, these fire the lasers) 27×18 -->
    <g id="inv-octopus">
      <rect x="6"  y="0"  width="15" height="3" class="inv"/>
      <rect x="0"  y="3"  width="27" height="3" class="inv"/>
      <rect x="0"  y="6"  width="27" height="3" class="inv"/>
      <rect x="3"  y="6"  width="3"  height="3" class="inv2"/>
      <rect x="21" y="6"  width="3"  height="3" class="inv2"/>
      <rect x="0"  y="9"  width="27" height="3" class="inv"/>
      <rect x="3"  y="12" width="6"  height="3" class="inv"/>
      <rect x="18" y="12" width="6"  height="3" class="inv"/>
      <rect x="0"  y="15" width="3"  height="3" class="inv"/>
      <rect x="9"  y="15" width="3"  height="3" class="inv"/>
      <rect x="15" y="15" width="3"  height="3" class="inv"/>
      <rect x="24" y="15" width="3"  height="3" class="inv"/>
    </g>

    <!-- Player cannon -->
    <g id="player">
      <rect x="12" y="0"  width="6"  height="3" class="ui2"/>
      <rect x="6"  y="3"  width="18" height="3" class="ui2"/>
      <rect x="0"  y="6"  width="30" height="6" class="ui2"/>
    </g>
  </defs>

  <!-- Background -->
  <rect width="{SVG_W}" height="{SVG_H}" fill="#000000"/>

  <!-- Score bar -->
  <text x="120" y="16" class="ui" text-anchor="middle">SCORE&lt;1&gt;</text>
  <text x="400" y="16" class="ui" text-anchor="middle">HI-SCORE</text>
  <text x="680" y="16" class="ui" text-anchor="middle">SCORE&lt;2&gt;</text>
  <text x="120" y="28" class="ui" text-anchor="middle">{sc}</text>
  <text x="400" y="28" class="ui" text-anchor="middle">{hi}</text>
  <text x="680" y="28" class="ui" text-anchor="middle">000000</text>

  <!-- ═══ INVADER FORMATION (CSS discrete-step march) ═══ -->
  <g class="formation">
{inv_str}
  </g>

  <!-- ═══ CONTRIBUTION GRID (@{label}'s real commit history) ═══ -->
{grid_str}

  <!-- ═══ LASERS + EXPLOSIONS ═══ -->
{anim_str}

  <!-- ═══ PLAYER SHIP — moves to each fire position, pauses, then continues ═══ -->
  <g>
    <use href="#player"/>
    <animateTransform attributeName="transform" type="translate"
      values="{cannon_val}"
      keyTimes="{cannon_kt}"
      calcMode="linear"
      dur="{CYCLE}s" repeatCount="indefinite"/>
  </g>

  <!-- Bottom bar -->
  <line x1="0" y1="{SVG_H - 22}" x2="{SVG_W}" y2="{SVG_H - 22}"
        stroke="#39d353" stroke-width="1"/>
  <text x="10"         y="{SVG_H - 7}" class="ui2">3</text>
  <use href="#player" transform="translate(26,{SVG_H - 20}) scale(0.65)"/>
  <use href="#player" transform="translate(56,{SVG_H - 20}) scale(0.65)"/>
  <use href="#player" transform="translate(86,{SVG_H - 20}) scale(0.65)"/>
  <text x="{SVG_W - 10}" y="{SVG_H - 7}" class="ui" text-anchor="end">CREDIT 00</text>

</svg>"""

# ─────────────────────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--username")
    p.add_argument("--token")
    p.add_argument("--out",  default=".")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--demo", action="store_true")
    args = p.parse_args()

    if args.demo:
        print("Demo mode")
        weeks, total = make_demo(args.seed)
        label = "your-username"
    elif args.username and args.token:
        print(f"Fetching @{args.username}...")
        weeks, total = fetch(args.username, args.token)
        label = args.username
        print(f"  {total:,} contributions")
    else:
        p.error("Use --demo  or  --username + --token")

    events = plan_events(weeks, args.seed)
    print(f"  {len(events)} fire events planned")

    svg = gen_svg(weeks, total, events, label)
    out = Path(args.out)
    (out / "space_invaders.svg").write_text(svg)
    (out / "README.md").write_text(
        f'# 👾 @{label}\n\n<p align="center">\n'
        f'  <img src="space_invaders.svg" width="{SVG_W}"/>\n</p>\n'
    )
    print("  Wrote space_invaders.svg + README.md")

if __name__ == "__main__":
    main()
