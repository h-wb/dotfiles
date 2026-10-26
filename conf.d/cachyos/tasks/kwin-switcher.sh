# The `cachyos:kwin-switcher` task: Cmd+Tab / Cmd+` (Command sends Ctrl).
# A held modifier can't be faked by a remap, so Ctrl is added to KWin's own
# switchers. On Plasma 6 Wayland kglobalaccel lives inside KWin: editing
# kglobalshortcutsrc does nothing until re-login, but its D-Bus API applies live
# and persists the file. Keys are Qt codes: Ctrl 0x04000000 | Shift 0x02000000.
set -u

add_ctrl() { # add_ctrl <kwin action> <Qt keycode of the Ctrl variant>
	id="['kwin','$1','KWin','$1']"
	cur="$(gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
		--method org.kde.KGlobalAccel.shortcutKeys "$id" 2>/dev/null)" ||
		{ echo "[skip] KWin not running — re-run from the Plasma session for Cmd+Tab"; exit 0; }
	case "$cur" in *"[$2, "*) return 0 ;; esac
	keys="$(printf '%s' "$cur" | grep -oE '\[[0-9]+, [0-9]+, [0-9]+, [0-9]+\]' | sed 's/.*/(&,)/' | paste -sd, -)"
	gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
		--method org.kde.KGlobalAccel.setForeignShortcutKeys "$id" "[${keys:+$keys, }([$2, 0, 0, 0],)]" >/dev/null &&
		echo "[info] KWin: $1 += Ctrl"
}

add_ctrl "Walk Through Windows" 83886081                                  # Ctrl+Tab
add_ctrl "Walk Through Windows (Reverse)" 117440513                        # Ctrl+Shift+Tab
add_ctrl "Walk Through Windows of Current Application" 67108960            # Ctrl+`
add_ctrl "Walk Through Windows of Current Application (Reverse)" 67108990  # Ctrl+~
