<div align="center">

### ~/.dotfiles&nbsp;

#### \> Managed with *chezmoi*&nbsp;

</div>

## Overview

This repository contains my dotfiles managed by [chezmoi](https://github.com/twpayne/chezmoi).


## Set up new MacOS

1. Sign in to iCloud and App Store
2. Log-in to BWS and get a new access token for the device
3. Run `sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/main/install.sh)"`


## Personal

1. To test template
    `chezmoi execute-template --init --promptString email=me@home.org < ~/.local/share/chezmoi/home/.chezmoi.toml.tmpl`


## Inspiration

https://github.com/twpayne/dotfiles
https://github.com/narze/dotfiles
https://github.com/nandalopes/dotfiles
https://github.com/cweagans/dotfiles

## Misc.

`chezmoi state delete-bucket --bucket=entryState`
`chezmoi state delete-bucket --bucket=scriptState`

## Security & Privacy System Preferences

### Full Disk Access
Grant full disk access to these apps:
* iTerm

### Screen Recording
* AltTab

### Accessibility
* AltTab
* Discord
* Plexamp
* Raycast
* KeyClu
* Mos
