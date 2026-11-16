# The shared fish setup (layer `fish`). A machine's own lines go in its folder,
# linked as ~/.config/fish/conf.d/<machine>.fish: fish reads those first.
# Aliases are mise [shell_alias].
fish_add_path -g $HOME/.local/bin

if status is-interactive
    set -g fish_greeting
    # mise last, so its tool dirs win on PATH.
    mise activate fish | source
    command -q starship; and starship init fish | source
else
    # `mise activate` is interactive-only; scripts get shims.
    mise activate fish --shims | source
end
