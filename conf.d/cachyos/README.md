---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-25
summary: What the CachyOS gaming desktop gets from this repo, and the KDE, keyboard and projector fixes that are easy to undo by mistake.
created: 2026-11-24T20:55
---

# The CachyOS desktop

A real Arch box: KDE Plasma, fish, NVIDIA, systemd, a monitor and a projector. Class `cachyos` is layers `workstation` and `fish` plus `conf.d/cachyos/`. None of neko's limits apply: apps are `pacman:` packages, services are systemd units, and the firewall is ufw through `[bootstrap.linux.firewall]`. sudo needs a password there, so run an apply over `ssh -t`.

## What it holds

- Only what was added after the installer, read from `/var/log/pacman.log` (install dates are useless: a full `-Syu` reset them). Theme, cursor, animation speed and the fish prompt are CachyOS's `/etc/skel` defaults; do not declare them. The shared `fish` layer's `config.fish` loads `fish/cachyos.fish`, which sources CachyOS's own fish config and sets `dotfiles_native_prompt`, so CachyOS keeps its greeting and prompt instead of starship. Switching to starship is the owner's call. `pacman -Qm` lib32 entries are orphans.
- No AUR helper: the packages needed are in the cachyos repo. RetroDECK is a system flatpak; Arch's flatpak ships the flathub remote, so the `pre-packages` hook only makes sure flatpak exists.
- The machine boots into the Steam Big Picture session; leaving it lands on the Plasma login.

## KDE

- Settings are `kwriteconfig6` keys in `cachyos:kde`, not dotfiles: Plasma and other apps rewrite those rc files and `mimeapps.list` themselves.
- Global shortcuts go through kglobalaccel's D-Bus, not `kglobalshortcutsrc`: kglobalaccel runs inside KWin on Plasma 6 Wayland, so an edited file is invisible until the next login. `cachyos:kwin-switcher` adds Ctrl+Tab and Ctrl+\` (Cmd+Tab and Cmd+\`) to KWin's switchers with `setForeignShortcutKeys`, which applies live and persists. A held Cmd+Tab cannot be a remap (xremap would release the modifier), which is why the switcher itself listens on Ctrl.

## A Mac keyboard: xremap

`xremap/config.yml`, the KDE build from mise, run by the `dev.mise.xremap` user unit bound to the Plasma session, so the gamescope session gets a plain keyboard.

- The keyboard's Ctrl, Win and Alt act as Control, Option and Command. Command sends Ctrl in apps (so Ctrl+C and the like work) and Super in terminals, where it maps to Ctrl+Shift; the physical Control stays a real Ctrl. Steam games (`/^steam_app_/`) are left out.
- Key names are evdev (`LeftBrace`, `PageUp`, `SysRq` for Print Screen), not X11 keysyms.
- App names are KWin's resourceClass. To list them, load a throwaway KWin script that `print`s `workspace.windowList()` and read the journal.
- Device access is a udev `uaccess` rule for that keyboard only, not the `input` group, which would expose every input device.

## The projector

A gamescope-session drop-in pins `OUTPUT_CONNECTOR`, and a gamescope Lua display script forces SDR Rec.709/D65: the projector's EDID claims an HDR mode the GPU cannot drive at 4K60, and a wrong white point. Doctor `gamescope-projector` catches a session-script update that renames the variable.

## Decky Loader

`cachyos:decky` runs the official installer, which cannot be piped to `sh` (it re-executes itself with sudo and uses bash here-strings) and needs Steam to have run once. The romm-tender plugin's settings hold an API token and are not managed here.
