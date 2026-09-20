# Bounded institutional gateway diagnostic · 2026-09-20

Planned after all eight DeepSeek representation cases in job 196060 returned HTTP 502. This is an operational diagnosis, not a new mathematical score or a change to the role-pilot gate.

At most two fresh requests to the same institutional gateway and served ID `deepseek-v4-flash-0731`, from the local client. First use only model, a minimal JSON status request, temperature=0 and max_tokens=32. If it fails, stop. If it succeeds, repeat with the pilot's response_format=json_object, chat_template_kwargs.enable_thinking=false, top_p=1 and a fixed seed. This can check current service reachability and those optional fields, but cannot explain earlier failures causally or prove the backend node/weights.

No retries, no alternative model, <=64 reserved output tokens, <=4096 request bytes each, 15-second socket timeout within a 30-second process deadline per request. Unknown usage remains unknown even on HTTP error. Preserve the exact credential-free request, status, successful response and private bounded error body with hashes. Public error text is bounded and removes credential values, key-like strings and private addresses. No service restart, routing change or additional population launch follows automatically.
