"""Deterministic render-prompt builders for labeled asset images."""

from __future__ import annotations

from schemas.asset_prompts import CharacterAssetPrompt, PropAssetPrompt, SceneAssetPrompt


def build_character_render_prompt(item: CharacterAssetPrompt) -> str:
    return (
        "Create one single horizontal 16:9 character reference sheet on a clean white or very pale warm gray background. "
        "The desired look is refined Chinese fantasy anime and polished xuanhuan manhua concept-art quality: elegant semi-realistic face rendering, crisp clean linework, smooth luminous shading, restrained cool color grading, delicate fabric sheen, and graceful high-fidelity costume detail. "
        "This must feel like a professional production character sheet, not a poster, not a magazine page, not a UI mockup, and not a catalog template. "
        "Left side: one large close-up half-body portrait of the same character, occupying about forty-five percent of the canvas width and reading as the dominant visual focus. "
        "Right side: exactly three full standing body views of the same character, arranged left to right as front, pure side, and back. "
        "The three standing views must be large and readable, not tiny. Each standing figure should fill most of the height of its own column from head to shoes, with both feet fully visible and the full silhouette clearly readable. "
        "No fourth figure, no duplicate angle, no extra portrait, no inset, no floating callout, and no cropped body. "
        "All four depictions must be unmistakably the same person with the same face, same hairline, same hairstyle, same hair length, same costume structure, same garment pattern, same shoes, same accessories, same body proportions, and same identity details. "
        "If the subject description does not explicitly include facial hair, do not invent a beard or mustache. If the subject description includes facial hair, it must remain visible and consistent in every applicable view. "
        "Use natural neutral standing posture for the three full-body views. Keep the right-side views elegant and clean, with enough scale to show the full outfit clearly rather than miniature doll-sized figures. "
        "Keep the canvas extremely clean: no text, no letters, no Chinese characters, no numbers, no QR code, no logo, no watermark, no page header, no footer, no corner mark, no color strip, no sidebar, no interface widget, no title block, no stamp, and no black outer frame. "
        "Only very faint thin guide lines are allowed between areas. No extra characters, no props, no furniture, no studio equipment, and no clutter. "
        f"Character subject details: {item.prompt}."
    )


def build_scene_render_prompt(item: SceneAssetPrompt) -> str:
    return (
        "Create one single horizontal 16:9 environment reference sheet on a clean white or very pale warm gray background. "
        "The visual style must match refined Chinese fantasy anime and polished xuanhuan manhua concept art: clear spatial perspective, elegant architectural drawing discipline, crisp linework, soft luminous shading, restrained cool palette, and clean production-design quality. "
        "This is an environment reference sheet, not a poster, not a brochure, not an architectural blueprint page, and not a UI layout. "
        "Left side: one large master view of the same location, occupying about forty-five percent of the canvas width and serving as the dominant scene overview. "
        "Right side: exactly three alternate full-location views of the exact same place, arranged vertically or in a clean stacked-right layout, each clearly showing a different viewing direction across the same space. "
        "The three alternate views must remain readable full-environment views rather than tiny inserts or detail crops. Each one should preserve the same architecture, landmark placement, entrance logic, ground pattern, depth layout, material treatment, and lighting logic as the large master view. "
        "This is a strictly empty environment sheet. No people, no crowd, no attendants, no silhouettes, no distant figures, no ghosted character traces, no statues shaped like humans, and no living beings anywhere. "
        "Keep the canvas extremely clean: no text, no letters, no Chinese characters, no numbers, no QR code, no logo, no watermark, no page header, no footer, no corner mark, no color strip, no sidebar, no title block, no annotation graphics, and no black outer frame. "
        "Only very faint thin guide lines are allowed if needed. No furniture catalog look, no infographic look, no UI chrome, and no decorative presentation-board furniture. "
        f"Scene subject details: {item.prompt}."
    )


def build_prop_render_prompt(item: PropAssetPrompt) -> str:
    return (
        "Create one single horizontal 16:9 prop reference sheet on a clean white or very pale warm gray background. "
        "The visual style must match refined Chinese fantasy anime and polished xuanhuan manhua concept art: crisp silhouette control, clean linework, soft luminous shading, restrained cool palette, believable material rendering, and high readability of shape. "
        "This is a prop reference sheet, not a poster, not a catalog page, not an engineering diagram, and not a UI layout. "
        "Left side: one large hero depiction of the exact same prop, occupying about forty-five percent of the canvas width. "
        "Right side: exactly three full-object views of the exact same prop, arranged from left to right as front, pure side, and back, or if true front-back is ambiguous, three clearly different full-object angles of the same single item. "
        "The three right-side views must be large and readable, not tiny. Each view should fill most of the height of its own column with the complete object visible from top to bottom. "
        "The prop is strictly an inanimate object. No humanoid silhouette, no mannequin, no torso stand, no holder figure, no hands, no wearer, no body parts, no clothing sheet logic, and no substitute object class. "
        "All four depictions must preserve the same silhouette, massing, volume, construction, material, surface finish, wear pattern, and identity-defining details. "
        "Any surface motif must remain abstract and unreadable. No letters, no Chinese characters, no numbers, no runes, no inscription, no engraved readable text, and no nameplate. "
        "Keep the canvas extremely clean: no text, no QR code, no logo, no watermark, no page header, no footer, no corner mark, no color strip, no sidebar, no title block, no annotation graphics, and no black outer frame. "
        "Only very faint thin guide lines are allowed if needed. Do not drift into a mannequin board, costume board, industrial sheet, or product brochure. "
        f"{item.isolation_rules}. "
        f"Prop subject details: {item.prompt}."
    )
