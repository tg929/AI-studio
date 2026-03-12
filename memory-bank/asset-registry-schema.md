# Asset Registry Schema

Last updated: 2026-03-12

## Why This Schema Exists

The reference project `BigBanana-AI-Director-main-2` uses a lightweight structure extraction schema with:

- `title`
- `genre`
- `logline`
- `characters`
- `scenes`
- `props`
- `storyParagraphs`

Reference: [scriptService.ts](/Users/tiangai/研究生/2工作/禹娲传媒/AI%20studio/BigBanana-AI-Director-main-2/services/ai/scriptService.ts#L521)

That structure is a good base, but it is not enough for this project because our later stages require:

- labeled asset image generation
- stable asset identity across many shots
- per-shot stitched asset boards
- stronger consistency control for character, scene, and prop generation

This project therefore uses a stricter and richer schema.

## Design Principles

1. Keep stable asset IDs across the whole workflow.
2. Extract only what is explicit or strongly implied by the script.
3. Do not generate image prompts in this stage.
4. Preserve enough detail to support later visual generation and storyboard planning.
5. Keep the output purely JSON and machine-friendly.

## Final Schema

```json
{
  "schema_version": "1.0",
  "source_script_name": "string",
  "title": "string",
  "genre": "string",
  "logline": "string",
  "story_meta": {
    "era": "string",
    "world_setting": "string",
    "tone": "string",
    "core_conflict": "string"
  },
  "characters": [
    {
      "id": "char_001",
      "name": "string",
      "aliases": ["string"],
      "role_type": "main|supporting|minor",
      "gender": "string",
      "age": "string",
      "occupation_identity": "string",
      "personality_traits": ["string"],
      "appearance_summary": "string",
      "costume_summary": "string",
      "identity_markers": ["string"],
      "must_keep_features": ["string"],
      "relationship_targets": [
        {
          "character_id": "char_002",
          "relation": "string",
          "description": "string"
        }
      ],
      "signature_prop_ids": ["prop_001"],
      "default_scene_ids": ["scene_001"],
      "first_appearance_segment_id": "seg_001"
    }
  ],
  "scenes": [
    {
      "id": "scene_001",
      "name": "string",
      "location": "string",
      "scene_type": "interior|exterior|mixed|unknown",
      "time_of_day": "string",
      "weather": "string",
      "atmosphere": "string",
      "environment_summary": "string",
      "key_visual_elements": ["string"],
      "must_keep_features": ["string"],
      "default_character_ids": ["char_001"],
      "default_prop_ids": ["prop_001"],
      "first_appearance_segment_id": "seg_001"
    }
  ],
  "props": [
    {
      "id": "prop_001",
      "name": "string",
      "aliases": ["string"],
      "category": "weapon|document|food_drink|vehicle|ornament|device|daily_item|other",
      "owner_character_ids": ["char_001"],
      "default_scene_ids": ["scene_001"],
      "significance": "string",
      "visual_summary": "string",
      "material_texture": "string",
      "condition_state": "string",
      "must_keep_features": ["string"],
      "first_appearance_segment_id": "seg_001"
    }
  ],
  "story_segments": [
    {
      "id": "seg_001",
      "order": 1,
      "summary": "string",
      "text": "string",
      "scene_ids": ["scene_001"],
      "character_ids": ["char_001"],
      "prop_ids": ["prop_001"]
    }
  ],
  "consistency_notes": ["string"],
  "ambiguities": [
    {
      "type": "string",
      "target_id": "string",
      "note": "string"
    }
  ]
}
```

## Field Rationale

### Top-level narrative fields

- `schema_version`
  Allows future schema evolution without breaking downstream code.

- `source_script_name`
  Keeps the source traceable when multiple runs exist.

- `title`, `genre`, `logline`
  Directly borrowed from the reference project's extraction layer because they are useful for style bible generation and general project context.

- `story_meta`
  This is a project-specific extension.
  It gives later stages better grounding for art direction and storyboard tone.

### Character fields

- `aliases`
  Needed because scripts often reference the same character with short names, titles, or kinship labels.

- `role_type`
  Helps later decide generation priority and shot importance.

- `occupation_identity`
  Better than just "role" for later image prompt generation.

- `personality_traits`
  Structured list is easier to reuse than one long paragraph.

- `appearance_summary`
  Records only script-grounded visible information.

- `costume_summary`
  Important for image consistency and video continuity.

- `identity_markers`
  Short explicit markers like scars, beard, robe color, body build, hairstyle.

- `must_keep_features`
  Non-negotiable appearance features for later image/video consistency.

- `relationship_targets`
  Needed because the user's asset format and later shot logic may rely on interpersonal relationships.

- `signature_prop_ids`
  Important for linking recurring character props.

- `default_scene_ids`
  Useful shorthand for likely recurring environments.

### Scene fields

- `scene_type`
  Normalized field for later layout logic and prompt routing.

- `time_of_day`, `weather`, `atmosphere`
  The reference project already uses similar structure; we keep and normalize it.

- `environment_summary`
  Script-grounded scene description for later scene asset generation.

- `key_visual_elements`
  Extracts landmark objects or recurring environmental anchors.

- `must_keep_features`
  Critical for keeping scene assets visually stable across later use.

### Prop fields

- `category`
  Based on the reference project's normalized prop categories, but adapted to a more explicit enum.

- `significance`
  Captures narrative importance, not just appearance.

- `visual_summary`, `material_texture`, `condition_state`
  These fields matter for prop image generation and continuity.

- `must_keep_features`
  Same purpose as for character and scene assets.

### Story segment fields

The reference project uses `storyParagraphs` linked to scenes.
This project upgrades that into `story_segments` with:

- stable `seg_*` IDs
- `summary`
- original `text`
- direct links to scenes, characters, and props

This makes later storyboard generation and debugging much easier.

### Consistency and ambiguity fields

- `consistency_notes`
  Global reminders that may affect all later visual stages.

- `ambiguities`
  Records unresolved script ambiguity instead of hallucinating certainty.

## Extraction Rules

The model must follow these rules when producing `asset_registry.json`:

1. Do not invent detailed appearance if the script does not provide it.
2. Do not invent relationships unless they are explicit or strongly implied.
3. Merge duplicate assets instead of outputting near-duplicates.
4. Use arrays instead of comma-joined strings where list structure matters.
5. If unknown, use `""` or `[]`, not fabricated content.
6. IDs must be stable and normalized:
   - `char_001`
   - `scene_001`
   - `prop_001`
   - `seg_001`

## Why This Is Final for V1

This schema is intentionally strong enough to support:

- style bible generation
- asset image prompt generation
- labeled asset image production
- storyboard generation with asset references
- shot reference board stitching
- video generation with stable asset reuse

Without adding image-model prompt text prematurely.
