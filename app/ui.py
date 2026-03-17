from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .api import create_api_app


def build_console_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Studio Operator Console</title>
  <style>
    :root {
      --bg: #f2ede3;
      --panel: rgba(255, 252, 246, 0.86);
      --panel-strong: #fffaf1;
      --ink: #1e2220;
      --muted: #58615c;
      --accent: #a6492f;
      --accent-2: #1d5b63;
      --line: rgba(30, 34, 32, 0.12);
      --ok: #2c7a4b;
      --warn: #a66c11;
      --bad: #a73932;
      --shadow: 0 24px 60px rgba(55, 40, 20, 0.12);
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(166, 73, 47, 0.18), transparent 32%),
        radial-gradient(circle at bottom right, rgba(29, 91, 99, 0.16), transparent 28%),
        linear-gradient(180deg, #f7f2e8 0%, #efe7da 100%);
      font-family: "IBM Plex Sans", "Avenir Next", "PingFang SC", "Noto Sans SC", sans-serif;
    }
    .shell {
      max-width: 1580px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
      margin-bottom: 18px;
    }
    .hero-card,
    .panel {
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.48);
      backdrop-filter: blur(18px);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }
    .hero-card {
      padding: 24px;
    }
    h1 {
      margin: 0;
      font-size: 34px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .lead {
      max-width: 50rem;
      margin-top: 12px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.6;
    }
    .hero-meta {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 16px;
    }
    .pill {
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 250, 241, 0.9);
      border: 1px solid var(--line);
      font-size: 12px;
      color: var(--muted);
    }
    .hero-side {
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      justify-content: space-between;
    }
    .hero-side strong {
      display: block;
      margin-bottom: 6px;
      font-size: 14px;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      color: var(--accent-2);
    }
    .hero-side p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 14px;
    }
    .layout {
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 18px;
      align-items: start;
    }
    .panel {
      padding: 18px;
    }
    .panel h2 {
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: -0.02em;
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      color: var(--muted);
    }
    input,
    select,
    textarea,
    button {
      font: inherit;
    }
    input,
    select,
    textarea {
      width: 100%;
      border: 1px solid rgba(33, 33, 33, 0.12);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.88);
      padding: 12px 13px;
      color: var(--ink);
    }
    textarea {
      min-height: 128px;
      resize: vertical;
    }
    .row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    button {
      border: 0;
      cursor: pointer;
      border-radius: 999px;
      padding: 11px 16px;
      background: linear-gradient(135deg, var(--accent), #cd6d43);
      color: white;
      font-weight: 700;
      letter-spacing: 0.01em;
      box-shadow: 0 12px 24px rgba(166, 73, 47, 0.18);
    }
    button.secondary {
      background: rgba(255, 255, 255, 0.88);
      color: var(--ink);
      box-shadow: none;
      border: 1px solid var(--line);
    }
    button.ghost {
      background: rgba(29, 91, 99, 0.1);
      color: var(--accent-2);
      box-shadow: none;
    }
    .status {
      padding: 11px 13px;
      border-radius: 14px;
      background: rgba(29, 91, 99, 0.08);
      color: var(--accent-2);
      font-size: 14px;
      line-height: 1.5;
      min-height: 44px;
    }
    .runs {
      display: grid;
      gap: 10px;
      max-height: 560px;
      overflow: auto;
      padding-right: 2px;
    }
    .run-card {
      padding: 14px;
      border-radius: 18px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
      cursor: pointer;
      transition: transform 0.16s ease, border-color 0.16s ease;
    }
    .run-card:hover {
      transform: translateY(-1px);
      border-color: rgba(166, 73, 47, 0.34);
    }
    .run-card.active {
      border-color: rgba(166, 73, 47, 0.72);
      box-shadow: inset 0 0 0 1px rgba(166, 73, 47, 0.18);
    }
    .run-top,
    .meta-line {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }
    .run-id {
      font-size: 16px;
      font-weight: 700;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      background: rgba(29, 91, 99, 0.1);
      color: var(--accent-2);
    }
    .tag.succeeded { background: rgba(44, 122, 75, 0.12); color: var(--ok); }
    .tag.running { background: rgba(29, 91, 99, 0.12); color: var(--accent-2); }
    .tag.awaiting_approval { background: rgba(166, 108, 17, 0.14); color: var(--warn); }
    .tag.blocked { background: rgba(166, 108, 17, 0.14); color: var(--warn); }
    .tag.failed { background: rgba(167, 57, 50, 0.12); color: var(--bad); }
    .tag.partial { background: rgba(88, 97, 92, 0.12); color: var(--muted); }
    .muted {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .detail-grid {
      display: grid;
      gap: 18px;
    }
    .detail-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .detail-head h2 {
      margin-bottom: 8px;
      font-size: 26px;
    }
    .detail-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .stage-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 10px;
    }
    .stage-card {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      padding: 14px;
      min-height: 134px;
    }
    .stage-card strong {
      display: block;
      margin-bottom: 8px;
      font-size: 15px;
    }
    .review-grid {
      display: grid;
      gap: 16px;
    }
    .review-card {
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
      padding: 16px;
    }
    .review-card h3 {
      margin: 0;
      font-size: 17px;
    }
    .review-toolbar,
    .review-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .review-toolbar {
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .review-actions {
      margin-top: 12px;
    }
    .review-actions button {
      box-shadow: none;
      padding: 9px 14px;
    }
    .review-actions .approve {
      background: var(--ok);
    }
    .review-actions .reject {
      background: var(--bad);
    }
    .review-actions .pending {
      background: var(--warn);
    }
    .review-form {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .review-shell {
      display: grid;
      gap: 14px;
    }
    .review-note {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .review-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(255, 255, 255, 0.76);
      color: var(--muted);
      cursor: pointer;
      box-shadow: none;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.01em;
    }
    .chip.active {
      background: rgba(166, 73, 47, 0.12);
      color: var(--accent);
      border-color: rgba(166, 73, 47, 0.28);
    }
    .review-search {
      min-width: 220px;
      flex: 1;
    }
    .compact-input {
      padding: 10px 12px;
    }
    .media-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }
    .media-card {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      overflow: hidden;
      display: grid;
    }
    .media-thumb {
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      display: block;
      background: rgba(88, 97, 92, 0.08);
    }
    .media-thumb-button {
      padding: 0;
      border-radius: 0;
      box-shadow: none;
      background: transparent;
    }
    .media-body {
      padding: 12px;
      display: grid;
      gap: 6px;
    }
    .media-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 6px;
    }
    .text-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      color: var(--accent-2);
      box-shadow: none;
      padding: 8px 12px;
      text-decoration: none;
      font-size: 12px;
      font-weight: 700;
    }
    .review-split {
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 14px;
      align-items: start;
    }
    .review-rail,
    .review-detail {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
    }
    .review-rail {
      padding: 10px;
      display: grid;
      gap: 8px;
      max-height: 640px;
      overflow: auto;
    }
    .review-detail {
      padding: 14px;
      display: grid;
      gap: 14px;
      min-height: 240px;
    }
    .shot-nav-card {
      width: 100%;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 250, 241, 0.86);
      color: var(--ink);
      box-shadow: none;
      padding: 12px;
      text-align: left;
    }
    .shot-nav-card.active {
      border-color: rgba(166, 73, 47, 0.42);
      background: rgba(166, 73, 47, 0.12);
    }
    .detail-grid-two {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
      gap: 14px;
    }
    .detail-section {
      display: grid;
      gap: 10px;
    }
    .board-frame {
      overflow: hidden;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(30, 34, 32, 0.04);
    }
    .board-frame img,
    .board-frame video {
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      display: block;
    }
    .reference-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
    }
    .reference-card {
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.86);
      overflow: hidden;
    }
    .reference-card .media-thumb {
      aspect-ratio: 4 / 3;
    }
    .reference-body {
      padding: 10px;
      display: grid;
      gap: 4px;
    }
    .video-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }
    .video-card {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      overflow: hidden;
      display: grid;
    }
    .video-card .media-thumb,
    .video-card video {
      aspect-ratio: 16 / 9;
      width: 100%;
      display: block;
      background: rgba(88, 97, 92, 0.08);
      object-fit: cover;
    }
    .video-body {
      padding: 12px;
      display: grid;
      gap: 8px;
    }
    .video-hero {
      display: grid;
      gap: 14px;
    }
    .video-frame {
      overflow: hidden;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(30, 34, 32, 0.04);
    }
    .video-frame video,
    .video-frame img {
      width: 100%;
      aspect-ratio: 16 / 9;
      display: block;
      object-fit: cover;
      background: rgba(88, 97, 92, 0.08);
    }
    .video-filter-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
    }
    .micro-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
    }
    .micro-card {
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
    }
    .micro-card strong {
      display: block;
      margin-bottom: 4px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: var(--muted);
    }
    .note-list {
      display: grid;
      gap: 8px;
    }
    .note-item {
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(30, 34, 32, 0.04);
      border: 1px solid rgba(30, 34, 32, 0.08);
    }
    .shot-list {
      display: grid;
      gap: 10px;
    }
    .shot-card {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      padding: 14px;
      display: grid;
      gap: 8px;
    }
    .json-box {
      padding: 12px;
      border-radius: 14px;
      background: rgba(30, 34, 32, 0.04);
      border: 1px solid rgba(30, 34, 32, 0.08);
      font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .summary-box {
      padding: 12px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
    }
    .summary-box strong {
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .artifact-list,
    .event-list,
    .task-list {
      display: grid;
      gap: 8px;
    }
    .artifact-row,
    .event-row,
    .task-row {
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
    }
    .artifact-row a {
      color: var(--accent-2);
      text-decoration: none;
      font-weight: 700;
    }
    .artifact-row a:hover {
      text-decoration: underline;
    }
    .code {
      font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }
    .empty {
      padding: 28px;
      border-radius: 18px;
      border: 1px dashed rgba(30, 34, 32, 0.18);
      color: var(--muted);
      text-align: center;
      background: rgba(255, 255, 255, 0.45);
    }
    .modal {
      position: fixed;
      inset: 0;
      display: none;
      place-items: center;
      padding: 24px;
      z-index: 30;
    }
    .modal.open {
      display: grid;
    }
    .modal-backdrop {
      position: absolute;
      inset: 0;
      background: rgba(18, 22, 20, 0.74);
      backdrop-filter: blur(8px);
    }
    .modal-card {
      position: relative;
      z-index: 1;
      width: min(1120px, 100%);
      max-height: calc(100vh - 48px);
      overflow: auto;
      border-radius: 24px;
      border: 1px solid rgba(255, 255, 255, 0.16);
      background: rgba(255, 250, 241, 0.96);
      box-shadow: 0 28px 90px rgba(0, 0, 0, 0.32);
      padding: 18px;
      display: grid;
      gap: 14px;
    }
    .modal-close {
      position: absolute;
      top: 14px;
      right: 14px;
      width: 42px;
      height: 42px;
      border-radius: 999px;
      box-shadow: none;
      background: rgba(30, 34, 32, 0.08);
      color: var(--ink);
      font-size: 18px;
      padding: 0;
    }
    .modal-media {
      width: 100%;
      border-radius: 18px;
      background: rgba(30, 34, 32, 0.04);
      overflow: hidden;
    }
    .modal-media img,
    .modal-media video {
      width: 100%;
      display: block;
      max-height: 72vh;
      object-fit: contain;
      background: #f3efe7;
    }
    .modal-meta {
      display: grid;
      gap: 8px;
    }
    @media (max-width: 1080px) {
      .hero,
      .layout {
        grid-template-columns: 1fr;
      }
      .review-split,
      .detail-grid-two {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-card">
        <h1>AI Studio Operator Console</h1>
        <div class="lead">
          这一版控制台直接面向 workflow operator，而不是聊天式代理壳。
          它基于共享 workflow service，先把 run 创建、run 观察、继续执行、单 stage 重跑这四个能力固定下来。
        </div>
        <div class="hero-meta">
          <span class="pill">Python-only</span>
          <span class="pill">Persisted run state</span>
          <span class="pill">Stage-aware rerun</span>
          <span class="pill">FastAPI console shell</span>
        </div>
      </div>
      <div class="hero-card hero-side">
        <div>
          <strong>Current Focus</strong>
          <p>先让 operator 能稳定操控现有 pipeline，并把 upstream、asset_images、storyboard 三个审批点接成真正的 gate。</p>
        </div>
        <div>
          <strong>Primary Actions</strong>
          <p>创建 run、查看 run 状态、继续中断流程、强制重跑某个 stage、读取 `_meta` 事件流。</p>
        </div>
      </div>
    </section>

    <section class="layout">
      <aside class="stack">
        <div class="panel">
          <h2>Create Or Resume</h2>
          <div class="stack">
            <label>Source Name
              <input id="source_script_name" placeholder="intent_input / 剧本名" />
            </label>
            <label>Execution
              <select id="execution_mode">
                <option value="mainline">mainline</option>
                <option value="upstream_only">upstream_only</option>
              </select>
            </label>
            <label>Source Text
              <textarea id="source_text" placeholder="输入关键词、brief 或完整剧本。系统会自动判断输入类型并选择上游路由。"></textarea>
            </label>
            <label>Parallel Planning
              <select id="parallel_planning">
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            </label>
            <div class="actions">
              <button onclick="createRun()">Launch Task</button>
              <button class="secondary" onclick="loadRuns()">Refresh Runs</button>
            </div>
            <div id="create_status" class="status">等待操作。</div>
          </div>
        </div>

        <div class="panel">
          <div class="meta-line">
            <h2 style="margin:0">Runs</h2>
            <button class="ghost" onclick="loadRuns()">Reload</button>
          </div>
          <div id="runs" class="runs"></div>
        </div>
      </aside>

      <main class="detail-grid">
        <div class="panel" id="run_detail_panel">
          <div class="empty">选择左侧 run 查看详情。</div>
        </div>
      </main>
    </section>
  </div>

  <div id="media_modal" class="modal" aria-hidden="true">
    <div class="modal-backdrop" onclick="closeMediaModal()"></div>
    <div class="modal-card">
      <button class="modal-close secondary" onclick="closeMediaModal()">×</button>
      <div id="media_modal_meta" class="modal-meta"></div>
      <div id="media_modal_content" class="modal-media"></div>
    </div>
  </div>

  <script>
    const stageOptions = [
      'upstream',
      'asset_extraction',
      'style_bible',
      'asset_prompts',
      'asset_images',
      'storyboard_seed',
      'storyboard',
      'shot_reference_boards',
      'board_publish',
      'video_jobs',
      'shot_videos',
      'final_video',
    ];

    let selectedRunId = '';
    let assetReviewCache = null;
    let storyboardReviewCache = null;
    let videoSummaryCache = null;
    let assetImageFilter = 'all';
    let assetImageQuery = '';
    let storyboardSelectedShotId = '';
    let shotVideoFilter = 'all';

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {'Content-Type': 'application/json'},
        ...options,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }
      return response.json();
    }

    async function safeApi(path) {
      try {
        return await api(path);
      } catch (error) {
        console.error(error);
        return null;
      }
    }

    function statusTag(status) {
      return `<span class="tag ${status || ''}">${status || 'unknown'}</span>`;
    }

    function escapeHtml(value) {
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function truncate(value, limit = 240) {
      const text = String(value || '');
      if (text.length <= limit) return text;
      return `${text.slice(0, limit)}...`;
    }

    function renderSummaryBox(label, value) {
      const display = Array.isArray(value) ? value.join(', ') : String(value || 'N/A');
      return `
        <div class="summary-box">
          <strong>${escapeHtml(label)}</strong>
          <div class="muted">${escapeHtml(display)}</div>
        </div>
      `;
    }

    function renderReviewSection(stage, title, reviewPayload, bodyHtml) {
      const review = reviewPayload?.review || {status: 'pending', reviewer: '', notes: ''};
      return `
        <section class="review-card">
          <div class="review-toolbar">
            <div>
              <h3>${escapeHtml(title)}</h3>
              <div class="muted">reviewer: ${escapeHtml(review.reviewer || 'unassigned')}</div>
            </div>
            ${statusTag(review.status)}
          </div>
          ${bodyHtml}
          <div class="review-form">
            <div class="row">
              <label>Reviewer
                <input class="compact-input" id="reviewer_${stage}" value="${escapeHtml(review.reviewer || '')}" placeholder="operator name" />
              </label>
              <label>Updated
                <input class="compact-input" value="${escapeHtml(review.updated_at || '')}" readonly />
              </label>
            </div>
            <label>Notes
              <textarea id="notes_${stage}" placeholder="记录通过原因、问题点或返工建议。">${escapeHtml(review.notes || '')}</textarea>
            </label>
            <div class="review-actions">
              <button class="approve" onclick="submitReview('${stage}', 'approved')">Approve</button>
              <button class="reject" onclick="submitReview('${stage}', 'rejected')">Reject</button>
              <button class="pending" onclick="submitReview('${stage}', 'pending')">Mark Pending</button>
            </div>
          </div>
        </section>
      `;
    }

    function renderUpstreamReview(reviewPayload) {
      const payload = reviewPayload?.payload || {};
      const summary = payload.summary || {};
      const artifacts = payload.artifacts || {};
      const summaryHtml = `
        <div class="summary-grid">
          ${renderSummaryBox('chosen_path', summary.chosen_path)}
          ${renderSummaryBox('recommended_operations', summary.recommended_operations || [])}
          ${renderSummaryBox('ready_for_extraction', summary.ready_for_extraction)}
          ${renderSummaryBox('blocking_issues', summary.blocking_issues || [])}
        </div>
      `;
      const routerJson = artifacts['intake_router.json'] ? JSON.stringify(artifacts['intake_router.json'], null, 2) : 'No intake_router.json';
      const readinessJson = artifacts['asset_readiness_report.json'] ? JSON.stringify(artifacts['asset_readiness_report.json'], null, 2) : 'No asset_readiness_report.json';
      const scriptPreview = artifacts['script_clean.txt'] ? truncate(artifacts['script_clean.txt'], 900) : 'No script_clean.txt';
      const bodyHtml = `
        ${summaryHtml}
        <div class="stack" style="margin-top:14px">
          <div>
            <div class="muted" style="margin-bottom:6px">intake_router.json</div>
            <div class="json-box">${escapeHtml(routerJson)}</div>
          </div>
          <div>
            <div class="muted" style="margin-bottom:6px">asset_readiness_report.json</div>
            <div class="json-box">${escapeHtml(readinessJson)}</div>
          </div>
          <div>
            <div class="muted" style="margin-bottom:6px">script_clean.txt</div>
            <div class="json-box">${escapeHtml(scriptPreview)}</div>
          </div>
        </div>
      `;
      return renderReviewSection('upstream', 'Upstream Review', reviewPayload, bodyHtml);
    }

    function humanizeGroup(group) {
      const labels = {
        all: 'All',
        characters: 'Characters',
        scenes: 'Scenes',
        props: 'Props',
        character: 'Character',
        scene: 'Scene',
        prop: 'Prop',
      };
      return labels[group] || group || 'Unknown';
    }

    function renderMediaElement(url, alt) {
      const raw = String(url || '');
      if (!raw) {
        return '<div class="media-thumb"></div>';
      }
      const normalized = raw.toLowerCase();
      if (/\\.(mp4|mov|webm)(\\?|$)/.test(normalized)) {
        return `<video class="media-thumb" src="${raw}" muted playsinline controls></video>`;
      }
      return `<img class="media-thumb" src="${raw}" alt="${escapeHtml(alt || 'preview')}" />`;
    }

    function openMediaModal(url, title = '', description = '', externalUrl = '') {
      if (!url) return;
      const modal = document.getElementById('media_modal');
      const meta = document.getElementById('media_modal_meta');
      const content = document.getElementById('media_modal_content');
      if (!modal || !meta || !content) return;
      const normalized = String(url).toLowerCase();
      const mediaHtml = /\\.(mp4|mov|webm)(\\?|$)/.test(normalized)
        ? `<video src="${url}" controls autoplay playsinline></video>`
        : `<img src="${url}" alt="${escapeHtml(title || 'preview')}" />`;
      meta.innerHTML = `
        <div class="meta-line">
          <strong>${escapeHtml(title || 'Preview')}</strong>
          ${externalUrl ? `<a class="text-button" href="${externalUrl}" target="_blank" rel="noopener noreferrer">Open Source</a>` : ''}
        </div>
        ${description ? `<div class="muted">${escapeHtml(description)}</div>` : ''}
      `;
      content.innerHTML = mediaHtml;
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    }

    function closeMediaModal() {
      const modal = document.getElementById('media_modal');
      const meta = document.getElementById('media_modal_meta');
      const content = document.getElementById('media_modal_content');
      if (!modal || !meta || !content) return;
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
      meta.innerHTML = '';
      content.innerHTML = '';
    }

    function isMediaModalOpen() {
      const modal = document.getElementById('media_modal');
      return Boolean(modal && modal.classList && modal.classList.contains('open'));
    }

    function hasActiveVideoPlayback() {
      return Array.from(document.querySelectorAll('video')).some(video => !video.paused && !video.ended);
    }

    function renderAssetImagesReview(reviewPayload) {
      const summary = reviewPayload?.payload?.summary || {};
      const summaryHtml = `
        <div class="summary-grid">
          ${renderSummaryBox('characters', summary.character_count)}
          ${renderSummaryBox('scenes', summary.scene_count)}
          ${renderSummaryBox('props', summary.prop_count)}
        </div>
      `;
      const bodyHtml = `
        <div class="review-shell">
          ${summaryHtml}
          <div class="review-note">按资产类型筛选，支持按名称或 ID 搜索。点击缩略图可以直接在控制台里放大检查。</div>
          <div class="review-controls">
            <div id="asset_images_filter_row" class="chip-row"></div>
            <input
              id="asset_images_query"
              class="review-search"
              placeholder="Search asset id / name / label"
              value="${escapeHtml(assetImageQuery)}"
              oninput="updateAssetImageQuery(this.value)"
            />
          </div>
          <div id="asset_images_filter_meta" class="muted"></div>
          <div id="asset_images_review_dynamic"></div>
        </div>
      `;
      return renderReviewSection('asset_images', 'Asset Images Review', reviewPayload, bodyHtml);
    }

    function renderReferenceAssetCard(asset) {
      const preview = asset.preview_url
        ? `
          <button class="media-thumb-button" onclick='openMediaModal(${JSON.stringify(asset.preview_url)}, ${JSON.stringify(asset.name || asset.asset_id)}, ${JSON.stringify(asset.label_text || asset.asset_type || "")})'>
            ${renderMediaElement(asset.preview_url, asset.name || asset.asset_id)}
          </button>
        `
        : '<div class="media-thumb"></div>';
      return `
        <div class="reference-card">
          ${preview}
          <div class="reference-body">
            <strong>${escapeHtml(asset.name || asset.asset_id)}</strong>
            <div class="muted">${escapeHtml(humanizeGroup(asset.group || asset.asset_type))}</div>
            <div class="code">${escapeHtml(asset.asset_id || '')}</div>
          </div>
        </div>
      `;
    }

    function paintAssetImagesReview() {
      const filterRoot = document.getElementById('asset_images_filter_row');
      const metaRoot = document.getElementById('asset_images_filter_meta');
      const contentRoot = document.getElementById('asset_images_review_dynamic');
      if (!filterRoot || !metaRoot || !contentRoot) return;

      const items = assetReviewCache?.payload?.items || [];
      const counts = {
        all: items.length,
        characters: items.filter(item => item.group === 'characters').length,
        scenes: items.filter(item => item.group === 'scenes').length,
        props: items.filter(item => item.group === 'props').length,
      };
      const groups = ['all', 'characters', 'scenes', 'props'];
      filterRoot.innerHTML = groups.map(group => `
        <button class="chip ${assetImageFilter === group ? 'active' : ''}" onclick="setAssetImageFilter('${group}')">
          ${humanizeGroup(group)} · ${counts[group]}
        </button>
      `).join('');

      const normalizedQuery = assetImageQuery.trim().toLowerCase();
      const filtered = items.filter(item => {
        const matchesGroup = assetImageFilter === 'all' || item.group === assetImageFilter;
        if (!matchesGroup) return false;
        if (!normalizedQuery) return true;
        return [item.id, item.name, item.label_text, item.group].join(' ').toLowerCase().includes(normalizedQuery);
      });
      metaRoot.textContent = `Showing ${filtered.length} / ${items.length} assets`;

      contentRoot.innerHTML = filtered.length ? `
        <div class="media-grid">
          ${filtered.map(item => `
            <div class="media-card">
              ${item.preview_url ? `
                <button class="media-thumb-button" onclick='openMediaModal(${JSON.stringify(item.preview_url)}, ${JSON.stringify(item.name || item.id)}, ${JSON.stringify(item.label_text || item.group || "")})'>
                  ${renderMediaElement(item.preview_url, item.name || item.id)}
                </button>
              ` : '<div class="media-thumb"></div>'}
              <div class="media-body">
                <strong>${escapeHtml(item.name || item.id)}</strong>
                <div class="muted">${escapeHtml(humanizeGroup(item.group))}</div>
                <div class="code">${escapeHtml(item.id || '')}</div>
                <div class="muted">${escapeHtml(item.label_text || '')}</div>
                <div class="media-actions">
                  ${item.preview_url ? `<button class="text-button" onclick='openMediaModal(${JSON.stringify(item.preview_url)}, ${JSON.stringify(item.name || item.id)}, ${JSON.stringify(item.label_text || item.group || "")})'>Inspect</button>` : ''}
                  ${item.preview_url ? `<a class="text-button" href="${item.preview_url}" target="_blank" rel="noopener noreferrer">Open File</a>` : ''}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      ` : '<div class="empty">当前筛选条件下没有资产卡片。</div>';
    }

    function setAssetImageFilter(group) {
      assetImageFilter = group;
      paintAssetImagesReview();
    }

    function updateAssetImageQuery(value) {
      assetImageQuery = value || '';
      paintAssetImagesReview();
    }

    function renderStoryboardReview(reviewPayload) {
      const summary = reviewPayload?.payload?.summary || {};
      const bodyHtml = `
        <div class="review-shell">
          <div class="summary-grid">
            ${renderSummaryBox('title', summary.title)}
            ${renderSummaryBox('shot_count', summary.shot_count)}
          </div>
          <div class="review-note">左侧快速切 shot，右侧集中看 prompt、镜头参数、关联参考资产和已有 board。</div>
          <div id="storyboard_review_dynamic"></div>
        </div>
      `;
      return renderReviewSection('storyboard', 'Storyboard Review', reviewPayload, bodyHtml);
    }

    function paintStoryboardReview() {
      const root = document.getElementById('storyboard_review_dynamic');
      if (!root) return;
      const shots = storyboardReviewCache?.payload?.shots || [];
      if (!shots.length) {
        root.innerHTML = '<div class="empty">storyboard 产物还不存在。</div>';
        return;
      }

      if (!storyboardSelectedShotId || !shots.some(shot => shot.shot_id === storyboardSelectedShotId)) {
        storyboardSelectedShotId = shots[0].shot_id;
      }
      const selectedShot = shots.find(shot => shot.shot_id === storyboardSelectedShotId) || shots[0];

      const railHtml = shots.map(shot => `
        <button class="shot-nav-card ${shot.shot_id === storyboardSelectedShotId ? 'active' : ''}" onclick='selectStoryboardShot(${JSON.stringify(shot.shot_id)})'>
          <div class="meta-line">
            <strong>${escapeHtml(shot.shot_id || 'shot')}</strong>
            <span class="muted">#${escapeHtml(shot.order || '')}</span>
          </div>
          <div class="muted">${escapeHtml(shot.shot_type || 'shot')}</div>
          <div style="margin-top:8px">${escapeHtml(truncate(shot.summary || '', 90))}</div>
        </button>
      `).join('');

      const referenceAssets = selectedShot.reference_assets || [];
      const boardHtml = selectedShot.board_preview_url ? `
        <div class="board-frame">
          <button class="media-thumb-button" onclick='openMediaModal(${JSON.stringify(selectedShot.board_preview_url)}, ${JSON.stringify(selectedShot.shot_id + " board")}, ${JSON.stringify(selectedShot.board_layout_template || "")}, ${JSON.stringify(selectedShot.board_public_url || selectedShot.board_preview_url)})'>
            ${renderMediaElement(selectedShot.board_preview_url, (selectedShot.shot_id || 'shot') + ' board')}
          </button>
        </div>
        <div class="media-actions">
          <button class="text-button" onclick='openMediaModal(${JSON.stringify(selectedShot.board_preview_url)}, ${JSON.stringify(selectedShot.shot_id + " board")}, ${JSON.stringify(selectedShot.board_layout_template || "")}, ${JSON.stringify(selectedShot.board_public_url || selectedShot.board_preview_url)})'>Inspect Board</button>
          ${selectedShot.board_public_url ? `<a class="text-button" href="${selectedShot.board_public_url}" target="_blank" rel="noopener noreferrer">Open Public URL</a>` : ''}
        </div>
      ` : '<div class="empty">当前 run 还没有可预览的 shot board。</div>';

      const referenceHtml = referenceAssets.length
        ? `<div class="reference-strip">${referenceAssets.map(renderReferenceAssetCard).join('')}</div>`
        : '<div class="empty">当前 shot 还没有可展示的参考资产。</div>';

      const continuityNotes = Array.isArray(selectedShot.continuity_notes) ? selectedShot.continuity_notes : [];
      root.innerHTML = `
        <div class="review-split">
          <div class="review-rail">${railHtml}</div>
          <div class="review-detail">
            <div class="meta-line">
              <div>
                <h3>${escapeHtml(selectedShot.shot_id || 'shot')}</h3>
                <div class="muted">${escapeHtml(selectedShot.summary || '')}</div>
              </div>
              ${statusTag(storyboardReviewCache?.review?.status || 'pending')}
            </div>
            <div class="micro-grid">
              <div class="micro-card"><strong>Shot Type</strong><div>${escapeHtml(selectedShot.shot_type || 'N/A')}</div></div>
              <div class="micro-card"><strong>Camera</strong><div>${escapeHtml([selectedShot.shot_size, selectedShot.camera_angle, selectedShot.camera_movement].filter(Boolean).join(' / ') || 'N/A')}</div></div>
              <div class="micro-card"><strong>Emotion</strong><div>${escapeHtml(selectedShot.emotion_tone || 'N/A')}</div></div>
              <div class="micro-card"><strong>Assets</strong><div>${escapeHtml(String(referenceAssets.length || 0))}</div></div>
            </div>
            <div class="detail-grid-two">
              <div class="detail-section">
                <div>
                  <div class="muted" style="margin-bottom:6px">Shot Prompt</div>
                  <div class="json-box">${escapeHtml(selectedShot.prompt || '')}</div>
                </div>
                <div class="note-list">
                  ${selectedShot.subject_action ? `<div class="note-item"><strong>Subject</strong><div>${escapeHtml(selectedShot.subject_action)}</div></div>` : ''}
                  ${selectedShot.background_action ? `<div class="note-item"><strong>Background</strong><div>${escapeHtml(selectedShot.background_action)}</div></div>` : ''}
                  ${continuityNotes.map(note => `<div class="note-item"><strong>Continuity</strong><div>${escapeHtml(note)}</div></div>`).join('')}
                </div>
              </div>
              <div class="detail-section">
                <div>
                  <div class="muted" style="margin-bottom:6px">Current Board Preview</div>
                  ${boardHtml}
                </div>
              </div>
            </div>
            <div class="detail-section">
              <div class="meta-line">
                <strong>Reference Assets</strong>
                <span class="muted">${escapeHtml(selectedShot.primary_scene_id || '')}</span>
              </div>
              ${referenceHtml}
            </div>
          </div>
        </div>
      `;
    }

    function selectStoryboardShot(shotId) {
      storyboardSelectedShotId = shotId;
      paintStoryboardReview();
    }

    function setShotVideoFilter(filter) {
      shotVideoFilter = filter;
      paintShotVideosSection();
    }

    function renderFinalVideoPanel(videoPayload) {
      const finalVideo = videoPayload?.final_video || {};
      const summary = videoPayload?.summary || {};
      const summaryHtml = `
        <div class="summary-grid">
          ${renderSummaryBox('shot_count', finalVideo.shot_count || summary.total_shots || 0)}
          ${renderSummaryBox('trim_leading_seconds', finalVideo.trim_leading_seconds ?? 'N/A')}
          ${renderSummaryBox('blackout_leading_seconds', finalVideo.blackout_leading_seconds ?? 'N/A')}
          ${renderSummaryBox('concat_mode', finalVideo.concat_mode || 'N/A')}
        </div>
      `;
      if (!finalVideo.available || !finalVideo.preview_url) {
        return `
          <section class="panel" style="padding:16px">
            <h2>Final Video</h2>
            ${summaryHtml}
            <div class="empty" style="margin-top:14px">最终拼接视频还不存在，完成 final_video stage 后会显示在这里。</div>
          </section>
        `;
      }

      return `
        <section class="panel" style="padding:16px">
          <h2>Final Video</h2>
          <div class="video-hero">
            ${summaryHtml}
            <div class="video-frame">
              <video src="${finalVideo.preview_url}" controls preload="metadata"></video>
            </div>
            <div class="media-actions">
              <button class="text-button" onclick='openMediaModal(${JSON.stringify(finalVideo.preview_url)}, ${JSON.stringify(finalVideo.title || "final video")}, ${JSON.stringify("stitched final output")})'>Inspect Final</button>
              <a class="text-button" href="${finalVideo.preview_url}" target="_blank" rel="noopener noreferrer">Open Final File</a>
            </div>
          </div>
        </section>
      `;
    }

    function paintShotVideosSection() {
      const root = document.getElementById('shot_videos_section_dynamic');
      const filterRoot = document.getElementById('shot_videos_filter_row');
      const metaRoot = document.getElementById('shot_videos_filter_meta');
      if (!root || !filterRoot || !metaRoot) return;

      const shotVideos = videoSummaryCache?.shot_videos || [];
      const statusCounts = shotVideos.reduce((acc, item) => {
        const key = item.status || 'unknown';
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
      const filters = ['all', 'succeeded', 'failed', 'timed_out', 'skipped_not_selected', 'skipped_job_not_ready'];
      filterRoot.innerHTML = filters
        .filter(item => item === 'all' || statusCounts[item])
        .map(item => `
          <button class="chip ${shotVideoFilter === item ? 'active' : ''}" onclick="setShotVideoFilter('${item}')">
            ${item === 'all' ? 'All' : item} · ${item === 'all' ? shotVideos.length : statusCounts[item]}
          </button>
        `)
        .join('');

      const filtered = shotVideos.filter(item => shotVideoFilter === 'all' || item.status === shotVideoFilter);
      metaRoot.textContent = `Showing ${filtered.length} / ${shotVideos.length} shot videos`;

      root.innerHTML = filtered.length ? `
        <div class="video-grid">
          ${filtered.map(item => `
            <div class="video-card">
              ${item.preview_url ? `<video class="media-thumb" src="${item.preview_url}" controls preload="metadata"></video>` : `<div class="media-thumb"></div>`}
              <div class="video-body">
                <div class="meta-line">
                  <strong>${escapeHtml(item.shot_id || 'shot')}</strong>
                  ${statusTag(item.status)}
                </div>
                <div class="muted">order ${escapeHtml(item.order || '')}</div>
                <div class="muted">segments: ${escapeHtml((item.segment_ids || []).join(', ') || 'N/A')}</div>
                ${item.error_message ? `<div class="muted">${escapeHtml(item.error_message)}</div>` : ''}
                <div class="media-actions">
                  ${item.preview_url ? `<button class="text-button" onclick='openMediaModal(${JSON.stringify(item.preview_url)}, ${JSON.stringify(item.shot_id || "shot video")}, ${JSON.stringify(item.status || "")}, ${JSON.stringify(item.external_url || item.preview_url)})'>Inspect</button>` : ''}
                  ${item.preview_url ? `<a class="text-button" href="${item.preview_url}" target="_blank" rel="noopener noreferrer">Open Local</a>` : ''}
                  ${item.external_url ? `<a class="text-button" href="${item.external_url}" target="_blank" rel="noopener noreferrer">Open Remote</a>` : ''}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      ` : '<div class="empty">当前筛选条件下没有分镜视频。</div>';
    }

    function renderShotVideosPanel(videoPayload) {
      const summary = videoPayload?.summary || {};
      return `
        <section class="panel" style="padding:16px">
          <h2>Shot Videos</h2>
          <div class="summary-grid">
            ${renderSummaryBox('total_shots', summary.total_shots || 0)}
            ${renderSummaryBox('succeeded_shots', summary.succeeded_shots || 0)}
            ${renderSummaryBox('failed_or_other', summary.failed_shots || 0)}
            ${renderSummaryBox('has_final_video', summary.has_final_video ? 'true' : 'false')}
          </div>
          <div class="video-filter-bar" style="margin-top:14px">
            <div id="shot_videos_filter_row" class="chip-row"></div>
            <div id="shot_videos_filter_meta" class="muted"></div>
          </div>
          <div id="shot_videos_section_dynamic" style="margin-top:14px"></div>
        </section>
      `;
    }

    async function submitReview(stage, status) {
      if (!selectedRunId) return;
      const reviewer = document.getElementById(`reviewer_${stage}`)?.value || '';
      const notes = document.getElementById(`notes_${stage}`)?.value || '';
      await api(`/api/runs/${selectedRunId}/reviews/${stage}`, {
        method: 'POST',
        body: JSON.stringify({status, reviewer, notes, metadata: {source: 'console'}}),
      });
      await loadRunDetail(selectedRunId);
    }

    async function loadRuns() {
      const payload = await api('/api/runs?limit=50');
      const runs = payload.runs || [];
      const root = document.getElementById('runs');
      if (!runs.length) {
        root.innerHTML = '<div class="empty">当前还没有 run。</div>';
        return;
      }
      root.innerHTML = runs.map(run => `
        <div class="run-card ${run.run_id === selectedRunId ? 'active' : ''}" onclick="selectRun('${run.run_id}')">
          <div class="run-top">
            <div class="run-id">${run.run_id}</div>
            ${statusTag(run.status)}
          </div>
          <div class="muted">${run.source_script_name || 'unnamed source'}</div>
          <div class="meta-line" style="margin-top:10px">
            <span class="muted">${run.current_stage || 'idle'}</span>
            <span class="muted">${run.updated_at || ''}</span>
          </div>
        </div>
      `).join('');
    }

    async function selectRun(runId) {
      selectedRunId = runId;
      assetImageFilter = 'all';
      assetImageQuery = '';
      storyboardSelectedShotId = '';
      shotVideoFilter = 'all';
      await loadRuns();
      await loadRunDetail(runId);
    }

    async function createRun() {
      const payload = {
        source_script_name: document.getElementById('source_script_name').value,
        input_mode: 'auto',
        execution_mode: document.getElementById('execution_mode').value,
        run_dir: '',
        source_path: '',
        source_text: document.getElementById('source_text').value,
        parallel_planning: document.getElementById('parallel_planning').value === 'true',
      };
      const statusBox = document.getElementById('create_status');
      statusBox.textContent = '正在提交任务...';
      try {
        const result = await api('/api/runs', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        statusBox.textContent = `任务已提交: ${result.task_id || 'sync-result'} / ${result.run_id || result.run_dir || ''}`;
        if (result.run_id) {
          selectedRunId = result.run_id;
          assetImageFilter = 'all';
          assetImageQuery = '';
          storyboardSelectedShotId = '';
          shotVideoFilter = 'all';
        }
        await loadRuns();
        if (selectedRunId) {
          await loadRunDetail(selectedRunId);
        }
      } catch (error) {
        statusBox.textContent = `提交失败: ${error.message}`;
      }
    }

    async function continueRun() {
      if (!selectedRunId) return;
      const result = await api(`/api/runs/${selectedRunId}/continue`, {
        method: 'POST',
        body: JSON.stringify({parallel_planning: false}),
      });
      await loadRunDetail(selectedRunId);
      alert(`continue task submitted: ${result.task_id}`);
    }

    async function rerunStage() {
      if (!selectedRunId) return;
      const stage = document.getElementById('rerun_stage').value;
      const result = await api(`/api/runs/${selectedRunId}/rerun-stage/${stage}`, {
        method: 'POST',
        body: JSON.stringify({force: true}),
      });
      await loadRunDetail(selectedRunId);
      alert(`rerun task submitted: ${result.task_id}`);
    }

    async function loadRunDetail(runId) {
      const [runPayload, artifactPayload, eventPayload, taskPayload, videoPayload, reviewsPayload, upstreamReview, assetReview, storyboardReview] = await Promise.all([
        api(`/api/runs/${runId}`),
        api(`/api/runs/${runId}/artifacts`),
        api(`/api/runs/${runId}/events?limit=30`),
        api(`/api/runs/${runId}/tasks?limit=12`),
        safeApi(`/api/runs/${runId}/videos`),
        safeApi(`/api/runs/${runId}/reviews`),
        safeApi(`/api/runs/${runId}/reviews/upstream`),
        safeApi(`/api/runs/${runId}/reviews/asset_images`),
        safeApi(`/api/runs/${runId}/reviews/storyboard`),
      ]);

      const runState = runPayload.run_state || {};
      const stages = runState.stages || {};
      const stageOrder = runState.stage_order || [];
      const artifacts = artifactPayload.artifacts || [];
      const events = (eventPayload.events || []).slice().reverse();
      const tasks = taskPayload.tasks || [];
      const reviewSummary = reviewsPayload?.reviews?.reviews || {};

      const stageCards = stageOrder.map(stageName => {
        const stage = stages[stageName] || {};
        return `
          <div class="stage-card">
            <div class="meta-line">
              <strong>${stageName}</strong>
              ${statusTag(stage.status)}
            </div>
            ${stage.preview_headline ? `<div class="muted" style="margin-top:8px">${escapeHtml(stage.preview_headline)}</div>` : ''}
            <div class="muted" style="margin-top:8px">${escapeHtml(stage.preview_text || stage.message || 'No stage summary yet.')}</div>
            <div class="muted" style="margin-top:10px">${stage.updated_at || ''}</div>
          </div>
        `;
      }).join('');

      const artifactRows = artifacts.filter(item => item.exists).map(item => `
        <div class="artifact-row">
          <div class="meta-line">
            <strong>${item.key}</strong>
            <span class="tag">${item.kind}</span>
          </div>
          <div class="code">${item.path}</div>
          <div style="margin-top:8px">
            ${item.preview_url ? `<a href="${item.preview_url}" target="_blank" rel="noopener noreferrer">open artifact</a>` : ''}
          </div>
        </div>
      `).join('') || '<div class="empty">暂无可展示产物。</div>';

      const eventRows = events.map(event => `
        <div class="event-row">
          <div class="meta-line">
            <strong>${event.event_type || 'event'}</strong>
            <span class="muted">${event.timestamp || ''}</span>
          </div>
          <div class="muted">${event.stage || ''}</div>
          <div>${event.message || ''}</div>
        </div>
      `).join('') || '<div class="empty">当前没有事件记录。</div>';

      const taskRows = tasks.map(task => `
        <div class="task-row">
          <div class="meta-line">
            <strong>${task.action}</strong>
            ${statusTag(task.status)}
          </div>
          <div class="muted">${task.task_id}</div>
          <div class="muted">${task.stage || ''}</div>
          <div>${task.error || ''}</div>
        </div>
      `).join('') || '<div class="empty">当前没有后台任务。</div>';

      const reviewOverview = ['upstream', 'asset_images', 'storyboard'].map(stage => `
        <span class="pill">${stage}: ${reviewSummary?.[stage]?.status || 'pending'}</span>
      `).join('');

      assetReviewCache = assetReview || null;
      storyboardReviewCache = storyboardReview || null;
      videoSummaryCache = videoPayload || null;
      const storyboardShots = storyboardReviewCache?.payload?.shots || [];
      if (!storyboardShots.some(shot => shot.shot_id === storyboardSelectedShotId)) {
        storyboardSelectedShotId = storyboardShots[0]?.shot_id || '';
      }

      document.getElementById('run_detail_panel').innerHTML = `
        <div class="detail-head">
          <div>
            <h2>${runId}</h2>
            <div class="muted">${runState.source_script_name || 'unnamed source'}</div>
            <div class="hero-meta" style="margin-top:10px">
              ${statusTag(runState.status)}
              <span class="pill">current_stage: ${runState.current_stage || 'idle'}</span>
              ${runState.awaiting_approval_stage ? `<span class="pill">awaiting: ${runState.awaiting_approval_stage}</span>` : ''}
              <span class="pill">updated: ${runState.updated_at || ''}</span>
              ${reviewOverview}
            </div>
          </div>
          <div class="detail-actions">
            <button class="secondary" onclick="loadRunDetail('${runId}')">Refresh</button>
            <button class="ghost" onclick="continueRun()">Continue</button>
            <select id="rerun_stage">
              ${stageOptions.map(stage => `<option value="${stage}">${stage}</option>`).join('')}
            </select>
            <button onclick="rerunStage()">Force Rerun Stage</button>
          </div>
        </div>

        <section class="panel" style="padding:16px; margin-top:18px">
          <h2>Stages</h2>
          <div class="stage-grid">${stageCards}</div>
        </section>

        <section class="panel" style="padding:16px">
          <h2>Reviews</h2>
          <div class="review-grid">
            ${renderUpstreamReview(upstreamReview)}
            ${renderAssetImagesReview(assetReview)}
            ${renderStoryboardReview(storyboardReview)}
          </div>
        </section>

        ${renderShotVideosPanel(videoSummaryCache)}

        ${renderFinalVideoPanel(videoSummaryCache)}

        <section class="panel" style="padding:16px">
          <h2>Tasks</h2>
          <div class="task-list">${taskRows}</div>
        </section>

        <section class="panel" style="padding:16px">
          <h2>Artifacts</h2>
          <div class="artifact-list">${artifactRows}</div>
        </section>

        <section class="panel" style="padding:16px">
          <h2>Recent Events</h2>
          <div class="event-list">${eventRows}</div>
        </section>
      `;

      paintAssetImagesReview();
      paintStoryboardReview();
      paintShotVideosSection();
    }

    async function pollCurrentRun() {
      if (!selectedRunId) {
        return;
      }
      if (isMediaModalOpen() || hasActiveVideoPlayback()) {
        return;
      }
      try {
        await loadRunDetail(selectedRunId);
        await loadRuns();
      } catch (error) {
        console.error(error);
      }
    }

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        closeMediaModal();
      }
    });

    loadRuns().catch(console.error);
    setInterval(pollCurrentRun, 6000);
  </script>
</body>
</html>
"""


def create_ui_app() -> FastAPI:
    app = create_api_app()

    @app.get("/", response_class=HTMLResponse)
    def console_home() -> HTMLResponse:
        return HTMLResponse(build_console_html())

    return app
