const AGENT_DEFS = {
  intent: {
    id: "intent",
    name: "意图识别 Agent",
    role: "理解输入，并生成可进入下游资产链路的标准剧本。",
    model: "文本大模型",
  },
  assets: {
    id: "assets",
    name: "资产提取 Agent",
    role: "提取人物、场景、道具，并生成一致的参考资产。",
    model: "文本大模型 + 图像大模型",
  },
  storyboard: {
    id: "storyboard",
    name: "分镜生成 Agent",
    role: "把剧本和资产推进成分镜、动态片段与最终成片。",
    model: "文本大模型 + 视频大模型",
  },
};

const STATUS_META = {
  pending: { label: "未到达", state: "pending" },
  idle: { label: "等待中", state: "pending" },
  running: { label: "运行中", state: "running" },
  review: { label: "等待确认", state: "review" },
  blocked: { label: "阻塞", state: "blocked" },
  done: { label: "已完成", state: "done" },
};

const SNAPSHOT_ORDER = [
  "upstream_review",
  "asset_review",
  "storyboard_review",
  "board_publish_blocked",
  "final_done",
];

const PROJECTS = [
  {
    id: "run23",
    title: "0324-1",
    runId: "run23",
    episodeTitle: "破命",
    status: "done",
    cover: "assets/run23/boards/shot_002.png",
    description: "少年握紧旧剑，誓要斩断宿命的枷锁。",
    tagline: "从一句创意出发，逐步推进到完整成片",
    inputMode: "brief",
    route: "expand_then_extract",
    runtime: "60 秒",
    shots: "6 镜头",
    checkpoints: "3 次关键确认",
  },
  {
    id: "run24",
    title: "0324-2",
    runId: "run24",
    episodeTitle: "现代沙雕场景测试",
    status: "blocked",
    cover: "assets/run23/boards/shot_001.png",
    description: "现代沙雕场景测试案例，用于补充展示另一类内容风格。",
    tagline: "偏现代都市与夸张喜剧节奏",
    inputMode: "brief",
    route: "expand_then_extract",
    runtime: "40 秒",
    shots: "4 镜头",
    checkpoints: "3 次关键确认",
  },
  {
    id: "run_fit",
    title: "01-陨落的天才",
    runId: "run_fit",
    episodeTitle: "历史已完成案例",
    status: "done",
    cover: "assets/run23/boards/shot_003.png",
    description: "已完成的长链路案例，用来承接系列化项目展示。",
    tagline: "更长篇幅的连续制作体验",
    inputMode: "script",
    route: "direct_extract",
    runtime: "120 秒",
    shots: "12 镜头",
    checkpoints: "3 次关键确认",
  },
];

const STATIC_TEXT = {
  inputSeed: "少年握紧旧剑，誓要斩断宿命的枷锁",
  routeSummary: "输入被识别为 brief，系统选择 expand_then_extract，以得到更适合资产提取的下游剧本。",
  generatedScriptExcerpt: "高空悬浮的圆形青石板祭坛孤立在翻涌的云海之上，此刻正是黄昏将尽的时刻，厚重的墨色乌云压得极低，几乎要触到祭坛的边缘，连一丝落日的余温都透不过来，整个空间都浸在冷得刺骨的昏暗里。祭坛的青石板地面上刻着繁复的暗红色命运图腾，十五六岁的黑衣少年阿尘被半透明的墨黑色丝线捆缚在图腾正中央，视线死死落在脚边那柄父亲遗留的旧剑上……",
  scriptCleanExcerpt: "标准化输出保留了祭坛、阿尘、旧剑、祭品宿命等核心锚点，并把剧情收束为可供下游资产提取的稳定剧本版本。",
  styleBibleExcerpt: "压抑、热血、反抗向。厚涂手绘国风漫风，质感厚重硬朗，兼具东方玄幻的诡谲感与写实细腻度。整体偏冷调，高光为暖金色。",
  assetSummary: "人物 3：阿尘 / 族中长老 / 阿尘父亲；场景 2：宿命祭坛 / 阿尘旧居小院；道具 2：旧剑 / 残损“祭”字木牌。",
  boardBlockedReason: "参考板已经准备完成，但外部访问暂时失败，所以流程还不能继续往动态片段生成推进。",
  finalSummary: "最终产出了 6 段动态片段，并完成了成片拼接。页面里的成片预览、首段片段和参考板都来自同一条完整制作记录。",
};

const HOME_FLOW_STEPS = [
  {
    number: "01",
    agentId: "intent",
    title: "意图识别 Agent",
    copy: "先理解你的输入，把一句灵感、brief 或完整脚本整理成可推进的完整剧本。",
    highlight: "输出完整剧本",
    snapshot: "upstream_review",
    action: "查看剧本阶段",
  },
  {
    number: "02",
    agentId: "assets",
    title: "资产提取 Agent",
    copy: "把剧本拆成角色、场景、道具，并生成一组可复用的视觉参考资产。",
    highlight: "输出参考资产",
    snapshot: "asset_review",
    action: "查看资产阶段",
  },
  {
    number: "03",
    agentId: "storyboard",
    title: "分镜生成 Agent",
    copy: "基于剧本和资产继续往下推，形成分镜、动态片段，并最终汇成成片。",
    highlight: "输出分镜与成片",
    snapshot: "storyboard_review",
    action: "查看分镜阶段",
  },
];

const SNAPSHOT_FOCUS = {
  upstream_review: [
    "先看完整剧本是否符合你的创意方向。",
    "确认角色关系和核心场景是否已经清楚。",
    "通过后再进入资产准备，不会提前跳到后续环节。",
  ],
  asset_review: [
    "重点确认角色脸型、服装和整体气质是否稳定。",
    "确认场景与道具是否足够支撑后续分镜。",
    "通过后才会进入正式分镜阶段。",
  ],
  storyboard_review: [
    "重点看镜头拆分是否顺畅、节奏是否合理。",
    "确认参考资产是否被正确绑定到镜头里。",
    "通过后会继续推进画面拼接与片段生成。",
  ],
  board_publish_blocked: [
    "当前主要问题不是分镜本身，而是参考板外链还不可用。",
    "参考板恢复可访问后，后面的动态片段会继续推进。",
    "右侧详情会说明当前卡点和对应画面预览。",
  ],
  final_done: [
    "三位 Agent 的主链路已经全部完成。",
    "可以回看每一段动态片段与最终成片。",
    "也可以切换前面几个阶段，演示整个协作过程。",
  ],
};

const SHOTS = [
  {
    id: "shot_001",
    title: "交代核心场景，营造压抑诡谲的宿命氛围",
    board: "assets/run23/boards/shot_001.png",
  },
  {
    id: "shot_002",
    title: "展现主角当前被困处境，铺垫后续反抗动因",
    board: "assets/run23/boards/shot_002.png",
  },
  {
    id: "shot_003",
    title: "闪回交代主角成为天定祭品的过往，补全人物动机",
    board: "assets/run23/boards/shot_003.png",
  },
  {
    id: "shot_004",
    title: "现实与回忆重新咬合，情绪从死寂转向愤怒沸腾",
    board: "assets/run23/boards/shot_004.png",
  },
  {
    id: "shot_005",
    title: "立誓举剑，正式向宿命发起反抗",
    board: "assets/run23/boards/shot_005.png",
  },
  {
    id: "shot_006",
    title: "命运意志开始回应，给下一集留下强钩子",
    board: "assets/run23/boards/shot_006.png",
  },
];

