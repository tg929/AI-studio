from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.task_runner import WorkflowTaskRunner
from app.workflow_service import WorkflowService
from app.ui import build_console_html
from pipeline.asset_images import build_jobs_payload, build_sensitive_retry_render_prompt
from pipeline.intent_to_script import normalize_intake_router_payload, read_json_string as read_stage_json_string
from pipeline.storyboard import normalize_storyboard_payload, validate_storyboard_against_registry
from prompts.asset_prompts import ASSET_PROMPTS_SYSTEM_PROMPT
from prompts.style_bible import STYLE_BIBLE_SYSTEM_PROMPT
from schemas.asset_prompts import AssetPrompts
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


class AssetImagePromptAssemblyTests(unittest.TestCase):
    def test_render_prompts_frontload_asset_specific_subject_and_project_style(self) -> None:
        asset_prompts = AssetPrompts.model_validate(
            {
                "schema_version": "1.0",
                "source_script_name": "custom_input",
                "title": "霓虹疑案",
                "visual_style": "近未来霓虹都市悬疑动漫设定风，冷色雨夜，写实材质。",
                "consistency_anchors": "蓝绿色霓虹倒影，潮湿柏油路，统一冷调高反差。",
                "characters": [
                    {
                        "id": "char_001",
                        "name": "林雾",
                        "label_text": "[林雾 人物参考]",
                        "prompt": "短发女侦探，深灰风衣，右眼下有细小伤痕，持旧式录音笔。",
                        "negative_prompt": "watermark, text",
                        "aspect_ratio": "16:9",
                        "framing": "Single-character reference sheet with a half-body to three-quarter portrait emphasis.",
                        "background_treatment": "Clean light background, centered subject, reserved bottom label area.",
                        "generation_intent": "Character consistency reference sheet for downstream storyboard and video generation.",
                        "card_layout_notes": "Label language: zh-CN.",
                    }
                ],
                "scenes": [
                    {
                        "id": "scene_001",
                        "name": "高架桥下雨夜街口",
                        "label_text": "[高架桥下雨夜街口 场景参考]",
                        "prompt": "高架桥阴影下的十字街口，潮湿柏油路面映出蓝绿色霓虹，远处便利店招牌虚化。",
                        "negative_prompt": "person, watermark",
                        "aspect_ratio": "16:9",
                        "framing": "Wide environment reference sheet.",
                        "figure_policy": "no_identifiable_characters",
                        "generation_intent": "Environment consistency reference sheet for downstream storyboard and video generation.",
                        "card_layout_notes": "Label language: zh-CN.",
                    }
                ],
                "props": [
                    {
                        "id": "prop_001",
                        "name": "旧式录音笔",
                        "label_text": "[旧式录音笔 道具参考]",
                        "prompt": "银黑双色旧式录音笔，磨损金属边框，按键凹陷，细长机身。",
                        "negative_prompt": "text, watermark",
                        "aspect_ratio": "16:9",
                        "framing": "Centered single-prop reference sheet.",
                        "isolation_rules": "Show only the single prop subject, with no people, hands, wearer, or extra same-category objects.",
                        "generation_intent": "Prop consistency reference sheet for downstream storyboard and video generation.",
                        "card_layout_notes": "Label language: zh-CN.",
                    }
                ],
            }
        )

        jobs = build_jobs_payload(asset_prompts)
        character_prompt = jobs["characters"][0]["render_prompt"]
        scene_prompt = jobs["scenes"][0]["render_prompt"]
        prop_prompt = jobs["props"][0]["render_prompt"]

        for prompt in (character_prompt, scene_prompt, prop_prompt):
            self.assertIn("项目统一美术风格：近未来霓虹都市悬疑动漫设定风，冷色雨夜，写实材质。", prompt)
            self.assertIn("统一一致性锚点：蓝绿色霓虹倒影，潮湿柏油路，统一冷调高反差。", prompt)
            self.assertNotIn("精致国风玄幻手绘漫风", prompt)

        self.assertIn("人物主体设定：短发女侦探，深灰风衣，右眼下有细小伤痕，持旧式录音笔。", character_prompt)
        self.assertLess(character_prompt.index("人物主体设定："), character_prompt.index("版式固定："))

        self.assertIn("场景主体设定：高架桥阴影下的十字街口，潮湿柏油路面映出蓝绿色霓虹，远处便利店招牌虚化。", scene_prompt)
        self.assertLess(scene_prompt.index("场景主体设定："), scene_prompt.index("版式固定："))

        self.assertIn("道具主体设定：银黑双色旧式录音笔，磨损金属边框，按键凹陷，细长机身。", prop_prompt)
        self.assertLess(prop_prompt.index("道具主体设定："), prop_prompt.index("版式固定："))

    def test_sensitive_retry_prompt_softens_high_risk_terms(self) -> None:
        asset_prompts = AssetPrompts.model_validate(
            {
                "schema_version": "1.0",
                "source_script_name": "custom_input",
                "title": "夜雨疑案",
                "visual_style": "写实向中式古风漫绘，带有惊悚悬疑的阴郁质感。",
                "consistency_anchors": "失踪线索人物与血迹道具保持一致（红鞋、黄符、半燃香）。",
                "characters": [
                    {
                        "id": "char_001",
                        "name": "调查学徒",
                        "label_text": "[调查学徒 人物参考]",
                        "prompt": "仵作学徒青年，面部有轻微伤痕，衣摆沾血迹。",
                        "negative_prompt": "watermark, text",
                        "aspect_ratio": "16:9",
                        "framing": "Single-character reference sheet with a half-body to three-quarter portrait emphasis.",
                        "background_treatment": "Clean light background, centered subject, reserved bottom label area.",
                        "generation_intent": "Character consistency reference sheet for downstream storyboard and video generation.",
                        "card_layout_notes": "Label language: zh-CN.",
                    }
                ],
                "scenes": [],
                "props": [],
            }
        )

        retry_prompt = build_sensitive_retry_render_prompt(
            item=asset_prompts.characters[0],
            asset_type="character",
            asset_prompts=asset_prompts,
        )

        self.assertNotIn("惊悚", retry_prompt)
        self.assertNotIn("阴郁", retry_prompt)
        self.assertNotIn("失踪", retry_prompt)
        self.assertNotIn("血迹", retry_prompt)
        self.assertNotIn("仵作", retry_prompt)
        self.assertIn("悬疑", retry_prompt)
        self.assertIn("细微痕迹", retry_prompt)
        self.assertIn("暗色污渍", retry_prompt)


