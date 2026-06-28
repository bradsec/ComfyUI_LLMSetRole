# LLM Set Role - Custom node for ComfyUI

A single node that presents a dropdown of LLM **roles** (system prompts) and outputs the selected role's text as a STRING. Wire that STRING into the `system_prompt` input of an LLM node (Ollama, etc.) to give the model a consistent role: a style transform, a summarizer, a translator, a captioner, an editor, anything you can write as a system prompt.

The node will be located under **Add Node > LLM**. Node name: **Set Role**.

Designed to pair with LLM nodes such as the [stavsap/comfyui-ollama](https://github.com/stavsap/comfyui-ollama) pack: this node supplies the system prompt, the LLM node does the generation.

## The problem it solves

Multi-stage prompt pipelines reuse the same long system prompts. Pasting that prose into a text box on every workflow is error-prone and hard to keep consistent. This node keeps each role as a Markdown file on disk and exposes them as a dropdown, so a workflow picks a role by name and the exact, version-controlled text flows into the LLM. The role widget's `control_after_generate` lets you step or randomize through your roles across a batch.

## Nodes included

- **Set Role** - dropdown of roles from `roles/*.md`, outputs the selected role text, its name, and the list position used.

## Inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `role` | combo | first role | The role whose text is output. The list is built from `roles/*.md` at startup (add a `.md` file and restart ComfyUI to add a role). Use the widget's `control_after_generate` to step or randomize across a batch. See Stepping below. |

## Outputs

| Output | Type | Description |
|---|---|---|
| `system_prompt` | STRING | The full text of the selected role file, ready to wire into an LLM node's `system_prompt` input. |
| `role_name` | STRING | The selected role's display name, e.g. for logging or filename suffixes. |
| `resolved_index` | INT | The selected role's position in the alphabetically sorted list. Useful for logging or labelling batched runs. |

## Stepping across a batch

The `role` widget carries ComfyUI's per-widget `control_after_generate` control,
the same one samplers put on `seed`. Use it to choose how the role advances
between generations:

- **fixed**: keep the selected role.
- **increment wrap**: advance to the next role each generation, wrapping from the
  last role back to the first. Drive a batch through every role in order.
- **randomize**: pick a random role each generation.

The frontend steps the combo itself, so the role you see selected on the node is
the role being used. Roles are sorted alphabetically by display name.

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

Expect 17 passing tests (title parsing, filename prettify, label-collision disambiguation, path-traversal rejection, missing-file error, edit hot-reload, bad-encoding tolerance, role resolution, shipped-role discovery).

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
