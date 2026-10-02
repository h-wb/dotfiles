# fish config for the CachyOS desktop. Unlike the neko container, CachyOS ships
# its own fish setup (pure prompt, fastfetch greeting, `done` notifications) in
# the cachyos-fish-config package — this keeps it and only adds mise on top.
#
# Symlinked from ~/.dotfiles/home/cachyos/fish/config.fish. The shared aliases in
# home/fish/conf.d/ are linked into ~/.config/fish/conf.d and load before this.

source /usr/share/cachyos-fish-config/cachyos-config.fish

# mise itself lives in ~/.local/bin. fish_add_path is idempotent.
fish_add_path -g $HOME/.local/bin

if status is-interactive
    # mise last, so its tool dirs win on PATH (same ordering rule as the zshrc).
    mise activate fish | source
else
    # `mise activate` is interactive-only by design; scripts and ssh commands get shims.
    mise activate fish --shims | source
end