class PromptTemplateBiasTests(unittest.TestCase):
    def test_asset_prompt_system_prompt_does_not_force_fantasy_project_world(self) -> None:
        self.assertNotIn("同一个东方玄幻项目世界", ASSET_PROMPTS_SYSTEM_PROMPT)
        self.assertNotIn("精致国风玄幻人物设定图", ASSET_PROMPTS_SYSTEM_PROMPT)
        self.assertIn("同一个项目世界", ASSET_PROMPTS_SYSTEM_PROMPT)

    def test_style_bible_system_prompt_does_not_force_guofeng_fantasy(self) -> None:
        self.assertNotIn("当前项目优先朝以下审美方向收敛：\n- 国风玄幻", STYLE_BIBLE_SYSTEM_PROMPT)
        self.assertIn("不得无依据地固定为某一种题材或时代", STYLE_BIBLE_SYSTEM_PROMPT)
        self.assertIn("以故事题材、时代、世界设定和角色身份为第一依据", STYLE_BIBLE_SYSTEM_PROMPT)


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

    def fake_generate_storyboard(self, *, style_bible_path: Path, model_config: object) -> None:
        storyboard_path = style_bible_path.parent.parent / "06_storyboard" / "storyboard.json"
        self.write_json(
            storyboard_path,
            {
                "source_run": style_bible_path.parent.parent.name,
                "shots": [],
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

    def test_resume_auto_approves_legacy_checkpoint_reviews_from_existing_artifacts(self) -> None:
        (self.run_dir / "01_input").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "01_input" / "script_clean.txt").write_text("legacy script", encoding="utf-8")
        self.write_json(self.run_dir / "02_assets" / "asset_registry.json", {"items": []})
        self.write_json(self.run_dir / "03_style" / "style_bible.json", {"style": "legacy"})
        self.write_json(self.run_dir / "04_asset_prompts" / "asset_prompts.json", {"items": []})
        self.write_json(
            self.run_dir / "05_asset_images" / "asset_images_manifest.json",
            {
                "source_run": self.run_dir.name,
                "characters": [],
                "scenes": [],
                "props": [],
            },
        )

        start_result = self.service.start_or_resume(run_dir=str(self.run_dir))

        self.assertEqual(start_result["status"], "ok")
        reviews = self.service.list_reviews(self.run_dir)["reviews"]
        self.assertEqual(reviews["upstream"]["status"], "approved")
        self.assertEqual(reviews["asset_images"]["status"], "approved")
        self.assertEqual(reviews["storyboard"]["status"], "pending")

        with mock.patch("app.workflow_service.generate_storyboard", side_effect=self.fake_generate_storyboard):
            result = self.service.run_stage("storyboard", run_dir=self.run_dir)

        self.assertEqual(result["status"], "ok")
        storyboard_review = self.service.get_review(self.run_dir, "storyboard")["review"]
        self.assertEqual(storyboard_review["status"], "pending")


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


class WorkflowVideoPayloadTests(unittest.TestCase):
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

    def test_video_payload_includes_shot_videos_and_final_video(self) -> None:
        service = WorkflowService(output_root=PROJECT_ROOT / "runs", env_file=None)

        payload = service.build_video_payload(PROJECT_ROOT / "runs" / "run14")

        self.assertEqual(payload["summary"]["total_shots"], 7)
        self.assertEqual(payload["summary"]["succeeded_shots"], 7)
        self.assertTrue(payload["summary"]["has_final_video"])
        self.assertTrue(payload["final_video"]["preview_url"])
        self.assertEqual(payload["final_video"]["shot_count"], 7)
        shot_001 = next(item for item in payload["shot_videos"] if item["shot_id"] == "shot_001")
        self.assertEqual(shot_001["status"], "succeeded")
        self.assertTrue(shot_001["preview_url"])
        self.assertTrue(shot_001["included_in_final"])


class WorkflowStagePreviewTests(unittest.TestCase):
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

    def test_inspect_run_enriches_stage_cards_with_preview_text(self) -> None:
        service = WorkflowService(output_root=PROJECT_ROOT / "runs", env_file=None)

        payload = service.inspect_run(PROJECT_ROOT / "runs" / "run10")["run_state"]
        asset_stage = payload["stages"]["asset_extraction"]
        prompt_stage = payload["stages"]["asset_prompts"]
        storyboard_stage = payload["stages"]["storyboard"]

        self.assertEqual(asset_stage["preview_headline"], "角色 4 / 场景 1 / 道具 1")
        self.assertIn("萧炎", asset_stage["preview_text"])
        self.assertEqual(prompt_stage["preview_headline"], "characters prompts · 4 items")
        self.assertIn("萧炎", prompt_stage["preview_text"])
        self.assertEqual(storyboard_stage["preview_headline"], "正式分镜 6 条")
        self.assertIn("shot_001", storyboard_stage["preview_text"])

    def test_inspect_run_exposes_route_decision_summary(self) -> None:
        service = WorkflowService(output_root=PROJECT_ROOT / "runs", env_file=None)

        payload = service.inspect_run(PROJECT_ROOT / "runs" / "run17")["route_decision"]

        self.assertTrue(payload["available"])
        self.assertEqual(payload["source_kind"], "full_script")
        self.assertEqual(payload["chosen_path"], "compress_then_extract")
        self.assertEqual(payload["project_target"]["target_shot_count"], 6)
        self.assertIn("压缩适配6个10秒镜头", payload["reasoning_summary"])
        self.assertEqual(payload["operator_hint"], "未指定漫剧美术风格")


class WorkflowTaskRunnerTests(unittest.TestCase):
    def test_launch_run_returns_background_task_before_mainline_finishes(self) -> None:
        fake_run_root = Path(tempfile.mkdtemp(prefix="task-runner-smoke-"))
        fake_run_dir = fake_run_root / "run99"
        mainline_started = mock.Mock()

        service = mock.Mock()
        service.load_source_script_name.return_value = "test-script"

        def run_mainline(**kwargs):
            progress_callback = kwargs["progress_callback"]
            fake_run_dir.mkdir(parents=True, exist_ok=True)
            progress_callback(
                {
                    "message": "正在接收并保存原始输入。",
                    "step": "输入接收",
                    "stage": "upstream",
                    "run_dir": str(fake_run_dir),
                }
            )
            mainline_started()
            time.sleep(0.1)
            return {"status": "ok", "run_dir": str(fake_run_dir), "stage": "mainline_workflow_completed"}

        service.run_mainline.side_effect = run_mainline
        runner = WorkflowTaskRunner(service)

        task = runner.launch_run(source_text="hello world", source_script_name="demo", execution_mode="mainline")

        self.assertEqual(task["action"], "run_mainline")
        self.assertIn(task["status"], {"queued", "running"})
        self.assertEqual(task["progress_step"], "输入接收")
        self.assertEqual(task["run_id"], "")

        deadline = time.time() + 2.0
        latest = runner.get_task(task["task_id"])
        while latest is not None and latest["status"] in {"queued", "running"} and time.time() < deadline:
            time.sleep(0.02)
            latest = runner.get_task(task["task_id"])

        self.assertIsNotNone(latest)
        self.assertEqual(mainline_started.call_count, 1)
        assert latest is not None
        self.assertEqual(latest["status"], "succeeded")
        self.assertEqual(latest["run_id"], "run99")
        self.assertEqual(latest["progress_message"], "正在接收并保存原始输入。")


class OperatorConsoleHtmlTests(unittest.TestCase):
    def test_console_html_uses_active_task_workspace_and_light_hint_copy(self) -> None:
        html = build_console_html()

        self.assertIn("当前任务", html)
        self.assertIn("提示：", html)
        self.assertNotIn("<strong>Risks</strong>", html)
        self.assertNotIn("<strong>Missing Critical Info</strong>", html)
        self.assertNotIn("<h2>Tasks</h2>", html)
        self.assertNotIn("<h2>Artifacts</h2>", html)
        self.assertIn("window.scrollTo({top: Math.min(scrollY, maxScroll), behavior: 'auto'})", html)


if __name__ == "__main__":
    unittest.main()
