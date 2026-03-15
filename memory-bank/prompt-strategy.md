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

## Current Prompt Families for This Project

### 1. Intake Router Prompt

Purpose:

- Decide which upstream path is most suitable for stable asset extraction under the current project spec.

Required behavior:

- Output valid JSON only
- Judge user goal, source form, material state, and route choice separately
- Prefer the minimum necessary transform before asset extraction

### 2. Intent Understanding Prompt

Purpose:

- Convert keywords or a short brief into a structured `intent_packet.json`.

Required behavior:

- Output valid JSON only
- Preserve the user's stated intent and separate it from assumptions
- Lock the short-form target spec before story expansion

### 3. Story Blueprint Prompt

Purpose:

- Convert `intent_packet.json` into a constrained `story_blueprint.json`.

Required behavior:

- Output valid JSON only
- Keep character / scene / prop counts controlled
- Produce a beat sheet that is asset-friendly and storyboard-friendly

### 4. Script Generation Prompt

Purpose:

- Convert `intent_packet.json + story_blueprint.json + intake_router.json` into an asset-ready script candidate.

Required behavior:

- Output plain script text only
- Stay visually concrete enough for asset extraction
- Preserve the blueprint's role / scene / prop constraints

### 5. Script Quality Prompt

Purpose:

- Review the generated script before it enters the expensive downstream stages.

Required behavior:

- Output valid JSON only
- Check whether the script stays within the short-form production envelope
- Surface repair instructions instead of silently letting weak scripts continue

### 6. Asset Readiness Prompt

Purpose:

- Judge whether the current script candidate is stable enough for asset extraction.

Required behavior:

- Output valid JSON only
- Score extraction-critical dimensions rather than literary quality
- Gate downstream asset extraction when readiness is too low

### 7. Asset Extraction Prompt

Purpose:

- Extract structured characters, scenes, props, and script-to-scene mapping.

Required behavior:

- Output valid JSON only
- No creative expansion beyond the script unless explicitly needed
- Deduplicate recurring assets

### 8. Asset Image Prompt

Purpose:

- Convert structured assets into image-generation prompts for labeled reference assets.

Required behavior:

- Follow one shared visual style
- Produce prompts separately for character, scene, and prop assets
- Respect the project's labeled asset format

### 9. Storyboard Prompt

Purpose:

- Convert the script into 10-second storyboard shots.

Required behavior:

- Output valid JSON only
- Each shot must reference existing asset IDs
- Each shot has one prompt suitable for video generation

### 10. Video Prompt

Purpose:

- Convert a shot definition into the final video-model prompt.

Required behavior:

- Use one stitched shot board image plus one shot prompt
- Preserve character/scene/prop consistency
- Prevent the model from turning the board layout itself into the visible video format
- If the stitched first frame cannot transition cleanly into the cinematic scene, prefer a very brief black-frame bridge over leaving the board visible

## Current Project-Specific Prompt Constraints

- The short-intent upstream path should converge to a roughly `60s`, `6-shot` micro-script before entering asset extraction.
- Upstream route selection should be explicit JSON, not hidden inside prompt-only branching.
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
- English-first prompt tuning improved cleanliness in `runs/run9`, but also pushed the model toward flatter generic template aesthetics. The preferred direction is now:
  - keep the cleaner canvas behavior from later runs
  - restore the older Chinese “设定组合图” style wording used in `runs/20260312-220137`
  - keep the prompt shorter and more subject-first instead of stacking too many prohibitions
- Current empirical status after the latest `run10` image-only iterations:
  - character sheets benefit from Chinese subject-first layout wording and a shorter composition spec
  - character identity consistency still depends heavily on the upstream asset prompt carrying explicit clothing color, hairstyle, and role markers
  - scene sheets need explicit “fully rendered alternate angles” wording, not “视图” alone, otherwise they drift toward diagram / plate layouts
  - prop sheets need explicit inert-object locking plus repeated category anchoring, otherwise they drift toward human-shaped boards or unrelated object classes