const SNAPSHOTS = {
  upstream_review: {
    key: "upstream_review",
    label: "剧本待确认",
    displayState: "review",
    timestamp: "2026-03-24 08:06:18",
    headline: "完整剧本已生成，等待剧本准备确认",
    description: "意图识别 Agent 已经把输入扩写成完整剧本，并整理出可以继续向下推进的标准版本。当前先停在剧本确认，等你看完再继续。",
    defaultAgent: "intent",
    nextSnapshot: "asset_review",
    nextLabel: "通过剧本确认",
    checkpoints: {
      upstream: "review",
      assets: "pending",
      storyboard: "pending",
    },
    agents: {
      intent: {
        status: "review",
        action: "完整剧本已生成，等待剧本准备确认",
        output: "brief · expand_then_extract",
        preview: {
          type: "text",
          text: STATIC_TEXT.generatedScriptExcerpt,
        },
      },
      assets: {
        status: "idle",
        action: "等待上游剧本放行",
        output: "人物 0 / 场景 0 / 道具 0",
        preview: {
          type: "text",
          text: "资产提取 Agent 尚未接到标准剧本输入，人物、场景、道具结构化抽取还未开始。",
        },
      },
      storyboard: {
        status: "idle",
        action: "等待资产链路启动",
        output: "0 shots",
        preview: {
          type: "text",
          text: "分镜生成 Agent 还未进入工作，正式分镜、参考板和视频链路均未激活。",
        },
      },
    },
    events: [
      { time: "08:01:54", title: "系统判断完成", detail: "输入被识别为 brief，路径选择 expand_then_extract。", agent: "意图识别 Agent", status: "done" },
      { time: "08:03:26", title: "梗概骨架生成", detail: "intent_packet 与 story_blueprint 已就绪。", agent: "意图识别 Agent", status: "done" },
      { time: "08:04:57", title: "标准剧本输出", detail: "下游继续读取的标准剧本版本已经就绪。", agent: "意图识别 Agent", status: "done" },
      { time: "08:06:18", title: "等待剧本确认", detail: "完整剧本已经生成，等待继续放行。", agent: "意图识别 Agent", status: "review" },
    ],
  },
  asset_review: {
    key: "asset_review",
    label: "资产待确认",
    displayState: "review",
    timestamp: "2026-03-24 08:13:46",
    headline: "参考资产已生成，等待参考资产确认",
    description: "剧本已经放行给下游，资产提取 Agent 完成了资产抽取、风格设定和参考资产生成。现在先确认这批视觉资产是否可用。",
    defaultAgent: "assets",
    nextSnapshot: "storyboard_review",
    nextLabel: "通过资产确认",
    checkpoints: {
      upstream: "done",
      assets: "review",
      storyboard: "pending",
    },
    agents: {
      intent: {
        status: "done",
        action: "标准剧本已放行至资产链路",
        output: "标准剧本已锁定",
        preview: {
          type: "text",
          text: STATIC_TEXT.routeSummary,
        },
      },
      assets: {
        status: "review",
        action: "参考资产图已生成，等待人工筛选",
        output: "人物 3 / 场景 2 / 道具 2",
        preview: {
          type: "gallery",
          items: [
            { src: "assets/run23/characters/char_001.jpeg", title: "阿尘", meta: "角色参考图" },
            { src: "assets/run23/scenes/scene_001.jpeg", title: "宿命祭坛", meta: "场景参考图" },
            { src: "assets/run23/props/prop_001.jpeg", title: "旧剑", meta: "道具参考图" },
          ],
        },
      },
      storyboard: {
        status: "idle",
        action: "等待资产确认结束",
        output: "未开始",
        preview: {
          type: "text",
          text: "分镜生成 Agent 将在资产审核通过后接收人物、场景、道具与风格基线。",
        },
      },
    },
    events: [
      { time: "08:11:07", title: "资产结构抽取完成", detail: "人物、场景、道具已经拆分完成。", agent: "资产提取 Agent", status: "done" },
      { time: "08:12:07", title: "风格基线建立", detail: "整体视觉方向已经统一下来。", agent: "资产提取 Agent", status: "done" },
      { time: "08:13:10", title: "资产 prompt 完成", detail: "角色、场景、道具 prompt 已整理。", agent: "资产提取 Agent", status: "done" },
      { time: "08:13:46", title: "参考资产待确认", detail: "参考资产已经生成，等待继续放行。", agent: "资产提取 Agent", status: "review" },
    ],
  },
  storyboard_review: {
    key: "storyboard_review",
    label: "分镜待确认",
    displayState: "review",
    timestamp: "2026-03-24 09:36:53",
    headline: "正式分镜已生成，等待分镜确认",
    description: "资产链路已经结束，分镜生成 Agent 刚完成正式分镜。当前先确认镜头拆分与画面目标，再继续往片段生成推进。",
    defaultAgent: "storyboard",
    nextSnapshot: "board_publish_blocked",
    nextLabel: "通过分镜确认",
    checkpoints: {
      upstream: "done",
      assets: "done",
      storyboard: "review",
    },
    agents: {
      intent: {
        status: "done",
        action: "剧本输入已冻结",
        output: "brief -> expand_then_extract",
        preview: {
          type: "text",
          text: STATIC_TEXT.scriptCleanExcerpt,
        },
      },
      assets: {
        status: "done",
        action: "参考资产已建立",
        output: "人物 3 / 场景 2 / 道具 2",
        preview: {
          type: "gallery",
          items: [
            { src: "assets/run23/characters/char_001.jpeg", title: "阿尘", meta: "主角设定" },
            { src: "assets/run23/characters/char_002.jpeg", title: "族中长老", meta: "配角设定" },
            { src: "assets/run23/scenes/scene_002.jpeg", title: "旧居小院", meta: "回忆场景" },
          ],
        },
      },
      storyboard: {
        status: "review",
        action: "正式分镜已生成，等待分镜确认",
        output: "正式分镜 6 条",
        preview: {
          type: "board",
          src: "assets/run23/boards/shot_002.png",
          title: "参考板预览",
          meta: "分镜确认前先看绑定资产与镜头目标是否一致",
        },
      },
    },
    events: [
      { time: "09:35:30", title: "资产确认通过", detail: "故事正式进入分镜阶段。", agent: "资产提取 Agent", status: "done" },
      { time: "09:35:33", title: "开始正式分镜", detail: "分镜生成 Agent 接管剧本与资产。", agent: "分镜生成 Agent", status: "running" },
      { time: "09:36:53", title: "正式分镜生成完成", detail: "镜头拆分和镜头目标已经整理完成。", agent: "分镜生成 Agent", status: "done" },
      { time: "09:36:53", title: "等待分镜确认", detail: "此时先确认镜头设计是否合理。", agent: "分镜生成 Agent", status: "review" },
    ],
  },
  board_publish_blocked: {
    key: "board_publish_blocked",
    label: "发布受阻",
    displayState: "blocked",
    timestamp: "2026-03-24 09:39:14",
    headline: "参考板发布链路阻塞，视频生成暂未开始",
    description: "分镜已经通过，参考板也已拼接完成，但外部访问还没有恢复，所以后面的动态片段暂时没有启动。",
    defaultAgent: "storyboard",
    nextSnapshot: "final_done",
    nextLabel: "继续执行到成片完成",
    checkpoints: {
      upstream: "done",
      assets: "done",
      storyboard: "done",
    },
    agents: {
      intent: {
        status: "done",
        action: "剧本链路已稳定",
        output: "剧本版本已稳定",
        preview: {
          type: "text",
          text: STATIC_TEXT.routeSummary,
        },
      },
      assets: {
        status: "done",
        action: "资产链路已完成",
        output: STATIC_TEXT.assetSummary,
        preview: {
          type: "gallery",
          items: [
            { src: "assets/run23/characters/char_001.jpeg", title: "阿尘", meta: "人物资产" },
            { src: "assets/run23/scenes/scene_001.jpeg", title: "宿命祭坛", meta: "场景资产" },
            { src: "assets/run23/props/prop_001.jpeg", title: "旧剑", meta: "道具资产" },
          ],
        },
      },
      storyboard: {
        status: "blocked",
        action: "参考板已发布到本地，但公网 URL 探活失败",
        output: "发布受阻 · 外部访问失败",
        preview: {
          type: "board",
          src: "assets/run23/boards/shot_003.png",
          title: "参考板",
          meta: "参考板已经拼好，但外部访问暂时不可用",
        },
      },
    },
    events: [
      { time: "09:39:04", title: "分镜确认通过", detail: "流程继续往参考板和片段阶段推进。", agent: "分镜生成 Agent", status: "done" },
      { time: "09:39:08", title: "参考板拼接完成", detail: "每个镜头都拿到了对应的参考板。", agent: "分镜生成 Agent", status: "done" },
      { time: "09:39:14", title: "参考板发布阻塞", detail: "外部访问没有通过，流程暂时停在参考板发布。", agent: "分镜生成 Agent", status: "blocked" },
      { time: "11:22:11", title: "重复探活仍失败", detail: "继续执行后外部访问仍未恢复。", agent: "分镜生成 Agent", status: "blocked" },
    ],
  },
  final_done: {
    key: "final_done",
    label: "最终完成",
    displayState: "done",
    timestamp: "2026-03-24 11:33:43",
    headline: "从一句创意到最终成片的整条主链路已经完成",
    description: "在恢复发布链路后，整条流程顺利推进完成，已经生成全部动态片段并拼接出最终成片。",
    defaultAgent: "storyboard",
    nextSnapshot: null,
    nextLabel: "",
    checkpoints: {
      upstream: "done",
      assets: "done",
      storyboard: "done",
    },
    agents: {
      intent: {
        status: "done",
        action: "完整剧本链路完成",
        output: "完整剧本 / 标准剧本",
        preview: {
          type: "text",
          text: STATIC_TEXT.generatedScriptExcerpt,
        },
      },
      assets: {
        status: "done",
        action: "人物、场景、道具参考资产已全部固化",
        output: "人物 3 / 场景 2 / 道具 2",
        preview: {
          type: "gallery",
          items: [
            { src: "assets/run23/characters/char_001.jpeg", title: "阿尘", meta: "主角参考" },
            { src: "assets/run23/characters/char_003.jpeg", title: "阿尘父亲", meta: "回忆人物" },
            { src: "assets/run23/scenes/scene_001.jpeg", title: "宿命祭坛", meta: "核心场景" },
          ],
        },
      },
      storyboard: {
        status: "done",
        action: "6 段动态片段已拼接为最终成片",
        output: "动态片段 6 / 成片 1",
        preview: {
          type: "video",
          src: "assets/run23/videos/shot_001.mp4",
          title: "首段动态片段",
          meta: "最终阶段预览画面",
        },
      },
    },
    events: [
      { time: "11:24:05", title: "参考板发布恢复可用", detail: "参考板外部访问已经恢复，流程可以继续。", agent: "分镜生成 Agent", status: "done" },
      { time: "11:24:05", title: "片段任务整理完成", detail: "所有镜头都已经进入可继续生成的状态。", agent: "分镜生成 Agent", status: "done" },
      { time: "11:33:24", title: "动态片段全部完成", detail: "所有镜头的动态片段都已生成。", agent: "分镜生成 Agent", status: "done" },
      { time: "11:33:43", title: "最终成片完成", detail: "完整成片已经成功输出。", agent: "分镜生成 Agent", status: "done" },
    ],
  },
};

