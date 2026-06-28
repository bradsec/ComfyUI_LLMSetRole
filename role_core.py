"""Shared core for ComfyUI_LLMSetRole.

Pure functions, no ComfyUI import. Scans roles/*.md, resolves dropdown labels,
and loads role text. Both API wrappers (V1 and V3) call into here so the logic
cannot drift.

Role files are plain Markdown kept verbatim as the LLM system prompt. A file
may declare its dropdown label on its first line as an HTML comment:

    <!-- title: Summarizer -->

When present that line is stripped from the emitted text. Without it the label
is derived from the filename (professional_photo.md -> "Professional Photo").

Edit a role and the node re-runs (mtime fingerprint). Add a new role file and
restart ComfyUI, since the dropdown options are built once at import.
"""

import os
import random
import re
from functools import lru_cache

MODES = ("fixed", "increment", "random")

ROLES_DIR = os.path.join(os.path.dirname(__file__), "roles")

NO_ROLES_LABEL = "(no roles found)"

# First-line title marker: <!-- title: Some Name -->
_TITLE_RE = re.compile(r"^\s*<!--\s*title:\s*(.+?)\s*-->\s*$", re.IGNORECASE)


def prettify_filename(filename):
    """professional_photo.md -> 'Professional Photo'."""
    stem = os.path.splitext(filename)[0]
    return stem.replace("_", " ").replace("-", " ").strip().title()


def parse_title(text, filename):
    """Return (title, body).

    If the first line is an HTML title comment, use it as the title and drop
    that line from the body. Otherwise the title is the prettified filename and
    the body is the text unchanged.
    """
    lines = text.split("\n", 1)
    m = _TITLE_RE.match(lines[0]) if lines else None
    if m:
        title = m.group(1).strip()
        body = lines[1] if len(lines) > 1 else ""
        return title, body
    return prettify_filename(filename), text


def _validate_name(filename):
    """Reject anything but a bare basename, so a label can never escape ROLES_DIR."""
    if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename) \
            or filename in (os.curdir, os.pardir):
        raise ValueError(f"Invalid role filename: {filename!r}")


@lru_cache(maxsize=None)
def _load_cached(filename, mtime):
    """Read and parse one role file, keyed on (filename, mtime).

    Including mtime in the key means editing a file invalidates the cached
    entry on the next access, so edits are picked up without a restart.
    errors="replace": one mis-encoded role file must not crash the import-time
    dropdown build and take the whole node down; it degrades to replacement chars.
    """
    with open(os.path.join(ROLES_DIR, filename), encoding="utf-8", errors="replace") as f:
        return parse_title(f.read(), filename)


def load_role_text(filename):
    """Return (title, body) for one role file.

    Cached on the file's mtime: editing a role is picked up on the next run
    without restarting ComfyUI; only adding or removing files needs a restart.
    """
    _validate_name(filename)
    path = os.path.join(ROLES_DIR, filename)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        raise FileNotFoundError(
            f"Role file not found: {filename!r} in {ROLES_DIR}. "
            f"It may have been removed; restart ComfyUI to refresh the list."
        )
    return _load_cached(filename, mtime)


def _scan_files():
    """Sorted list of *.md basenames in ROLES_DIR, or [] if none/missing."""
    if not os.path.isdir(ROLES_DIR):
        return []
    return sorted(
        e.name for e in os.scandir(ROLES_DIR)
        if e.is_file() and e.name.lower().endswith(".md")
    )


def list_roles():
    """Return [(label, filename)] sorted by label.

    Labels that collide after prettifying are disambiguated by appending the
    filename, so every label maps to exactly one file.
    """
    loaded = [(fn, load_role_text(fn)[0]) for fn in _scan_files()]
    counts = {}
    for _, title in loaded:
        counts[title] = counts.get(title, 0) + 1

    pairs = [(f"{title} ({fn})" if counts[title] > 1 else title, fn)
             for fn, title in loaded]
    pairs.sort(key=lambda p: p[0].lower())
    return pairs


def role_labels():
    """Combo option list. Never empty: falls back to a sentinel label."""
    labels = [label for label, _ in list_roles()]
    return labels or [NO_ROLES_LABEL]


def resolve_filename(label):
    """Map a dropdown label back to its role filename.

    Raises ValueError if the label is the no-roles sentinel or is unknown, so a
    crafted label can never reference a file outside ROLES_DIR.
    """
    if label == NO_ROLES_LABEL:
        raise ValueError(
            f"No role files found in {ROLES_DIR}. Add a .md file and restart ComfyUI."
        )
    for lbl, fn in list_roles():
        if lbl == label:
            return fn
    raise ValueError(f"Unknown role: {label!r}. Restart ComfyUI to refresh the list.")


