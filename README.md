# WoW Discord RPC for Gamescope / Wayland

A native Linux capture wrapper for [CraftPresence WoW Edition](https://github.com/CDAGaming/CraftPresence-Wow-Edition) that makes Discord Rich Presence work when World of Warcraft is running inside Gamescope on a Wayland desktop such as Hyprland.

It was built and tested with World of Warcraft 3.3.5a, CraftPresence v2.16.4 / `DiscordRichPresence.py` v1.9.0, Gamescope, UMU/GE-Proton, Hyprland, and native Discord.

## Why this exists

CraftPresence encodes Discord Rich Presence data as colored RGB frames in the WoW window. The upstream helper normally captures those pixels with platform-specific screenshot APIs.

On a Wayland + Gamescope setup there are two common problems:

- Wine/Win32 capture can target the wrong X server or fail through Gamescope.
- Capturing the final Hyprland output can rescale the RGB frames (for example 1.25x display scaling), corrupting the exact byte values CraftPresence encodes.

This wrapper reads the real WoW X11 window directly from Gamescope's nested X server. It then ignores blended frame edges, collapses stable RGB runs back into CraftPresence byte triplets, validates the payload, and lets the current upstream helper handle Discord RPC.

## Requirements

- Linux with Gamescope using a nested X11 server
- Native Discord client
- CraftPresence WoW Edition installed and working in-game
- The upstream `Script/DiscordRichPresence.py` file from CraftPresence
- Python 3.10+
- `Pillow`
- `pypresence >= 4.6.0`
- `python-xlib`

Install the Python dependencies in a virtual environment:

```bash
python -m venv ~/.local/share/craftpresence-gamescope-venv
~/.local/share/craftpresence-gamescope-venv/bin/python -m pip install -r requirements.txt
```

## Install

Copy `DiscordRichPresenceGamescope.py` into CraftPresence's `Script` directory next to the upstream `DiscordRichPresence.py`:

```text
World of Warcraft/
└── Interface/
    └── AddOns/
        └── CraftPresence/
            └── Script/
                ├── DiscordRichPresence.py
                └── DiscordRichPresenceGamescope.py
```

Optionally create `config.json` in that same `Script` directory:

```json
{
  "debug": false,
  "scan_rate": 1
}
```

## Run

Start WoW normally through Gamescope, then run:

```bash
~/.local/share/craftpresence-gamescope-venv/bin/python \
  /path/to/WoW/Interface/AddOns/CraftPresence/Script/DiscordRichPresenceGamescope.py
```

A successful startup should eventually log something like:

```text
Using direct Gamescope X11 capture on :1
Not connected to Discord, connecting to ID 805124430774272000...
Setting new activity: {...}
```

## Gamescope display / Xauthority

The defaults match a common UMU / Pressure Vessel Gamescope setup:

```text
DISPLAY=:1
XAUTHORITY=/run/pressure-vessel/Xauthority
```

If yours differs, override either value:

```bash
CRAFTPRESENCE_XDISPLAY=:2 \
CRAFTPRESENCE_XAUTHORITY=/path/to/Xauthority \
python DiscordRichPresenceGamescope.py
```

You can inspect a running WoW process to find these values, for example:

```bash
tr '\0' '\n' < /proc/$(pgrep -f -i 'Wow.exe' | tail -n 1)/environ \
  | grep -E '^(DISPLAY|XAUTHORITY)='
```

## CraftPresence settings

The wrapper expects the normal horizontal CraftPresence pixel strip at the top-left of the WoW window. The defaults used during development were:

- Frame Width: `6`
- Frame Height: `6`
- Frame Anchor Point: `TOPLEFT`
- Use Vertical Frames: off
- Starting Frame X Position: `0`
- Starting Frame Y Position: `0`

For troubleshooting, enable CraftPresence Debug Mode in-game and run:

```text
/cp update debug
```

You should see the colored encoded strip at the top-left of WoW.

## How decoding works

On the tested setup, the top edge of each 6px CraftPresence frame was blended by the renderer, while interior rows retained exact RGB values. The wrapper therefore:

1. Captures the top rows of the actual WoW X11 window inside Gamescope.
2. Tries clean interior rows before the blended edge rows.
3. Collapses stable runs of identical framebuffer colors into one RGB triplet.
4. Ignores short blended transition runs and black separator pixels.
5. Requires a structurally valid CraftPresence packet and a decimal Discord Client ID before accepting the decode.

This keeps Hyprland/output scaling out of the capture path entirely.

## Tested setup

- World of Warcraft 3.3.5a (WotLK)
- CraftPresence WoW Edition v2.16.4
- CraftPresence Python helper v1.9.0
- Gamescope 3.16.x
- Hyprland / Wayland
- UMU + GE-Proton
- Native Discord
- 3840x2160 game resolution
- 1.25x compositor scaling on the host (bypassed by the direct X11 capture)

Other configurations may work, but are not yet as well tested.

## Upstream / attribution

This project is an integration wrapper for CraftPresence WoW Edition and depends on its existing `DiscordRichPresence.py` helper for payload interpretation and Discord RPC behavior.

CraftPresence WoW Edition is developed by CDAGaming and is licensed separately by its upstream project:

https://github.com/CDAGaming/CraftPresence-Wow-Edition

This repository does not include the upstream CraftPresence addon or its helper; install CraftPresence separately and place this wrapper beside its helper.

## License

MIT. See [LICENSE](LICENSE).
