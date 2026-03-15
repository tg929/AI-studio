from veadk import Agent

from .workflow_tools import (
    inspect_current_run,
    run_asset_extraction_stage,
    run_asset_image_stage,
    run_asset_prompt_stage,
    run_board_publish_stage,
    run_final_video_stage,
    run_mainline_workflow,
    run_shot_reference_board_stage,
    run_shot_video_stage,
    run_storyboard_seed_stage,
    run_storyboard_stage,
    run_style_bible_stage,
    run_video_job_stage,
    start_or_resume_workflow,
)


root_agent = Agent(
    name="ai_studio_flow",
    description="A full script-to-video workflow agent for the AI Studio project.",
    instruction=(
        "You are the workflow operator for the AI Studio short-drama video pipeline. "
        "Your primary job is to run the project's mainline workflow end to end inside VeADK web. "
        "For normal user requests, prefer `run_mainline_workflow`. "
        "Use `start_or_resume_workflow` and the stage-specific tools only when the user explicitly asks to resume, rerun, or debug a specific stage. "
        "After every tool call, explain which run directory and key artifact paths were produced."
    ),
    model_name="doubao-seed-2-0-pro-260215",
    tools=[
        run_mainline_workflow,
        inspect_current_run,
        start_or_resume_workflow,
        run_asset_extraction_stage,
        run_storyboard_seed_stage,
        run_style_bible_stage,
        run_asset_prompt_stage,
        run_asset_image_stage,
        run_storyboard_stage,
        run_shot_reference_board_stage,
        run_board_publish_stage,
        run_video_job_stage,
        run_shot_video_stage,
        run_final_video_stage,
    ],
)
