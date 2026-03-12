# Open Questions

These questions are still unresolved and should be reviewed before major implementation.

## Schema

- How much biography detail should character assets carry in V1?
- Should scenes be pure environment assets, or can they include implied human traces?

## Asset Images

- What exact labeled layout should character, scene, and prop assets follow?
- How dense should the labels be in V1?
- Should we support multiple variations per character asset in V1 or later?

## Storyboard

- What is the final field set for `storyboard.json`?
- Do shots need explicit emotion, camera language, and pacing fields in V1?
- Should shot prompts be strictly normalized or allow stylistic variation?

## Video

- Final target resolution for V1: keep at 720p or move higher?
- Final FPS target for V1?
- What is the exact prompt guardrail wording to stop the video model from reproducing the board layout?

## Human Review

- Should users approve asset extraction before image generation?
- Should users approve asset images before storyboard generation?
- Should users approve storyboard before video generation?

## Production Outputs

- Exact directory layout for run outputs
- Naming conventions for asset, board, shot, and final video files
