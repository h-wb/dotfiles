# Keeps CachyOS's own fish setup and adds mise. Aliases are mise [shell_alias].
source /usr/share/cachyos-fish-config/cachyos-config.fish

fish_add_path -g $HOME/.local/bin

if status is-interactive
    # mise last, so its tool dirs win on PATH.
    mise activate fish | source
else
    # `mise activate` is interactive-only; scripts and ssh commands get shims.
    mise activate fish --shims | source
end