const state = {
  view: "home",
  selectedProjectId: "run23",
  activeSnapshotId: "upstream_review",
  activeAgentId: "storyboard",
  notice: "",
  ideaDraft: "",
};

const appRoot = document.getElementById("app");
const mediaModal = document.getElementById("mediaModal");
const mediaModalMeta = document.getElementById("mediaModalMeta");
const mediaModalBody = document.getElementById("mediaModalBody");
const closeMediaModalButton = document.getElementById("closeMediaModal");

function getProject(projectId = state.selectedProjectId) {
  return PROJECTS.find((project) => project.id === projectId) || PROJECTS[0];
}

function getSnapshot(snapshotId = state.activeSnapshotId) {
  return SNAPSHOTS[snapshotId] || SNAPSHOTS.upstream_review;
}

function getAgentState(snapshot, agentId) {
  return snapshot.agents[agentId] || { status: "idle", action: "等待中", output: "", preview: { type: "text", text: "" } };
}

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.idle;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function truncate(text, limit = 170) {
  const value = String(text || "").trim();
  if (value.length <= limit) return value;
  return `${value.slice(0, limit - 1)}…`;
}

function renderStatusPill(status) {
  const meta = statusMeta(status);
  return `<span class="status-pill" data-state="${meta.state}">${escapeHtml(meta.label)}</span>`;
}

function renderMediaButton(item, className = "cover-button") {
  if (!item || !item.src) return "";
  const kind = item.kind || guessMediaKind(item.src);
  const meta = item.meta || "";
  return `
    <button
      type="button"
      class="${className}"
      data-open-media="true"
      data-media-kind="${escapeHtml(kind)}"
      data-media-src="${escapeHtml(item.src)}"
      data-media-title="${escapeHtml(item.title || "")}"
      data-media-meta="${escapeHtml(meta)}"
    >
      ${kind === "video"
        ? `<video class="thumbnail-video" src="${escapeHtml(item.src)}" muted playsinline loop preload="metadata"></video>`
        : `<img src="${escapeHtml(item.src)}" alt="${escapeHtml(item.title || "媒体预览")}" />`}
    </button>
  `;
}

function guessMediaKind(src) {
  const normalized = String(src || "").toLowerCase();
  return /\.(mp4|mov|webm)$/.test(normalized) ? "video" : "image";
}

