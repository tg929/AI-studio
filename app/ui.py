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
  <title>AI Studio 制作台</title>
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
    .workbench-shell {
      display: grid;
      gap: 16px;
    }
    .action-panel {
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.88), rgba(255, 249, 241, 0.82));
    }
    .action-panel h2 {
      margin-bottom: 8px;
    }
    .action-text {
      font-size: 24px;
      line-height: 1.35;
      letter-spacing: -0.02em;
    }
    .workbench-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }
    .timeline-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .timeline-item {
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      display: grid;
      gap: 4px;
    }
    .timeline-item.active {
      border-color: rgba(29, 91, 99, 0.24);
      background: rgba(29, 91, 99, 0.08);
    }
    .timeline-item.complete {
      border-color: rgba(44, 122, 75, 0.18);
      background: rgba(44, 122, 75, 0.08);
    }
    .timeline-item.pending {
      opacity: 0.72;
    }
    .timeline-kicker {
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .hint-line {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid rgba(30, 34, 32, 0.08);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .workspace-summary {
      display: grid;
      gap: 8px;
      margin-top: 14px;
    }
    .event-list {
      display: grid;
      gap: 8px;
    }
    .event-row {
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
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
        <h1>AI Studio 制作台</h1>
        <div class="lead">
          这一版界面直接面向创作流程操作，不再强调底层工程细节。
          你可以在这里发起任务、观察进度、处理中断节点，并查看当前最重要的产出内容。
        </div>
        <div class="hero-meta">
          <span class="pill">纯 Python 实现</span>
          <span class="pill">运行状态可恢复</span>
          <span class="pill">支持按阶段重跑</span>
          <span class="pill">本地控制台界面</span>
        </div>
      </div>
      <div class="hero-card hero-side">
        <div>
          <strong>当前重点</strong>
          <p>先让你能稳定地发起任务、查看过程、确认关键节点，并清楚知道系统现在正在做什么。</p>
        </div>
        <div>
          <strong>常用操作</strong>
          <p>新建任务、查看状态、继续执行、重跑某个阶段，以及检查当前最重要的中间结果。</p>
        </div>
      </div>
    </section>

    <section class="layout">
      <aside class="stack">
        <div class="panel">
          <h2>新建任务</h2>
          <div class="stack">
            <label>项目名称
              <input id="source_script_name" placeholder="例如：斗气大陆第一幕" />
            </label>
            <label>处理范围
              <select id="execution_mode">
                <option value="mainline">完整流程</option>
                <option value="upstream_only">仅准备剧本</option>
              </select>
            </label>
            <label>输入内容
              <textarea id="source_text" placeholder="输入关键词、简介或完整剧本。系统会自动判断输入类型，并选择合适的处理路径。"></textarea>
            </label>
            <label>提前准备镜头草稿
              <select id="parallel_planning">
                <option value="true">开启</option>
                <option value="false">关闭</option>
              </select>
            </label>
            <div class="actions">
              <button onclick="createRun()">开始执行</button>
              <button class="secondary" onclick="loadRuns()">刷新列表</button>
            </div>
            <div id="create_status" class="status">等待操作。</div>
          </div>
        </div>

        <div class="panel">
          <div class="meta-line">
            <h2 style="margin:0">任务列表</h2>
            <button class="ghost" onclick="loadRuns()">刷新</button>
          </div>
          <div id="runs" class="runs"></div>
        </div>
      </aside>

      <main class="detail-grid">
        <div class="panel" id="run_detail_panel">
          <div class="empty">请先从左侧选择任务，或直接新建一个任务。</div>
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
      {value: 'upstream', label: '剧本准备'},
      {value: 'asset_extraction', label: '提取角色与场景'},
      {value: 'style_bible', label: '统一风格设定'},
      {value: 'asset_prompts', label: '生成参考资产说明'},
      {value: 'asset_images', label: '生成参考资产图'},
      {value: 'storyboard_seed', label: '预排镜头'},
      {value: 'storyboard', label: '正式分镜'},
      {value: 'shot_reference_boards', label: '拼接镜头参考板'},
      {value: 'board_publish', label: '发布参考板链接'},
      {value: 'video_jobs', label: '整理视频生成任务'},
      {value: 'shot_videos', label: '生成分镜视频'},
      {value: 'final_video', label: '拼接最终成片'},
    ];
    const processSteps = ['输入接收', '系统判断', '剧本准备', '资产建立', '参考资产', '正式分镜'];

    let selectedRunId = '';
    let activeTaskId = '';
    let activeRunId = '';
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

    function humanizeStatus(status) {
      const labels = {
        pending: '待处理',
        queued: '排队中',
        running: '执行中',
        succeeded: '已完成',
        failed: '执行失败',
        blocked: '已阻塞',
        partial: '部分完成',
        awaiting_approval: '等待确认',
        skipped: '已跳过',
        timed_out: '超时',
        skipped_not_selected: '未选中',
        skipped_job_not_ready: '未准备好',
        approved: '已通过',
        rejected: '已退回',
      };
      return labels[status] || status || '未知状态';
    }

    function statusTag(status) {
      return `<span class="tag ${status || ''}">${escapeHtml(humanizeStatus(status || ''))}</span>`;
    }

    function formatLocalTimestamp(value) {
      const text = String(value || '').trim();
      if (!text) return '';
      const date = new Date(text);
      if (Number.isNaN(date.getTime())) return text;
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hour = String(date.getHours()).padStart(2, '0');
      const minute = String(date.getMinutes()).padStart(2, '0');
      const second = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
    }

    function renderStageTime(stage) {
      const label = String(stage?.display_time_label || '').trim();
      const timestamp = String(stage?.display_time_at || '').trim();
      if (!label) return '';
      if (!timestamp) return label;
      return `${label} ${formatLocalTimestamp(timestamp)}`;
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
      const display = Array.isArray(value) ? value.join('、') : String(value || '暂无');
      return `
        <div class="summary-box">
          <strong>${escapeHtml(label)}</strong>
          <div class="muted">${escapeHtml(display)}</div>
        </div>
      `;
    }

    function humanizeStageName(stageName) {
      const labels = Object.fromEntries(stageOptions.map(option => [option.value, option.label]));
      return labels[stageName] || stageName || '当前阶段';
    }

    function humanizeExecutionMode(mode) {
      const labels = {
        mainline: '完整流程',
        upstream_only: '仅准备剧本',
      };
      return labels[mode] || mode || '默认执行';
    }

    function humanizeSourceKind(sourceKind) {
      const labels = {
        keywords: '关键词',
        brief: '简述',
        full_script: '完整剧本',
        script: '完整剧本',
        mixed: '混合输入',
        unknown: '待判断',
      };
      return labels[sourceKind] || sourceKind || '待判断';
    }

    function humanizeChosenPath(path) {
      const labels = {
        direct_extract: '直接进入资产链路',
        compress_then_extract: '先压缩再进入资产链路',
        rewrite_then_extract: '先重写再进入资产链路',
        expand_then_extract: '先扩写再进入资产链路',
        confirm_then_continue: '先停下等待确认',
        pending: '待判断',
      };
      return labels[path] || path || '待判断';
    }

    function humanizeOperation(operation) {
      const labels = {
        expand: '扩写剧情',
        compress: '压缩收束剧情',
        rewrite_for_asset_clarity: '补强人物与场景细节',
      };
      return labels[operation] || operation || '待处理';
    }

    function humanizeOperationList(operations) {
      if (!Array.isArray(operations) || !operations.length) {
        return ['暂无'];
      }
      return operations.map(humanizeOperation);
    }

    function humanizeTaskStatus(status) {
      return humanizeStatus(status);
    }

    function humanizeReviewStage(stage) {
      const labels = {
        upstream: '剧本准备确认',
        asset_images: '参考资产确认',
        storyboard: '分镜确认',
      };
      return labels[stage] || stage || '待确认';
    }

    function humanizeEventType(eventType) {
      const labels = {
        task_queued: '任务已排队',
        task_started: '任务已开始',
        task_finished: '任务已结束',
        task_failed: '任务执行失败',
        operator_progress: '系统正在处理',
        stage_started: '阶段开始',
        stage_succeeded: '阶段完成',
        stage_failed: '阶段失败',
        stage_blocked: '阶段已阻塞',
        approval_required: '等待确认',
        review_reset: '确认状态已重置',
      };
      return labels[eventType] || eventType || '执行事件';
    }

    function buildRouteDecisionHeadline(routeDecision) {
      const sourceKind = humanizeSourceKind(routeDecision?.source_kind);
      const chosenPath = humanizeChosenPath(routeDecision?.chosen_path);
      return `识别为${sourceKind}，系统将${chosenPath}。`;
    }

    function renderRouteDecisionCore(routeDecision) {
      const projectTarget = routeDecision?.project_target || {};
      const reasoning = truncate(routeDecision?.reasoning_summary || '系统正在整理这次输入的判断依据。', 180);
      const operatorHint = truncate(routeDecision?.operator_hint || '', 90);
      return `
        <div class="summary-box">
          <strong>本次判断</strong>
          <div>${escapeHtml(buildRouteDecisionHeadline(routeDecision))}</div>
        </div>
        <div class="summary-grid">
          ${renderSummaryBox('输入判定', humanizeSourceKind(routeDecision?.source_kind))}
          ${renderSummaryBox('执行路径', humanizeChosenPath(routeDecision?.chosen_path))}
          ${renderSummaryBox('目标时长', projectTarget.target_runtime_sec || '暂无')}
          ${renderSummaryBox('目标镜头', projectTarget.target_shot_count || '暂无')}
        </div>
        <div class="workspace-summary">
          <div class="summary-box">
            <strong>判断依据</strong>
            <div class="muted">${escapeHtml(reasoning)}</div>
          </div>
        </div>
        ${operatorHint ? `<div class="hint-line">提示：${escapeHtml(operatorHint)}</div>` : ''}
      `;
    }

    function stageToProcessStep(stageName) {
      if (!stageName) return '输入接收';
      if (stageName === 'upstream') return '剧本准备';
      if (['asset_extraction', 'style_bible', 'asset_prompts'].includes(stageName)) return '资产建立';
      if (stageName === 'asset_images') return '参考资产';
      if (['storyboard_seed', 'storyboard', 'shot_reference_boards', 'board_publish', 'video_jobs', 'shot_videos', 'final_video'].includes(stageName)) {
        return '正式分镜';
      }
      return '剧本准备';
    }

    function resolveTaskProcessStep(task, runPayload) {
      const taskStep = processSteps.includes(task?.progress_step) ? task.progress_step : '';
      const runStep = stageToProcessStep(runPayload?.run_state?.current_stage || task?.progress_stage || '');
      if (!taskStep) {
        return runStep;
      }
      const taskIndex = processSteps.indexOf(taskStep);
      const runIndex = processSteps.indexOf(runStep);
      return runIndex > taskIndex ? runStep : taskStep;
    }

    function fallbackCurrentAction(task, runPayload) {
      const runState = runPayload?.run_state || {};
      const taskMessage = String(task?.progress_message || '').trim();
      const taskStage = String(task?.progress_stage || '').trim();
      const runStage = String(runState.current_stage || '').trim();
      const genericResumeMessages = new Set([
        '任务已提交，正在等待后台执行。',
        '任务已提交，正在创建工作空间。',
        '正在恢复已有运行目录。',
      ]);
      const taskMessageLooksStale = (
        taskMessage
        && genericResumeMessages.has(taskMessage)
        && taskStage === 'upstream'
        && runStage
        && runStage !== 'upstream'
      );
      if (taskMessage && !taskMessageLooksStale) {
        return taskMessage;
      }
      if (runState.awaiting_approval_stage) {
        return `当前产物已生成，请先确认${humanizeReviewStage(runState.awaiting_approval_stage)}后继续。`;
      }
      const stageName = runState.current_stage || task?.progress_stage || '';
      const labels = {
        upstream: '正在整理标准剧本输入。',
        asset_extraction: '正在抽取角色、场景和道具。',
        style_bible: '正在建立统一风格基线。',
        asset_prompts: '正在整理参考资产生成说明。',
        asset_images: '正在生成参考资产图。',
        storyboard: '正在生成生产级分镜。',
      };
      return labels[stageName] || '系统正在处理当前任务。';
    }

    function renderProcessTimeline(task, runPayload) {
      const currentStep = resolveTaskProcessStep(task, runPayload);
      const currentIndex = Math.max(0, processSteps.indexOf(currentStep));
      const taskStatus = task?.status || 'running';
      return `
        <section class="panel" style="padding:16px">
          <h2>执行流程</h2>
          <div class="timeline-list">
            ${processSteps.map((step, index) => {
              let statusClass = 'pending';
              let statusText = '待开始';
              if (index < currentIndex || (taskStatus === 'succeeded' && index <= currentIndex)) {
                statusClass = 'complete';
                statusText = '已完成';
              } else if (index === currentIndex) {
                statusClass = taskStatus === 'failed' || taskStatus === 'blocked' ? 'failed' : 'active';
                statusText = taskStatus === 'failed' || taskStatus === 'blocked' ? '异常中断' : '处理中';
              }
              return `
                <div class="timeline-item ${statusClass}">
                  <div class="meta-line">
                    <strong>${escapeHtml(step)}</strong>
                    <span class="timeline-kicker">${escapeHtml(statusText)}</span>
                  </div>
                  <div class="muted">${index === currentIndex ? escapeHtml(fallbackCurrentAction(task, runPayload)) : ' '}</div>
                </div>
              `;
            }).join('')}
          </div>
        </section>
      `;
    }

    function renderCurrentArtifactSummary(task, runPayload) {
      if (!runPayload) {
        return `
          <section class="panel" style="padding:16px">
            <h2>当前产物摘要</h2>
            <div class="summary-box">
              <strong>系统正在准备</strong>
              <div class="muted">${escapeHtml(task?.progress_message || '任务已提交，正在创建工作空间。')}</div>
            </div>
          </section>
        `;
      }

      const routeDecision = runPayload.route_decision || {};
      const runState = runPayload.run_state || {};
      const currentStageName = runState.current_stage || task?.progress_stage || 'upstream';
      const stagePayload = (runState.stages || {})[currentStageName] || (runState.stages || {}).upstream || {};

      if (routeDecision.available && resolveTaskProcessStep(task, runPayload) === '系统判断') {
        return `
          <section class="panel" style="padding:16px">
            <h2>当前产物摘要</h2>
            ${renderRouteDecisionCore(routeDecision)}
          </section>
        `;
      }

      return `
        <section class="panel" style="padding:16px">
          <h2>当前产物摘要</h2>
          <div class="summary-box">
            <strong>${escapeHtml(stagePayload.preview_headline || humanizeStageName(currentStageName) || '当前阶段')}</strong>
            <div class="muted">${escapeHtml(stagePayload.preview_text || stagePayload.message || fallbackCurrentAction(task, runPayload))}</div>
          </div>
        </section>
      `;
    }

    function renderActiveTaskPanel(task, runPayload, events) {
      const runState = runPayload?.run_state || {};
      const latestRunId = task?.run_id || runState.run_id || activeRunId || '待分配';
      const recentEvents = (events || []).slice(-5).reverse();
      const eventRows = recentEvents.length ? recentEvents.map(event => `
        <div class="event-row">
          <div class="meta-line">
            <strong>${escapeHtml(event.message || humanizeEventType(event.event_type || '') || '执行事件')}</strong>
            <span class="muted">${escapeHtml(event.timestamp || '')}</span>
          </div>
          <div class="muted">${escapeHtml(humanizeStageName(event.stage || '') || '')}</div>
        </div>
      `).join('') : '<div class="empty">系统正在准备更多过程信息。</div>';

      return `
        <div class="workbench-shell">
          <section class="action-panel">
            <div class="timeline-kicker">当前任务</div>
            <div class="action-text">${escapeHtml(fallbackCurrentAction(task, runPayload))}</div>
            <div class="workbench-meta">
              <span class="pill">任务编号：${escapeHtml(task?.task_id || '')}</span>
              <span class="pill">任务目录：${escapeHtml(latestRunId)}</span>
              <span class="pill">状态：${escapeHtml(humanizeTaskStatus(task?.status || 'running'))}</span>
              <span class="pill">流程：${escapeHtml(resolveTaskProcessStep(task, runPayload))}</span>
            </div>
          </section>
          ${renderProcessTimeline(task, runPayload)}
          ${renderCurrentArtifactSummary(task, runPayload)}
          <section class="panel" style="padding:16px">
            <div class="meta-line">
              <h2 style="margin:0">执行过程</h2>
              ${task?.run_id ? `<button class="ghost" onclick="focusRunDetail()">查看完整详情</button>` : ''}
            </div>
            <div class="event-list" style="margin-top:14px">${eventRows}</div>
          </section>
        </div>
      `;
    }

    function renderIntoDetailPanel(html, options = {}) {
      const root = document.getElementById('run_detail_panel');
      if (!root) return;
      const preserveViewport = Boolean(options.preserveViewport);
      const scrollY = preserveViewport ? window.scrollY : 0;
      root.innerHTML = html;
      if (preserveViewport) {
        requestAnimationFrame(() => {
          const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
          window.scrollTo({top: Math.min(scrollY, maxScroll), behavior: 'auto'});
        });
      }
    }

    function renderReviewSection(stage, title, reviewPayload, bodyHtml) {
      const review = reviewPayload?.review || {status: 'pending', reviewer: '', notes: ''};
      return `
        <section class="review-card">
          <div class="review-toolbar">
            <div>
              <h3>${escapeHtml(title)}</h3>
              <div class="muted">审核人：${escapeHtml(review.reviewer || '未填写')}</div>
            </div>
            ${statusTag(review.status)}
          </div>
          ${bodyHtml}
          <div class="review-form">
            <div class="row">
              <label>审核人
                <input class="compact-input" id="reviewer_${stage}" value="${escapeHtml(review.reviewer || '')}" placeholder="填写处理人姓名" />
              </label>
              <label>更新时间
                <input class="compact-input" value="${escapeHtml(formatLocalTimestamp(review.updated_at || ''))}" readonly />
              </label>
            </div>
            <label>备注
              <textarea id="notes_${stage}" placeholder="记录通过原因、问题点或返工建议。">${escapeHtml(review.notes || '')}</textarea>
            </label>
            <div class="review-actions">
              <button class="approve" onclick="submitReview('${stage}', 'approved')">确认通过</button>
              <button class="reject" onclick="submitReview('${stage}', 'rejected')">退回调整</button>
              <button class="pending" onclick="submitReview('${stage}', 'pending')">标记待处理</button>
            </div>
          </div>
        </section>
      `;
    }

    function renderRouteDecisionPanel(routeDecision) {
      if (!routeDecision || !routeDecision.available) {
        return `
          <section class="panel" style="padding:16px">
            <h2>系统判断</h2>
            <div class="empty" style="margin-top:14px">当前任务还没有可展示的系统判断。</div>
          </section>
        `;
      }

      return `
        <section class="panel" style="padding:16px; margin-top:18px">
          <h2>系统判断</h2>
          ${renderRouteDecisionCore(routeDecision)}
        </section>
      `;
    }

    function renderUpstreamReview(reviewPayload) {
      const payload = reviewPayload?.payload || {};
      const summary = payload.summary || {};
      const artifacts = payload.artifacts || {};
      const summaryHtml = `
        <div class="summary-grid">
          ${renderSummaryBox('执行路径', humanizeChosenPath(summary.chosen_path))}
          ${renderSummaryBox('系统会做什么', humanizeOperationList(summary.recommended_operations))}
          ${renderSummaryBox('可继续进入资产阶段', summary.ready_for_extraction ? '是' : '否')}
          ${renderSummaryBox('阻塞问题', summary.blocking_issues || [])}
        </div>
      `;
      const routerJson = artifacts['intake_router.json'] ? JSON.stringify(artifacts['intake_router.json'], null, 2) : '暂无路由判断结果';
      const readinessJson = artifacts['asset_readiness_report.json'] ? JSON.stringify(artifacts['asset_readiness_report.json'], null, 2) : '暂无可读性检查结果';
      const scriptPreview = artifacts['script_clean.txt'] ? truncate(artifacts['script_clean.txt'], 900) : '暂无标准剧本';
      const bodyHtml = `
        ${summaryHtml}
        <div class="stack" style="margin-top:14px">
          <div>
            <div class="muted" style="margin-bottom:6px">系统判断详情</div>
            <div class="json-box">${escapeHtml(routerJson)}</div>
          </div>
          <div>
            <div class="muted" style="margin-bottom:6px">可继续执行检查</div>
            <div class="json-box">${escapeHtml(readinessJson)}</div>
          </div>
          <div>
            <div class="muted" style="margin-bottom:6px">当前标准剧本</div>
            <div class="json-box">${escapeHtml(scriptPreview)}</div>
          </div>
        </div>
      `;
      return renderReviewSection('upstream', '剧本准备确认', reviewPayload, bodyHtml);
    }

    function humanizeGroup(group) {
      const labels = {
        all: '全部',
        characters: '人物',
        scenes: '场景',
        props: '道具',
        character: '人物',
        scene: '场景',
        prop: '道具',
      };
      return labels[group] || group || '未知';
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
      return `<img class="media-thumb" src="${raw}" alt="${escapeHtml(alt || '预览图')}" />`;
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
        : `<img src="${url}" alt="${escapeHtml(title || '预览图')}" />`;
      meta.innerHTML = `
        <div class="meta-line">
          <strong>${escapeHtml(title || '预览')}</strong>
          ${externalUrl ? `<a class="text-button" href="${externalUrl}" target="_blank" rel="noopener noreferrer">打开来源</a>` : ''}
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
          ${renderSummaryBox('人物', summary.character_count)}
          ${renderSummaryBox('场景', summary.scene_count)}
          ${renderSummaryBox('道具', summary.prop_count)}
        </div>
      `;
      const bodyHtml = `
        <div class="review-shell">
          ${summaryHtml}
          <div class="review-note">按资产类型筛选，支持按名称或编号搜索。点击缩略图可以直接在控制台里放大检查。</div>
          <div class="review-controls">
            <div id="asset_images_filter_row" class="chip-row"></div>
            <input
              id="asset_images_query"
              class="review-search"
              placeholder="搜索资产名称、编号或标签"
              value="${escapeHtml(assetImageQuery)}"
              oninput="updateAssetImageQuery(this.value)"
            />
          </div>
          <div id="asset_images_filter_meta" class="muted"></div>
          <div id="asset_images_review_dynamic"></div>
        </div>
      `;
      return renderReviewSection('asset_images', '参考资产确认', reviewPayload, bodyHtml);
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
      metaRoot.textContent = `当前显示 ${filtered.length} / ${items.length} 张参考资产`;

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
                  ${item.preview_url ? `<button class="text-button" onclick='openMediaModal(${JSON.stringify(item.preview_url)}, ${JSON.stringify(item.name || item.id)}, ${JSON.stringify(item.label_text || item.group || "")})'>查看大图</button>` : ''}
                  ${item.preview_url ? `<a class="text-button" href="${item.preview_url}" target="_blank" rel="noopener noreferrer">打开本地文件</a>` : ''}
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
            ${renderSummaryBox('标题', summary.title)}
            ${renderSummaryBox('镜头数', summary.shot_count)}
          </div>
          <div class="review-note">左侧快速切换镜头，右侧集中查看镜头描述、镜头参数、关联参考资产和已有参考板。</div>
          <div id="storyboard_review_dynamic"></div>
        </div>
      `;
      return renderReviewSection('storyboard', '分镜确认', reviewPayload, bodyHtml);
    }

    function paintStoryboardReview() {
      const root = document.getElementById('storyboard_review_dynamic');
      if (!root) return;
      const shots = storyboardReviewCache?.payload?.shots || [];
      if (!shots.length) {
        root.innerHTML = '<div class="empty">当前还没有可查看的正式分镜。</div>';
        return;
      }

      if (!storyboardSelectedShotId || !shots.some(shot => shot.shot_id === storyboardSelectedShotId)) {
        storyboardSelectedShotId = shots[0].shot_id;
      }
      const selectedShot = shots.find(shot => shot.shot_id === storyboardSelectedShotId) || shots[0];

      const railHtml = shots.map(shot => `
        <button class="shot-nav-card ${shot.shot_id === storyboardSelectedShotId ? 'active' : ''}" onclick='selectStoryboardShot(${JSON.stringify(shot.shot_id)})'>
          <div class="meta-line">
            <strong>${escapeHtml(shot.shot_id || '镜头')}</strong>
            <span class="muted">#${escapeHtml(shot.order || '')}</span>
          </div>
          <div class="muted">${escapeHtml(shot.shot_type || '镜头')}</div>
          <div style="margin-top:8px">${escapeHtml(truncate(shot.summary || '', 90))}</div>
        </button>
      `).join('');

      const referenceAssets = selectedShot.reference_assets || [];
      const boardHtml = selectedShot.board_preview_url ? `
        <div class="board-frame">
          <button class="media-thumb-button" onclick='openMediaModal(${JSON.stringify(selectedShot.board_preview_url)}, ${JSON.stringify(selectedShot.shot_id + " 参考板")}, ${JSON.stringify(selectedShot.board_layout_template || "")}, ${JSON.stringify(selectedShot.board_public_url || selectedShot.board_preview_url)})'>
            ${renderMediaElement(selectedShot.board_preview_url, (selectedShot.shot_id || '镜头') + ' 参考板')}
          </button>
        </div>
        <div class="media-actions">
          <button class="text-button" onclick='openMediaModal(${JSON.stringify(selectedShot.board_preview_url)}, ${JSON.stringify(selectedShot.shot_id + " 参考板")}, ${JSON.stringify(selectedShot.board_layout_template || "")}, ${JSON.stringify(selectedShot.board_public_url || selectedShot.board_preview_url)})'>查看参考板</button>
          ${selectedShot.board_public_url ? `<a class="text-button" href="${selectedShot.board_public_url}" target="_blank" rel="noopener noreferrer">打开公开链接</a>` : ''}
        </div>
      ` : '<div class="empty">当前还没有可预览的镜头参考板。</div>';

      const referenceHtml = referenceAssets.length
        ? `<div class="reference-strip">${referenceAssets.map(renderReferenceAssetCard).join('')}</div>`
        : '<div class="empty">当前镜头还没有可展示的参考资产。</div>';

      const continuityNotes = Array.isArray(selectedShot.continuity_notes) ? selectedShot.continuity_notes : [];
      root.innerHTML = `
        <div class="review-split">
          <div class="review-rail">${railHtml}</div>
          <div class="review-detail">
            <div class="meta-line">
              <div>
                <h3>${escapeHtml(selectedShot.shot_id || '镜头')}</h3>
                <div class="muted">${escapeHtml(selectedShot.summary || '')}</div>
              </div>
              ${statusTag(storyboardReviewCache?.review?.status || 'pending')}
            </div>
            <div class="micro-grid">
              <div class="micro-card"><strong>镜头类型</strong><div>${escapeHtml(selectedShot.shot_type || '暂无')}</div></div>
              <div class="micro-card"><strong>镜头参数</strong><div>${escapeHtml([selectedShot.shot_size, selectedShot.camera_angle, selectedShot.camera_movement].filter(Boolean).join(' / ') || '暂无')}</div></div>
              <div class="micro-card"><strong>情绪氛围</strong><div>${escapeHtml(selectedShot.emotion_tone || '暂无')}</div></div>
              <div class="micro-card"><strong>参考资产数</strong><div>${escapeHtml(String(referenceAssets.length || 0))}</div></div>
            </div>
            <div class="detail-grid-two">
              <div class="detail-section">
                <div>
                  <div class="muted" style="margin-bottom:6px">镜头描述</div>
                  <div class="json-box">${escapeHtml(selectedShot.prompt || '')}</div>
                </div>
                <div class="note-list">
                  ${selectedShot.subject_action ? `<div class="note-item"><strong>主体动作</strong><div>${escapeHtml(selectedShot.subject_action)}</div></div>` : ''}
                  ${selectedShot.background_action ? `<div class="note-item"><strong>背景动作</strong><div>${escapeHtml(selectedShot.background_action)}</div></div>` : ''}
                  ${continuityNotes.map(note => `<div class="note-item"><strong>连续性提示</strong><div>${escapeHtml(note)}</div></div>`).join('')}
                </div>
              </div>
              <div class="detail-section">
                <div>
                  <div class="muted" style="margin-bottom:6px">当前参考板</div>
                  ${boardHtml}
                </div>
              </div>
            </div>
            <div class="detail-section">
              <div class="meta-line">
                <strong>参考资产</strong>
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

    function humanizeShotVideoFilter(filter) {
      const labels = {
        all: '全部',
        succeeded: '已完成',
        failed: '失败',
        timed_out: '超时',
        skipped_not_selected: '未选中',
        skipped_job_not_ready: '未准备好',
      };
      return labels[filter] || humanizeStatus(filter);
    }

    function renderFinalVideoPanel(videoPayload) {
      const finalVideo = videoPayload?.final_video || {};
      const summary = videoPayload?.summary || {};
      const summaryHtml = `
        <div class="summary-grid">
          ${renderSummaryBox('镜头数', finalVideo.shot_count || summary.total_shots || 0)}
          ${renderSummaryBox('前段裁切秒数', finalVideo.trim_leading_seconds ?? '暂无')}
          ${renderSummaryBox('前段黑场秒数', finalVideo.blackout_leading_seconds ?? '暂无')}
          ${renderSummaryBox('拼接方式', finalVideo.concat_mode || '暂无')}
        </div>
      `;
      if (!finalVideo.available || !finalVideo.preview_url) {
        return `
          <section class="panel" style="padding:16px">
            <h2>最终成片</h2>
            ${summaryHtml}
            <div class="empty" style="margin-top:14px">最终拼接视频还不存在，完成最终成片阶段后会显示在这里。</div>
          </section>
        `;
      }

      return `
        <section class="panel" style="padding:16px">
          <h2>最终成片</h2>
          <div class="video-hero">
            ${summaryHtml}
            <div class="video-frame">
              <video src="${finalVideo.preview_url}" controls preload="metadata"></video>
            </div>
            <div class="media-actions">
              <button class="text-button" onclick='openMediaModal(${JSON.stringify(finalVideo.preview_url)}, ${JSON.stringify(finalVideo.title || "最终成片")}, ${JSON.stringify("拼接后的最终输出")})'>查看成片</button>
              <a class="text-button" href="${finalVideo.preview_url}" target="_blank" rel="noopener noreferrer">打开本地文件</a>
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
            ${humanizeShotVideoFilter(item)} · ${item === 'all' ? shotVideos.length : statusCounts[item]}
          </button>
        `)
        .join('');

      const filtered = shotVideos.filter(item => shotVideoFilter === 'all' || item.status === shotVideoFilter);
      metaRoot.textContent = `当前显示 ${filtered.length} / ${shotVideos.length} 条分镜视频`;

      root.innerHTML = filtered.length ? `
        <div class="video-grid">
          ${filtered.map(item => `
            <div class="video-card">
              ${item.preview_url ? `<video class="media-thumb" src="${item.preview_url}" controls preload="metadata"></video>` : `<div class="media-thumb"></div>`}
              <div class="video-body">
                <div class="meta-line">
                  <strong>${escapeHtml(item.shot_id || '镜头')}</strong>
                  ${statusTag(item.status)}
                </div>
                <div class="muted">顺序：${escapeHtml(item.order || '')}</div>
                <div class="muted">对应片段：${escapeHtml((item.segment_ids || []).join('、') || '暂无')}</div>
                ${item.error_message ? `<div class="muted">${escapeHtml(item.error_message)}</div>` : ''}
                <div class="media-actions">
                  ${item.preview_url ? `<button class="text-button" onclick='openMediaModal(${JSON.stringify(item.preview_url)}, ${JSON.stringify(item.shot_id || "分镜视频")}, ${JSON.stringify(humanizeStatus(item.status || ""))}, ${JSON.stringify(item.external_url || item.preview_url)})'>查看视频</button>` : ''}
                  ${item.preview_url ? `<a class="text-button" href="${item.preview_url}" target="_blank" rel="noopener noreferrer">打开本地文件</a>` : ''}
                  ${item.external_url ? `<a class="text-button" href="${item.external_url}" target="_blank" rel="noopener noreferrer">打开远程链接</a>` : ''}
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
          <h2>分镜视频</h2>
          <div class="summary-grid">
            ${renderSummaryBox('总镜头数', summary.total_shots || 0)}
            ${renderSummaryBox('已完成', summary.succeeded_shots || 0)}
            ${renderSummaryBox('失败或其他', summary.failed_shots || 0)}
            ${renderSummaryBox('已生成最终成片', summary.has_final_video ? '是' : '否')}
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
        root.innerHTML = '<div class="empty">当前还没有任务记录。</div>';
        return;
      }
      root.innerHTML = runs.map(run => `
        <div class="run-card ${run.run_id === selectedRunId ? 'active' : ''}" onclick="selectRun('${run.run_id}')">
          <div class="run-top">
            <div class="run-id">${run.run_id}</div>
            ${statusTag(run.status)}
          </div>
          <div class="muted">${run.source_script_name || '未命名任务'}</div>
          <div class="meta-line" style="margin-top:10px">
            <span class="muted">${humanizeStageName(run.current_stage || '') || '待处理'}</span>
            <span class="muted">${escapeHtml(formatLocalTimestamp(run.updated_at || ''))}</span>
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
      await loadRightPanel();
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
        statusBox.textContent = `任务已提交：${result.task_id || '已创建'} / ${result.run_id || result.run_dir || ''}`;
        activeTaskId = result.task_id || '';
        activeRunId = result.run_id || '';
        if (result.run_id) {
          selectedRunId = result.run_id;
          assetImageFilter = 'all';
          assetImageQuery = '';
          storyboardSelectedShotId = '';
          shotVideoFilter = 'all';
        }
        await loadRuns();
        await loadRightPanel();
      } catch (error) {
        statusBox.textContent = `提交失败：${error.message}`;
      }
    }

    function focusRunDetail() {
      activeTaskId = '';
      activeRunId = '';
      if (selectedRunId) {
        loadRunDetail(selectedRunId).catch(console.error);
      }
    }

    async function continueRun() {
      if (!selectedRunId) return;
      const result = await api(`/api/runs/${selectedRunId}/continue`, {
        method: 'POST',
        body: JSON.stringify({parallel_planning: false}),
      });
      activeTaskId = result.task_id || '';
      activeRunId = selectedRunId;
      await loadRightPanel();
    }

    async function rerunStage() {
      if (!selectedRunId) return;
      const stage = document.getElementById('rerun_stage').value;
      const result = await api(`/api/runs/${selectedRunId}/rerun-stage/${stage}`, {
        method: 'POST',
        body: JSON.stringify({force: true}),
      });
      activeTaskId = result.task_id || '';
      activeRunId = selectedRunId;
      await loadRightPanel();
    }

    async function loadActiveTaskPanel(taskId, options = {}) {
      const task = await safeApi(`/api/tasks/${taskId}`);
      if (!task) {
        activeTaskId = '';
        activeRunId = '';
        return false;
      }

      if (task.run_id) {
        activeRunId = task.run_id;
        selectedRunId = task.run_id;
      }

      if (!['queued', 'running'].includes(task.status)) {
        activeTaskId = '';
        return false;
      }

      let runPayload = null;
      let events = [];
      if (task.run_id) {
        runPayload = await safeApi(`/api/runs/${task.run_id}`);
        const eventPayload = await safeApi(`/api/runs/${task.run_id}/events?limit=24`);
        events = eventPayload?.events || [];
      }

      renderIntoDetailPanel(renderActiveTaskPanel(task, runPayload, events), options);
      return true;
    }

    async function loadRunDetail(runId, options = {}) {
      const [runPayload, videoPayload, reviewsPayload, upstreamReview, assetReview, storyboardReview] = await Promise.all([
        api(`/api/runs/${runId}`),
        safeApi(`/api/runs/${runId}/videos`),
        safeApi(`/api/runs/${runId}/reviews`),
        safeApi(`/api/runs/${runId}/reviews/upstream`),
        safeApi(`/api/runs/${runId}/reviews/asset_images`),
        safeApi(`/api/runs/${runId}/reviews/storyboard`),
      ]);

      const runState = runPayload.run_state || {};
      const routeDecision = runPayload.route_decision || {};
      const stages = runState.stages || {};
      const stageOrder = runState.stage_order || [];
      const reviewSummary = reviewsPayload?.reviews?.reviews || {};

      const stageCards = stageOrder.map(stageName => {
        const stage = stages[stageName] || {};
        return `
          <div class="stage-card">
            <div class="meta-line">
              <strong>${escapeHtml(humanizeStageName(stageName))}</strong>
              ${statusTag(stage.status)}
            </div>
            ${stage.preview_headline ? `<div class="muted" style="margin-top:8px">${escapeHtml(stage.preview_headline)}</div>` : ''}
            <div class="muted" style="margin-top:8px">${escapeHtml(stage.preview_text || stage.message || '当前还没有阶段摘要。')}</div>
            <div class="muted" style="margin-top:10px">${escapeHtml(renderStageTime(stage))}</div>
          </div>
        `;
      }).join('');

      const reviewOverview = ['upstream', 'asset_images', 'storyboard'].map(stage => `
        <span class="pill">${humanizeReviewStage(stage)}：${humanizeStatus(reviewSummary?.[stage]?.status || 'pending')}</span>
      `).join('');

      assetReviewCache = assetReview || null;
      storyboardReviewCache = storyboardReview || null;
      videoSummaryCache = videoPayload || null;
      const storyboardShots = storyboardReviewCache?.payload?.shots || [];
      if (!storyboardShots.some(shot => shot.shot_id === storyboardSelectedShotId)) {
        storyboardSelectedShotId = storyboardShots[0]?.shot_id || '';
      }

      renderIntoDetailPanel(`
        <div class="detail-head">
          <div>
            <h2>${runId}</h2>
            <div class="muted">${runState.source_script_name || '未命名任务'}</div>
            <div class="hero-meta" style="margin-top:10px">
              ${statusTag(runState.status)}
              <span class="pill">当前阶段：${escapeHtml(humanizeStageName(runState.current_stage || '') || '待处理')}</span>
              ${runState.awaiting_approval_stage ? `<span class="pill">待确认：${escapeHtml(humanizeReviewStage(runState.awaiting_approval_stage))}</span>` : ''}
              <span class="pill">更新时间：${escapeHtml(formatLocalTimestamp(runState.updated_at || ''))}</span>
              ${reviewOverview}
            </div>
          </div>
          <div class="detail-actions">
            <button class="secondary" onclick="loadRunDetail('${runId}')">刷新当前页</button>
            <button class="ghost" onclick="continueRun()">继续执行</button>
            <select id="rerun_stage">
              ${stageOptions.map(stage => `<option value="${stage.value}">${stage.label}</option>`).join('')}
            </select>
            <button onclick="rerunStage()">重跑所选阶段</button>
          </div>
        </div>

        ${renderRouteDecisionPanel(routeDecision)}

        <section class="panel" style="padding:16px">
          <h2>当前流程阶段</h2>
          <div class="stage-grid">${stageCards}</div>
        </section>

        <section class="panel" style="padding:16px">
          <h2>人工确认</h2>
          <div class="review-grid">
            ${renderUpstreamReview(upstreamReview)}
            ${renderAssetImagesReview(assetReview)}
            ${renderStoryboardReview(storyboardReview)}
          </div>
        </section>

        ${renderShotVideosPanel(videoSummaryCache)}

        ${renderFinalVideoPanel(videoSummaryCache)}
      `, options);

      paintAssetImagesReview();
      paintStoryboardReview();
      paintShotVideosSection();
    }

    function renderIdlePanel(options = {}) {
      renderIntoDetailPanel('<div class="empty">请先从左侧选择一个任务，或直接新建一个任务。</div>', options);
    }

    async function loadRightPanel(options = {}) {
      if (activeTaskId) {
        const handled = await loadActiveTaskPanel(activeTaskId, options);
        if (handled) {
          return;
        }
      }
      if (selectedRunId) {
        await loadRunDetail(selectedRunId, options);
        return;
      }
      renderIdlePanel(options);
    }

    async function pollCurrentRun() {
      if (isMediaModalOpen() || hasActiveVideoPlayback()) {
        return;
      }
      try {
        await loadRightPanel({preserveViewport: true});
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

    Promise.all([loadRuns(), loadRightPanel()]).catch(console.error);
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
