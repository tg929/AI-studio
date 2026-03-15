"""Pydantic schema for intake_router.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import StrictModel


UserGoal = Literal["auto", "create_story", "expand_input", "compress_input", "rewrite_for_visuals", "extract_assets"]
SourceForm = Literal["keywords", "brief", "partial_script", "full_script", "mixed"]
MaterialState = Literal["idea_only", "synopsis_like", "outline_like", "script_like", "asset_ready_script"]
AssetReadinessEstimate = Literal["low", "medium", "high"]
ChosenPath = Literal[
    "expand_then_extract",
    "compress_then_extract",
    "rewrite_then_extract",
    "direct_extract",
    "confirm_then_continue",
]
RecommendedOperation = Literal["expand", "compress", "rewrite_for_asset_clarity"]


class ProjectTarget(StrictModel):
    target_runtime_sec: int = Field(ge=30, le=180)
    target_shot_count: int = Field(ge=3, le=12)
    target_script_length_chars: int = Field(ge=800, le=6000)
    shot_duration_sec: int = Field(ge=1, le=30)


class IntakeRouter(StrictModel):
    schema_version: Literal["1.0"]
    source_script_name: str
    user_goal: UserGoal
    source_form: SourceForm
    material_state: MaterialState
    project_target: ProjectTarget
    asset_readiness_estimate: AssetReadinessEstimate
    chosen_path: ChosenPath
    recommended_operations: list[RecommendedOperation] = Field(max_length=2)
    reasons: list[str]
    risks: list[str]
    missing_critical_info: list[str]
    needs_confirmation: bool
    confirmation_points: list[str]

    @model_validator(mode="after")
    def validate_intake_router(self) -> "IntakeRouter":
        if not self.source_script_name:
            raise ValueError("source_script_name must not be empty")
        if not self.reasons:
            raise ValueError("reasons must not be empty")

        if self.chosen_path == "confirm_then_continue":
            if not self.needs_confirmation:
                raise ValueError("needs_confirmation must be true when chosen_path=confirm_then_continue")
            if not self.confirmation_points:
                raise ValueError("confirmation_points must not be empty when confirmation is required")
            if self.recommended_operations:
                raise ValueError("recommended_operations must be empty when chosen_path=confirm_then_continue")
            return self

        if self.needs_confirmation:
            raise ValueError("needs_confirmation must be false unless chosen_path=confirm_then_continue")
        if self.confirmation_points:
            raise ValueError("confirmation_points must be empty unless chosen_path=confirm_then_continue")

        expected_primary = {
            "expand_then_extract": "expand",
            "compress_then_extract": "compress",
            "rewrite_then_extract": "rewrite_for_asset_clarity",
            "direct_extract": "",
        }[self.chosen_path]
        if expected_primary:
            if not self.recommended_operations:
                raise ValueError(f"recommended_operations must not be empty for {self.chosen_path}")
            if self.recommended_operations[0] != expected_primary:
                raise ValueError(
                    f"recommended_operations must start with {expected_primary} for {self.chosen_path}, "
                    f"got {self.recommended_operations}"
                )
        elif self.recommended_operations:
            raise ValueError(f"recommended_operations must be empty for {self.chosen_path}")

        if len(self.recommended_operations) == 2:
            if tuple(self.recommended_operations) not in {
                ("expand", "rewrite_for_asset_clarity"),
                ("compress", "rewrite_for_asset_clarity"),
                ("rewrite_for_asset_clarity", "compress"),
            }:
                raise ValueError(
                    "recommended_operations only supports expand+rewrite_for_asset_clarity, "
                    "compress+rewrite_for_asset_clarity, or rewrite_for_asset_clarity+compress in V1"
                )

        return self
