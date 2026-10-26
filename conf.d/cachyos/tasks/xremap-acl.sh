# The `cachyos:xremap-acl` task. The udev rule only applies on device
# add/change, so re-trigger input devices once when the Rainy 75's nodes don't
# carry this user's ACL yet.
for n in /sys/class/input/event*; do
	[ "$(cat "$n/device/name" 2>/dev/null)" = "Telink Wireless Gaming Keyboard" ] || continue
	getfacl -p "/dev/input/${n##*/}" 2>/dev/null | grep -q "^user:$(id -un):" && continue
	echo "[info] applying the xremap udev rule"
	sudo udevadm control --reload && sudo udevadm trigger --action=change --subsystem-match=input &&
		systemctl --user try-restart dev.mise.xremap.service
	exit
done