function renderPreview(preview) {
  if (!preview) return "";
  if (preview.type === "gallery") {
    return `
      <div class="agent-preview gallery">
        ${preview.items.map((item) => `<img src="${escapeHtml(item.src)}" alt="${escapeHtml(item.title)}" />`).join("")}
      </div>
    `;
  }
  if (preview.type === "board") {
    return `
      <div class="agent-preview board">
        <img src="${escapeHtml(preview.src)}" alt="${escapeHtml(preview.title || "参考板")}" />
      </div>
    `;
  }
  if (preview.type === "video") {
    return `
      <div class="agent-preview board">
        <video class="thumbnail-video" src="${escapeHtml(preview.src)}" muted playsinline loop preload="metadata"></video>
      </div>
    `;
  }
  return `<div class="agent-preview text">${escapeHtml(preview.text || "")}</div>`;
}

function renderHomeView() {
  const featured = getProject("run23");
  return `
    <section class="home-view landing-view">
      <section class="landing-hero">
        <article class="landing-copy-panel">
          <span class="eyebrow">AI 漫剧制作台</span>
          <h1 class="landing-title">一句创意推进最终成片</h1>
          <div class="landing-copy">
            从一句灵感、一个 brief，或者一段完整脚本开始。三个 Agent 会依次完成剧本理解、视觉资产准备和分镜生成，你可以在关键节点查看结果并继续推进。
          </div>
          <div class="chip-row landing-tags">
            <span class="chip">关键词</span>
            <span class="chip">brief</span>
            <span class="chip">完整脚本</span>
          </div>
        </article>

        <article class="composer-card">
          <div class="composer-kicker">第一步</div>
          <h2 class="composer-title">先输入你的创意</h2>
          <div class="composer-copy">可以先从一句话开始，后面再去看三个 Agent 是怎么把它往下推进的。</div>
          <label class="composer-field" for="ideaDraft">创意输入</label>
          <textarea id="ideaDraft" class="idea-input" data-idea-input="true" placeholder="例如：少年握紧旧剑，誓要斩断宿命的枷锁">${escapeHtml(state.ideaDraft)}</textarea>
          <div class="hero-actions">
            <button type="button" class="btn" data-open-project="run23" data-start-snapshot="upstream_review" data-focus-agent="intent">开始体验</button>
            <button type="button" class="ghost-btn" data-fill-sample="true">填入示例</button>
            <button type="button" class="ghost-btn" data-clear-idea="true">清空输入</button>
          </div>
        </article>
      </section>

      <section class="journey-panel">
        <div class="section-head">
          <div>
            <h2 class="section-title">之后会经过什么流程</h2>
            <div class="section-meta">不用先读一整屏信息，直接从这三步进入你关心的环节。</div>
          </div>
          <button type="button" class="ghost-btn" data-open-project="run23" data-start-snapshot="upstream_review" data-focus-agent="intent">进入制作流</button>
        </div>

        <div class="journey-grid">
          ${HOME_FLOW_STEPS.map((step) => `
            <article class="journey-card">
              <div class="journey-number">${escapeHtml(step.number)}</div>
              <div class="journey-title">${escapeHtml(step.title)}</div>
              <div class="journey-copy">${escapeHtml(step.copy)}</div>
              <div class="journey-highlight">${escapeHtml(step.highlight)}</div>
              <button
                type="button"
                class="mini-btn"
                data-open-project="run23"
                data-start-snapshot="${escapeHtml(step.snapshot)}"
                data-focus-agent="${escapeHtml(step.agentId)}"
              >
                ${escapeHtml(step.action)}
              </button>
            </article>
          `).join("")}
        </div>
      </section>

      <section class="focus-panel">
        <div class="section-head">
          <div>
            <h2 class="section-title">${escapeHtml(featured.title)} · ${escapeHtml(featured.episodeTitle)}</h2>
            <div class="section-meta">${escapeHtml(featured.description)}</div>
          </div>
        </div>
        <div class="focus-strip">
          <div class="focus-card">
            <div class="focus-title">你会先看到</div>
            <div class="focus-copy">剧本是怎么被整理出来的，什么时候适合进入下游。</div>
          </div>
          <div class="focus-card">
            <div class="focus-title">然后会看到</div>
            <div class="focus-copy">人物、场景、道具怎么被组织成一组稳定的视觉参考。</div>
          </div>
          <div class="focus-card">
            <div class="focus-title">最后会看到</div>
            <div class="focus-copy">分镜、动态片段和最终成片是怎样一步步收束出来的。</div>
          </div>
        </div>
      </section>
    </section>
  `;
}

function renderSidebar(project, snapshot) {
  const focusItems = SNAPSHOT_FOCUS[snapshot.key] || [];
  return `
    <aside class="sidebar-stack">
      <section class="sidebar-card">
        <h3 class="sidebar-title">当前项目</h3>
        <div class="body-copy">${escapeHtml(project.description)}</div>
        <div class="chip-row" style="margin-top:14px">
          <span class="chip">${escapeHtml(project.runtime)}</span>
          <span class="chip">${escapeHtml(project.shots)}</span>
          <span class="chip">三 Agent 协作</span>
        </div>
      </section>

      <section class="sidebar-card">
        <h3 class="sidebar-title">创意输入</h3>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">一句创意</span><span class="kv-value">${escapeHtml(state.ideaDraft || STATIC_TEXT.inputSeed)}</span></div>
          <div class="kv-row"><span class="kv-key">输入方式</span><span class="kv-value">brief / 单句创意</span></div>
          <div class="kv-row"><span class="kv-key">当前节点</span><span class="kv-value">${escapeHtml(snapshot.label)}</span></div>
        </div>
      </section>

      <section class="sidebar-card">
        <h3 class="sidebar-title">此刻建议关注</h3>
        <div class="artifact-list">
          ${focusItems.map((item) => `
            <div class="artifact-card">
              <div class="artifact-copy">${escapeHtml(item)}</div>
            </div>
          `).join("")}
        </div>
      </section>

      <section class="sidebar-card">
        <h3 class="sidebar-title">核心元素</h3>
        <div class="artifact-list">
          <div class="artifact-card">
            <div class="artifact-title">人物</div>
            <div class="artifact-copy">阿尘 / 族中长老 / 阿尘父亲</div>
          </div>
          <div class="artifact-card">
            <div class="artifact-title">场景</div>
            <div class="artifact-copy">宿命祭坛 / 阿尘旧居小院</div>
          </div>
          <div class="artifact-card">
            <div class="artifact-title">道具</div>
            <div class="artifact-copy">旧剑 / 残损“祭”字木牌</div>
          </div>
        </div>
      </section>
    </aside>
  `;
}

