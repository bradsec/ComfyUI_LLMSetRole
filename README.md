# LLM Set Role - Custom node for ComfyUI

A single node that presents a dropdown of LLM **roles** (system prompts) and outputs the selected role's text as a STRING. Wire that STRING into the `system_prompt` input of an LLM node (Ollama, etc.) to give the model a consistent role: a style transform, a summarizer, a translator, a captioner, an editor, anything you can write as a system prompt.

The node will be located under **Add Node > LLM**. Node name: **Set Role**.

Designed to pair with LLM nodes such as the [stavsap/comfyui-ollama](https://github.com/stavsap/comfyui-ollama) pack: this node supplies the system prompt, the LLM node does the generation.

## The problem it solves

Multi-stage prompt pipelines reuse the same long system prompts. Pasting that prose into a text box on every workflow is error-prone and hard to keep consistent. This node keeps each role as a Markdown file on disk and exposes them as a dropdown, so a workflow picks a role by name and the exact, version-controlled text flows into the LLM. Modes let you also step or randomize through your roles across a batch.

## Nodes included

- **Set Role** - dropdown of roles from `roles/*.md`, outputs the selected role text, its name, and the list position used.

## Inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `mode` | combo | `fixed` | How the role is chosen: `fixed`, `increment`, or `random`. See Selection modes below. |
| `role` | combo | first role | Role used in `fixed` mode. The list is built from `roles/*.md` at startup. Add a `.md` file and restart ComfyUI to add a role. |
| `start` | INT | `0` | Lower bound position (0-based) into the alphabetically sorted role list. Bounds `increment` and `random`. |
| `end` | INT | `-1` | Upper bound position; `-1` means the last role. Out-of-range values are clamped. |

## Outputs

| Output | Type | Description |
|---|---|---|
| `system_prompt` | STRING | The full text of the selected role file, ready to wire into an LLM node's `system_prompt` input. |
| `role_name` | STRING | The selected role's display name, e.g. for logging or filename suffixes. |
| `resolved_index` | INT | The list position actually used. Useful for logging or labelling batched runs. |

## Selection modes

Roles are sorted alphabetically by display name; `start`/`end` index into that
list (0-based, `end = -1` means the last). The range is inclusive.

- **fixed**: output the `role` dropdown. `start`/`end` ignored.
- **increment**: output the next role alphabetically, advancing one step per
  generation and wrapping from `end` back to `start`. The node steps on its own;
  there is no extra widget to set. The counter is per-node and process-local, so
  it restarts from `start` when ComfyUI restarts.
- **random**: output a role picked at random within `start..end`, fresh each
  generation.

`increment` and `random` re-run the node on every generation (so a downstream LLM
node re-runs too); `fixed` only re-runs when the role or its file text changes.

## Adding roles

1. Drop a new `.md` file into the `roles/` directory. The file content is the system prompt, kept verbatim. See `roles/example.md.example` for the format.
2. The dropdown label defaults to the prettified filename: `summarizer.md` becomes `Summarizer`.
3. To set an explicit label, make the **first line** of the file an HTML comment:

   ```markdown
   <!-- title: Concise Summarizer -->
   ```

   That line is stripped from the output and is used only as the dropdown label. (An HTML comment is used rather than a `#` heading because role files commonly start with their own `#` heading.)
4. Restart ComfyUI so the new file appears in the dropdown. Editing an existing role does not need a restart: the node re-runs when the file changes.

Your `roles/*.md` files are gitignored, so your prompts stay private and local. The shipped `roles/example.md.example` is tracked only as a format reference and is not loaded by the node.

## Usage

```
[Set Role].system_prompt -> [Ollama Generate].system_prompt
your prompt text         -> [Ollama Generate].prompt
```

## Testing

### Unit tests (no ComfyUI needed)

```bash
cd ComfyUI_LLMSetRole
python -m unittest test_set_role -v
```

Expect 25 passing tests (title parsing, filename prettify, label-collision disambiguation, path-traversal rejection, missing-file error, edit hot-reload, bad-encoding tolerance, range bounds/clamp/swap, increment wrap, random determinism, mode selection, shipped-role discovery).

### In ComfyUI

1. Restart ComfyUI so the node loads. Confirm it appears once under **Add Node > LLM** as **Set Role**, with no import error in `user/comfyui.log`.
2. Add the node, pick a role and mode, and wire `system_prompt` into your LLM node.
3. Run the workflow. The LLM node receives the selected role text.

## Installation

### ComfyUI Manager (recommended)

In ComfyUI, open **Manager > Custom Nodes Manager**, search for **ComfyUI_LLMSetRole**, click **Install**, then restart ComfyUI.

### Manual install

Clone into your ComfyUI `custom_nodes` directory and restart ComfyUI:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/bradsec/ComfyUI_LLMSetRole
```

No extra dependencies (Python stdlib only).

## Compatibility

Dual API: exports the legacy V1 `NODE_CLASS_MAPPINGS` and a V3 `comfy_entrypoint` (`comfy_api`). On builds whose loader reads `NODE_CLASS_MAPPINGS` first, the V1 path is used and `comfy_entrypoint` is skipped, so the node is never registered twice.

---

## Support

If you find this useful, please consider [starring the repo](https://github.com/bradsec/ComfyUI_LLMSetRole). Stars help other people discover these nodes.
