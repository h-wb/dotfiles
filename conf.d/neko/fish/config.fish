# fish config for the neko/xfce container. The Macs stay on zsh + z4h + p10k;
# this box gets fish because it is a disposable desktop, not a machine where
# 15 years of zsh muscle memory needs to keep working.
#
# Lives in the dotfiles repo at conf.d/neko/fish/. Aliases come from mise
# ([shell_alias]), set by the `mise activate` below.

# ~/.local/bin holds mise itself plus the ~/.local/opt app shims (code, firefox).
# fish_add_path is idempotent, so this is safe to re-run.
fish_add_path -g $HOME/.local/bin

if status is-interactive
    set -g fish_greeting # no "Welcome to fish" banner

    # mise last, so its tool dirs win on PATH (same ordering rule as the zshrc).
    mise activate fish | source
    starship init fish | source
else
    # Non-interactive shells (scripts, ssh commands, the xfce autostart) get the
    # shims instead: `mise activate` is interactive-only by design.
    mise activate fish --shims | source
end
