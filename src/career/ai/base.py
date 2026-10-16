"""Provider abstraction (roadmap §38). Nothing outside career.ai imports a vendor SDK."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field, ValidationError

from career.analysis import prompts
from career.analysis.classifier import ActivityAnalysis
from career.analysis.context import ContextPacket

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AIError(RuntimeError):
    """The provider could not produce a usable answer (network, auth, refusal, bad output)."""


class PolishedBullet(BaseModel):
    id: str
    text: str


class PolishedBullets(BaseModel):
    bullets: list[PolishedBullet]


class Summary(BaseModel):
    text: str = Field(max_length=800)


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """A JSON schema every provider's structured-output mode accepts: all properties
    required, no extra properties, no validation keywords (Pydantic re-checks those)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return clean(defs[node["$ref"].split("/")[-1]])
            out = {k: clean(v) for k, v in node.items()
                   if k not in {"title", "default", "minLength", "maxLength", "maxItems", "minItems", "ge", "le",
                                "minimum", "maximum", "description", "exclusiveMinimum", "exclusiveMaximum"}}
            if "anyOf" in out:  # Optional[X] → X | null
                types = [o.get("type") for o in out["anyOf"] if "type" in o]
                if len(types) == len(out["anyOf"]) and all(isinstance(t, str) for t in types):
                    out = {"type": types}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [clean(n) for n in node]
        return node

    return clean(schema)


class AIProvider(ABC):
    name: str = "base"
    default_model: str = ""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or self.default_model
        self.api_key = api_key

    @abstractmethod
    def available(self) -> bool:
        """Configured and reachable enough to try (key present, server up...)."""

    @abstractmethod
    def _complete_json(self, system: str, user: str, schema: dict[str, Any], effort: str) -> str:
        """Return the raw JSON text of a structured response. Raise AIError on failure."""

    def structured(self, system: str, user: str, output: type[T], effort: str = "low") -> T:
        raw = self._complete_json(system, user, strict_schema(output), effort)
        try:
            return output.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AIError(f"{self.name} returned invalid output: {exc}") from exc

    # roadmap §6 interface ---------------------------------------------------
    def analyze(self, context: ContextPacket) -> ActivityAnalysis:
        payload = context.model_dump_json(exclude={"session_id"}, exclude_defaults=True)
        return self.structured(prompts.ANALYZE_SYSTEM, prompts.analyze_user(payload), ActivityAnalysis, effort="low")

    def extract_skills(self, context: ContextPacket) -> list[str]:
        return self.analyze(context).skills

    def summarize(self, stats: dict[str, Any]) -> str:
        return self.structured(prompts.SUMMARY_SYSTEM, json.dumps(stats, ensure_ascii=False, default=str), Summary).text

    def generate_cv(self, bullets: list[dict[str, str]]) -> list[PolishedBullet]:
        result = self.structured(prompts.CV_SYSTEM, prompts.cv_user(bullets), PolishedBullets, effort="medium")
        return result.bullets


class FakeProvider(AIProvider):
    """Deterministic provider for tests and offline demos: returns queued JSON answers."""

    name = "fake"
    default_model = "fake-1"

    def __init__(self, answers: list[Any] | None = None, up: bool = True):
        super().__init__()
        self.answers = list(answers or [])
        self.up = up
        self.calls: list[tuple[str, str]] = []

    def available(self) -> bool:
        return self.up

    def _complete_json(self, system: str, user: str, schema: dict[str, Any], effort: str) -> str:
        self.calls.append((system, user))
        if not self.answers:
            raise AIError("no answer queued")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)
