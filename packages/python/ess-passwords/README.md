# ess-passwords

Readable passwords from a filtered EFF wordlist — the kind you can read
aloud on a call without wincing.

```bash
$ ess-passwords generate
swept-staunch-circling-showdown-SCREEN
(63 bits of entropy from 6,131 candidate words)
```

The password goes to stdout and the entropy note to stderr, so it pipes
straight into a secret store:

```bash
ess-passwords generate | uv run pulumi config set myproj:dbPassword --secret
```

From Python:

```python
from ess_passwords import PasswordOptions, generate_password

generated = generate_password(PasswordOptions(word_count=6, digit_count=4))
print(generated.value)         # VOCATION-paddle-move-bonding-overrate-scruffy-2810
print(generated.entropy_bits)  # 88.8
```

## Installation

From the workspace root:

```bash
uv sync --all-packages
```

A plain `uv sync` will not put the `ess-passwords` command on `PATH`.

## CLI

### `ess-passwords generate`

Prints one password per line. Read-only — it writes nothing, so there is
no `--dry-run` and no confirmation prompt.

| Flag | Default | Description |
|---|---|---|
| `--words` | `5` | Number of words in the password |
| `--separator` | `-` | String joining the words |
| `--max-length` | none | Regenerate until the password fits in this many characters |
| `--capitalize-at` | random | Position of the upper-cased word, counting from 0 |
| `--digits` | `0` | Digits to append after the last word |
| `--count` / `-n` | `1` | Number of passwords to print |
| `--json` | off | Emit JSON: an object, or an array when `--count` is above 1 |

## API

### `generate_password(options=None) -> GeneratedPassword`

Generates one password. Exactly one word is upper-cased. The result
carries no date, symbol, or other tail — append whatever the consuming
system's complexity rules need, and size `max_length` to leave room for
it. Raises `PasswordPolicyError` when the options cannot produce a
password.

### `PasswordOptions`

Frozen dataclass. Every field is optional.

| Field | Default | Description |
|---|---|---|
| `word_count` | `5` | Number of words in the password |
| `separator` | `"-"` | String joining the words, and the digits when asked for |
| `max_length` | `None` | Reject and regenerate passwords longer than this |
| `capitalized_index` | `None` | Position of the one upper-cased word, from 0. `None` picks one at random per password |
| `digit_count` | `0` | Digits appended after the last word |

### `GeneratedPassword`

Frozen dataclass with `value`, `entropy_bits`, and `wordlist_size`.
`entropy_bits` counts the random word and digit choices only. Which word
is capitalised is not counted: it is worth just `log2(word_count)`
against a scheme an attacker already knows, and understating strength is
the safe direction.

### `load_wordlist()` and `excluded_words()`

The candidate words, and the profanity and sexual terms filtered out of
them. Entropy is derived from the filtered list, so exclusions are
reflected in reported strength automatically. `load_wordlist()` reads
and filters the EFF file once per process and returns the same immutable
tuple thereafter; word selection is per password, so this does not make
passwords repeat. If a crude word slips through, add it to
`_EXCLUDED_WORDS` in [`wordlist.py`](src/ess_passwords/wordlist.py)
rather than regenerating a password by hand.

## Running tests

```bash
uv run pytest packages/python/ess-passwords
```

## License

Generation uses
[xkcdpass](https://github.com/redacted/XKCD-password-generator)
(BSD-3-Clause), which bundles the EFF long wordlist.
