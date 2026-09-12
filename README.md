# WoW Discord RPC for Gamescope / Wayland

[![CI](https://github.com/sivert-io/wow-discord-rpc-gamescope/actions/workflows/ci.yml/badge.svg)](https://github.com/sivert-io/wow-discord-rpc-gamescope/actions/workflows/ci.yml)

A native Linux capture wrapper for [CraftPresence WoW Edition](https://github.com/CDAGaming/CraftPresence-Wow-Edition) that makes Discord Rich Presence work when World of Warcraft runs inside Gamescope on a Wayland desktop such as Hyprland.

Built and tested with World of Warcraft 3.3.5a, CraftPresence v2.16.4 / `DiscordRichPresence.py` v1.9.0, Gamescope, UMU/GE-Proton, Hyprland, and native Discord.

## Why this exists

CraftPresence encodes Discord Rich Presence data as colored RGB frames in the WoW window. The upstream helper normally captures those pixels with platform-specific screenshot APIs.

On Wayland + Gamescope setups:

- Wine/Win32 capture can target the wrong X server or fail through Gamescope.
- Capturing the final compositor output can rescale the RGB frames and corrupt the exact byte values CraftPresence encoded.

This wrapper reads the actual WoW X11 window from Gamescope's nested X server, samples stable frame interiors, reconstructs the encoded payload, validates it, and then reuses CraftPresence's upstream Discord RPC logic.

## Requirements

- Linux with Gamescope using a nested X11 server
- Native Discord client
- CraftPresence WoW Edition installed and working in-game
- Upstream `Script/DiscordRichPresence.py` from CraftPresence
- Python 3.10+
- `Pillow`
- `pypresence >= 4.6.0`
- `python-xlib`

## Quick install

Clone or download this repository, then run:

```bash
./install.sh "/path/to/World of Warcraft" --autostart
```

Example:

```bash
./install.sh "$HOME/Games/WoW-3.3.5a" --autostart
```

If there is exactly one `Wow.exe` below `~/Games`, the path can be omitted:

```bash
./install.sh --autostart
```

The installer:

1. Verifies WoW and CraftPresence.
2. Creates `~/.local/share/craftpresence-gamescope-venv`.
3. Installs the Python dependencies.
4. Copies `DiscordRichPresenceGamescope.py` beside CraftPresence's upstream helper.
5. Creates `config.json` if one does not already exist.
6. With `--autostart`, installs and enables a systemd user service.

No root privileges are required.

## Background/autostart mode

With `--autostart`, the helper starts as a **systemd user service** when you log in and stays idle until WoW appears. When WoW starts, it discovers the game's Gamescope X11 environment, reads the CraftPresence frames, and connects to native Discord. When WoW closes, Rich Presence is cleared and the helper waits for the next launch.

Check service status:

```bash
systemctl --user status wow-discord-rpc-gamescope.service
```

Follow logs:

```bash
journalctl --user -u wow-discord-rpc-gamescope -f
```

Stop it temporarily:

```bash
systemctl --user stop wow-discord-rpc-gamescope.service
```

Disable autostart:

```bash
systemctl --user disable --now wow-discord-rpc-gamescope.service
```

Enable it again:

```bash
systemctl --user enable --now wow-discord-rpc-gamescope.service
```

This approach is launcher-independent: Lutris, a shell command, Steam shortcuts, or other launch methods can all be used without changing the service.

## Manual install

Create a virtual environment and install dependencies:

```bash
python -m venv ~/.local/share/craftpresence-gamescope-venv
~/.local/share/craftpresence-gamescope-venv/bin/python -m pip install -r requirements.txt
```

Copy `DiscordRichPresenceGamescope.py` into CraftPresence's `Script` directory next to `DiscordRichPresence.py`:

```text
World of Warcraft/
└── Interface/
    └── AddOns/
        └── CraftPresence/
            └── Script/
                ├── DiscordRichPresence.py
                └── DiscordRichPresenceGamescope.py
```

Optionally create `config.json` there:

```json
{
  "debug": false,
  "scan_rate": 1
}
```

Run:

```bash
~/.local/share/craftpresence-gamescope-venv/bin/python \
  "/path/to/WoW/Interface/AddOns/CraftPresence/Script/DiscordRichPresenceGamescope.py"
```

A successful connection looks similar to:

```text
Gamescope X11 capture enabled; waiting for World of Warcraft
Using Gamescope X11 display :1 with Xauthority /run/pressure-vessel/Xauthority
Not connected to Discord, connecting to ID 805124430774272000...
Setting new activity: {...}
```

## Automatic Gamescope detection

The helper inspects the running `Wow.exe` process under `/proc` and uses its `DISPLAY` and `XAUTHORITY` values. This is important for background-service mode because Gamescope may not exist yet when the helper starts.

You can still force either value if needed:

```bash
CRAFTPRESENCE_XDISPLAY=:2 \
CRAFTPRESENCE_XAUTHORITY=/path/to/Xauthority \
python DiscordRichPresenceGamescope.py
```

Explicit `CRAFTPRESENCE_*` values take precedence over automatic detection.

## CraftPresence settings

The wrapper expects the normal horizontal CraftPresence pixel strip at the top-left of the WoW window. The tested settings are:

- Frame Width: `6`
- Frame Height: `6`
- Frame Anchor Point: `TOPLEFT`
- Use Vertical Frames: off
- Starting Frame X Position: `0`
- Starting Frame Y Position: `0`

CraftPresence Debug Mode is **not required for normal use**. For troubleshooting, enable it and run:

```text
/cp update debug
```

You should see the colored encoded strip at the top-left of WoW.

## How decoding works

On the tested setup, the top edge of each CraftPresence frame is blended by rendering, while interior rows retain the exact RGB values. The wrapper therefore:

1. Captures the top rows of the real WoW X11 window inside Gamescope.
2. Tries clean interior rows before blended edge rows.
3. Collapses stable runs of identical framebuffer colors into one RGB triplet.
4. Ignores short blended transitions and black separator pixels.
5. Requires a structurally valid CraftPresence packet and a plausible decimal Discord Client ID.

This bypasses Hyprland/output scaling entirely.

## Tested setup

- World of Warcraft 3.3.5a (WotLK)
- CraftPresence WoW Edition v2.16.4
- CraftPresence Python helper v1.9.0
- Gamescope 3.16.x
- Hyprland / Wayland
- UMU + GE-Proton
- Native Discord
- 3840x2160 game resolution
- 1.25x compositor scaling on the host

Other configurations may work. Compatibility reports are welcome through GitHub Issues.

## Troubleshooting

### The service is running but no Rich Presence appears

Follow the logs:

```bash
journalctl --user -u wow-discord-rpc-gamescope -f
```

Then in WoW enable CraftPresence Debug Mode and run `/cp update debug`. Confirm that the colored strip appears in the top-left.

### Wrong Gamescope display

Normally this is detected automatically. To override it:

```bash
CRAFTPRESENCE_XDISPLAY=:1 python DiscordRichPresenceGamescope.py
```

For a systemd service, add overrides with:

```bash
systemctl --user edit wow-discord-rpc-gamescope.service
```

For example:

```ini
[Service]
Environment=CRAFTPRESENCE_XDISPLAY=:1
Environment=CRAFTPRESENCE_XAUTHORITY=/run/pressure-vessel/Xauthority
```

Then run:

```bash
systemctl --user daemon-reload
systemctl --user restart wow-discord-rpc-gamescope.service
```

## Upstream / attribution

This project is an integration wrapper for CraftPresence WoW Edition and depends on its existing `DiscordRichPresence.py` helper for payload interpretation and Discord RPC behavior.

CraftPresence WoW Edition is developed by CDAGaming and is licensed separately by its upstream project:

https://github.com/CDAGaming/CraftPresence-Wow-Edition

This repository does not include the upstream CraftPresence addon or helper. Install CraftPresence separately and place this wrapper beside its helper.

## License

MIT. See [LICENSE](LICENSE).