function renderFlow(snapshot) {
  return `
    <section class="flow-stack">
      <section class="flow-stage">
        <div class="flow-head">
          <div>
            <h2 class="flow-title">三 Agent 制作流</h2>
            <div class="flow-copy">${escapeHtml(snapshot.description)}</div>
          </div>
          ${renderStatusPill(snapshot.displayState)}
        </div>

        <div class="agent-flow">
          ${Object.keys(AGENT_DEFS).map((agentId) => renderAgentCard(agentId, snapshot)).join("")}
        </div>
      </section>

      <section class="event-strip">
        <h3 class="strip-title">最近事件流</h3>
        <div class="event-list">
          ${snapshot.events.map((event) => `
            <article class="event-row">
              <div class="event-time">${escapeHtml(event.time)}</div>
              <div class="event-title">${escapeHtml(event.title)}</div>
              <div class="event-meta">${escapeHtml(event.agent)}</div>
              <div class="event-meta">${escapeHtml(event.detail)}</div>
              <div>${renderStatusPill(event.status)}</div>
            </article>
          `).join("")}
        </div>
      </section>
    </section>
  `;
}

function renderAgentCard(agentId, snapshot) {
  const def = AGENT_DEFS[agentId];
  const agentState = getAgentState(snapshot, agentId);
  const isActive = state.activeAgentId === agentId;

  return `
    <article class="agent-card ${isActive ? "active" : ""}" data-agent="${escapeHtml(agentId)}">
      <div class="agent-top">
        <div>
          <h3 class="agent-name">${escapeHtml(def.name)}</h3>
          <div class="agent-role">${escapeHtml(def.role)}</div>
        </div>
        ${renderStatusPill(agentState.status)}
      </div>

      <div class="agent-body">
        <div>
          <div class="agent-caption">当前动作</div>
          <div class="agent-action">${escapeHtml(agentState.action)}</div>
        </div>
        <div class="agent-output">${escapeHtml(agentState.output)}</div>
        ${renderPreview(agentState.preview)}
      </div>

      <button type="button" class="mini-btn" data-agent="${escapeHtml(agentId)}">展开查看</button>
    </article>
  `;
}

function renderWorkspaceView() {
  const project = getProject();
  const snapshot = getSnapshot();
  const nextSnapshot = snapshot.nextSnapshot ? SNAPSHOTS[snapshot.nextSnapshot] : null;

  if (!snapshot.agents[state.activeAgentId]) {
    state.activeAgentId = snapshot.defaultAgent;
  }

  return `
    <section class="workspace-view">
      <section class="workspace-shell">
        <header class="workspace-toolbar">
          <div>
            <span class="eyebrow">AI 漫剧制作流</span>
            <h1 class="toolbar-title">${escapeHtml(project.title)} · ${escapeHtml(project.episodeTitle)}</h1>
            <div class="toolbar-subline">
              ${escapeHtml(snapshot.headline)}
              ${state.notice ? ` · ${escapeHtml(state.notice)}` : ""}
            </div>
            <div class="snapshot-row">
              ${SNAPSHOT_ORDER.map((snapshotKey) => `
                <button
                  type="button"
                  class="snapshot-chip ${snapshotKey === state.activeSnapshotId ? "active" : ""}"
                  data-snapshot="${escapeHtml(snapshotKey)}"
                >
                  ${escapeHtml(SNAPSHOTS[snapshotKey].label)}
                </button>
              `).join("")}
            </div>
          </div>

          <div class="toolbar-actions">
            <button type="button" class="ghost-btn" data-back-home="true">返回项目首页</button>
            ${nextSnapshot ? `<button type="button" class="btn" data-advance="true">${escapeHtml(snapshot.nextLabel)}</button>` : `<button type="button" class="btn" data-snapshot="upstream_review">从开头回看流程</button>`}
          </div>
        </header>

        <div class="workspace-grid">
          ${renderSidebar(project, snapshot)}
          ${renderFlow(snapshot)}
          <aside class="drawer-stack">
            ${renderDrawer(snapshot, state.activeAgentId)}
          </aside>
        </div>
      </section>
    </section>
  `;
}

function renderDrawer(snapshot, agentId) {
  switch (agentId) {
    case "intent":
      return renderIntentDrawer(snapshot);
    case "assets":
      return renderAssetsDrawer(snapshot);
    case "storyboard":
    default:
      return renderStoryboardDrawer(snapshot);
  }
}

function stepRow(label, status, meta = "") {
  return `
    <div class="step-row">
      <span class="step-dot ${escapeHtml(status)}"></span>
      <div class="step-label">${escapeHtml(label)}</div>
      <div class="step-meta">${escapeHtml(meta)}</div>
    </div>
  `;
}

function artifactTextCard(title, copy, code = "") {
  return `
    <article class="artifact-card">
      <div class="artifact-title">${escapeHtml(title)}</div>
      <div class="artifact-copy">${escapeHtml(copy)}</div>
      ${code ? `<div class="artifact-code">${escapeHtml(code)}</div>` : ""}
    </article>
  `;
}

