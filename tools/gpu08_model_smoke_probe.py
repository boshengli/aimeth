#!/usr/bin/env python3
"""Issue one bounded, non-mathematical request to a loopback OpenAI API."""
import json
import os
import sys
import time
import urllib.error
import urllib.request


def main():
    base = os.environ.get("AIMETH_API_BASE", "http://127.0.0.1:18000/v1")
    model = os.environ["AIMETH_SERVE_NAME"]
    output_dir = os.environ["AIMETH_RUN_ROOT"]
    prompt = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an API smoke-test endpoint. Do not solve or discuss any mathematical problem. Return exactly one JSON object and no other text."},
            {"role": "user", "content": 'Return exactly this JSON object: {"status":"ready","model":"%s"}' % model},
        ],
        "temperature": 1.0,
        "top_p": 1.0,
        "max_tokens": 1024,
        "stream": False,
    }
    request_path = os.path.join(output_dir, "request.json")
    response_path = os.path.join(output_dir, "response.json")
    summary_path = os.path.join(output_dir, "summary.json")
    with open(request_path, "w") as f:
        json.dump(prompt, f, ensure_ascii=False, indent=2)
        f.write("\n")

    health_url = base.rsplit("/v1", 1)[0] + "/health"
    deadline = time.monotonic() + 1800
    healthy = False
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=10) as response:
                healthy = response.status == 200
            if healthy:
                break
        except Exception:
            time.sleep(10)
    if not healthy:
        raise RuntimeError("server did not become healthy within 1800 seconds")

    data = json.dumps(prompt, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(base + "/chat/completions", data=data, headers={"Content-Type": "application/json"})
    start = time.monotonic()
    status = None
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    elapsed = round(time.monotonic() - start, 4)
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        parsed = {"non_json_response_body": body.decode("utf-8", errors="replace")}
    with open(response_path, "w") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
        f.write("\n")

    choices = parsed.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    content = message.get("content") or ""
    try:
        content_json = json.loads(content)
    except Exception:
        content_json = None
    summary = {
        "http_status": status,
        "model_requested": model,
        "model_returned": parsed.get("model"),
        "finish_reason": choice.get("finish_reason"),
        "final_content_nonempty": bool(content),
        "structured_output_valid": isinstance(content_json, dict) and content_json.get("status") == "ready" and content_json.get("model") == model,
        "reasoning_content_present": bool(message.get("reasoning_content")),
        "usage": parsed.get("usage"),
        "elapsed_seconds": elapsed,
        "response_id": parsed.get("id"),
        "server_healthy": True,
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(summary, ensure_ascii=False))
    if status != 200 or not content or choice.get("finish_reason") != "stop":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
