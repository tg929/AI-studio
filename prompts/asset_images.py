"""Deterministic render-prompt builders for labeled asset images."""

from __future__ import annotations

from schemas.asset_prompts import CharacterAssetPrompt, PropAssetPrompt, SceneAssetPrompt


def _compact_text(value: str) -> str:
    return " ".join(str(value).split()).strip()


def _project_style_block(*, visual_style: str, consistency_anchors: str) -> str:
    return (
        f"项目统一美术风格：{_compact_text(visual_style)}。"
        f"统一一致性锚点：{_compact_text(consistency_anchors)}。"
        "先锁定主体与世界观，再执行设定板版式。"
    )


def build_character_render_prompt(
    item: CharacterAssetPrompt,
    *,
    visual_style: str,
    consistency_anchors: str,
) -> str:
    return (
        "请生成一张高质量横向白底人物设定组合图。"
        f"人物主体设定：{_compact_text(item.prompt)}。"
        f"{_project_style_block(visual_style=visual_style, consistency_anchors=consistency_anchors)}"
        "目标是稳定的人物一致性参考图，背景干净留白，主体清楚可读。"
        "版式固定：左侧一张大幅近景半身主视觉，右侧三张足够大的完整全身视图，从左到右固定为正面、纯侧面、背面。"
        "右侧三张不能是缩略图，必须头到脚完整入画，鞋履完整可见。"
        "四个视图必须是完全同一人物，脸型、五官、肤色、发际线、发长、发型、服装结构、服饰花纹、鞋履、配饰、身材比例、身份特征全部保持一致。"
        "必须严格服从人物主体设定里的性别、年龄段、气质、服装类别、服装主色、服装细节和发型长度，不允许擅自改成其他人物类型。"
        "右侧三张全身图站姿自然端正，手臂自然放置，不做夸张动作，服装轮廓必须清楚稳定。"
        "背景保持纯净留白，只允许极淡分隔线。"
        "不要出现额外人物、额外道具、摄影器材、家具、杂物、可读文字、页眉页脚、页码、二维码、logo、水印、UI控件、模板装饰、黑色厚边框或脏污边缘。"
    )


def build_scene_render_prompt(
    item: SceneAssetPrompt,
    *,
    visual_style: str,
    consistency_anchors: str,
) -> str:
    return (
        "请生成一张高质量横向白底场景设定组合图。"
        f"场景主体设定：{_compact_text(item.prompt)}。"
        f"{_project_style_block(visual_style=visual_style, consistency_anchors=consistency_anchors)}"
        "目标是稳定的空场景一致性参考图，主体空间结构清楚可读。"
        "版式固定：左侧一张同一地点的大幅主全景图，右侧从上到下三张等大的辅助视角图，分别表现主轴正向视角、侧向斜视视角、从对侧回看的反向视角。"
        "右侧三张必须是完整上色渲染的场景视图，不能是局部特写、线稿、草图、平面图、俯视图、建筑蓝图或灰白草模图。"
        "四个视图必须保持同一场景的建筑布局、核心地标位置、入口方向、地面结构、材质逻辑、光照方向和空间层次完全一致。"
        "这是严格的空场景设定图，绝对不要出现人物、人群、侍从、路人、远景小人、人物剪影、角色残影、类人雕像或任何生物。"
        "背景保持纯净留白，只允许极淡分隔线。"
        "不要出现可读文字、页眉页脚、页码、二维码、logo、水印、说明框、版式装饰、UI控件、黑色厚边框、杂志页感、说明书页感或信息图模板感。"
    )


def build_prop_render_prompt(
    item: PropAssetPrompt,
    *,
    visual_style: str,
    consistency_anchors: str,
) -> str:
    return (
        "请生成一张高质量横向白底道具设定组合图。"
        f"道具主体设定：{_compact_text(item.prompt)}。"
        f"{_project_style_block(visual_style=visual_style, consistency_anchors=consistency_anchors)}"
        "目标是稳定的单一道具一致性参考图，主体轮廓和材质清楚可读。"
        "只展示单一道具本体，不要人物、手部、佩戴者或额外同类物体。"
        "版式固定：左侧一张同一道具的大幅英雄主视图，右侧从上到下三张等大的完整辅助视角图。"
        "若该道具有明确正背侧关系，则右侧三张依次为正视、纯侧视、背视；若前后不明显，也必须是同一件道具的三个不同完整角度。"
        "右侧三张必须够大、够清楚、可直接看清完整轮廓和结构，不能像缩略图，每张都必须把整件道具完整画出来。"
        "这件道具必须始终是无生命物体，绝对不能出现人形、模特支架、人体轮廓、手持展示、佩戴展示、服装展示、角色站姿、人体局部或替代物体。"
        "四个视图必须保持同一件道具的轮廓、体积比例、结构、材质、表面纹理、磨损和识别性细节完全一致。"
        "表面纹样只能是抽象不可读纹样，不允许出现汉字、英文字母、数字、符文、铭文或刻字。"
        "背景保持纯净留白，只允许极淡分隔线。"
        "不要漂移成角色设定板、商品广告页、工业零件图册，也不要出现可读文字、二维码、logo、水印、页眉页脚、页码、说明框、模板装饰、UI控件、黑色厚边框、假占位圆圈或线框示意图。"
    )
