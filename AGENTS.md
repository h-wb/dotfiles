# dotfiles: instructions for agents

Every machine's setup and every agent's configuration, applied by mise. Start with the [handbook](https://github.com/h-wb/handbook): [Workshop](https://github.com/h-wb/handbook/blob/main/Systems/Workshop.md) says how agent configuration fits with home-ops. The pages: [README.md](README.md) (machines, layout, everyday use), [docs/mise.md](docs/mise.md) (how mise is used, and what was rejected), and a `README.md` in `conf.d/ai`, `conf.d/proton-pass` and each machine's folder.

## Private data stays out

Private data only reaches models trusted with it; a general agent never reads it. This repo is public and general: never write personal details, a real domain, addresses (internal IPs included), names of people, or secrets, in files, tests, comments, commits or pull requests. The cluster's domain is `SECRET_DOMAIN`, resolved by fnox from Proton Pass at apply time; spell it nowhere, which is why the resolver file is `/etc/resolver/k8s-gateway`. Examples and tests use `example.test`. Secrets are `pass://` references in a `fnox.toml`, never values.

## Where you work

- On a pod (Paseo, neko, code-server), edit in `~/Repositories/dotfiles`, in a Paseo worktree. `~/.dotfiles` is the pod's live config: home-ops' `DOTFILES_REF` (`master`), checked out again at every start, so an edit there does not last.
- Bare `mise bootstrap` applies to the machine you are on. Test in a sandbox `HOME` instead: [docs/mise.md](docs/mise.md#test-a-change-without-touching-the-machine).

## Layout

- The repo is mise's config directory: `~/.config/mise` links to `~/.dotfiles`. The machine's environment is declared by its caller, never detected: `mise bootstrap --save-env` writes it to the untracked `miserc.local.toml`, and `[env_sets]` in `miserc.toml` adds the layers ([docs/mise.md](docs/mise.md#how-a-machine-picks-its-files)).
- `config.toml`: what every machine wants, the Paseo pods included. `config.workstation.toml`: machines a person works at.
- `conf.d/<folder>/`: one per machine, one per feature. The name says where it loads (`neko/`, `neko-anki/`, `ai/`); `test_conf_d_folder_names_say_where_they_load` enforces it.
- `home/` the root configs' sources, `scripts/` the apply task's body, the Proton Pass preflight and `land`, `tests/test_setup.py` the regressions, `locks/` the lock sidecars.
- `vendor/skills`: the [h-wb/skills](https://github.com/h-wb/skills) catalogue, a submodule that follows its `main`. A skill and its groups are written there; here a place only declares the groups it takes ([conf.d/ai](conf.d/ai/README.md#skills)). Clone with `--recurse-submodules`, or let the next bootstrap check it out.

## Test

```sh
python3 tests/test_setup.py -v      # Python 3.11+, throwaway homes, offline mise, nothing provisioned
mise tasks validate --errors-only
mise doctor project                 # on a machine with the repo applied
```

CI (`.github/workflows/test.yml`) runs the tests on macOS and Linux with the minimum and the latest mise, then loads and renders each of the five classes. It fails on `master` today (HOMEL-121), so compare a failure with `master` before blaming your change. Run the tests before each commit. `test_fish_config_loads` needs fish on the machine.

## Rules that are easy to break

- No custom script where mise has the feature: a tool is a `[tools]` line, a package a `[bootstrap.packages]` entry, a service a launchd or systemd entry, a step a mise task. A body longer than a few lines goes in the folder's `tasks/`; `bin/` only holds what belongs in `~/.local/bin`.
- No per-class apply. `config.toml` holds only what every machine wants; a machine is its layers plus what only it has.
- Configuration is rendered from templates, defined once. Templates read `{{ vars.x }}` and never name a source; each var defaults to the process environment. Agent configuration is written once in `conf.d/ai/` and rendered per scope. Never edit a rendered file to fix it.
- Secrets go through fnox and Proton Pass. Every fnox call that provisions is `fnox --if-missing error exec` (a global flag, before the subcommand): with the default `warn`, a dead session renders every secret-gated file empty over the good copy. Never `remove_empty = true` on such a template, and no `[bootstrap.secrets]` for shared templates. Repos log in by extending the `proton-login` template, never with their own script ([proton-pass](conf.d/proton-pass/README.md)).
- Only real scripts are committed executable (`install.sh`, `scripts/*`, `conf.d/*/bin/*`): a template takes its source's mode. Doctor `file-modes` checks it.
- Commit `mise*.lock` with the `locks/` sidecars; never lock with `--platform`; read `git diff mise*.lock` after a lock ([lockfiles](docs/mise.md#lockfiles)).
- One bootstrap, two steps, on every machine: `mise bootstrap --from` for the checkout, then `mise run apply` ([docs/mise.md](docs/mise.md#one-bootstrap-two-steps)). Don't add a second way to do either. home-ops runs `mise run apply --unattended`: keep the task's name and flags.
- Nothing pulls: a person updates a workstation's clone with git, and every pod gets the commit home-ops pins. Don't add a pull, a detection rule or a hold file.
- Never edit `vendor/skills` here: change the skill or its group in h-wb/skills. Machines and pods take its `main` at their next apply or start; nothing is committed here.
- A regression caught by hand gets a doctor check or a test.

## Branch and pull request

The default branch is `master`, protected: branch, pull request, the owner's review. Titles follow Conventional Commits. A change that makes a page wrong fixes the page in the same pull request. On the general Paseo pod the bot cannot push `.github/workflows/`: the `paseo-workspace-hygiene` skill has the hand-off.