function renderIntentDrawer(snapshot) {
  const isReview = snapshot.key === "upstream_review";
  const gateMeta = isReview
    ? {
        title: "剧本准备确认",
        copy: "完整剧本、标准化脚本和下游可读性检查都已生成。确认通过后，资产提取 Agent 才会正式接手。",
        primary: "确认通过，进入资产提取",
        secondary: "退回修改",
      }
    : {
        title: "剧本准备确认已通过",
        copy: "剧本确认已经通过，后续阶段都会基于这份标准剧本继续往下生成。",
        primary: "",
        secondary: "",
      };

  const stepStates = {
    upstream_review: [
      ["输入识别", "done", "08:01:05"],
      ["路由判断", "done", "08:01:54"],
      ["梗概骨架", "done", "08:03:26"],
      ["完整剧本生成", "done", "08:04:57"],
      ["标准化输出", "done", "08:04:57"],
      ["下游检查", "done", "08:06:18"],
      ["剧本准备确认", "current", "等待确认"],
    ],
    asset_review: [
      ["输入识别", "done", "08:01:05"],
      ["路由判断", "done", "08:01:54"],
      ["梗概骨架", "done", "08:03:26"],
      ["完整剧本生成", "done", "08:04:57"],
      ["标准化输出", "done", "08:04:57"],
      ["下游检查", "done", "08:06:18"],
      ["剧本准备确认", "done", "08:08:20"],
    ],
    storyboard_review: [
      ["输入识别", "done", "08:01:05"],
      ["路由判断", "done", "08:01:54"],
      ["梗概骨架", "done", "08:03:26"],
      ["完整剧本生成", "done", "08:04:57"],
      ["标准化输出", "done", "08:04:57"],
      ["下游检查", "done", "08:06:18"],
      ["剧本准备确认", "done", "08:08:20"],
    ],
    board_publish_blocked: [
      ["输入识别", "done", "08:01:05"],
      ["路由判断", "done", "08:01:54"],
      ["梗概骨架", "done", "08:03:26"],
      ["完整剧本生成", "done", "08:04:57"],
      ["标准化输出", "done", "08:04:57"],
      ["下游检查", "done", "08:06:18"],
      ["剧本准备确认", "done", "08:08:20"],
    ],
    final_done: [
      ["输入识别", "done", "08:01:05"],
      ["路由判断", "done", "08:01:54"],
      ["梗概骨架", "done", "08:03:26"],
      ["完整剧本生成", "done", "08:04:57"],
      ["标准化输出", "done", "08:04:57"],
      ["下游检查", "done", "08:06:18"],
      ["剧本准备确认", "done", "08:08:20"],
    ],
  }[snapshot.key];

  return `
    <section class="drawer-card">
      <div class="drawer-header">
        <div>
          <span class="eyebrow">${escapeHtml(AGENT_DEFS.intent.model)}</span>
          <h2 class="drawer-headline">${escapeHtml(AGENT_DEFS.intent.name)}</h2>
          <div class="drawer-subline">${escapeHtml(snapshot.agents.intent.action)}</div>
        </div>
        ${renderStatusPill(snapshot.agents.intent.status)}
      </div>

      <section class="drawer-section">
        <h3 class="drawer-section-title">Agent 概览</h3>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">输入形态</span><span class="kv-value">brief / 单句创意</span></div>
          <div class="kv-row"><span class="kv-key">系统判断</span><span class="kv-value">先扩写成完整剧本，再继续往下游推进</span></div>
          <div class="kv-row"><span class="kv-key">当前目标</span><span class="kv-value">生成可供资产链路复用的标准剧本</span></div>
          <div class="kv-row"><span class="kv-key">当前产出</span><span class="kv-value">完整剧本 / 标准剧本</span></div>
        </div>
      </section>

      <section class="drawer-section">
        <h3 class="drawer-section-title">内部步骤流</h3>
        <div class="step-list">
          ${stepStates.map((step) => stepRow(step[0], step[1], step[2])).join("")}
        </div>
      </section>

      <section class="drawer-section">
        <h3 class="drawer-section-title">关键产物</h3>
        <div class="artifact-list">
          ${artifactTextCard("系统判断", STATIC_TEXT.routeSummary, "先扩写成完整剧本\n再把内容收束为可继续推进的版本")}
          ${artifactTextCard("扩写后的完整剧本", "这一版会优先把人物、事件和场景补清楚，方便后面继续生成资产。", STATIC_TEXT.generatedScriptExcerpt)}
          ${artifactTextCard("标准化剧本", "这是下游继续读取的稳定版本，会保留最重要的叙事和视觉锚点。", STATIC_TEXT.scriptCleanExcerpt)}
        </div>
      </section>

      <section class="drawer-section">
        <div class="gate-card">
          <div class="gate-title">${escapeHtml(gateMeta.title)}</div>
          <div class="gate-copy">${escapeHtml(gateMeta.copy)}</div>
          ${isReview ? `
            <div class="gate-actions">
              <button type="button" class="btn" data-advance="true">${escapeHtml(gateMeta.primary)}</button>
              <button type="button" class="ghost-btn bad" data-toast="当前页面先展示主线流程，退回分支暂未展开。">${escapeHtml(gateMeta.secondary)}</button>
            </div>
          ` : ""}
        </div>
      </section>
    </section>
  `;
}

function renderAssetsDrawer(snapshot) {
  const isReview = snapshot.key === "asset_review";
  const isReached = ["asset_review", "storyboard_review", "board_publish_blocked", "final_done"].includes(snapshot.key);

  const stepStates = !isReached
    ? [
        ["资产结构化提取", "pending", "等待剧本放行"],
        ["风格设定", "pending", "未开始"],
        ["资产 prompt 生成", "pending", "未开始"],
        ["参考资产图生成", "pending", "未开始"],
        ["参考资产确认", "pending", "未到达"],
      ]
    : isReview
      ? [
          ["资产结构化提取", "done", "08:11:07"],
          ["风格设定", "done", "08:12:07"],
          ["资产 prompt 生成", "done", "08:13:10"],
          ["参考资产图生成", "done", "08:13:46"],
          ["参考资产确认", "current", "等待确认"],
        ]
      : [
          ["资产结构化提取", "done", "08:11:07"],
          ["风格设定", "done", "08:12:07"],
          ["资产 prompt 生成", "done", "08:13:10"],
          ["参考资产图生成", "done", "08:13:46"],
          ["参考资产确认", "done", "09:35:30"],
        ];

  const gateHtml = !isReached
    ? `
      <div class="gate-card">
        <div class="gate-title">等待上游放行</div>
        <div class="gate-copy">意图识别 Agent 还未完成剧本准备确认，资产提取 Agent 目前只是一个待命工位。</div>
      </div>
    `
    : isReview
      ? `
        <div class="gate-card">
          <div class="gate-title">参考资产确认</div>
          <div class="gate-copy">人物、场景、道具的参考图都已生成。确认通过后，分镜生成 Agent 将开始绑定资产并输出正式分镜。</div>
          <div class="gate-actions">
            <button type="button" class="btn" data-advance="true">确认通过，进入分镜生成</button>
            <button type="button" class="ghost-btn bad" data-toast="当前页面先展示主线流程，退回分支暂未展开。">退回重做</button>
          </div>
        </div>
      `
      : `
        <div class="gate-card">
          <div class="gate-title">参考资产确认已通过</div>
          <div class="gate-copy">这一步确认已经通过，后续的分镜与片段都会继续复用这批参考资产。</div>
        </div>
      `;

  return `
    <section class="drawer-card">
      <div class="drawer-header">
        <div>
          <span class="eyebrow">${escapeHtml(AGENT_DEFS.assets.model)}</span>
          <h2 class="drawer-headline">${escapeHtml(AGENT_DEFS.assets.name)}</h2>
          <div class="drawer-subline">${escapeHtml(snapshot.agents.assets.action)}</div>
        </div>
        ${renderStatusPill(snapshot.agents.assets.status)}
      </div>

      <section class="drawer-section">
        <h3 class="drawer-section-title">Agent 概览</h3>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">资产总量</span><span class="kv-value">人物 3 / 场景 2 / 道具 2</span></div>
          <div class="kv-row"><span class="kv-key">主视觉方向</span><span class="kv-value">东方玄幻 / 厚涂手绘国风漫风</span></div>
          <div class="kv-row"><span class="kv-key">当前目标</span><span class="kv-value">生成可复用的参考资产图</span></div>
          <div class="kv-row"><span class="kv-key">当前产出</span><span class="kv-value">角色参考 / 场景参考 / 道具参考</span></div>
        </div>
      </section>

      <section class="drawer-section">
        <h3 class="drawer-section-title">内部步骤流</h3>
        <div class="step-list">
          ${stepStates.map((step) => stepRow(step[0], step[1], step[2])).join("")}
        </div>
      </section>

      <section class="drawer-section">
        <h3 class="drawer-section-title">关键产物</h3>
        <div class="artifact-list">
          ${artifactTextCard("资产结构摘要", "这一阶段先把人物、场景、道具拆清楚，方便后续统一出图。", STATIC_TEXT.assetSummary)}
          ${artifactTextCard("风格基线", "视觉方向会在这里先被统一下来，避免不同资产风格漂移。", STATIC_TEXT.styleBibleExcerpt)}
          <div class="media-grid">
            ${[
              { src: "assets/run23/characters/char_001.jpeg", title: "阿尘", meta: "人物参考图" },
              { src: "assets/run23/characters/char_002.jpeg", title: "族中长老", meta: "人物参考图" },
              { src: "assets/run23/scenes/scene_001.jpeg", title: "宿命祭坛", meta: "场景参考图" },
              { src: "assets/run23/props/prop_001.jpeg", title: "旧剑", meta: "道具参考图" },
            ].map((item) => `
              <article class="media-card">
                ${renderMediaButton(item, "media-button")}
                <div class="media-caption">
                  <strong>${escapeHtml(item.title)}</strong>
                  <div class="body-copy">${escapeHtml(item.meta)}</div>
                </div>
              </article>
            `).join("")}
          </div>
        </div>
      </section>

      <section class="drawer-section">
        ${gateHtml}
      </section>
    </section>
  `;
}

