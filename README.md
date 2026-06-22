# jsoncli

Turn any JSON file into a **beautiful, collapsible, bracket-free tree** in your terminal.

No more squinting at `{`, `}`, `[`, `]`, and trailing commas. `jsoncli` reads a
`.json` file and renders it as a navigable tree you can expand and collapse with
the arrow keys — color-coded by type, with soft hints like `3 items` instead of
raw brackets.

## Install (recommended)

```bash
pipx install /Users/afroza/jsoncli      # isolated, always on your PATH
# or
pip install /Users/afroza/jsoncli
```

## Use

```bash
jsoncli sample.json        # open a file
cat sample.json | jsoncli  # or pipe JSON in
```

### Keys

| Key        | Action                                              |
| ---------- | --------------------------------------------------- |
| `↑` / `↓`  | Move between nodes                                  |
| `Enter`    | On an object/array: expand / collapse. On a leaf: open the full value in a scrollable popup |
| `/`        | Search keys and values (Enter to run, Esc to cancel) |
| `n` / `N`  | Jump to next / previous match                       |
| `e`        | Expand everything (disabled on very large files)    |
| `c`        | Collapse everything                                 |
| `q`        | Quit                                                |

### Big files

The tree loads **lazily** — a node's children are only built when you expand it,
so even multi-megabyte files open instantly instead of materializing every node
up front. The header shows the total node count. Search scans the underlying data
(not just what's on screen), then expands the tree to reveal each match, so it
finds things in collapsed branches too. (`e`/expand-all is refused past ~20k nodes
to avoid materializing the whole document at once.)

Inside the value popup: `↑`/`↓` to scroll, `Esc` / `Enter` / `q` to close.
This is how you read long fields (e.g. embedded HTML narratives) in full without
them being clipped to the terminal width.

If a value looks like HTML/XML (such as a FHIR `text.div` narrative), the popup
opens in a **formatted, syntax-highlighted view** — indented and readable instead
of one long line. Press **`f`** to toggle between the formatted view and the
**raw, byte-exact original value**. Non-markup values open raw with no toggle.
Formatting only changes the *display*; the underlying data is never modified.

## Docker (optional)

The viewer is interactive, so it needs a TTY (`-it`) and your file mounted in:

```bash
docker build -t jsoncli /Users/afroza/jsoncli
docker run --rm -it -v "$PWD":/data jsoncli sample.json
```

## How it simplifies the structure

- **Objects** show as a named node with a `N fields` hint — no braces.
- **Arrays** show as a named node with a `N items` hint — no brackets, index-labeled children.
- **Leaf values** show as `key:  value`, colored by type (string / number / bool / null).
- Strings are shown **without surrounding quotes** for calmer reading.

## Project layout

```
jsoncli/
├── jsoncli/
│   ├── cli.py      # argument parsing + JSON loading
│   ├── app.py      # the interactive Textual tree app
│   └── render.py   # label styling / type colors
├── sample.json     # try it: jsoncli sample.json
├── Dockerfile      # optional container build
└── pyproject.toml
```
