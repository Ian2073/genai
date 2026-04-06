"""Coreference backend adapter layer.

This module isolates coreference backend selection from scoring logic.
Current backends:
- remote_fastcoref: HTTP call to the dedicated coref service
- local_fastcoref: in-process fastcoref model (no service dependency)
- fallback_rules: lightweight in-process rules
- llm_coref: reserved placeholder for future migration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

try:
    from fastcoref import FCoref
except Exception:  # Optional dependency.
    FCoref = None

LogFn = Optional[Callable[..., None]]


DEFAULT_PRONOUNS = [
    "he",
    "she",
    "it",
    "they",
    "his",
    "her",
    "their",
    "him",
    "them",
    "他",
    "她",
    "牠",
    "它",
    "他們",
    "她們",
    "牠們",
    "它們",
    "其",
    "該",
]


def _safe_log(log_fn: LogFn, message: str, *args: Any) -> None:
    if log_fn is None:
        return
    try:
        log_fn(message, *args)
    except Exception:
        return


def _build_relations_from_clusters(clusters: List[List[str]]) -> List[Dict[str, Any]]:
    relations: List[Dict[str, Any]] = []
    for cluster in clusters:
        if not isinstance(cluster, list) or len(cluster) <= 1:
            continue
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                relations.append(
                    {
                        "entity1": cluster[i],
                        "entity2": cluster[j],
                        "confidence": 0.85,
                        "relation_type": "coreference",
                    }
                )
    return relations


def _build_result(
    *,
    chains: List[List[str]],
    relations: List[Dict[str, Any]],
    method: str,
    backend_name: str,
    backend_mode: str,
    fallback_mode: bool,
    degradation_reason: Optional[str],
) -> Dict[str, Any]:
    return {
        "coreference_chains": chains,
        "coreference_relations": relations,
        "total_relations": len(relations),
        "average_confidence": (
            sum(float(item.get("confidence", 0.0)) for item in relations) / len(relations)
            if relations
            else 0.0
        ),
        "method": method,
        "backend_name": backend_name,
        "backend_mode": backend_mode,
        "fallback_mode": fallback_mode,
        "degradation_reason": degradation_reason,
    }


@dataclass
class RemoteFastCorefBackend:
    service_url: str
    request_timeout_sec: int
    logger_warn: LogFn = None

    name: str = "remote_fastcoref"

    def check_health(self) -> bool:
        try:
            response = requests.get(f"{self.service_url}/health", timeout=5)
            if response.status_code != 200:
                return False
            data = response.json()
            return bool(data.get("model_loaded", False))
        except Exception as exc:
            _safe_log(self.logger_warn, "Coref service health check failed: %s", exc)
            return False

    def resolve_story_coreferences(self, story_text: str) -> Dict[str, Any]:
        try:
            response = requests.post(
                f"{self.service_url}/coref/resolve",
                json={"text": story_text},
                timeout=self.request_timeout_sec,
            )
        except requests.Timeout as exc:
            raise TimeoutError("remote_timeout") from exc
        except Exception as exc:
            raise RuntimeError("remote_exception") from exc

        if response.status_code != 200:
            raise RuntimeError(f"remote_http_{response.status_code}")

        try:
            payload = response.json() or {}
        except Exception as exc:
            raise RuntimeError("remote_invalid_json") from exc

        if payload.get("error"):
            raise RuntimeError("remote_service_error")

        raw_clusters = payload.get("clusters") or []
        clusters: List[List[str]] = []
        for item in raw_clusters:
            if isinstance(item, list):
                clusters.append([str(x) for x in item])

        relations = _build_relations_from_clusters(clusters)
        return _build_result(
            chains=clusters,
            relations=relations,
            method="remote_service",
            backend_name=self.name,
            backend_mode="auto",
            fallback_mode=False,
            degradation_reason=None,
        )


@dataclass
class LocalFastCorefBackend:
    model_name_or_path: Optional[str]
    device_preference: str
    max_tokens_in_batch: int
    logger_warn: LogFn = None

    name: str = "local_fastcoref"
    model: Any = None
    available: bool = False

    def _resolve_device(self) -> str:
        pref = (self.device_preference or "auto").strip().lower()
        if pref in {"cuda", "cuda:0"}:
            return "cuda:0"
        if pref == "cpu":
            return "cpu"
        try:
            import torch

            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def load(self) -> bool:
        if FCoref is None:
            _safe_log(self.logger_warn, "fastcoref is not installed; local coref backend disabled")
            self.available = False
            return False

        kwargs: Dict[str, Any] = {}
        if self.model_name_or_path:
            kwargs["model_name_or_path"] = self.model_name_or_path

        try:
            self.model = FCoref(device=self._resolve_device(), **kwargs)
            self.available = True
            return True
        except Exception as exc:
            _safe_log(self.logger_warn, "Failed to initialize local fastcoref backend: %s", exc)
            self.model = None
            self.available = False
            return False

    def resolve_story_coreferences(self, story_text: str) -> Dict[str, Any]:
        if not self.available or self.model is None:
            raise RuntimeError("local_backend_unavailable")

        try:
            preds = self.model.predict(
                texts=[story_text],
                max_tokens_in_batch=max(128, int(self.max_tokens_in_batch or 2048)),
            )
            clusters = preds[0].get_clusters(as_strings=True) if preds else []
            clusters = [list(map(str, cluster)) for cluster in clusters if isinstance(cluster, list)]
        except Exception as exc:
            raise RuntimeError("local_exception") from exc

        relations = _build_relations_from_clusters(clusters)
        return _build_result(
            chains=clusters,
            relations=relations,
            method="local_fastcoref",
            backend_name=self.name,
            backend_mode="auto",
            fallback_mode=False,
            degradation_reason=None,
        )


@dataclass
class RuleBasedCorefBackend:
    pronouns: List[str]

    name: str = "fallback_rules"

    def resolve_story_coreferences(
        self,
        story_text: str,
        entities: List[str],
        *,
        backend_mode: str,
        reason: str,
    ) -> Dict[str, Any]:
        relations: List[Dict[str, Any]] = []
        chains: List[List[str]] = []
        text_lower = (story_text or "").lower()

        for entity in entities:
            chain = [entity]
            entity_pos = text_lower.find((entity or "").lower())
            if entity_pos < 0:
                continue

            for pronoun in self.pronouns:
                pronoun_pos = text_lower.find(pronoun)
                if pronoun_pos < 0:
                    continue
                if abs(entity_pos - pronoun_pos) >= 120:
                    continue

                chain.append(pronoun)
                relations.append(
                    {
                        "entity1": entity,
                        "entity2": pronoun,
                        "confidence": 0.6,
                        "relation_type": "fallback_coreference",
                    }
                )

            if len(chain) > 1:
                chains.append(chain)

        return _build_result(
            chains=chains,
            relations=relations,
            method="fallback_rules",
            backend_name=self.name,
            backend_mode=backend_mode,
            fallback_mode=True,
            degradation_reason=reason,
        )


class LLMCorefBackend:
    """Reserved backend for future llm_coref migration."""

    name = "llm_coref"

    def resolve_story_coreferences(self, story_text: str, entities: List[str]) -> Dict[str, Any]:
        raise NotImplementedError("llm_backend_not_implemented")


class CorefBackendAdapter:
    """Routes coreference requests to configured backend with safe fallback."""

    VALID_MODES = {"auto", "remote", "local", "rules", "llm"}

    def __init__(
        self,
        *,
        service_url: str,
        backend_mode: str,
        request_timeout_sec: int,
        local_model_name_or_path: Optional[str] = None,
        local_device_preference: str = "auto",
        local_max_tokens_in_batch: int = 2048,
        enable_local_fastcoref: bool = True,
        pronouns: Optional[List[str]] = None,
        logger_info: LogFn = None,
        logger_warn: LogFn = None,
    ):
        normalized_mode = (backend_mode or "auto").strip().lower()
        if normalized_mode not in self.VALID_MODES:
            _safe_log(logger_warn, "Invalid COREF_BACKEND_MODE=%s, fallback to auto", normalized_mode)
            normalized_mode = "auto"

        self.backend_mode = normalized_mode
        self.logger_info = logger_info
        self.logger_warn = logger_warn

        self.remote_backend = RemoteFastCorefBackend(
            service_url=service_url,
            request_timeout_sec=request_timeout_sec,
            logger_warn=logger_warn,
        )
        self.local_backend = LocalFastCorefBackend(
            model_name_or_path=local_model_name_or_path,
            device_preference=local_device_preference,
            max_tokens_in_batch=local_max_tokens_in_batch,
            logger_warn=logger_warn,
        )
        self.rules_backend = RuleBasedCorefBackend(pronouns=list(pronouns or DEFAULT_PRONOUNS))
        self.llm_backend = LLMCorefBackend()

        self.local_available = (
            self.local_backend.load()
            if enable_local_fastcoref and self.backend_mode != "rules"
            else False
        )

        should_check_remote = False
        if self.backend_mode == "remote":
            should_check_remote = True
        elif self.backend_mode == "auto" and not self.local_available:
            should_check_remote = True

        self.remote_available = self.remote_backend.check_health() if should_check_remote else False

    def _resolve_rules(self, story_text: str, entities: List[str], *, reason: str) -> Dict[str, Any]:
        return self.rules_backend.resolve_story_coreferences(
            story_text,
            entities,
            backend_mode=self.backend_mode,
            reason=reason,
        )

    def _resolve_remote(self, story_text: str) -> Dict[str, Any]:
        result = self.remote_backend.resolve_story_coreferences(story_text)
        result["backend_mode"] = self.backend_mode
        result["backend_name"] = self.remote_backend.name
        result["fallback_mode"] = False
        result["degradation_reason"] = None
        return result

    def _resolve_local(self, story_text: str) -> Dict[str, Any]:
        result = self.local_backend.resolve_story_coreferences(story_text)
        result["backend_mode"] = self.backend_mode
        result["backend_name"] = self.local_backend.name
        result["fallback_mode"] = False
        result["degradation_reason"] = None
        return result

    def resolve_story_coreferences(self, story_text: str, entities: List[str]) -> Dict[str, Any]:
        if self.backend_mode == "rules":
            _safe_log(self.logger_info, "Coref backend forced to rules mode (COREF_BACKEND_MODE=rules)")
            return self._resolve_rules(story_text, entities, reason="backend_forced_rules")

        if self.backend_mode == "llm":
            _safe_log(self.logger_warn, "llm_coref backend is not enabled yet, fallback to rules")
            return self._resolve_rules(story_text, entities, reason="llm_backend_not_implemented")

        if self.backend_mode == "local":
            if self.local_available:
                try:
                    return self._resolve_local(story_text)
                except Exception as exc:
                    _safe_log(self.logger_warn, "Local coref backend failed: %s", exc)
            if self.remote_available:
                _safe_log(self.logger_warn, "Local coref unavailable, fallback to remote backend")
                try:
                    return self._resolve_remote(story_text)
                except Exception as exc:
                    _safe_log(self.logger_warn, "Remote coref backend failed after local fallback: %s", exc)
            return self._resolve_rules(story_text, entities, reason="local_backend_unavailable")

        if self.backend_mode == "auto":
            # Prefer local in-process backend for stability (no service dependency).
            if self.local_available:
                try:
                    return self._resolve_local(story_text)
                except Exception as exc:
                    _safe_log(self.logger_warn, "Local coref backend failed in auto mode: %s", exc)

            if self.remote_available:
                try:
                    return self._resolve_remote(story_text)
                except TimeoutError:
                    _safe_log(self.logger_warn, "Coref request timed out in auto mode, fallback to rules")
                    return self._resolve_rules(story_text, entities, reason="remote_timeout")
                except RuntimeError as exc:
                    reason = str(exc) or "remote_exception"
                    _safe_log(self.logger_warn, "Coref request failed in auto mode: %s", reason)
                    return self._resolve_rules(story_text, entities, reason=reason)
                except Exception as exc:
                    _safe_log(self.logger_warn, "Coref request failed in auto mode: %s", exc)
                    return self._resolve_rules(story_text, entities, reason="remote_exception")

            _safe_log(self.logger_warn, "No coref model backend available in auto mode, fallback to rules")
            return self._resolve_rules(story_text, entities, reason="no_backend_available")

        if self.backend_mode == "remote" and not self.remote_available:
            if self.local_available:
                _safe_log(self.logger_warn, "Remote coref backend unavailable, fallback to local backend")
                try:
                    return self._resolve_local(story_text)
                except Exception as exc:
                    _safe_log(self.logger_warn, "Local coref backend failed after remote fallback: %s", exc)
            return self._resolve_rules(story_text, entities, reason="remote_backend_unavailable")

        try:
            return self._resolve_remote(story_text)
        except TimeoutError:
            _safe_log(self.logger_warn, "Coref request timed out, fallback to rules")
            reason = "remote_timeout"
        except RuntimeError as exc:
            reason = str(exc) or "remote_exception"
            _safe_log(self.logger_warn, "Coref request failed: %s, fallback to rules", reason)
        except Exception as exc:
            reason = "remote_exception"
            _safe_log(self.logger_warn, "Coref request failed: %s, fallback to rules", exc)

        if self.local_available:
            _safe_log(self.logger_warn, "Remote coref backend failed, fallback to local backend")
            try:
                return self._resolve_local(story_text)
            except Exception as exc:
                _safe_log(self.logger_warn, "Local coref backend failed after remote error: %s", exc)

        return self._resolve_rules(story_text, entities, reason=reason)
