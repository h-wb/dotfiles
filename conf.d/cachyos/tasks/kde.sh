# The `cachyos:kde` task: KDE keys that differ from CachyOS's defaults.
# kwriteconfig6 writes single keys (Plasma rewrites these files itself), needs
# no D-Bus, and Plasma reads them at the next login.
set -u
k() { kwriteconfig6 "$@" || echo "[warn] kwriteconfig6 $*"; }

# Mac modifiers come from xremap: drop the old XKB swap so the two don't stack,
# and tell the running session now.
k --file kxkbrc --group Layout --key Options ""
k --file kxkbrc --group Layout --key ResetOldOptions true
dbus-send --session --type=signal /Layouts org.kde.keyboard.reloadConfig 2>/dev/null || true

# A lone Super tap would open the launcher, and Super is what Control sends in apps.
k --file kwinrc --group ModifierOnlyShortcuts --key Meta ""
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true

# Natural scrolling on the Telink keyboard's touchpad (vendor/product id groups).
k --file kcminputrc --group Libinput --group 12815 --group 20616 \
	--group "Telink Wireless Gaming Keyboard" --key NaturalScroll true

# Default browser: the zen.desktop that zen-browser-bin installs.
for t in x-scheme-handler/http x-scheme-handler/https x-scheme-handler/chrome \
	text/html application/xhtml+xml application/x-extension-htm \
	application/x-extension-html application/x-extension-shtml \
	application/x-extension-xhtml application/x-extension-xht; do
	k --file mimeapps.list --group "Default Applications" --key "$t" zen.desktop
done

echo "[ok] kde settings applied"
