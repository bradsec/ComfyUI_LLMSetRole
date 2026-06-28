"""ComfyUI_LLMSetRole nodes.

A role picker: a dropdown of system-prompt roles loaded from roles/*.md, output
as a STRING to wire into an LLM node's system_prompt input. A mode control
selects the role: a fixed dropdown pick, an automatic alphabetical step (one role
per generation), or a fresh random pick, bounded to a start..end slice of the list.

Dual-API: the shared core (role_core.select) is wrapped by a V1 class
(NODE_CLASS_MAPPINGS, authoritative on the 0.25.0 if/elif loader) and an
import-guarded V3 class (comfy_entrypoint) for builds whose loader prefers the
comfy_api schema. node_id "LLMSetRole" is fixed in both.
"""

from . import role_core as core

NODE_ID = "LLMSetRole"
DISPLAY_NAME = "Set Role"
CATEGORY = "LLM"
DESCRIPTION = "Pick an LLM role system prompt from roles/*.md (fixed, increment, or random) and output it as a STRING for an LLM node's system_prompt."

_ROLE_TIP = ("Role used in 'fixed' mode. The list is built from roles/*.md at "
             "startup; add a .md file and restart ComfyUI to add a role.")
_MODE_TIP = ("fixed: use the role dropdown. increment: step to the next role "
             "alphabetically each generation, wrapping within start..end. random: a "
             "fresh random role within start..end each generation. increment and random "
             "advance on their own; no extra widget to set.")
_START_TIP = "Lower bound position (0-based) into the alphabetically sorted role list."
_END_TIP = "Upper bound position; -1 means the last role. Out-of-range values are clamped."

# Combo options built once at import. role_core guarantees a non-empty list.
_ROLE_OPTIONS = core.role_labels()
_DEFAULT_ROLE = _ROLE_OPTIONS[0]
_MAX_INT = 0xFFFFFFFFFFFFFFFF


# -- V1 node -------------------------------------------------------------------

class LLMSetRoleNode:
    CATEGORY = CATEGORY
    FUNCTION = "set_role"
    OUTPUT_NODE = False
    DESCRIPTION = DESCRIPTION
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("system_prompt", "role_name", "resolved_index")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (list(core.MODES), {"default": "fixed", "tooltip": _MODE_TIP}),
                "role": (_ROLE_OPTIONS, {"default": _DEFAULT_ROLE, "tooltip": _ROLE_TIP}),
                "start": ("INT", {"default": 0, "min": 0, "max": _MAX_INT, "tooltip": _START_TIP}),
                "end": ("INT", {"default": -1, "min": -1, "max": _MAX_INT, "tooltip": _END_TIP}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    def set_role(self, mode, role, start, end, unique_id=None):
        return core.select(mode, role, start, end, unique_id)

    @classmethod
    def IS_CHANGED(cls, mode, role, start, end, unique_id=None):
        return core.select_fingerprint(mode, role, start, end)


NODE_CLASS_MAPPINGS = {NODE_ID: LLMSetRoleNode}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: DISPLAY_NAME}


# -- V3 node (import-guarded comfy_api schema) ---------------------------------

try:
    from comfy_api.v0_0_2 import io, ComfyExtension

    class LLMSetRoleV3(io.ComfyNode):
        @classmethod
        def define_schema(cls) -> io.Schema:
            return io.Schema(
                node_id=NODE_ID,
                display_name=DISPLAY_NAME,
                category=CATEGORY,
                description=DESCRIPTION,
                inputs=[
                    io.Combo.Input("mode", options=list(core.MODES),
                                   default="fixed", tooltip=_MODE_TIP),
                    io.Combo.Input("role", options=_ROLE_OPTIONS,
                                   default=_DEFAULT_ROLE, tooltip=_ROLE_TIP),
                    io.Int.Input("start", default=0, min=0, max=_MAX_INT, tooltip=_START_TIP),
                    io.Int.Input("end", default=-1, min=-1, max=_MAX_INT, tooltip=_END_TIP),
                ],
                hidden=[io.Hidden.unique_id],
                outputs=[
                    io.String.Output(id="system_prompt", display_name="system_prompt"),
                    io.String.Output(id="role_name", display_name="role_name"),
                    io.Int.Output(id="resolved_index", display_name="resolved_index"),
                ],
            )

        @classmethod
        def fingerprint_inputs(cls, mode, role, start, end):
            return core.select_fingerprint(mode, role, start, end)

        @classmethod
        def execute(cls, mode, role, start, end) -> io.NodeOutput:
            body, title, pos = core.select(mode, role, start, end, cls.hidden.unique_id)
            return io.NodeOutput(body, title, pos)

    class LLMSetRoleExtension(ComfyExtension):
        async def get_node_list(self):
            return [LLMSetRoleV3]

    async def comfy_entrypoint() -> "LLMSetRoleExtension":
        return LLMSetRoleExtension()

except ImportError:
    # Older ComfyUI without comfy_api: V1 mappings above are the only path.
    pass
