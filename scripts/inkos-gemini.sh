#!/usr/bin/env bash
# Wrapper: runs `inkos` routed entirely through Gemini (google service),
# since the Anthropic key is no longer in use. Verified working
# 2026-07-10 via `--service google --model gemini-2.5-flash
# --api-key-env GEMINI_API_KEY --api-format responses` — see CLAUDE.md's
# MODEL ROUTING section for why these specific flags (not INKOS_LLM_*
# env vars, which InkOS did not pick up in testing) and the empty-text
# retry quirk on short prompts.
#
# 2026-07-12: gemini-2.5-flash started 404ing ("no longer available to
# new users"). Switched to gemini-2.0-flash-001 — confirmed working via
# `inkos doctor`, which internally settles on models/gemini-flash-latest
# after its usual empty-text retries.
set -euo pipefail
exec inkos --service google --model gemini-2.0-flash-001 --api-key-env GEMINI_API_KEY --api-format responses "$@"
