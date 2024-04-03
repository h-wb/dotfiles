#!/usr/bin/env bash

export BW_USER="$(chezmoi execute-template '{{ get . "bw_email" }}')"

bw() {
  bw_exec=$(sh -c "NODE_OPTIONS=\"--no-deprecation\" which bw")
  local -r bw_session_file='/var/root/.bitwarden.session' # Only accessible as root

  _read_token_from_file() {

    local -r err_token_not_found="Token not found, please run bw --regenerate-session-key"
    case $1 in
    '--force')
      unset BW_SESSION
      ;;
    esac

    if [ "$BW_SESSION" = "$err_token_not_found" ]; then
      unset BW_SESSION
    fi

    # If the session key env variable is not set, read it from the file
    # if file it not there, ask user to regenerate it
    if [ -z "$BW_SESSION" ]; then
      export BW_SESSION="$(
        sh -c "sudo cat $bw_session_file 2> /dev/null"
        # shellcheck disable=SC2181
        if [ "$?" -ne "0" ]; then
          echo "$err_token_not_found"
          sudo -k # De-elevate privileges
          exit 1
        fi
        sudo -k # De-elevate privileges
      )"

      # shellcheck disable=SC2181
      if [ "$BW_SESSION" = "$err_token_not_found" ]; then
        echo "$err_token_not_found"
        return 1
      fi
    fi
  }

  case $1 in
  '--regenerate-session-key')
    echo "Regenerating session key, this has invalidated all existing sessions..."
    sudo rm -f /var/root/.bitwarden.session && ${bw_exec} logout 2>/dev/null # Invalidate all existing sessions

    NODE_OPTIONS="--no-deprecation" ${bw_exec} login "${BW_USER}" --raw | sudo tee /var/root/.bitwarden.session &>/dev/null # Generate new session key

    _read_token_from_file --force # Read the new session key for immediate use
    sudo -k                       # De-elevate privileges, only doing this now so _read_token_from_file can resuse the same sudo session
    ;;

  '--help' | '-h' | "")
    ${bw_exec} "$@"
    echo "To regenerate your session key type:"
    echo "  bw --regenerate-session-key"
    ;;

  *)
  
    _read_token_from_file

    NODE_OPTIONS="--no-deprecation" ${bw_exec} "$@" --session "$BW_SESSION"
    ;;
  esac
}