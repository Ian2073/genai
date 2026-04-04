"""Coreference backend adapter layer.

This module isolates coreference backend selection from scoring logic.
Current backends:
- remote_fastcoref: HTTP call to the dedicated coref service
- fallback_rules: lightweight in-process rules
- llm_coref: reserved placeholder for future migration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

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
                if abs(entity_pos - pronoun_pos) >= 200:
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

    VALID_MODES = {"auto", "remote", "rules", "llm"}

    def __init__(
        self,
        *,
        service_url: str,
        backend_mode: str,
        request_timeout_sec: int,
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
        self.rules_backend = RuleBasedCorefBackend(pronouns=list(pronouns or DEFAULT_PRONOUNS))
        self.llm_backend = LLMCorefBackend()

        self.remote_available = (
            self.remote_backend.check_health() if self.backend_mode != "rules" else False
        )

    def resolve_story_coreferences(self, story_text: str, entities: List[str]) -> Dict[str, Any]:
        if self.backend_mode == "rules":
            _safe_log(self.logger_info, "Coref backend forced to rules mode (COREF_BACKEND_MODE=rules)")
            return self.rules_backend.resolve_story_coreferences(
                story_text,
                entities,
                backend_mode="rules",
                reason="backend_forced_rules",
            )

        if self.backend_mode == "llm":
            _safe_log(self.logger_warn, "llm_coref backend is not enabled yet, fallback to rules")
            return self.rules_backend.resolve_story_coreferences(
                story_text,
                entities,
                backend_mode="llm",
                reason="llm_backend_not_implemented",
            )

        if self.backend_mode == "remote" and not self.remote_available:
            _safe_log(self.logger_warn, "Remote coref backend unavailable, fallback to rules")
            return self.rules_backend.resolve_story_coreferences(
                story_text,
                entities,
                backend_mode="remote",
                reason="remote_backend_unavailable",
            )

        if self.backend_mode == "auto" and not self.remote_available:
            _safe_log(self.logger_warn, "Coref service unavailable in auto mode, fallback to rules")
            return self.rules_backend.resolve_story_coreferences(
                story_text,
                entities,
                backend_mode="auto",
                reason="service_unavailable",
            )

        try:
            result = self.remote_backend.resolve_story_coreferences(story_text)
            result["backend_mode"] = self.backend_mode
            result["backend_name"] = self.remote_backend.name
            result["fallback_mode"] = False
            result["degradation_reason"] = None
            return result
        except TimeoutError:
            _safe_log(self.logger_warn, "Coref request timed out, fallback to rules")
            reason = "remote_timeout"
        except RuntimeError as exc:
            reason = str(exc) or "remote_exception"
            _safe_log(self.logger_warn, "Coref request failed: %s, fallback to rules", reason)
        except Exception as exc:
            reason = "remote_exception"
            _safe_log(self.logger_warn, "Coref request failed: %s, fallback to rules", exc)

        return self.rules_backend.resolve_story_coreferences(
            story_text,
            entities,
            backend_mode=self.backend_mode,
            reason=reason,
        )