def apply_role(label):
    """Resolve a role label to (system_prompt, role_name)."""
    fn = resolve_filename(label)
    title, body = load_role_text(fn)
    return body, title


def role_fingerprint(label):
    """Identity for caching: filename + mtime, or the label itself if unresolved."""
    try:
        fn = resolve_filename(label)
        mtime = os.path.getmtime(os.path.join(ROLES_DIR, fn))
        return f"{fn}:{mtime}"
    except (ValueError, FileNotFoundError, OSError):
        return str(label)


# -- Position-based selection (fixed / increment / random) ---------------------

def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _bounds(start, end, n):
    """Return (lo, hi, span) inclusive position bounds within a list of size n.

    end < 0 means "last". Out-of-range values are clamped; reversed bounds are
    swapped. Assumes n >= 1 (callers handle the empty case first).
    """
    lo = _clamp(start, 0, n - 1)
    hi = _clamp(end if end >= 0 else n - 1, 0, n - 1)
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi, hi - lo + 1


def label_index(label):
    """Position of a dropdown label in the sorted role list, or 0 if absent."""
    for i, (lbl, _) in enumerate(list_roles()):
        if lbl == label:
            return i
    return 0


def pick_index(mode, value, start, end, n):
    """Resolve a role position for increment/random modes from an integer `value`.

    Pure helper used by select() and the tests:
    increment: lo + (value mod span), wrapping at the end back to the start.
    random:    lo + Random(value).randrange(span), deterministic per value.
    Raises ValueError if there are no roles.
    """
    if n < 1:
        raise ValueError(
            f"No role files found in {ROLES_DIR}. Add a .md file and restart ComfyUI."
        )
    lo, _, span = _bounds(start, end, n)
    if mode == "random":
        return lo + random.Random(value).randrange(span)
    # increment (and any unknown mode falls back to deterministic stepping)
    return lo + (value % span)


# -- Increment state -----------------------------------------------------------
# Per-node counters for increment mode, keyed by the node's unique_id. Process-
# local: stepping restarts from the first role when ComfyUI restarts. select()
# advances the counter, and the node forces a re-run each generation
# (select_fingerprint returns NaN) so the walk progresses instead of caching.
_increment_counters = {}


def reset_counters():
    """Clear all increment state. Used by tests; harmless at runtime."""
    _increment_counters.clear()


def _next_increment_pos(node_key, start, end, n):
    """Advance this node's counter and return the next position within bounds."""
    c = _increment_counters.get(node_key, 0)
    _increment_counters[node_key] = c + 1
    return pick_index("increment", c, start, end, n)


def _random_pos(start, end, n):
    """A fresh random position within bounds, non-reproducible by design."""
    lo, _, span = _bounds(start, end, n)
    return lo + random.randrange(span)


def role_at(pos):
    """(label, filename) at a position. Raises ValueError if no roles."""
    roles = list_roles()
    if not roles:
        raise ValueError(
            f"No role files found in {ROLES_DIR}. Add a .md file and restart ComfyUI."
        )
    return roles[pos]


def select(mode, role, start, end, node_key=None):
    """Resolve (system_prompt, role_name, resolved_index) for any mode.

    fixed: use the dropdown `role`. increment: the next role alphabetically,
    advancing this node's counter and wrapping within [start, end]. random: a
    fresh random role within [start, end], picked anew each call.
    """
    if mode == "fixed":
        pos = label_index(role)
        body, title = apply_role(role)
        return body, title, pos
    n = len(list_roles())
    if n < 1:
        raise ValueError(
            f"No role files found in {ROLES_DIR}. Add a .md file and restart ComfyUI."
        )
    pos = _random_pos(start, end, n) if mode == "random" \
        else _next_increment_pos(node_key, start, end, n)
    _, fn = role_at(pos)
    title, body = load_role_text(fn)
    return body, title, pos


def select_fingerprint(mode, role, start, end):
    """Cache identity.

    fixed caches on the resolved file's mtime so the node only re-runs when the
    role or its text changes. increment/random return NaN, which never equals
    itself, so ComfyUI re-runs the node every generation and the walk advances.
    """
    if mode != "fixed":
        return float("nan")
    try:
        pos = label_index(role)
        _, fn = role_at(pos)
        mtime = os.path.getmtime(os.path.join(ROLES_DIR, fn))
        return f"fixed:{pos}:{fn}:{mtime}"
    except (ValueError, FileNotFoundError, OSError):
        return f"fixed:{role}"