function renderStoryboardDrawer(snapshot) {
  const snapshotKey = snapshot.key;
  const isReview = snapshotKey === "storyboard_review";
  const isBlocked = snapshotKey === "board_publish_blocked";
  const isFinal = snapshotKey === "final_done";
  const isReached = ["storyboard_review", "board_publish_blocked", "final_done"].includes(snapshotKey);

  let stepStates;
  if (!isReached) {
    stepStates = [
      ["正式分镜生成", "pending", "等待上游资产链路结束"],
      ["镜头参考板拼接", "pending", "未开始"],
      ["参考板发布", "pending", "未开始"],
      ["视频任务整理", "pending", "未开始"],
      ["动态片段生成", "pending", "未开始"],
      ["最终成片拼接", "pending", "未开始"],
    ];
  } else if (isReview) {
    stepStates = [
      ["正式分镜生成", "done", "09:36:53"],
      ["分镜确认", "current", "等待确认"],
      ["镜头参考板拼接", "pending", "未开始"],
      ["参考板发布", "pending", "未开始"],
      ["视频任务整理", "pending", "未开始"],
      ["动态片段生成", "pending", "未开始"],
      ["最终成片拼接", "pending", "未开始"],
    ];
  } else if (isBlocked) {
    stepStates = [
      ["正式分镜生成", "done", "09:36:53"],
      ["分镜确认", "done", "09:39:04"],
      ["镜头参考板拼接", "done", "09:39:08"],
      ["参考板发布", "blocked", "09:39:14"],
      ["视频任务整理", "pending", "等待发布链路恢复"],
      ["动态片段生成", "pending", "等待发布链路恢复"],
      ["最终成片拼接", "pending", "等待视频生成完成"],
    ];
  } else {
    stepStates = [
      ["正式分镜生成", "done", "09:36:53"],
      ["分镜确认", "done", "09:39:04"],
      ["镜头参考板拼接", "done", "09:39:08"],
      ["参考板发布", "done", "11:24:05"],
      ["视频任务整理", "done", "11:24:05"],
      ["动态片段生成", "done", "11:33:24"],
      ["最终成片拼接", "done", "11:33:43"],
    ];
  }

  const gateHtml = isReview
    ? `
      <div class="gate-card">
        <div class="gate-title">分镜确认</div>
        <div class="gate-copy">正式分镜已经产出。此时主要是判断镜头拆分、镜头目标与核心资产绑定是否合理。</div>
        <div class="gate-actions">
          <button type="button" class="btn" data-advance="true">确认通过，进入参考板发布</button>
          <button type="button" class="ghost-btn bad" data-toast="当前页面先展示主线流程，退回分支暂未展开。">退回修改</button>
        </div>
      </div>
    `
    : isBlocked
      ? `
        <div class="gate-card">
          <div class="gate-title">阻塞原因</div>
          <div class="gate-copy">${escapeHtml(STATIC_TEXT.boardBlockedReason)}</div>
          <div class="gate-actions">
            <button type="button" class="btn" data-advance="true">继续执行到成片完成</button>
            <button type="button" class="ghost-btn brand" data-toast="这里展示的是恢复可访问后再继续向下推进。">查看恢复说明</button>
          </div>
        </div>
      `
      : isFinal
        ? `
          <div class="gate-card">
            <div class="gate-title">最终结果</div>
            <div class="gate-copy">${escapeHtml(STATIC_TEXT.finalSummary)}</div>
            <div class="gate-actions">
              <button type="button" class="ghost-btn brand" data-open-media="true" data-media-kind="video" data-media-src="assets/run23/videos/final_video.mp4" data-media-title="最终成片" data-media-meta="完整输出预览">打开最终成片</button>
            </div>
          </div>
        `
        : `
          <div class="gate-card">
            <div class="gate-title">等待前序 Agent 放行</div>
            <div class="gate-copy">在当前快照里，分镜生成 Agent 尚未接管真实执行任务。</div>
          </div>
        `;

  const artifactSection = isFinal
    ? `
      <div class="artifact-list">
        ${artifactTextCard("正式分镜摘要", "这一阶段已经把故事拆成了 6 个镜头，并明确了每个镜头的画面目标。", "shot_001 交代核心场景，营造压抑诡谲的宿命氛围\\nshot_002 展现主角当前被困处境，铺垫后续反抗动因\\nshot_003 闪回交代主角成为天定祭品的过往\\nshot_004 情绪从死寂转向愤怒沸腾")}
        <div class="board-gallery">
          ${SHOTS.slice(0, 4).map((shot) => renderMediaButton({ src: shot.board, title: `${shot.id} 参考板`, meta: shot.title }, "cover-button")).join("")}
        </div>
        <div class="media-grid">
          <article class="media-card">
            ${renderMediaButton({ src: "assets/run23/videos/shot_001.mp4", title: "首段动态片段", meta: "片段预览", kind: "video" }, "media-button")}
            <div class="media-caption">
              <strong>首段动态片段</strong>
              <div class="body-copy">用来预览分镜进入动态生成后的画面效果。</div>
            </div>
          </article>
          <article class="media-card">
            ${renderMediaButton({ src: "assets/run23/videos/final_video.mp4", title: "最终成片", meta: "完整输出预览", kind: "video" }, "media-button")}
            <div class="media-caption">
              <strong>最终成片</strong>
              <div class="body-copy">所有动态片段汇总后的完整输出。</div>
            </div>
          </article>
        </div>
      </div>
    `
    : isBlocked
      ? `
        <div class="artifact-list">
          ${artifactTextCard("阻塞说明", "参考板地址已经准备好了，但外部访问暂时没有通过，所以流程停在这里。", STATIC_TEXT.boardBlockedReason)}
          <div class="board-gallery">
            ${SHOTS.slice(0, 4).map((shot) => renderMediaButton({ src: shot.board, title: `${shot.id} 参考板`, meta: shot.title }, "cover-button")).join("")}
          </div>
        </div>
      `
      : isReview
        ? `
          <div class="artifact-list">
            ${artifactTextCard("正式分镜摘要", "这一阶段主要确认镜头拆分是否合理。", "shot_001 交代核心场景，营造压抑诡谲的宿命氛围\\nshot_002 展现主角当前被困处境，铺垫后续反抗动因\\nshot_003 闪回交代主角成为天定祭品的过往\\nshot_004 展现主角从回忆回归现实，情绪从死寂转向愤怒沸腾")}
            <div class="shot-list">
              ${SHOTS.slice(0, 4).map((shot) => `
                <div class="shot-card">
                  <div class="artifact-title">${escapeHtml(shot.id)}</div>
                  <div class="artifact-copy">${escapeHtml(shot.title)}</div>
                </div>
              `).join("")}
            </div>
          </div>
        `
        : `
          <div class="artifact-list">
            ${artifactTextCard("待机状态", "分镜生成 Agent 还未接管 run23。", "会在人物、场景、道具参考资产确认通过后启动。")}
          </div>
        `;

  return `
    <section class="drawer-card">
      <div class="drawer-header">
        <div>
          <span class="eyebrow">${escapeHtml(AGENT_DEFS.storyboard.model)}</span>
          <h2 class="drawer-headline">${escapeHtml(AGENT_DEFS.storyboard.name)}</h2>
          <div class="drawer-subline">${escapeHtml(snapshot.agents.storyboard.action)}</div>
        </div>
        ${renderStatusPill(snapshot.agents.storyboard.status)}
      </div>

      <section class="drawer-section">
        <h3 class="drawer-section-title">Agent 概览</h3>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">镜头规格</span><span class="kv-value">6 镜头 / 单镜头 10 秒 / 16:9</span></div>
          <div class="kv-row"><span class="kv-key">参考画面</span><span class="kv-value">每个镜头都会绑定一张拼接参考板</span></div>
          <div class="kv-row"><span class="kv-key">当前推进</span><span class="kv-value">分镜 -> 参考板 -> 动态片段 -> 成片</span></div>
          <div class="kv-row"><span class="kv-key">当前产出</span><span class="kv-value">${isFinal ? "成片预览" : isBlocked ? "参考板链接待恢复" : isReview ? "正式分镜" : "等待启动"}</span></div>
        </div>
      </section>

      <section class="drawer-section">
        <h3 class="drawer-section-title">内部步骤流</h3>
        <div class="step-list">
          ${stepStates.map((step) => stepRow(step[0], step[1], step[2])).join("")}
        </div>
      </section>

      <section class="drawer-section">
        <h3 class="drawer-section-title">关键产物</h3>
        ${artifactSection}
      </section>

      <section class="drawer-section">
        ${gateHtml}
      </section>
    </section>
  `;
}

