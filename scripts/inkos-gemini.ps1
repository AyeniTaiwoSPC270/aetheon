# Wrapper: runs `inkos` routed entirely through Gemini (google service),
# since the Anthropic key is no longer in use. Verified working
# 2026-07-10 via `--service google --model gemini-2.5-flash
# --api-key-env GEMINI_API_KEY --api-format responses` -- see CLAUDE.md's
# MODEL ROUTING section for why these specific flags (not INKOS_LLM_*
# env vars, which InkOS did not pick up in testing) and the empty-text
# retry quirk on short prompts.
& inkos --service google --model gemini-2.5-flash --api-key-env GEMINI_API_KEY --api-format responses @args
