"""Pydantic schema for asset_readiness_report.json."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from schemas.asset_registry import StrictModel


StrengthScore = Literal["weak", "usable", "strong"]
AmbiguityRisk = Literal["high", "medium", "low"]
EvaluatedTextKind = Literal["raw_input", "transformed_script"]
OverallStatus = Literal["ready", "borderline", "not_ready"]
SuggestedNextAction = Literal["extract", "expand", "compress", "rewrite_for_asset_clarity", "confirm"]


class DimensionScores(StrictModel):
    character_clarity: StrengthScore
    scene_clarity: StrengthScore
    prop_clarity: StrengthScore
    visual_anchor_density: StrengthScore
    event_chain_coherence: StrengthScore
    spec_fit_for_60s_6shots: StrengthScore
    ambiguity_risk: AmbiguityRisk
    extraction_stability: StrengthScore


class AssetReadinessReport(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    evaluated_text_kind: EvaluatedTextKind
    overall_status: OverallStatus
    safe_to_extract: bool
    dimension_scores: DimensionScores
    blocking_issues: list[str]
    suggested_next_action: SuggestedNextAction
    repair_focus: list[str]
    summary: str

    @model_validator(mode="after")
    def validate_asset_readiness_report(self) -> "AssetReadinessReport":
        if not self.source_script_name:
            raise ValueError("source_script_name must not be empty")
        if not self.summary:
            raise ValueError("summary must not be empty")

        if self.overall_status == "ready":
            if not self.safe_to_extract:
                raise ValueError("safe_to_extract must be true when overall_status=ready")
            if self.suggested_next_action != "extract":
                raise ValueError("suggested_next_action must be extract when overall_status=ready")
            if self.blocking_issues:
                raise ValueError("blocking_issues must be empty when overall_status=ready")

        if self.overall_status == "not_ready":
            if self.safe_to_extract:
                raise ValueError("safe_to_extract must be false when overall_status=not_ready")
            if self.suggested_next_action == "extract":
                raise ValueError("suggested_next_action must not be extract when overall_status=not_ready")

        if self.safe_to_extract and self.suggested_next_action != "extract":
            raise ValueError("suggested_next_action must be extract when safe_to_extract=true")

        return self
