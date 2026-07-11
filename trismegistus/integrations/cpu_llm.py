from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()
_MODEL: Any | None = None
_MODEL_PATH = ""
_LOAD_ERROR = ""


DEFAULT_REPO_ID = "bartowski/Hermes-3-Llama-3.2-3B-GGUF"
DEFAULT_MODEL_FILE = "Hermes-3-Llama-3.2-3B-IQ2_M.gguf"


def enabled() -> bool:
    return os.environ.get("TRISMEGISTUS_ENABLE_CPU_LLM", "0") == "1"


def repo_id() -> str:
    return os.environ.get("TRISMEGISTUS_CPU_LLM_REPO", DEFAULT_REPO_ID).strip() or DEFAULT_REPO_ID


def model_file() -> str:
    return os.environ.get("TRISMEGISTUS_CPU_LLM_FILE", DEFAULT_MODEL_FILE).strip() or DEFAULT_MODEL_FILE


def model_type() -> str:
    return "llama.cpp"


def model_name() -> str:
    return f"{repo_id()}::{model_file()}"


def _imports() -> tuple[Any, Any]:
    try:
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        return hf_hub_download, Llama
    except Exception as exc:  # noqa: BLE001 - surfaced in runtime status.
        raise RuntimeError(f"llama-cpp-python GGUF model stack is not importable: {exc}") from exc


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _model_path() -> str:
    configured = os.environ.get("TRISMEGISTUS_CPU_LLM_PATH", "").strip()
    if configured:
        return configured
    hf_hub_download, _ = _imports()
    return str(hf_hub_download(repo_id=repo_id(), filename=model_file()))


def _load() -> Any:
    global _MODEL, _MODEL_PATH, _LOAD_ERROR
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        _, Llama = _imports()
        try:
            path = _model_path()
            model = Llama(
                model_path=path,
                n_ctx=_int_env("TRISMEGISTUS_CPU_LLM_CONTEXT", 1024),
                n_threads=max(1, _int_env("TRISMEGISTUS_CPU_LLM_THREADS", 2)),
                n_gpu_layers=0,
                verbose=False,
            )
            _MODEL = model
            _MODEL_PATH = path
            _LOAD_ERROR = ""
            return model
        except Exception as exc:  # noqa: BLE001
            _LOAD_ERROR = str(exc)
            raise


def _prompt(messages: list[dict[str, str]]) -> str:
    system_parts: list[str] = []
    dialog_parts: list[str] = []
    for item in messages:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role = str(item.get("role") or "user").strip().lower()
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            dialog_parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        else:
            dialog_parts.append(f"<|im_start|>user\n{content}<|im_end|>")
    if system_parts:
        dialog_parts.insert(0, "<|im_start|>system\n" + "\n\n".join(system_parts) + "<|im_end|>")
    dialog_parts.append("<|im_start|>assistant\n")
    return "\n".join(dialog_parts)


def _chat_completion(model: Any, messages: list[dict[str, str]], max_new_tokens: int) -> str:
    if hasattr(model, "create_chat_completion"):
        result = model.create_chat_completion(
            messages=[
                {
                    "role": str(item.get("role") or "user"),
                    "content": str(item.get("content") or ""),
                }
                for item in messages
                if str(item.get("content") or "").strip()
            ],
            max_tokens=max_new_tokens,
            temperature=_float_env("TRISMEGISTUS_CPU_LLM_TEMPERATURE", 0.35),
            top_p=_float_env("TRISMEGISTUS_CPU_LLM_TOP_P", 0.9),
            repeat_penalty=_float_env("TRISMEGISTUS_CPU_LLM_REPETITION_PENALTY", 1.08),
        )
        choices = result.get("choices") if isinstance(result, dict) else None
        if choices:
            message = choices[0].get("message") or {}
            return str(message.get("content") or choices[0].get("text") or "").strip()
    prompt = _prompt(messages)
    result = model(
        prompt,
        max_tokens=max_new_tokens,
        temperature=_float_env("TRISMEGISTUS_CPU_LLM_TEMPERATURE", 0.35),
        top_p=_float_env("TRISMEGISTUS_CPU_LLM_TOP_P", 0.9),
        repeat_penalty=_float_env("TRISMEGISTUS_CPU_LLM_REPETITION_PENALTY", 1.08),
        stop=["<|im_end|>", "<|im_start|>user", "<|eot_id|>"],
    )
    choices = result.get("choices") if isinstance(result, dict) else None
    if choices:
        return str(choices[0].get("text") or "").strip()
    return ""


def status() -> dict[str, Any]:
    if not enabled():
        return {
            "name": "Hosted GGUF model route",
            "ready": False,
            "enabled": False,
            "skipped": "Set TRISMEGISTUS_ENABLE_CPU_LLM=1 to enable the CPU-hosted GGUF fallback.",
        }
    try:
        _imports()
        import_ready = True
        import_error = ""
    except Exception as exc:  # noqa: BLE001
        import_ready = False
        import_error = str(exc)
    return {
        "name": "Hosted GGUF model route",
        "enabled": True,
        "installed": import_ready,
        "ready": bool(import_ready and _MODEL is not None),
        "loaded": _MODEL is not None,
        "load_required": _MODEL is None,
        "model": model_name(),
        "repo_id": repo_id(),
        "model_file": model_file(),
        "model_type": model_type(),
        "provider": "llama-cpp-python/gguf-cpu",
        "model_path": _MODEL_PATH,
        "model_path_exists": bool(_MODEL_PATH and Path(_MODEL_PATH).exists()),
        "import_error": import_error,
        "load_error": _LOAD_ERROR,
        "truth_boundary": (
            "This is a real CPU-hosted GGUF route. It can produce live model text only "
            "after the GGUF file loads and a chat turn answers. Installed is not the same "
            "as live. It is still not NemoClaw/OpenClaw autonomy or an official benchmark route. "
            "For professional field answers, use a strong Hermes/OpenAI-compatible provider or "
            "raise the host class enough to run the Hermes-3 3B+ GGUF target."
        ),
    }


def generate(messages: list[dict[str, str]], max_tokens: int = 500) -> dict[str, Any]:
    if not enabled():
        return {
            "ok": False,
            "source": "hosted-gguf",
            "runtime_lane": "cpu-local-disabled",
            "error": "CPU GGUF fallback is disabled.",
        }
    started = time.time()
    try:
        model = _load()
        max_new_tokens = max(16, min(max_tokens, _int_env("TRISMEGISTUS_CPU_LLM_MAX_NEW_TOKENS", 220)))
        text = _chat_completion(model, messages, max_new_tokens)
        return {
            "ok": bool(text),
            "source": "hosted-gguf",
            "runtime_lane": "cpu-local-gguf",
            "provider": "llama-cpp-python/gguf-cpu",
            "model": model_name(),
            "text": text,
            "latency_ms": round((time.time() - started) * 1000),
            "truth_boundary": (
                "Real CPU-hosted GGUF inference. This proves hosted generation if the model "
                "loaded and answered; it does not prove NemoClaw worker autonomy, Hermes-3 "
                "quality, or benchmark performance."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "source": "hosted-gguf",
            "runtime_lane": "cpu-local-gguf",
            "provider": "llama-cpp-python/gguf-cpu",
            "model": model_name(),
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }
