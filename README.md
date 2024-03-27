<div align="center">

### ~/.dotfiles&nbsp;

#### \> Managed with *chezmoi*&nbsp;

</div>

## Overview

This repository contains my dotfiles managed by [chezmoi](https://github.com/twpayne/chezmoi).


## Set up new MacOS

1. Sign in to iCloud and App Store
2. Run `./install.sh`
3. Run `exec zsh`
4. `chezmoi init https://github.com/h-wb/dotfiles.git`


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

