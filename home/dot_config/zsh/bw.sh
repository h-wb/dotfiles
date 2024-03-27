
#!/usr/bin/env sh
#
# Log in to and unlock Bitwarden CLI.
#
# If you save the returned session key in a BW_SESSION envvar that will unlock
# your Bitwarden vault for the current shell session. Once BW_SESSION has been
# set in one shell session it'll also be inherited by any commands or scripts
# run from that shell session.
#
# Usage (sh):
#
#     BW_SESSION=$(bw-open <EMAIL>)
#     export BW_SESSION
#
# Usage (fish):
#
#     set -x BW_SESSION (bw-open <EMAIL>)
#
# You can do this multiple times in a row and it won't ask for your password
# each time: it'll see the already-exported BW_SESSION envvar and just print it
# again.
#
# If a BW_PASSWORD envvar is set it'll use that as the Bitwarden master
# password instead of asking your for it.
#
# sh:
#
#     read -p "Bitwarden master password: " BW_PASSWORD
#
# fish:
#
#     read -sP "Bitwarden master password: " BW_PASSWORD

if ! bw login --check > /dev/null
then
    BW_SESSION="$(bw login --raw "$1" "$BW_PASSWORD")"
    export BW_SESSION
fi

if ! bw unlock --check > /dev/null
then
    BW_SESSION="$(bw unlock --raw "$BW_PASSWORD")"
    export BW_SESSION
fi


