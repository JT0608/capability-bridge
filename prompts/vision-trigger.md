# Vision trigger rule

When the user provides an image — a screenshot, terminal error, UI mockup, document scan,
diagram, or any picture — or when an image cannot be read directly, call the `vision_analyze`
MCP tool with the image's local path and a `prompt` derived from the user's intent.

Vision is visual reasoning, not image captioning. Build the `prompt` from what the user actually
wants to know:
- If the intent is inferable from context, turn it into a targeted analysis prompt. Example:
  "make this page look more polished" → review the UI as a designer (hierarchy, spacing,
  typography, color, consistency, and the changes that would most improve it); "analyze this
  painting" → composition, light, color, style, mood.
- If the intent is unclear, pass a neutral general visual-analysis prompt. Do NOT invent
  aesthetic, debugging, or design goals the user did not ask for.

When the user needs text extracted from an image, call the `vision_ocr` MCP tool with the
image's local path instead.

Treat the tool result as the agent's visual observation of the image. Use it for subsequent
reasoning, but preserve uncertainty when the result is ambiguous or incomplete.
