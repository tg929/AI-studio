# Implementation Plan

This plan follows the vibe-coding principle: small steps, explicit outputs, and a validation method for each step.

## Step 0: Environment and Connectivity

Status: done

Goal:

- Verify local Python and AgentKit setup.
- Verify text, image, and video model connectivity.

Validation:

- `smoke_test_models.py` succeeds for text, image, and video.

## Step 1: Asset Schema and Asset Extraction Prompt

Status: next

Goal:

- Finalize `asset_registry.json` schema.
- Finalize the asset extraction system prompt.

Outputs:

- Asset schema document
- Prompt draft

Validation:

- The schema can represent the full default script.
- The prompt can produce valid JSON matching the schema.

## Step 2: Implement Script Preprocessing and Asset Extraction Node

Goal:

- Read the script file.
- Normalize script text.
- Call the text model to generate `asset_registry.json`.

Outputs:

- `script_clean.json`
- `asset_registry.json`

Validation:

- JSON is valid.
- Characters, scenes, and props are extracted without obvious duplication.

## Step 3: Art Direction and Asset Prompt Generation

Goal:

- Generate a project-level style bible.
- Generate prompts for character, scene, and prop asset images.

Outputs:

- `style_bible.json`
- `asset_prompts.json`

Validation:

- Prompt outputs are complete for all assets.
- Style directions are globally coherent.

## Step 4: Asset Image Generation

Goal:

- Generate labeled asset images for characters, scenes, and props.

Outputs:

- `asset_images/`
- `asset_images_manifest.json`

Validation:

- Every asset has a usable labeled image.
- Naming and labeling are consistent.

## Step 5: Storyboard Generation

Goal:

- Generate `storyboard.json` from the original script.
- Each shot must be 10 seconds.
- Each shot must reference existing asset IDs.

Outputs:

- `storyboard.json`

Validation:

- Shot JSON is valid.
- No missing asset references.
- Shot duration is locked to 10 seconds.

## Step 6: Shot Reference Board Generation

Goal:

- Build one stitched asset board image for each shot.

Outputs:

- `shot_reference_boards/`
- `shot_reference_manifest.json`

Validation:

- Exactly one stitched board per shot.
- Only assets used in that shot appear on the board.

## Step 7: Shot Video Generation

Goal:

- Generate one video per shot using `shot prompt + stitched board image`.

Outputs:

- `shot_videos/`
- `video_jobs.json`

Validation:

- One video per shot is generated successfully.
- Output duration is close to 10 seconds.

## Step 8: Final Video Concatenation

Goal:

- Concatenate all shot videos into a final video.

Outputs:

- `final/final_video.mp4`

Validation:

- Final video is playable.
- Shot order is correct.
- No missing segments.
