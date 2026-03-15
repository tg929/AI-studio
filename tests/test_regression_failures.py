from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.workflow_service import WorkflowService
from pipeline.intent_to_script import normalize_intake_router_payload, read_json_string as read_stage_json_string
from pipeline.storyboard import normalize_storyboard_payload, validate_storyboard_against_registry
from schemas.asset_registry import AssetRegistry
from schemas.intake_router import IntakeRouter
from schemas.storyboard import Storyboard


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RegressionFailureTests(unittest.TestCase):
    def test_intake_router_normalization_repairs_misaligned_operations(self) -> None:
        source_context = json.loads((PROJECT_ROOT / "runs" / "run17" / "00_source" / "source_context.json").read_text())
        response = json.loads((PROJECT_ROOT / "runs" / "run17" / "00_source" / "intake_router_response.json").read_text())
        payload = normalize_intake_router_payload(
            read_stage_json_string(response["choices"][0]["message"]["content"]),
            source_script_name="02-斗气大陆",
            source_context=source_context,
        )

        router = IntakeRouter.model_validate(payload)

        self.assertEqual(router.chosen_path, "rewrite_then_extract")
        self.assertEqual(router.recommended_operations, ["rewrite_for_asset_clarity", "compress"])

    def test_storyboard_validation_accepts_signature_props_for_present_characters(self) -> None:
        asset_registry = AssetRegistry.model_validate(
            json.loads((PROJECT_ROOT / "runs" / "run16" / "02_assets" / "asset_registry.json").read_text())
        )
        response = json.loads((PROJECT_ROOT / "runs" / "run16" / "06_storyboard" / "storyboard_response.json").read_text())
        payload = normalize_storyboard_payload(
            read_stage_json_string(response["choices"][0]["message"]["content"]),
            run_name="run16",
            asset_registry=asset_registry,
        )

        storyboard = Storyboard.model_validate(payload)
        validate_storyboard_against_registry(storyboard, asset_registry)

        shot_002 = next(shot for shot in storyboard.shots if shot.id == "shot_002")
        self.assertIn("prop_001", shot_002.prop_ids)

    def test_storyboard_validation_still_rejects_unrelated_props(self) -> None:
        asset_registry = AssetRegistry.model_validate(
            json.loads((PROJECT_ROOT / "runs" / "run16" / "02_assets" / "asset_registry.json").read_text())
        )
        response = json.loads((PROJECT_ROOT / "runs" / "run16" / "06_storyboard" / "storyboard_response.json").read_text())
        payload = normalize_storyboard_payload(
            read_stage_json_string(response["choices"][0]["message"]["content"]),
            run_name="run16",
            asset_registry=asset_registry,
        )
        for shot in payload["shots"]:
            if shot.get("id") == "shot_002":
                shot["prop_ids"] = ["prop_003", "prop_002"]
                break

        storyboard = Storyboard.model_validate(payload)

        with self.assertRaisesRegex(ValueError, "allowed coverage"):
            validate_storyboard_against_registry(storyboard, asset_registry)

    def test_intake_router_normalization_clears_stale_confirmation_flags(self) -> None:
        source_context = json.loads((PROJECT_ROOT / "runs" / "run17" / "00_source" / "source_context.json").read_text())
        payload = normalize_intake_router_payload(
            {
                "chosen_path": "compress_then_extract",
                "recommended_operations": ["compress"],
                "needs_confirmation": True,
                "confirmation_points": ["double check before continuing"],
                "reasons": ["input is long enough to compress"],
                "risks": ["condensing may drop detail"],
                "missing_critical_info": [],
            },
            source_script_name="02-斗气大陆",
            source_context=source_context,
        )

        self.assertEqual(payload["chosen_path"], "compress_then_extract")
        self.assertFalse(payload["needs_confirmation"])
        self.assertEqual(payload["confirmation_points"], [])

    def test_intake_router_normalization_backfills_confirmation_points_for_confirm_path(self) -> None:
        source_context = json.loads((PROJECT_ROOT / "runs" / "run17" / "00_source" / "source_context.json").read_text())
        payload = normalize_intake_router_payload(
            {
                "chosen_path": "confirm_then_continue",
                "recommended_operations": [],
                "needs_confirmation": False,
                "confirmation_points": [],
                "reasons": ["source intent conflicts with project target"],
                "risks": ["route could over-expand the material"],
                "missing_critical_info": ["confirm target length"],
            },
            source_script_name="02-斗气大陆",
            source_context=source_context,
        )

        self.assertTrue(payload["needs_confirmation"])
        self.assertEqual(payload["confirmation_points"], ["confirm target length"])


class WorkflowReviewGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_root = Path(self.temp_dir.name)
        self.run_dir = self.output_root / "run_gate"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        config_stub = SimpleNamespace(model_name="stub-model", base_url="http://example.invalid")
        self._patches = [
            mock.patch("app.workflow_service.load_text_model_config", return_value=config_stub),
            mock.patch("app.workflow_service.load_image_model_config", return_value=config_stub),
            mock.patch("app.workflow_service.load_video_model_config", return_value=config_stub),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.service = WorkflowService(output_root=self.output_root, env_file=None)

    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def fake_generate_asset_images(self, *, asset_prompts_path: Path, model_config: object) -> None:
        manifest_path = asset_prompts_path.parent.parent / "05_asset_images" / "asset_images_manifest.json"
        self.write_json(
            manifest_path,
            {
                "source_run": asset_prompts_path.parent.parent.name,
                "characters": [],
                "scenes": [],
                "props": [],
            },
        )

    def test_review_gate_blocks_storyboard_until_asset_images_is_approved(self) -> None:
        self.service.submit_review(self.run_dir, stage="upstream", status="approved")

        result = self.service.run_stage("storyboard", run_dir=self.run_dir)

        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(result["review_stage"], "asset_images")

        run_state = self.service.inspect_run(self.run_dir)["run_state"]
        self.assertEqual(run_state["status"], "awaiting_approval")
        self.assertEqual(run_state["awaiting_approval_stage"], "asset_images")
        self.assertEqual(run_state["stages"]["asset_images"]["status"], "awaiting_approval")

    def test_asset_images_stage_resets_review_and_marks_run_awaiting_approval(self) -> None:
        self.write_json(self.run_dir / "04_asset_prompts" / "asset_prompts.json", {"items": []})
        self.service.submit_review(self.run_dir, stage="upstream", status="approved")

        with mock.patch("app.workflow_service.generate_asset_images", side_effect=self.fake_generate_asset_images):
            result = self.service.run_stage("asset_images", run_dir=self.run_dir)

        self.assertEqual(result["status"], "ok")
        review = self.service.get_review(self.run_dir, "asset_images")["review"]
        self.assertEqual(review["status"], "pending")

        run_state = self.service.inspect_run(self.run_dir)["run_state"]
        self.assertEqual(run_state["status"], "awaiting_approval")
        self.assertEqual(run_state["awaiting_approval_stage"], "asset_images")
        self.assertEqual(run_state["stages"]["asset_images"]["status"], "awaiting_approval")

    def test_approving_review_clears_awaiting_state(self) -> None:
        self.write_json(self.run_dir / "04_asset_prompts" / "asset_prompts.json", {"items": []})
        self.service.submit_review(self.run_dir, stage="upstream", status="approved")

        with mock.patch("app.workflow_service.generate_asset_images", side_effect=self.fake_generate_asset_images):
            self.service.run_stage("asset_images", run_dir=self.run_dir)

        approval = self.service.submit_review(self.run_dir, stage="asset_images", status="approved", reviewer="operator")

        self.assertEqual(approval["reviews"]["reviews"]["asset_images"]["status"], "approved")

        run_state = self.service.inspect_run(self.run_dir)["run_state"]
        self.assertEqual(run_state["status"], "running")
        self.assertEqual(run_state["awaiting_approval_stage"], "")
        self.assertEqual(run_state["stages"]["asset_images"]["status"], "succeeded")


class WorkflowReviewPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config_stub = SimpleNamespace(model_name="stub-model", base_url="http://example.invalid")
        cls._patches = [
            mock.patch("app.workflow_service.load_text_model_config", return_value=config_stub),
            mock.patch("app.workflow_service.load_image_model_config", return_value=config_stub),
            mock.patch("app.workflow_service.load_video_model_config", return_value=config_stub),
        ]
        for patcher in cls._patches:
            patcher.start()

    @classmethod
    def tearDownClass(cls) -> None:
        for patcher in reversed(cls._patches):
            patcher.stop()

    def test_storyboard_review_payload_includes_reference_assets_and_board_preview(self) -> None:
        service = WorkflowService(output_root=PROJECT_ROOT / "runs", env_file=None)

        payload = service.build_review_payload(PROJECT_ROOT / "runs" / "run16", "storyboard")
        shot_002 = next(shot for shot in payload["shots"] if shot["shot_id"] == "shot_002")
        reference_ids = {asset["asset_id"] for asset in shot_002["reference_assets"]}

        self.assertIn("scene_001", reference_ids)
        self.assertIn("char_001", reference_ids)
        self.assertTrue(shot_002["board_preview_url"])
        self.assertEqual(shot_002["board_layout_template"], "grid_2x1")


if __name__ == "__main__":
    unittest.main()
