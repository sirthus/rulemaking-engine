#!/usr/bin/env python3

import requests


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 30

SUPPORTED_MODEL_PROFILES = {
    "qwen3:14b": {
        "model": "qwen3:14b",
        "display_name": "Qwen 3 14B",
        "purpose": "Accuracy-first local labeling baseline",
        "recommended_no_think": True,
        "status": "supported",
        "warning": None,
    },
    "gemma3:12b-it-q8_0": {
        "model": "gemma3:12b-it-q8_0",
        "display_name": "Gemma 3 12B Instruct Q8",
        "purpose": "Speed-first local labeling alternative",
        "recommended_no_think": False,
        "status": "supported",
        "warning": None,
    },
}


def resolve_model_profile(model: str | None) -> dict:
    normalized = (model or "").strip()
    if normalized in SUPPORTED_MODEL_PROFILES:
        profile = dict(SUPPORTED_MODEL_PROFILES[normalized])
        profile["supported"] = True
        return profile

    return {
        "model": normalized,
        "display_name": normalized or "Unknown model",
        "purpose": "Custom or experimental local model",
        "recommended_no_think": False,
        "status": "experimental",
        "warning": (
            "This model is not in the validated local profile list. "
            "Proceed only if you have validated it locally."
        ),
        "supported": False,
    }


def _extract_model_names(tags_payload: dict) -> list[str]:
    if not isinstance(tags_payload, dict):
        raise RuntimeError("Ollama /api/tags returned an unexpected payload.")

    models = tags_payload.get("models")
    if not isinstance(models, list):
        raise RuntimeError("Ollama /api/tags did not include a models list.")

    names = []
    for model_entry in models:
        if not isinstance(model_entry, dict):
            continue
        for key in ("model", "name"):
            value = model_entry.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
                break
    return sorted(set(names))


def run_preflight(
    ollama_url: str,
    model: str,
    session: requests.Session | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    resolved_url = (ollama_url or DEFAULT_OLLAMA_URL).rstrip("/")
    resolved_model = (model or "").strip()
    profile = resolve_model_profile(resolved_model)
    active_session = session or requests.Session()
    endpoint = f"{resolved_url}/api/tags"

    try:
        response = active_session.get(endpoint, timeout=timeout_seconds)
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"Ollama preflight timed out at {resolved_url}. Check whether the daemon is running."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {resolved_url}. Start `ollama serve` and try again."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama preflight failed: {exc}") from exc

    if response.status_code != 200:
        detail = response.text.strip()
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get("error"):
            detail = str(payload["error"])
        raise RuntimeError(f"Ollama preflight returned HTTP {response.status_code}: {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Ollama preflight returned malformed JSON from /api/tags.") from exc

    installed_models = _extract_model_names(payload)
    if resolved_model and resolved_model not in installed_models:
        raise RuntimeError(
            f"Model `{resolved_model}` is not installed in Ollama. Run `ollama pull {resolved_model}` first."
        )

    warnings = []
    if profile.get("warning"):
        warnings.append(profile["warning"])

    return {
        "ollama_url": resolved_url,
        "model": resolved_model,
        "profile": profile,
        "installed_models": installed_models,
        "installed_model_count": len(installed_models),
        "reachable": True,
        "warnings": warnings,
    }


def preflight_summary_lines(preflight: dict) -> list[str]:
    profile = preflight["profile"]
    lines = [
        f"Ollama reachable at {preflight['ollama_url']}",
        f"Model: {preflight['model']} ({profile['status']})",
        f"Profile: {profile['purpose']}",
        f"Recommended no_think: {bool(profile.get('recommended_no_think'))}",
        f"Installed models detected: {preflight.get('installed_model_count', 0)}",
    ]
    for warning in preflight.get("warnings", []):
        lines.append(f"Warning: {warning}")
    return lines


def profile_for_manifest(profile: dict | None) -> dict | None:
    if not isinstance(profile, dict):
        return None
    return {
        "model": profile.get("model"),
        "display_name": profile.get("display_name"),
        "purpose": profile.get("purpose"),
        "recommended_no_think": bool(profile.get("recommended_no_think")),
        "status": profile.get("status"),
        "warning": profile.get("warning"),
        "supported": bool(profile.get("supported")),
    }
