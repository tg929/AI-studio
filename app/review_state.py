from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .run_state import utc_now_iso


ReviewStage = Literal["upstream", "asset_images", "storyboard"]
ReviewStatus = Literal["pending", "approved", "rejected"]

REVIEW_STAGE_ORDER: tuple[ReviewStage, ...] = ("upstream", "asset_images", "storyboard")


class StageReview(BaseModel):
    stage: ReviewStage
    status: ReviewStatus = "pending"
    reviewer: str = ""
    notes: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunReviews(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    updated_at: str
    reviews: dict[str, StageReview] = Field(default_factory=dict)


def reviews_path(run_dir: Path) -> Path:
    meta_dir = run_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    return meta_dir / "reviews.json"


def build_default_reviews(run_dir: Path) -> RunReviews:
    timestamp = utc_now_iso()
    reviews = {
        stage: StageReview(stage=stage, updated_at=timestamp)
        for stage in REVIEW_STAGE_ORDER
    }
    return RunReviews(run_id=run_dir.name, updated_at=timestamp, reviews=reviews)


def load_reviews(run_dir: Path) -> RunReviews | None:
    path = reviews_path(run_dir)
    if not path.exists():
        return None
    return RunReviews.model_validate_json(path.read_text(encoding="utf-8"))


def ensure_reviews(run_dir: Path) -> RunReviews:
    existing = load_reviews(run_dir)
    if existing is not None:
        changed = False
        for stage in REVIEW_STAGE_ORDER:
            if stage not in existing.reviews:
                existing.reviews[stage] = StageReview(stage=stage, updated_at=existing.updated_at)
                changed = True
        if changed:
            write_reviews(run_dir, existing)
        return existing
    reviews = build_default_reviews(run_dir)
    write_reviews(run_dir, reviews)
    return reviews


def write_reviews(run_dir: Path, reviews: RunReviews) -> Path:
    path = reviews_path(run_dir)
    path.write_text(reviews.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def update_review(
    run_dir: Path,
    *,
    stage: ReviewStage,
    status: ReviewStatus,
    reviewer: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> RunReviews:
    reviews = ensure_reviews(run_dir)
    now = utc_now_iso()
    review = reviews.reviews.get(stage) or StageReview(stage=stage)
    review.status = status
    review.updated_at = now
    review.reviewer = reviewer
    review.notes = notes
    if metadata:
        review.metadata.update(metadata)
    reviews.reviews[stage] = review
    reviews.updated_at = now
    write_reviews(run_dir, reviews)
    return reviews
