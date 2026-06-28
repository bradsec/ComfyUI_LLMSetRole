"""ComfyUI_LLMSetRole nodes.

A role picker: a dropdown of system-prompt roles loaded from roles/*.md, output
as a STRING to wire into an LLM node's system_prompt input. To step or randomize
roles across a batch, use the role widget's own control_after_generate control
("fixed", "increment wrap", or "randomize"); the frontend advances the combo, so
the node needs no mode, counter, or index logic of its own.

Dual-API: the shared core (role_core.resolve) is wrapped by a V1 class
(NODE_CLASS_MAPPINGS, authoritative on the 0.25.0 if/elif loader) and an
import-guarded V3 class (comfy_entrypoint) for builds whose loader prefers the
comfy_api schema. node_id "LLMSetRole" is fixed in both.
"""

from . import role_core as core

NODE_ID = "LLMSetRole"
DISPLAY_NAME = "Set Role"
CATEGORY = "LLM"
DESCRIPTION = "Pick an LLM role system prompt from roles/*.md and output it as a STRING for an LLM node's system_prompt. Use the role widget's control_after_generate to step or randomize roles across a batch."

_ROLE_TIP = ("The role whose Markdown becomes the system prompt. Set this widget's "
             "control_after_generate to step roles across a batch: 'fixed' holds it, "
             "'increment wrap' advances one role per generation and wraps around, "
             "'randomize' picks at random. The list is built from roles/*.md at "
             "startup; add a .md file and restart ComfyUI to add a role.")

# Combo options built once at import. role_core guarantees a non-empty list.
_ROLE_OPTIONS = core.role_labels()
_DEFAULT_ROLE = _ROLE_OPTIONS[0]


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
                "role": (_ROLE_OPTIONS, {"default": _DEFAULT_ROLE,
                                         "control_after_generate": True,
                                         "tooltip": _ROLE_TIP}),
            }
        }

    def set_role(self, role):
        return core.resolve(role)

    @classmethod
    def IS_CHANGED(cls, role):
        return core.role_fingerprint(role)


NODE_CLASS_MAPPINGS = {NODE_ID: LLMSetRoleNode}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: DISPLAY_NAME}


# -- V3 node (import-guarded comfy_api schema) ---------------------------------

try:
    from comfy_api.v0_0_2 import io, ComfyExtension

    def _role_input():
        """io.Combo.Input for the role, tolerating comfy_api builds whose Combo
        does not accept control_after_generate (older schema versions)."""
        try:
            return io.Combo.Input("role", options=_ROLE_OPTIONS, default=_DEFAULT_ROLE,
                                  control_after_generate=True, tooltip=_ROLE_TIP)
        except TypeError:
            return io.Combo.Input("role", options=_ROLE_OPTIONS, default=_DEFAULT_ROLE,
                                  tooltip=_ROLE_TIP)

    class LLMSetRoleV3(io.ComfyNode):
        @classmethod
        def define_schema(cls) -> io.Schema:
            return io.Schema(
                node_id=NODE_ID,
                display_name=DISPLAY_NAME,
                category=CATEGORY,
                description=DESCRIPTION,
                inputs=[_role_input()],
                outputs=[
                    io.String.Output(id="system_prompt", display_name="system_prompt"),
                    io.String.Output(id="role_name", display_name="role_name"),
                    io.Int.Output(id="resolved_index", display_name="resolved_index"),
                ],
            )

        @classmethod
        def fingerprint_inputs(cls, role):
            return core.role_fingerprint(role)

        @classmethod
        def execute(cls, role) -> io.NodeOutput:
            body, title, pos = core.resolve(role)
            return io.NodeOutput(body, title, pos)

    class LLMSetRoleExtension(ComfyExtension):
        async def get_node_list(self):
            return [LLMSetRoleV3]

    async def comfy_entrypoint() -> "LLMSetRoleExtension":
        return LLMSetRoleExtension()

except ImportError:
    # Older ComfyUI without comfy_api: V1 mappings above are the only path.
    pass
