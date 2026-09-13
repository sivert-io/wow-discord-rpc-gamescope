# WoW Discord RPC for Gamescope / Wayland

[![CI](https://github.com/sivert-io/wow-discord-rpc-gamescope/actions/workflows/ci.yml/badge.svg)](https://github.com/sivert-io/wow-discord-rpc-gamescope/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/sivert-io/wow-discord-rpc-gamescope)](https://github.com/sivert-io/wow-discord-rpc-gamescope/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Discord Rich Presence for **World of Warcraft on Linux/Wayland**, using [CraftPresence WoW Edition](https://github.com/CDAGaming/CraftPresence-Wow-Edition) and direct capture from the X11 server nested inside Gamescope.

Designed for setups where WoW runs through **Gamescope + Proton/Wine** on Wayland compositors such as **Hyprland**.

The complete background/autostart flow has been verified in-game with WoW 3.3.5a, Gamescope, GE-Proton, Hyprland and native Discord.

## Why this exists

CraftPresence sends Rich Presence data by encoding it into a small strip of colored RGB frames inside the WoW window.

The upstream helper normally reads those pixels using platform screenshot APIs. On Wayland + Gamescope setups, that can break because:

* Wine/Win32 capture can target the wrong X server or fail through Gamescope.
* Capturing the final Wayland compositor output can rescale the RGB frames and corrupt the exact values CraftPresence encoded.

This wrapper instead captures the **actual WoW X11 window inside Gamescope**, before compositor scaling.

It then reconstructs the CraftPresence payload and passes it back to the upstream CraftPresence Discord RPC implementation.

## Requirements

* Linux
* Gamescope
* World of Warcraft running through Wine/Proton
* Native Discord client
* [CraftPresence WoW Edition](https://github.com/CDAGaming/CraftPresence-Wow-Edition)
* CraftPresence's upstream `Script/DiscordRichPresence.py`
* Python 3.10+
* systemd user services for optional autostart mode

Python dependencies are installed automatically by the installer.

## Quick install

Clone the repository:

```bash
git clone https://github.com/sivert-io/wow-discord-rpc-gamescope.git
cd wow-discord-rpc-gamescope
```

Then install with background/autostart support:

```bash
./install.sh "/path/to/World of Warcraft" --autostart
```

Example:

```bash
./install.sh "$HOME/Games/WoW-3.3.5a" --autostart
```

If exactly one `Wow.exe` exists below `~/Games`, you can omit the path:

```bash
./install.sh --autostart
```

No root privileges are required.

The installer will:

1. Verify the WoW and CraftPresence installation.
2. Create `~/.local/share/craftpresence-gamescope-venv`.
3. Install the required Python dependencies.
4. Install `DiscordRichPresenceGamescope.py` beside CraftPresence's upstream helper.
5. Create a default `config.json` if one does not already exist.
6. Optionally install and enable the systemd user service.

Existing `config.json` files are preserved.

## Autostart / background mode

With `--autostart`, the helper runs as a systemd user service.

It can start before WoW or Gamescope exists. It stays idle until WoW launches, automatically discovers the game's Gamescope X11 environment, reads the CraftPresence pixel data and connects to Discord.

When WoW exits, the helper stays available for the next launch.

This is launcher-independent: WoW can be started through Lutris, Steam, a shell command, UMU or another launcher.

Check the service:

```bash
systemctl --user status wow-discord-rpc-gamescope.service
```

Follow its logs:

```bash
journalctl --user -u wow-discord-rpc-gamescope -f
```

A successful launch looks similar to:

```text
Gamescope X11 capture enabled; waiting for World of Warcraft
Using Gamescope X11 display :1 with Xauthority /run/pressure-vessel/Xauthority
Not connected to Discord, connecting to ID 805124430774272000...
Setting new activity: {...}
```

## Updating

Update the repository:

```bash
git pull
```

Then rerun the installer:

```bash
./install.sh "/path/to/World of Warcraft" --autostart
```

The installer updates the virtual environment and helper while preserving an existing CraftPresence `config.json`.

## Disabling autostart

Temporarily stop the service:

```bash
systemctl --user stop wow-discord-rpc-gamescope.service
```

Disable it completely:

```bash
systemctl --user disable --now wow-discord-rpc-gamescope.service
```

Enable it again:

```bash
systemctl --user enable --now wow-discord-rpc-gamescope.service
```

## Uninstall

Disable and remove the background service:

```bash
systemctl --user disable --now wow-discord-rpc-gamescope.service
rm -f "$HOME/.config/systemd/user/wow-discord-rpc-gamescope.service"
systemctl --user daemon-reload
```

Remove the native helper from CraftPresence:

```bash
rm -f "/path/to/World of Warcraft/Interface/AddOns/CraftPresence/Script/DiscordRichPresenceGamescope.py"
```

Optionally remove the Python environment:

```bash
rm -rf "$HOME/.local/share/craftpresence-gamescope-venv"
```

Do **not** remove CraftPresence's upstream `DiscordRichPresence.py`; this wrapper depends on it.

## Manual mode

Autostart is optional.

Install without `--autostart`:

```bash
./install.sh "/path/to/World of Warcraft"
```

The installer prints the exact Python command required to launch the helper manually.

A manual installation can also be created with:

```bash
python -m venv ~/.local/share/craftpresence-gamescope-venv
~/.local/share/craftpresence-gamescope-venv/bin/python -m pip install -r requirements.txt
```

Then place:

```text
DiscordRichPresenceGamescope.py
```

beside:

```text
CraftPresence/Script/DiscordRichPresence.py
```

and run it with the virtual environment's Python interpreter.

## Automatic Gamescope detection

The helper inspects running `Wow.exe` processes through `/proc` and retrieves their `DISPLAY` and `XAUTHORITY` environment values.

This allows the background service to start before Gamescope exists.

Manual overrides are still available:

```bash
CRAFTPRESENCE_XDISPLAY=:2 \
CRAFTPRESENCE_XAUTHORITY=/path/to/Xauthority \
python DiscordRichPresenceGamescope.py
```

Explicit `CRAFTPRESENCE_*` variables take precedence over automatic detection.

For a systemd override:

```bash
systemctl --user edit wow-discord-rpc-gamescope.service
```

Example:

```ini
[Service]
Environment=CRAFTPRESENCE_XDISPLAY=:1
Environment=CRAFTPRESENCE_XAUTHORITY=/run/pressure-vessel/Xauthority
```

Then reload:

```bash
systemctl --user daemon-reload
systemctl --user restart wow-discord-rpc-gamescope.service
```

## CraftPresence settings

The wrapper expects the standard horizontal CraftPresence pixel strip at the top-left of the WoW window.

The verified settings are:

* Frame Width: `6`
* Frame Height: `6`
* Frame Anchor Point: `TOPLEFT`
* Use Vertical Frames: off
* Starting Frame X Position: `0`
* Starting Frame Y Position: `0`

CraftPresence Debug Mode is **not required during normal use**.

For troubleshooting, enable Debug Mode and run:

```text
/cp update debug
```

You should see the encoded colored strip at the top-left of the WoW window.

## How it works

The top edge of each CraftPresence frame can be blended by the rendering pipeline, while pixels inside the frame retain their exact RGB values.

The wrapper:

1. Finds the WoW window on Gamescope's nested X server.
2. Captures only the top portion of that window.
3. Prefers stable interior rows of the CraftPresence frames.
4. Collapses runs of identical pixels back into RGB triplets.
5. Ignores short blended transitions and CraftPresence separator pixels.
6. Validates the decoded payload and Discord application ID.
7. Passes the decoded data to CraftPresence's existing Discord RPC implementation.

Because capture happens inside Gamescope, host compositor scaling does not alter the encoded pixel values.

## Verified setup

The complete flow has been verified with:

* World of Warcraft 3.3.5a WotLK
* CraftPresence WoW Edition v2.16.4
* CraftPresence Python helper v1.9.0
* Gamescope 3.16.x
* Hyprland / Wayland
* UMU
* GE-Proton
* Native Discord
* Python 3.14
* 3840×2160 WoW resolution
* 1.25× host compositor scaling

Verified behavior includes:

* systemd service running before WoW
* automatic WoW detection
* automatic Gamescope `DISPLAY` detection
* automatic `XAUTHORITY` detection
* correct CraftPresence pixel decoding
* correct Discord application/client ID
* character, level, faction, realm and location updates
* Discord Rich Presence activation without manually starting the helper

Other Gamescope/Wayland configurations may work as well. Compatibility reports are welcome through GitHub Issues.

## Troubleshooting

### Service is running, but no Rich Presence appears

Watch the service log:

```bash
journalctl --user -u wow-discord-rpc-gamescope -f
```

Then enable CraftPresence Debug Mode in WoW and run:

```text
/cp update debug
```

Confirm that the colored CraftPresence strip appears in the top-left corner.

### Gamescope display detection is wrong

Normally no configuration is necessary.

You can force the display manually:

```bash
CRAFTPRESENCE_XDISPLAY=:1 python DiscordRichPresenceGamescope.py
```

For background mode, use a systemd override as described above.

### CraftPresence helper is missing

The wrapper does not replace CraftPresence.

Make sure this file exists:

```text
Interface/AddOns/CraftPresence/Script/DiscordRichPresence.py
```

Then rerun `install.sh`.

## Upstream / attribution

This project is an integration wrapper for [CraftPresence WoW Edition](https://github.com/CDAGaming/CraftPresence-Wow-Edition).

It depends on CraftPresence's existing `DiscordRichPresence.py` helper for payload interpretation and Discord RPC behavior.

CraftPresence is developed and licensed separately by its upstream project.

This repository does **not** redistribute the CraftPresence addon or upstream helper.

## License

MIT. See [LICENSE](LICENSE).
