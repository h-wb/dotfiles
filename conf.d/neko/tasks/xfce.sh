# The `neko:xfce` task (skips without an XFCE session). Writes land in
# ~/.config/xfce4/xfconf, on the PVC.
set -u
x() { # x <channel> <property> <type> <value>
  xfconf-query -c "$1" -p "$2" --create -t "$3" -s "$4" 2>/dev/null \
    || echo "[warn] could not set $1 $2"
}

# ── Fonts & rendering ──────────────────────────────────────────────────────
# The desktop is re-encoded as video, and subpixel fuzz is what an encoder
# wastes bitrate on: slight hinting, no subpixel.
x xsettings /Gtk/FontName          string "Sans 10"
x xsettings /Gtk/MonospaceFontName string "MesloLGS NF 11"
x xsettings /Xft/Antialias         int    1
x xsettings /Xft/Hinting           int    1
x xsettings /Xft/HintStyle         string "hintslight"
x xsettings /Xft/RGBA              string "none"
x xsettings /Xft/DPI               int    96
x xsettings /Net/EnableEventSounds int    0
x xsettings /Net/EnableInputFeedbackSounds int 0

# ── Window manager ─────────────────────────────────────────────────────────
# Compositing is pure CPU cost when the "screen" is a gstreamer pipeline.
x xfwm4 /general/use_compositing bool  false
x xfwm4 /general/workspace_count int   1
x xfwm4 /general/title_font      string "Sans Bold 9"
x xfwm4 /general/zoom_desktop    bool  false

# ── Desktop ────────────────────────────────────────────────────────────────
x xfce4-desktop /desktop-icons/style int 0

# ── Session ────────────────────────────────────────────────────────────────
# A pod that rolls constantly should come back to a known desktop.
x xfce4-session /general/SaveOnExit          bool false
x xfce4-session /shutdown/LockScreen         bool false
x xfce4-session /startup/ssh-agent/enabled   bool false   # pass-cli runs the agent
x xfce4-session /startup/gpg-agent/enabled   bool false

# ── Never blank, never lock ────────────────────────────────────────────────
# Nobody sits at this screen; a blanked display just streams black.
# (neko-bootstrap's `xset s off -dpms` covers the X server side.)
x xfce4-power-manager /xfce4-power-manager/dpms-enabled              bool false
x xfce4-power-manager /xfce4-power-manager/blank-on-ac               int  0
x xfce4-power-manager /xfce4-power-manager/dpms-on-ac-sleep          int  0
x xfce4-power-manager /xfce4-power-manager/dpms-on-ac-off            int  0
x xfce4-power-manager /xfce4-power-manager/lock-screen-suspend-hibernate bool false
x xfce4-screensaver /saver/enabled bool false
x xfce4-screensaver /lock/enabled  bool false

# ── Keyboard ───────────────────────────────────────────────────────────────
x keyboards /Default/KeyRepeat/Delay int 200
x keyboards /Default/KeyRepeat/Rate  int 40

# Not Super: the browser tab running neko rarely sees it.
x xfce4-keyboard-shortcuts "/commands/custom/<Primary><Alt>t" string "xfce4-terminal"

# ── Thunar ─────────────────────────────────────────────────────────────────
x thunar /last-view          string "ThunarDetailsView"
x thunar /misc-single-click  bool   false

# ── Panel ──────────────────────────────────────────────────────────────────
# Autohide the bottom dock; a customised layout may have no panel-2.
if xfconf-query -c xfce4-panel -p /panels/panel-2 >/dev/null 2>&1; then
  x xfce4-panel /panels/panel-2/autohide-behavior int 2
  x xfce4-panel /panels/panel-2/size              int 44
fi

echo "[ok] xfce settings applied"
