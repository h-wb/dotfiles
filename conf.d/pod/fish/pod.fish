# The pods run mise from its image. code-server builds its terminals from a login
# bash, whose /etc/profile drops it from PATH.
fish_add_path -g /opt/mise/usr/local/bin