function renderWorkspaceShell() {
  return renderWorkspaceView();
}

function renderApp() {
  appRoot.innerHTML = state.view === "home" ? renderHomeView() : renderWorkspaceShell();
  hydrateVideos();
}

function hydrateVideos() {
  document.querySelectorAll("video[muted][loop]").forEach((video) => {
    video.play().catch(() => {});
  });
}

function openProject(projectId, snapshotId = "upstream_review", agentId = "") {
  state.selectedProjectId = projectId;
  state.view = "workspace";
  state.activeSnapshotId = SNAPSHOTS[snapshotId] ? snapshotId : "upstream_review";
  state.activeAgentId = agentId || SNAPSHOTS[state.activeSnapshotId].defaultAgent;
  state.notice = "";
  if (!state.ideaDraft.trim()) {
    state.ideaDraft = STATIC_TEXT.inputSeed;
  }
  renderApp();
}

function setSnapshot(snapshotId) {
  if (!SNAPSHOTS[snapshotId]) return;
  state.activeSnapshotId = snapshotId;
  state.activeAgentId = SNAPSHOTS[snapshotId].defaultAgent;
  state.notice = "";
  renderApp();
}

function advanceSnapshot() {
  const snapshot = getSnapshot();
  if (!snapshot.nextSnapshot) {
    state.notice = "当前已经是最终快照。";
    renderApp();
    return;
  }
  setSnapshot(snapshot.nextSnapshot);
}

function flashNotice(message) {
  state.notice = message;
  renderApp();
  window.clearTimeout(flashNotice.timer);
  flashNotice.timer = window.setTimeout(() => {
    state.notice = "";
    renderApp();
  }, 2600);
}

function openMedia(kind, src, title, meta) {
  if (!src) return;
  mediaModalMeta.innerHTML = `
    <h3 class="media-title">${escapeHtml(title || "媒体预览")}</h3>
    <div class="media-subline">${escapeHtml(meta || "")}</div>
  `;
  mediaModalBody.innerHTML = kind === "video"
    ? `<video src="${escapeHtml(src)}" controls autoplay playsinline></video>`
    : `<img src="${escapeHtml(src)}" alt="${escapeHtml(title || "媒体预览")}" />`;
  mediaModal.classList.add("open");
  mediaModal.setAttribute("aria-hidden", "false");
}

function closeMediaModal() {
  mediaModal.classList.remove("open");
  mediaModal.setAttribute("aria-hidden", "true");
  mediaModalMeta.innerHTML = "";
  mediaModalBody.innerHTML = "";
}

document.addEventListener("click", (event) => {
  const projectButton = event.target.closest("[data-open-project]");
  if (projectButton) {
    openProject(
      projectButton.getAttribute("data-open-project"),
      projectButton.getAttribute("data-start-snapshot") || "upstream_review",
      projectButton.getAttribute("data-focus-agent") || "",
    );
    return;
  }

  const fillSampleButton = event.target.closest("[data-fill-sample]");
  if (fillSampleButton) {
    state.ideaDraft = STATIC_TEXT.inputSeed;
    renderApp();
    return;
  }

  const clearIdeaButton = event.target.closest("[data-clear-idea]");
  if (clearIdeaButton) {
    state.ideaDraft = "";
    renderApp();
    return;
  }

  const backHomeButton = event.target.closest("[data-back-home]");
  if (backHomeButton) {
    state.view = "home";
    state.notice = "";
    renderApp();
    return;
  }

  const snapshotButton = event.target.closest("[data-snapshot]");
  if (snapshotButton) {
    setSnapshot(snapshotButton.getAttribute("data-snapshot"));
    return;
  }

  const advanceButton = event.target.closest("[data-advance]");
  if (advanceButton) {
    advanceSnapshot();
    return;
  }

  const toastButton = event.target.closest("[data-toast]");
  if (toastButton) {
    flashNotice(toastButton.getAttribute("data-toast"));
    return;
  }

  const agentButton = event.target.closest("[data-agent]");
  if (agentButton) {
    state.activeAgentId = agentButton.getAttribute("data-agent");
    renderApp();
    return;
  }

  const mediaButton = event.target.closest("[data-open-media]");
  if (mediaButton) {
    openMedia(
      mediaButton.getAttribute("data-media-kind"),
      mediaButton.getAttribute("data-media-src"),
      mediaButton.getAttribute("data-media-title"),
      mediaButton.getAttribute("data-media-meta"),
    );
  }
});

document.addEventListener("input", (event) => {
  const ideaInput = event.target.closest("[data-idea-input]");
  if (!ideaInput) return;
  state.ideaDraft = ideaInput.value;
});

closeMediaModalButton.addEventListener("click", closeMediaModal);
mediaModal.addEventListener("click", (event) => {
  if (event.target === mediaModal) {
    closeMediaModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeMediaModal();
  }
});

renderApp();
