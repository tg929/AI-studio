"""Pydantic schema for script_quality_report.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import StrictModel


class HardChecks(StrictModel):
    length_range_ok: bool
    paragraph_count_ok: bool
    named_character_count_ok: bool
    scene_count_ok: bool
    narrative_arc_ok: bool
    visual_anchor_density_ok: bool


class QualityScores(StrictModel):
    asset_extraction_readiness: int = Field(ge=1, le=10)
    storyboard_readiness: int = Field(ge=1, le=10)
    visual_specificity: int = Field(ge=1, le=10)
    character_clarity: int = Field(ge=1, le=10)
    scene_clarity: int = Field(ge=1, le=10)
    prop_support: int = Field(ge=1, le=10)


class ScriptQualityReport(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    title: str
    passes_hard_checks: bool
    hard_checks: HardChecks
    quality_scores: QualityScores
    strengths: list[str]
    risks: list[str]
    recommended_repairs: list[str]
    repair_needed: bool
    summary: str

    @model_validator(mode="after")
    def validate_script_quality_report(self) -> "ScriptQualityReport":
        computed_pass = all(self.hard_checks.model_dump(mode="json").values())
        if self.passes_hard_checks != computed_pass:
            raise ValueError(
                f"passes_hard_checks must match hard_checks aggregate: expected {computed_pass}, got {self.passes_hard_checks}"
            )
        if not self.source_script_name:
            raise ValueError("source_script_name must not be empty")
        if not self.title:
            raise ValueError("title must not be empty")
        if not self.summary:
            raise ValueError("summary must not be empty")
        if not self.passes_hard_checks and not self.repair_needed:
            raise ValueError("repair_needed must be true when hard checks do not pass")
        if self.repair_needed and not self.recommended_repairs:
            raise ValueError("recommended_repairs must not be empty when repair_needed is true")
        return self
