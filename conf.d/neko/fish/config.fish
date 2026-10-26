# neko's shell (the Macs stay on zsh). Aliases are mise [shell_alias].
fish_add_path -g $HOME/.local/bin

if status is-interactive
    set -g fish_greeting
    # mise last, so its tool dirs win on PATH.
    mise activate fish | source
    starship init fish | source
else
    # `mise activate` is interactive-only; scripts and the autostart get shims.
    mise activate fish --shims | source
end
