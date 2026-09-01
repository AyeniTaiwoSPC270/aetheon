# Wrapper: runs `inkos` routed entirely through Gemini (google service),
# since the Anthropic key is no longer in use. Verified working
# 2026-07-10 via `--service google --model gemini-2.5-flash
# --api-key-env GEMINI_API_KEY --api-format responses` -- see CLAUDE.md's
# MODEL ROUTING section for why these specific flags (not INKOS_LLM_*
# env vars, which InkOS did not pick up in testing) and the empty-text
# retry quirk on short prompts.
#
# 2026-07-12: gemini-2.5-flash started 404ing ("no longer available to
# new users"). Switched to gemini-2.0-flash-001 -- confirmed working via
# `inkos doctor`, which internally settles on models/gemini-flash-latest
# after its usual empty-text retries.
#
# 2026-09-01: gemini-2.0-flash-001 hard-404'd too (Google: "no longer
# available ... use models/gemini-3.6-flash"). That name isn't in
# InkOS's own google-service model registry though (inkos-core's
# endpoints/google.js) and gets rejected client-side. Switched to
# gemini-flash-latest -- a stable alias in that registry rather than a
# dated snapshot, so it shouldn't need to rotate again the same way.
# Confirmed working via a real `inkos audit` call.
& inkos --service google --model gemini-flash-latest --api-key-env GEMINI_API_KEY --api-format responses @args
