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
import re
from functools import lru_cache

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


# -- Selection -----------------------------------------------------------------
# Stepping (one-by-one, random) is handled by the frontend's per-widget
# control_after_generate on the `role` combo ("increment wrap" / "randomize"),
# so the core only resolves the currently-selected label. No mode, counter, or
# index math lives here.

def label_index(label):
    """Position of a dropdown label in the sorted role list, or 0 if absent."""
    for i, (lbl, _) in enumerate(list_roles()):
        if lbl == label:
            return i
    return 0


def resolve(role):
    """Resolve (system_prompt, role_name, resolved_index) for the selected role."""
    body, title = apply_role(role)
    return body, title, label_index(role)
