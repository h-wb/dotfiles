# miroir-collector-run: each source's delivery token from the login Keychain
# into the variable its `token_env` names, in the collector's environment only.
# A token is never printed, logged, passed as an argument or written to a file.
import json
import os
from pathlib import Path
import subprocess
import sys

SECURITY = "/usr/bin/security"


def keychain_token(service, account):
    # stderr is dropped: security's diagnostics are not ours to log.
    result = subprocess.run(
        [SECURITY, "find-generic-password", "-s", service, "-a", account, "-w"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    token = result.stdout.rstrip(b"\n")
    if result.returncode or not token:
        return None
    return token.decode("utf-8", errors="surrogateescape")


def main():
    config = os.environ["MIROIR_COLLECTOR_CONFIG"]
    service = os.environ["MIROIR_KEYCHAIN_SERVICE"]
    collector = str(Path.home() / ".local/bin/miroir-collector")
    try:
        sources = json.loads(Path(config).read_text(encoding="utf-8"))["sources"]
        entries = [(str(source["id"]), str(source["token_env"])) for source in sources]
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit(f"miroir-collector: cannot read sources from {config}")

    # No token from the caller's environment reaches the collector.
    env = os.environ.copy()
    for _, name in entries:
        env.pop(name, None)

    found = []
    for source_id, name in entries:
        token = keychain_token(service, source_id)
        if token is None:
            print(f"miroir-collector: skipping {source_id!r}: no Keychain token",
                  file=sys.stderr)
        else:
            found.append((source_id, name, token))

    command = [collector, "run", "--config", config]
    if len(found) == len(entries):
        sys.stdout.flush()
        os.execve(collector, command, {**env, **{name: token for _, name, token in found}})

    # A plain `run` would still collect and spool a tokenless source and fail
    # its delivery: run the others one by one instead, each with its own token.
    # Nothing to run at all is a failure, so a scheduler's log does not read as fine.
    status = 0 if found else 1
    for source_id, name, token in found:
        code = subprocess.run(command + ["--source", source_id], env={**env, name: token}).returncode
        status = status or (code if code >= 0 else 128 - code)
    return status


if __name__ == "__main__":
    sys.exit(main())
