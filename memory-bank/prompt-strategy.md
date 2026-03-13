# Prompt Strategy

## Reference Sources

Primary references reviewed so far:

- Volcano Engine docs
- `BigBanana-AI-Director-main-2`
- `EnzeD/vibe-coding`

## Important Reference Findings from `BigBanana-AI-Director-main-2`

Useful ideas we should adapt:

- Generate a global art direction/style bible before downstream visual prompts.
- Force JSON output for text-model planning steps.
- Reference assets by stable IDs.
- Keep prompt templates centralized and editable.
- Add hard video guardrails so the reference image is used for consistency and not reproduced as a collage.

Ideas we should not copy directly:

- TS/React implementation details
- The "no text in generated board image" rule
- Any assumption that production implementation should mirror the reference repo structure

## Four Major Prompt Families for This Project

### 1. Asset Extraction Prompt

Purpose:

- Extract structured characters, scenes, props, and script-to-scene mapping.

Required behavior:

- Output valid JSON only
- No creative expansion beyond the script unless explicitly needed
- Deduplicate recurring assets

### 2. Asset Image Prompt

Purpose:

- Convert structured assets into image-generation prompts for labeled reference assets.

Required behavior:

- Follow one shared visual style
- Produce prompts separately for character, scene, and prop assets
- Respect the project's labeled asset format

### 3. Storyboard Prompt

Purpose:

- Convert the script into 10-second storyboard shots.

Required behavior:

- Output valid JSON only
- Each shot must reference existing asset IDs
- Each shot has one prompt suitable for video generation

### 4. Video Prompt

Purpose:

- Convert a shot definition into the final video-model prompt.

Required behavior:

- Use one stitched shot board image plus one shot prompt
- Preserve character/scene/prop consistency
- Prevent the model from turning the board layout itself into the visible video format

## Current Project-Specific Prompt Constraints

- Asset images are labeled.
- Shot duration is fixed at 10 seconds.
- The stitched board contains only the assets used in that shot.
- Inter-stage text outputs should be JSON-first.
- The production runtime is Python + AgentKit.

## Asset Image Prompt Lessons

- Avoid headline-style imperative phrases such as `Create ONE ...` in image prompts. The image model may copy them into the canvas as visible text.
- Keep the text-model asset prompt focused on subject identity and consistency anchors. Do not let it generate page-template language.
- Put layout control in the image-stage prompt, but describe composition as visual arrangement, not as printable editorial design.
- For scene assets, "empty environment only" must be repeated very explicitly, otherwise the model tends to add background crowds.
- For props, suppress readable inscriptions and symbolic marks aggressively; object names can leak into engraved surface text if the wording is too literal.
- Avoid overly explicit forbidden tokens like `QR code`, `barcode`, and `watermark` when possible; some image-model runs literalize those terms into template-like decorations.
- For underage characters, avoid exact numeric age wording in image prompts; broader visual descriptors are safer and produced more stable runs.
- The Volcano image client currently does not expose a dedicated `negative_prompt` field in the SDK wrapper we are using, so render-prompt wording is doing almost all the suppression work.
- Disabling image-side `optimize_prompt` is beneficial here because service-side prompt rewriting weakens carefully tuned anti-template constraints.
- Current target layout:
  - character: left close-up portrait + right three full-body views (front / side / back)
  - scene: left master view + right three same-location auxiliary views
  - prop: left hero view + right three full object views (front / side / back)
- Current empirical status after `runs/run9`:
  - character prompts respond well to English prompt tightening
  - prop prompts still drift into mannequin/torso-display imagery
  - scene prompts still drift into presentation-board composition and human-figure leakage
