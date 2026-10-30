assets/report_engine/index-template.html
----------------------------------------
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>Reports — Research vault</title>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap">

<style>
:root {
  --bg:           oklch(0.972 0.012 85);
  --bg-elevated:  oklch(0.945 0.014 85);
  --text:         oklch(0.22  0.018 85);
  --text-muted:   oklch(0.45  0.014 85);
  --text-subtle:  oklch(0.58  0.012 85);
  --rule:         oklch(0.86  0.012 85);
  --rule-strong:  oklch(0.78  0.014 85);
  --accent:       oklch(0.50  0.135 35);
  --accent-soft:  oklch(0.92  0.04  35);
  --accent-ring:  oklch(0.55  0.16  35 / 0.40);

  --font-body:  'Newsreader','Iowan Old Style',Georgia,serif;
  --font-ui:    'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  --font-mono:  'JetBrains Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}
[data-theme="dark"] {
  --bg:           oklch(0.135 0.008 260);
  --bg-elevated:  oklch(0.175 0.008 260);
  --text:         oklch(0.94  0.006 260);
  --text-muted:   oklch(0.72  0.006 260);
  --text-subtle:  oklch(0.55  0.006 260);
  --rule:         oklch(0.27  0.008 260);
  --rule-strong:  oklch(0.38  0.008 260);
  --accent:       oklch(0.74  0.13  35);
  --accent-soft:  oklch(0.30  0.08  35);
  --accent-ring:  oklch(0.74  0.14  35 / 0.45);
}

*,*::before,*::after { box-sizing: border-box; }
html,body { margin:0; padding:0; }
body {
  font-family: var(--font-body);
  font-size: 1.0625rem;
  line-height: 1.55;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

.topbar {
  position: sticky; top: 0; z-index: 10;
  display: flex; justify-content: flex-end; gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  background: var(--bg);
  border-bottom: 1px solid var(--rule);
}
.topbar__btn {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.35rem 0.6rem;
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 4px;
  color: var(--text-muted);
  font-family: var(--font-ui); font-size: 0.78rem;
  cursor: pointer;
}
.topbar__btn:hover { color: var(--text); border-color: var(--rule-strong); }

main {
  max-width: 900px;
  margin: 0 auto;
  padding: 3rem 1.5rem 6rem;
}
.eyebrow {
  font-family: var(--font-ui);
  font-size: 0.72rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 0.5rem;
  font-weight: 500;
}
h1 {
  font-family: var(--font-body);
  font-size: 2rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  margin: 0 0 0.4rem;
}
.lede {
  font-style: italic;
  color: var(--text-muted);
  font-size: 1.05rem;
  margin: 0 0 2.5rem;
  max-width: 56ch;
}

.filter-row {
  display: flex; align-items: center; gap: 0.75rem;
  margin: 0 0 1rem;
}
.filter-row label { font-family: var(--font-ui); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-subtle); }
.filter-input {
  flex: 1;
  padding: 0.45rem 0.6rem;
  background: var(--bg-elevated);
  border: 1px solid var(--rule);
  border-radius: 4px;
  font-family: var(--font-ui);
  font-size: 0.85rem;
  color: var(--text);
}
.filter-input:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-color: var(--accent); }

.reports-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-body);
}
.reports-table th, .reports-table td {
  text-align: left;
  padding: 0.7rem 0.6rem;
  border-bottom: 1px solid var(--rule);
  font-weight: 400;
  vertical-align: baseline;
}
.reports-table th {
  font-family: var(--font-ui);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-subtle);
  border-bottom: 2px solid var(--rule-strong);
  padding-bottom: 0.5rem;
  cursor: pointer;
  user-select: none;
}
.reports-table th[aria-sort="ascending"]::after { content: " ↑"; color: var(--accent); }
.reports-table th[aria-sort="descending"]::after { content: " ↓"; color: var(--accent); }
.reports-table tbody tr { cursor: pointer; }
.reports-table tbody tr:hover { background: var(--bg-elevated); }
.reports-table tbody tr:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.col-date { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-subtle); width: 6.5rem; }
.col-title a { color: var(--text); text-decoration: none; }
.col-title a:hover { color: var(--accent); }
.col-tags { font-family: var(--font-ui); font-size: 0.72rem; color: var(--text-muted); width: 12rem; }
.col-read { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-subtle); width: 4.5rem; text-align: right; }
.col-status { font-family: var(--font-ui); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; width: 7.5rem; color: var(--text-muted); }

.status-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 999px;
  margin-right: 6px;
  vertical-align: middle;
}
.status-dot--draft     { background: oklch(0.72 0.010 85); }
.status-dot--in-review { background: oklch(0.65 0.13  80); }
.status-dot--reviewed  { background: oklch(0.62 0.08  200); }
.status-dot--final     { background: oklch(0.65 0.10  160); }

.empty-state {
  padding: 2rem 0;
  font-style: italic;
  color: var(--text-subtle);
  text-align: center;
}

@media (max-width: 640px) {
  .reports-table thead { display: none; }
  .reports-table, .reports-table tbody, .reports-table tr, .reports-table td { display: block; width: 100%; }
  .reports-table tr { padding: 0.75rem 0; border-bottom: 1px solid var(--rule); }
  .reports-table td { padding: 0.15rem 0; border: none; }
  .col-tags::before { content: "Tags: "; color: var(--text-subtle); }
  .col-read::before { content: "Reading: "; color: var(--text-subtle); }
  .col-status::before { content: "Status: "; color: var(--text-subtle); }
}
</style>
</head>

<body>

<div class="topbar">
  <button class="topbar__btn" id="theme-toggle" type="button" aria-label="Toggle theme" title="Toggle theme (T)">Theme</button>
</div>

<main>
  <p class="eyebrow">Research vault · {{REPORT_COUNT_LABEL}}</p>
  <h1>Reports</h1>
  <p class="lede">Sortable index. Click a column header to re-sort, or filter to narrow.</p>

  <div class="filter-row">
    <label for="filter-input">Filter</label>
    <input type="text" id="filter-input" class="filter-input" placeholder="Filter by title, tag, summary…" />
  </div>

  <table class="reports-table" id="reports-table">
    <thead>
      <tr>
        <th data-col="date" aria-sort="descending">Date</th>
        <th data-col="title">Title</th>
        <th data-col="tags">Tags</th>
        <th data-col="reading_time_min">Read</th>
        <th data-col="status">Status</th>
      </tr>
    </thead>
    <tbody id="reports-tbody">{{REPORTS_TBODY}}</tbody>
  </table>
  <p class="empty-state" id="empty-state" hidden>No reports match — clear the filter.</p>
</main>

<script id="report-index" type="application/json">
{{REPORTS_JSON}}
</script>

<script>
(function () {
  const data = JSON.parse(document.getElementById('report-index').textContent);
  const tbody = document.getElementById('reports-tbody');
  const filterInput = document.getElementById('filter-input');
  const empty = document.getElementById('empty-state');
  const headers = document.querySelectorAll('th[data-col]');

  let sort = { col: 'date', dir: 'desc' };
  try {
    const saved = localStorage.getItem('report-index.sort');
    if (saved) sort = JSON.parse(saved);
  } catch (e) {}

  function persistSort() {
    try { localStorage.setItem('report-index.sort', JSON.stringify(sort)); } catch (e) {}
  }

  function cmp(a, b, col) {
    const va = a[col]; const vb = b[col];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (Array.isArray(va) && Array.isArray(vb)) return va.join(',').localeCompare(vb.join(','));
    if (typeof va === 'number' && typeof vb === 'number') return va - vb;
    return String(va).localeCompare(String(vb));
  }

  function sortedReports() {
    const list = data.reports.slice();
    list.sort((a, b) => {
      const r = cmp(a, b, sort.col);
      return sort.dir === 'asc' ? r : -r;
    });
    return list;
  }

  function statusLabel(s) {
    return ({ 'draft': 'Draft', 'in-review': 'In review', 'reviewed': 'Reviewed', 'final': 'Final' })[s] || s;
  }

  function rowHtml(r) {
    const tags = (r.tags || []).join(' · ');
    return '<tr tabindex="0" data-href="' + escapeAttr(r.href) + '">' +
      '<td class="col-date">' + escapeText(r.date) + '</td>' +
      '<td class="col-title"><a href="' + escapeAttr(r.href) + '">' + escapeText(r.title) + '</a></td>' +
      '<td class="col-tags">' + escapeText(tags) + '</td>' +
      '<td class="col-read">' + escapeText(r.reading_time_min + 'm') + '</td>' +
      '<td class="col-status"><span class="status-dot status-dot--' + escapeAttr(r.status) + '"></span>' + escapeText(statusLabel(r.status)) + '</td>' +
    '</tr>';
  }

  function escapeText(s) {
    return String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[c]));
  }
  function escapeAttr(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  }

  function matches(r, q) {
    if (!q) return true;
    const hay = (r.title + ' ' + (r.tags || []).join(' ') + ' ' + (r.summary || '') + ' ' + (r.eyebrow || '')).toLowerCase();
    return hay.includes(q);
  }

  function render() {
    const q = filterInput.value.trim().toLowerCase();
    const rows = sortedReports().filter(r => matches(r, q));
    tbody.innerHTML = rows.map(rowHtml).join('');
    empty.hidden = rows.length !== 0;
    headers.forEach(h => {
      const c = h.getAttribute('data-col');
      if (c === sort.col) {
        h.setAttribute('aria-sort', sort.dir === 'asc' ? 'ascending' : 'descending');
      } else {
        h.removeAttribute('aria-sort');
      }
    });
  }

  headers.forEach(h => {
    h.addEventListener('click', () => {
      const col = h.getAttribute('data-col');
      if (sort.col === col) {
        sort.dir = sort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        sort.col = col;
        sort.dir = col === 'date' || col === 'reading_time_min' ? 'desc' : 'asc';
      }
      persistSort();
      render();
    });
  });

  let t = 0;
  filterInput.addEventListener('input', () => {
    clearTimeout(t);
    t = setTimeout(render, 80);
  });

  tbody.addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-href]');
    if (!tr) return;
    if (e.target.tagName === 'A') return;
    window.location.href = tr.getAttribute('data-href');
  });
  tbody.addEventListener('keydown', (e) => {
    const tr = e.target.closest('tr[data-href]');
    if (!tr) return;
    if (e.key === 'Enter') {
      window.location.href = tr.getAttribute('data-href');
    }
  });

  const themeBtn = document.getElementById('theme-toggle');
  const apply = (mode) => {
    document.documentElement.setAttribute('data-theme', mode);
    try { localStorage.setItem('report-theme', mode); } catch (e) {}
  };
  const initial = (() => {
    try { return localStorage.getItem('report-theme'); } catch (e) { return null; }
  })() || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  apply(initial);
  themeBtn.addEventListener('click', () => {
    apply(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 't' || e.key === 'T') themeBtn.click();
  });

  render();
})();
</script>

</body>
</html>


assets/report_engine/render.mjs
----------------------------------------
#!/usr/bin/env node
/*
 * render.mjs — convert a Markdown report into a designed HTML report.
 *
 * Usage:
 *   node render.mjs <input.md> [output.html]
 *
 * The input must start with a YAML frontmatter block:
 *
 *   ---
 *   title: ...
 *   summary: ...
 *   generated_by: ...
 *   date: 2026-05-05
 *   tags: [a, b, c]
 *   sources: 14
 *   version: 1
 *   ---
 *
 * Supported Markdown:
 *   - # / ## / ### / #### headings (auto-ids, # anchor links)
 *   - paragraphs with **bold**, *italic*, `code`, [link](url), ==mark==, [^1]
 *   - ordered + unordered lists (one level of nesting)
 *   - tables (pipe syntax, header + separator + rows; align via : in separator)
 *   - fenced code blocks ```lang [path/to/file]
 *   - blockquotes; with leading [TAG] turns into a callout:
 *       quiet typographic: NOTE, INSIGHT, CAUTION, ASIDE
 *       boxed with icon:   INFO, WARNING, TIP, DANGER
 *   - footnotes: [^1] in body, [^1]: text definitions
 *   - definition lists (term + ": " line)
 *   - horizontal rule (---)
 *   - images: ![caption](url) → framed + zoomable figure
 *
 * Conventions:
 *   - The first italic-only paragraph immediately after an H2 becomes a section lede.
 *   - The first paragraph of the very first section gets a drop-cap.
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parseReportComments } from './comments.mjs';
import { buildIndex, writeIndexArtifacts, safeJsonForScript, sweepInlineIndex } from './build-index.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const TEMPLATE_PATH = path.join(__dirname, 'template.html');

// ---------- helpers ----------

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
}

function slug(s) {
  // Keep non-Latin letters (CJK etc.). The upstream rule stripped everything
  // outside [a-z0-9], which turned every Chinese heading into id="" and made
  // its TOC link point at "#". \p{L}\p{N} keeps Chinese/Japanese/Korean intact.
  const out = String(s).toLowerCase()
    .replace(/[`~!@#$%^&*()+={}\[\]|\\:;"'<>,.?\/]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '');
  return out ? out.slice(0, 80) : 'section';
}

// ---------- frontmatter ----------

function parseFrontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!m) return { meta: {}, body: text };
  const meta = {};
  for (const line of m[1].split(/\r?\n/)) {
    const mm = line.match(/^([\w_-]+):\s*(.*)$/);
    if (!mm) continue;
    let [, key, val] = mm;
    val = val.trim();
    if (val.startsWith('[') && val.endsWith(']')) {
      val = val.slice(1, -1).split(',').map(s => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
    } else if (/^["'].*["']$/.test(val)) {
      val = val.slice(1, -1);
    }
    meta[key] = val;
  }
  return { meta, body: m[2] };
}

// ---------- inline ----------

const FN_USED = new Set();

function inline(text) {
  // Process in order: code (highest precedence) → fnrefs → links → bold → italic → mark
  // Code spans pull text out so other inline rules don't fire inside.
  // Placeholders must be unmatchable by surrounding prose. Upstream used a bare
  // index ("0", "1", ...) and unstashed with /(\d+)/g, which rewrote every number
  // in the body (624, 51, $1.00) into placeholders[i] -> "undefined". NUL-wrapped
  // sentinels cannot appear in the source text.
  const placeholders = [];
  function stash(html) { placeholders.push(html); return `\u0000${placeholders.length - 1}\u0000`; }
  function unstash(s) {
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => placeholders[+i] ?? '');
  }

  // 1. inline code
  text = text.replace(/`([^`]+)`/g, (_, c) => stash(`<code>${escapeHtml(c)}</code>`));

  // 2. footnote refs
  text = text.replace(/\[\^([^\]]+)\]/g, (_, n) => {
    FN_USED.add(n);
    return stash(`<a class="fnref" href="#fn${slug(n)}" data-fn="${escapeHtml(n)}" id="fnref${slug(n)}">[${escapeHtml(n)}]</a>`);
  });

  // 3. images: ![alt](url) — handled at block level for figures, but inline images become plain <img>
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) =>
    stash(`<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy">`));

  // 4. links: [text](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, t, u) => {
    const safeU = /^(https?:|mailto:|#|\/)/.test(u) ? u : '#';
    return stash(`<a href="${escapeHtml(safeU)}">${escapeHtml(t)}</a>`);
  });

  // 5. bold then italic (bold first because ** must precede *)
  text = escapeHtml(text);
  text = text.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/(^|[^\w*])\*([^*\n]+?)\*(?=[^\w*]|$)/g, '$1<em>$2</em>');
  text = text.replace(/(^|[^\w_])_([^_\n]+?)_(?=[^\w_]|$)/g, '$1<em>$2</em>');

  // 6. mark
  text = text.replace(/==([^=]+?)==/g, '<mark>$1</mark>');

  return unstash(text);
}

// ---------- block tokenizer + renderer ----------

const CALLOUT_TAGS = {
  // typographic (quiet)
  NOTE:    { box: false, label: 'Note' },
  INSIGHT: { box: false, label: 'Insight' },
  CAUTION: { box: false, label: 'Caution' },
  ASIDE:   { box: false, label: 'Aside' },
  // boxed
  INFO:    { box: true,  label: 'Info',    iconKey: 'info' },
  WARNING: { box: true,  label: 'Warning', iconKey: 'warning' },
  TIP:     { box: true,  label: 'Tip',     iconKey: 'tip' },
  DANGER:  { box: true,  label: 'Danger',  iconKey: 'danger' },
};

const ICONS = {
  info:    '<svg viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M11 7.5h.01M10 11h1v4h1"/></svg>',
  warning: '<svg viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 3l8.5 15h-17z"/><path d="M11 9v4M11 16h.01"/></svg>',
  tip:     '<svg viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 16h6"/><path d="M9 19h4"/><path d="M7 11.5a4 4 0 1 1 8 0c0 1.7-1 2.6-1.5 3.2-.3.4-.5.7-.5 1.3H9c0-.6-.2-.9-.5-1.3-.5-.6-1.5-1.5-1.5-3.2z"/></svg>',
  danger:  '<svg viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4h8l4 4v6l-4 4H7l-4-4V8z"/><path d="M11 8v4M11 15h.01"/></svg>',
};

function copyButton() {
  return `<button class="codeblock__copy" type="button" aria-label="Copy code">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="4" y="4" width="9" height="9" rx="1.5"/>
              <path d="M3 11V3.5C3 3 3.5 2.5 4 2.5h7.5"/>
            </svg>
            <span class="copy-label">Copy</span>
          </button>`;
}

function reportBlockAttr(blockId) {
  return ` data-report-block-id="${escapeHtml(blockId)}"`;
}

function renderReportComments(comments, blockId) {
  if (!comments.length) return '';
  const items = comments.map(comment => {
    const status = comment.status === 'resolved' ? 'resolved' : 'open';
    const resolved = comment.resolvedNote
      ? `<p class="report-comment-note__resolved">Resolved: ${escapeHtml(comment.resolvedNote)}</p>`
      : '';
    return `<article class="report-comment-note" data-report-comment-note="${escapeHtml(comment.id)}" data-report-comment-status="${status}">
      <a class="report-comment-note__meta" id="comment-${escapeHtml(comment.id)}" href="#comment-${escapeHtml(comment.id)}" data-report-comment-marker="${escapeHtml(comment.id)}" data-report-comment-status="${status}" data-report-comment-target="${escapeHtml(comment.target || blockId)}" aria-label="${status} comment ${escapeHtml(comment.id)}"><span class="report-comment-note__status">${status}</span><span class="report-comment-note__id">${escapeHtml(comment.id)}</span></a>
      <p class="report-comment-note__body">${escapeHtml(comment.body || 'No comment text.')}</p>
      ${resolved}
    </article>`;
  }).join('');
  return `<aside class="report-comment-margin" data-report-comment-target="${escapeHtml(blockId)}" aria-label="Review comments for ${escapeHtml(blockId)}">${items}</aside>`;
}

function withReportComments(html, comments, blockId) {
  return html + renderReportComments(comments, blockId);
}

// Render a code block; very lightweight syntax tinting via 3 tokens
function renderCode(lang, filename, raw, blockId = '') {
  let body = escapeHtml(raw);
  if (lang) {
    // comments (//, #, --) — full-line
    body = body.split('\n').map(line => {
      const m = line.match(/^(\s*)(\/\/.*|#.*|--.*)$/);
      if (m && (lang.match(/^(js|ts|tsx|jsx|java|c|cpp|css|scss|go|rs|php|swift|kt)/) ? m[2].startsWith('//') :
                lang.match(/^(py|sh|bash|yml|yaml|toml|rb|conf)/) ? m[2].startsWith('#') :
                lang.match(/^(sql|hs|lua)/) ? m[2].startsWith('--') : false)) {
        return `${m[1]}<span class="tk-com">${m[2]}</span>`;
      }
      return line;
    }).join('\n');
    // strings
    body = body.replace(/(['"`])((?:\\.|(?!\1)[^\\])*?)\1/g, (_, q, s) => `<span class="tk-str">${q}${s}${q}</span>`);
    // keywords (rough union covering common langs; intentional false-positives are fine)
    const kws = /\b(import|export|from|as|default|return|const|let|var|function|class|extends|new|this|super|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|async|await|yield|public|private|protected|static|interface|type|enum|implements|namespace|module|package|def|lambda|None|True|False|nil|null|undefined|in|of|is|not|and|or|pass|with|raise|self|fn|impl|trait|use|mut|pub|let|where|select|from|where|join|on|insert|update|delete)\b/g;
    body = body.replace(kws, '<span class="tk-kw">$1</span>');
    // numbers
    body = body.replace(/\b(\d+\.?\d*)\b/g, '<span class="tk-num">$1</span>');
  }
  const meta = `<div class="codeblock__meta">${lang ? `<span class="codeblock__lang">${escapeHtml(lang)}</span>` : ''}${copyButton()}</div>`;
  const header = (filename || lang)
    ? `<div class="codeblock__header"><span class="codeblock__path">${escapeHtml(filename || '')}</span>${meta}</div>`
    : '';
  return `<div class="codeblock"${blockId ? reportBlockAttr(blockId) : ''}>${header}<pre><code>${body}</code></pre></div>`;
}

function renderCallout(tag, body, blockId = '') {
  const attrs = blockId ? reportBlockAttr(blockId) : '';
  const conf = CALLOUT_TAGS[tag];
  if (!conf) {
    return `<blockquote${attrs}>${body}</blockquote>`;
  }
  if (conf.box) {
    return `<div class="callout-box" data-callout="${tag.toLowerCase()}" role="note"${attrs}>
      <span class="callout-box__icon" aria-hidden="true">${ICONS[conf.iconKey]}</span>
      <div class="callout-box__body">${body}</div>
    </div>`;
  }
  return `<blockquote class="callout" data-callout="${tag.toLowerCase()}"${attrs}>
    <span class="callout__label">${conf.label}</span>
    ${body}
  </blockquote>`;
}

function renderHeading(level, text, blockId = '') {
  const id = slug(text);
  const anchor = `<a class="heading-anchor" href="#${id}" aria-label="Link to ${escapeHtml(text)}">#</a>`;
  const attrs = blockId ? reportBlockAttr(blockId) : '';
  if (level === 1) return { html: `<h1${attrs}>${inline(text)}</h1>`, id, level };
  if (level === 4) return { html: `<h4${attrs}>${inline(text)}</h4>`, id, level };
  return { html: `<h${level} id="${id}"${attrs}>${inline(text)}${anchor}</h${level}>`, id, level };
}

function isItalicOnly(line) {
  const t = line.trim();
  return /^\*[^*]+\*$/.test(t) || /^_[^_]+_$/.test(t);
}

function stripItalic(line) {
  return line.trim().replace(/^[*_](.+)[*_]$/, '$1');
}

function tokenize(md) {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  let i = 0;
  const out = [];

  while (i < lines.length) {
    const line = lines[i];

    // skip blank
    if (/^\s*$/.test(line)) { i++; continue; }

    // report review comment marker
    if (/^\s*<!--\s*@report-comment\b/.test(line)) {
      const buf = [line];
      i++;
      while (i < lines.length && !/-->\s*$/.test(buf[buf.length - 1])) {
        buf.push(lines[i]);
        i++;
      }
      const comment = parseReportComments(buf.join('\n'))[0];
      if (comment) out.push({ type: 'reportComment', comment });
      continue;
    }

    // footnote def
    const fnDef = line.match(/^\[\^([^\]]+)\]:\s*(.*)$/);
    if (fnDef) {
      const num = fnDef[1];
      let body = fnDef[2];
      i++;
      while (i < lines.length && /^\s+\S/.test(lines[i])) {
        body += '\n' + lines[i].replace(/^\s+/, '');
        i++;
      }
      out.push({ type: 'fnDef', num, body });
      continue;
    }

    // hr
    if (/^---+\s*$/.test(line)) { out.push({ type: 'hr' }); i++; continue; }

    // heading
    const h = line.match(/^(#{1,4})\s+(.+?)\s*#*$/);
    if (h) { out.push({ type: 'heading', level: h[1].length, text: h[2] }); i++; continue; }

    // fenced code
    const fence = line.match(/^```\s*(\S*)\s*(.*)$/);
    if (fence) {
      const lang = fence[1] || '';
      const filename = fence[2] || '';
      const buf = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++; // skip closing fence
      out.push({ type: 'code', lang, filename, body: buf.join('\n') });
      continue;
    }

    // table — header line + separator
    if (line.includes('|') && i + 1 < lines.length && /^[\s|:\-]+$/.test(lines[i+1]) && lines[i+1].includes('-')) {
      const splitRow = (row) => {
        const trimmed = row.trim().replace(/^\||\|$/g, '');
        return trimmed.split('|').map(c => c.trim());
      };
      const header = splitRow(line);
      const sep = splitRow(lines[i+1]);
      const aligns = sep.map(s => {
        if (s.startsWith(':') && s.endsWith(':')) return 'center';
        if (s.endsWith(':')) return 'right';
        return 'left';
      });
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes('|') && !/^\s*$/.test(lines[i])) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      out.push({ type: 'table', header, aligns, rows });
      continue;
    }

    // blockquote (incl. callouts)
    if (/^>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ''));
        i++;
      }
      const joined = buf.join('\n').trim();
      const cm = joined.match(/^\[(\w+)\]\s*([\s\S]*)$/);
      if (cm && CALLOUT_TAGS[cm[1].toUpperCase()]) {
        out.push({ type: 'callout', tag: cm[1].toUpperCase(), body: cm[2] });
      } else {
        out.push({ type: 'blockquote', body: joined });
      }
      continue;
    }

    // unordered list
    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        let item = lines[i].replace(/^[-*]\s+/, '');
        i++;
        // Continuation lines (indented)
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) { item += ' ' + lines[i].trim(); i++; }
        items.push(item);
      }
      out.push({ type: 'ul', items });
      continue;
    }

    // ordered list
    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        let item = lines[i].replace(/^\d+\.\s+/, '');
        i++;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) { item += ' ' + lines[i].trim(); i++; }
        items.push(item);
      }
      out.push({ type: 'ol', items });
      continue;
    }

    // image (block-level → framed figure when on its own line)
    const img = line.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/);
    if (img) { out.push({ type: 'figure', caption: img[1], src: img[2] }); i++; continue; }

    // definition list: term followed by `: text`
    if (i + 1 < lines.length && /^:\s+/.test(lines[i+1])) {
      const pairs = [];
      while (i + 1 < lines.length && /^:\s+/.test(lines[i+1]) && !/^\s*$/.test(lines[i])) {
        const term = lines[i].trim();
        i++;
        let dd = lines[i].replace(/^:\s+/, '');
        i++;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) { dd += ' ' + lines[i].trim(); i++; }
        pairs.push({ term, dd });
        // skip blank between pairs
        while (i < lines.length && /^\s*$/.test(lines[i])) i++;
      }
      out.push({ type: 'dl', pairs });
      continue;
    }

    // paragraph (consume until blank)
    const buf = [line];
    i++;
    while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^[#>\-*\d]/.test(lines[i]) && !/^!\[.*\]\(.*\)\s*$/.test(lines[i]) && !/^```/.test(lines[i])) {
      buf.push(lines[i]); i++;
    }
    out.push({ type: 'p', text: buf.join(' ') });
  }
  return out;
}

function render(tokens) {
  const headings = [];
  let html = '';
  let sectionStarted = false;
  let dropCapApplied = false;
  let lastHeadingLevel = 0;
  let pendingSectionLede = false;
  let inSection = false;
  let reportBlockCounter = 0;
  let pendingReportComments = [];

  const nextReportBlock = () => `block:b${++reportBlockCounter}`;
  const takeReportComments = () => {
    const comments = pendingReportComments;
    pendingReportComments = [];
    return comments;
  };

  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];

    if (t.type === 'reportComment') {
      pendingReportComments.push(t.comment);
      continue;
    }

    if (t.type === 'heading') {
      const blockId = nextReportBlock();
      const comments = takeReportComments();
      const h = renderHeading(t.level, t.text, blockId);
      if (t.level === 2) {
        if (inSection) html += '</section>';
        const id = slug(t.text);
        html += `\n<section aria-labelledby="${id}">\n`;
        inSection = true;
        pendingSectionLede = true;
        headings.push({ level: 2, id, text: t.text });
      } else if (t.level === 3) {
        const id = slug(t.text);
        headings.push({ level: 3, id, text: t.text, parent: headings.findLast(x => x.level === 2)?.id });
      }
      html += withReportComments(h.html, comments, blockId);
      lastHeadingLevel = t.level;
      continue;
    }

    if (t.type === 'p') {
      const blockId = nextReportBlock();
      const comments = takeReportComments();
      let cls = '';
      if (pendingSectionLede && isItalicOnly(t.text)) {
        cls = ' class="section-lede"';
        const inner = inline(stripItalic(t.text));
        html += withReportComments(`<p${cls}${reportBlockAttr(blockId)}><em>${inner}</em></p>`, comments, blockId);
        pendingSectionLede = false;
        continue;
      }
      pendingSectionLede = false;
      if (!dropCapApplied && lastHeadingLevel === 2) {
        cls = ' class="dropcap"';
        dropCapApplied = true;
      }
      html += withReportComments(`<p${cls}${reportBlockAttr(blockId)}>${inline(t.text)}</p>`, comments, blockId);
      continue;
    }

    pendingSectionLede = false;

    if (t.type === 'ul') {
      const trailingAsides = [];
      const inner = t.items.map(it => {
        const blockId = nextReportBlock();
        const aside = renderReportComments(takeReportComments(), blockId);
        if (aside) trailingAsides.push(aside);
        return `<li${reportBlockAttr(blockId)}>${inline(it)}</li>`;
      }).join('');
      html += `<ul>${inner}</ul>${trailingAsides.join('')}`;
      continue;
    }
    if (t.type === 'ol') {
      const trailingAsides = [];
      const inner = t.items.map(it => {
        const blockId = nextReportBlock();
        const aside = renderReportComments(takeReportComments(), blockId);
        if (aside) trailingAsides.push(aside);
        return `<li${reportBlockAttr(blockId)}>${inline(it)}</li>`;
      }).join('');
      html += `<ol>${inner}</ol>${trailingAsides.join('')}`;
      continue;
    }
    if (t.type === 'hr') {
      const blockId = nextReportBlock();
      html += withReportComments(`<hr${reportBlockAttr(blockId)}>`, takeReportComments(), blockId);
      continue;
    }
    if (t.type === 'code') {
      const blockId = nextReportBlock();
      html += withReportComments(renderCode(t.lang, t.filename, t.body, blockId), takeReportComments(), blockId);
      continue;
    }
    if (t.type === 'callout') {
      const blockId = nextReportBlock();
      html += withReportComments(renderCallout(t.tag, `<p>${inline(t.body)}</p>`, blockId), takeReportComments(), blockId);
      continue;
    }
    if (t.type === 'blockquote') {
      const blockId = nextReportBlock();
      html += withReportComments(`<blockquote${reportBlockAttr(blockId)}>${inline(t.body).split('\n').map(l => `<p>${l}</p>`).join('')}</blockquote>`, takeReportComments(), blockId);
      continue;
    }
    if (t.type === 'table') {
      const tableComments = takeReportComments();
      const trailingAsides = [];
      const thead = '<thead><tr>' + t.header.map((h, k) => `<th${t.aligns[k] === 'right' ? ' class="num"' : ''}>${inline(h)}</th>`).join('') + '</tr></thead>';
      const tbody = '<tbody>' + t.rows.map((r, rowIndex) => {
        const blockId = nextReportBlock();
        const comments = rowIndex === 0 ? tableComments : [];
        const aside = renderReportComments(comments, blockId);
        if (aside) trailingAsides.push(aside);
        return '<tr' + reportBlockAttr(blockId) + '>' + r.map((c, k) => `<td${t.aligns[k] === 'right' ? ' class="num"' : ''}>${inline(c)}</td>`).join('') + '</tr>';
      }).join('') + '</tbody>';
      const tableWrapAttr = trailingAsides.length ? ' data-report-has-comment="true"' : '';
      html += `<div class="table-wrap"${tableWrapAttr}><table>${thead}${tbody}</table></div>${trailingAsides.join('')}`;
      continue;
    }
    if (t.type === 'figure') {
      const blockId = nextReportBlock();
      const comments = takeReportComments();
      const isAnchor = t.src.startsWith('#');
      const inner = isAnchor
        ? `<div class="placeholder" data-anchor="${escapeHtml(t.src)}" style="aspect-ratio: 2/1; display: flex; align-items: center; justify-content: center; color: var(--text-faint); font-family: var(--font-ui); font-size: 0.8125rem;">${escapeHtml(t.src)}</div>`
        : `<img src="${escapeHtml(t.src)}" alt="${escapeHtml(t.caption)}" loading="lazy">`;
      html += withReportComments(`<figure class="framed"${reportBlockAttr(blockId)}>
        <div class="zoomable" tabindex="0" role="button" aria-label="Open image in viewer">${inner}</div>
        ${t.caption ? `<figcaption>${inline(t.caption)}</figcaption>` : ''}
      </figure>`, comments, blockId);
      continue;
    }
    if (t.type === 'dl') {
      const trailingAsides = [];
      const inner = t.pairs.map(p => {
        const blockId = nextReportBlock();
        const aside = renderReportComments(takeReportComments(), blockId);
        if (aside) trailingAsides.push(aside);
        return `<div class="def__entry"${reportBlockAttr(blockId)}><dt>${inline(p.term)}</dt><dd>${inline(p.dd)}</dd></div>`;
      }).join('');
      html += `<dl class="def">${inner}</dl>${trailingAsides.join('')}`;
      continue;
    }
    // fnDef handled separately at end
  }

  if (inSection) html += '</section>';
  return { html, headings };
}

function renderFootnotes(tokens) {
  const defs = tokens.filter(t => t.type === 'fnDef');
  if (defs.length === 0) return '';
  let items = defs.map(d =>
    `<li id="fn${slug(d.num)}">${inline(d.body)} <a class="fn-back" href="#fnref${slug(d.num)}" aria-label="Back to reference ${escapeHtml(d.num)}">↩</a></li>`
  ).join('');
  return `\n<section class="footnotes" aria-labelledby="footnotes" id="footnotes-section">
    <h2 id="footnotes">Footnotes<a class="heading-anchor" href="#footnotes" aria-label="Link to Footnotes">#</a></h2>
    <ol>${items}</ol>
  </section>`;
}

function renderToc(headings) {
  // Build nested ToC: h2 items, optionally containing h3 sub-items.
  let html = '<ol class="toc__list">';
  let openSub = false;
  for (let i = 0; i < headings.length; i++) {
    const h = headings[i];
    if (h.level === 2) {
      if (openSub) { html += '</ol></li>'; openSub = false; }
      // Look ahead — does this h2 have h3 children?
      const hasChildren = headings.slice(i + 1).findIndex(x => x.level === 2) !== 0
        && headings.slice(i + 1).some((x, k, arr) => x.level === 3 && (arr.slice(0, k).findIndex(y => y.level === 2) === -1));
      // simpler: peek next; if next is h3 with parent === h.id, open sub
      const next = headings[i + 1];
      if (next && next.level === 3 && next.parent === h.id) {
        html += `<li class="toc__item"><a class="toc__link" href="#${h.id}">${escapeHtml(h.text)}</a><ol class="toc__list">`;
        openSub = true;
      } else {
        html += `<li class="toc__item"><a class="toc__link" href="#${h.id}">${escapeHtml(h.text)}</a></li>`;
      }
    } else if (h.level === 3) {
      if (!openSub) {
        // Should not happen if h3 follows h2; orphan h3
        html += `<li class="toc__item"><a class="toc__link" href="#${h.id}">${escapeHtml(h.text)}</a></li>`;
      } else {
        html += `<li class="toc__item"><a class="toc__link" href="#${h.id}">${escapeHtml(h.text)}</a></li>`;
      }
    }
  }
  if (openSub) html += '</ol></li>';
  html += '</ol>';
  return html;
}

// ---------- main ----------

function usage() {
  console.error('Usage: node render.mjs <input.md> [output.html]');
}

const rawArgs = process.argv.slice(2);
const flags = new Set();
const positional = [];
for (const a of rawArgs) {
  if (a.startsWith('--')) flags.add(a);
  else positional.push(a);
}
if (positional.length < 1) { usage(); process.exit(1); }

const inputPath = path.resolve(positional[0]);
if (!fs.existsSync(inputPath)) {
  console.error(`error: input file not found: ${inputPath}`);
  process.exit(1);
}

const raw = fs.readFileSync(inputPath, 'utf8');
const { meta, body } = parseFrontmatter(raw);

if (!meta.title) {
  console.error('error: frontmatter must include a "title" field');
  process.exit(1);
}

const STATUS_VALUES = new Set(['draft', 'in-review', 'reviewed', 'final']);

if (meta.status === undefined || meta.status === '') {
  process.stderr.write(`${path.basename(inputPath)}: defaulted status=draft; add 'status:' to frontmatter\n`);
  meta.status = 'draft';
} else if (!STATUS_VALUES.has(meta.status)) {
  console.error(`error: frontmatter "status" must be one of: ${[...STATUS_VALUES].join(', ')} (got "${meta.status}")`);
  process.exit(1);
}

FN_USED.clear();
const tokens = tokenize(body);
const { html: articleHtml, headings } = render(tokens);
const footnotesHtml = renderFootnotes(tokens);
const tocHtml = renderToc(headings);

const date = (meta.date || new Date().toISOString().slice(0, 10));
const outputPath = positional[1]
  ? path.resolve(positional[1])
  : path.join(path.dirname(inputPath), `${slug(meta.title)}-${date}.html`);

let template = fs.readFileSync(TEMPLATE_PATH, 'utf8');

// title
template = template.replace(/<title>[\s\S]*?<\/title>/, `<title>${escapeHtml(meta.title)}</title>`);

// metadata block
const tagsHtml = (Array.isArray(meta.tags) ? meta.tags : (meta.tags ? [meta.tags] : []))
  .map(t => `<span class="tag">${escapeHtml(t)}</span>`).join(' ');
const articleHeader = `<header class="article-header">
  ${meta.eyebrow ? `<p class="eyebrow">${escapeHtml(meta.eyebrow)}</p>` : ''}
  <h1>${inline(meta.title)}</h1>
  ${meta.summary ? `<p class="lede">${inline(meta.summary)}</p>` : ''}
  <dl class="meta">
    <dt>generated by</dt> <dd>${escapeHtml(meta.generated_by || meta.generatedBy || 'AI agent')}</dd>
    <dt>date</dt> <dd>${escapeHtml(date)}</dd>
    <dt>reading time</dt> <dd id="reading-time">~? min read</dd>
    ${tagsHtml ? `<dt>tags</dt> <dd>${tagsHtml}</dd>` : ''}
    ${meta.sources != null ? `<dt>sources</dt> <dd>${escapeHtml(String(meta.sources))}</dd>` : ''}
    ${meta.version != null ? `<dt>version</dt> <dd>${escapeHtml(String(meta.version))}</dd>` : ''}
  </dl>
</header>`;

// Replace the article header block
template = template.replace(/<!-- BEGIN: ARTICLE HEADER -->[\s\S]*?<!-- END: ARTICLE HEADER -->/, articleHeader);

// Replace article body block
template = template.replace(/<!-- BEGIN: ARTICLE BODY[\s\S]*?<!-- END: ARTICLE BODY -->/, articleHtml);

// Replace the entire ToC block (between BEGIN/END markers) so the documentation
// comment in the template doesn't confuse a more permissive regex.
const tocBlock = `<nav class="toc-rail" id="toc-rail" aria-label="On this page">
    <button class="toc-rail__toggle" type="button" aria-expanded="false" aria-controls="toc">
      <span>On this page</span>
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>
    </button>
    <div class="toc" id="toc">
      <h2 class="toc__heading">On this page</h2>
      ${tocHtml}
    </div>
  </nav>`;
template = template.replace(/<!-- BEGIN: TABLE OF CONTENTS[\s\S]*?<!-- END: TABLE OF CONTENTS -->/, tocBlock);

// Insert footnotes section before the existing footnotes block, then remove the stub
if (footnotesHtml) {
  template = template.replace(/<!-- BEGIN: FOOTNOTES[\s\S]*?<!-- END: FOOTNOTES -->/, footnotesHtml);
} else {
  template = template.replace(/<!-- BEGIN: FOOTNOTES[\s\S]*?<!-- END: FOOTNOTES -->/, '');
}

// Remove the SOURCES stub if no sources content was authored — for v1, leave an empty marker.
template = template.replace(/<!-- BEGIN: SOURCES[\s\S]*?<!-- END: SOURCES -->/, '');
template = template.replace(/<!-- BEGIN: GLOSSARY[\s\S]*?<!-- END: GLOSSARY -->/, '');

// Embed source MD. data-source-path lets the review server mirror comment
// writes back to the sibling .md file so the markdown source stays in sync.
const sourceBasename = path.basename(inputPath);
template = template.replace(/<script id="source-md"[\s\S]*?<\/script>/,
  `<script id="source-md" type="text/markdown" data-source-path="${escapeHtml(sourceBasename)}">\n${raw}\n</script>`);

const reportsDir = path.dirname(outputPath);
fs.mkdirSync(reportsDir, { recursive: true });

// Pre-write without the inline snapshot so buildIndex sees this report
// alongside its siblings. buildIndex only reads the source-md frontmatter
// so the empty report-index placeholder is fine at this stage.
fs.writeFileSync(outputPath, template, 'utf8');

const index = buildIndex(reportsDir);
const currentSlug = path.basename(outputPath, '.html').replace(/-\d{4}-\d{2}-\d{2}$/, '');
const snapshot = { ...index, current_slug: currentSlug };
const snapshotJson = safeJsonForScript(snapshot);

template = template.replace(
  /<script id="report-index" type="application\/json">[\s\S]*?<\/script>/,
  `<script id="report-index" type="application/json">\n${snapshotJson}\n</script>`
);

// Final write with the embedded snapshot.
fs.writeFileSync(outputPath, template, 'utf8');

// Persist the on-disk JSON so external readers / the index.html page can use it.
writeIndexArtifacts(reportsDir, snapshot);
sweepInlineIndex(reportsDir, index);

console.log(`✓ rendered: ${outputPath}`);

// ---------- auto-open review server ----------
//
// One shared review server per reports directory. If a server is already
// running for this dir, reuse its port and just open the browser to the
// freshly rendered report. Otherwise spawn a new server rooted at the dir.
// Skipped when stdio is not a TTY (tests, CI) or when --no-open is passed.

async function pickFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

function canConnect(port) {
  return new Promise(resolve => {
    const sock = net.connect(port, '127.0.0.1');
    sock.setTimeout(150);
    sock.on('connect', () => { sock.destroy(); resolve(true); });
    sock.on('error', () => resolve(false));
    sock.on('timeout', () => { sock.destroy(); resolve(false); });
  });
}

async function waitForPort(port, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await canConnect(port)) return true;
    await new Promise(r => setTimeout(r, 50));
  }
  return false;
}

function pidIsAlive(pid) {
  if (!pid || !Number.isFinite(pid)) return false;
  try { process.kill(pid, 0); return true; } catch { return false; }
}

function openerCmd() {
  if (process.platform === 'darwin') return 'open';
  if (process.platform === 'win32') return 'start';
  return 'xdg-open';
}

function pidFilePathForDir(dir) {
  const hash = crypto.createHash('sha1').update(dir).digest('hex').slice(0, 12);
  return path.join(os.tmpdir(), `report-review-dir-${hash}.pid`);
}

function readSidecar(pidFile) {
  if (!fs.existsSync(pidFile)) return null;
  try {
    const [pidStr, portStr] = fs.readFileSync(pidFile, 'utf8').split('\n');
    const pid = parseInt(pidStr, 10);
    const port = parseInt(portStr, 10);
    if (!pid || !port) return null;
    return { pid, port };
  } catch { return null; }
}

async function autoOpenReviewServer() {
  const pidFile = pidFilePathForDir(reportsDir);
  const filename = path.basename(outputPath);
  let port;

  const existing = readSidecar(pidFile);
  if (existing && pidIsAlive(existing.pid) && await canConnect(existing.port)) {
    port = existing.port;
  } else {
    // Stale or missing — clean up and spawn fresh.
    if (existing && pidIsAlive(existing.pid)) {
      try { process.kill(existing.pid, 'SIGTERM'); } catch {}
    }
    port = await pickFreePort();
    const reviewScript = path.join(__dirname, 'review.mjs');
    const child = spawn('node', [reviewScript, reportsDir, `--port=${port}`], {
      detached: true,
      stdio: 'ignore',
    });
    child.unref();
    fs.writeFileSync(pidFile, `${child.pid}\n${port}\n`, 'utf8');
    const up = await waitForPort(port, 3000);
    if (!up) {
      console.error(`review server did not come up on port ${port}`);
      return;
    }
  }

  const url = `http://127.0.0.1:${port}/${filename}`;
  console.log(`↗ review server: ${url}`);
  const opener = spawn(openerCmd(), [url], { detached: true, stdio: 'ignore' });
  opener.unref();
}

if (process.stdout.isTTY && !flags.has('--no-open')) {
  await autoOpenReviewServer();
}


assets/report_engine/review-summary.mjs
----------------------------------------
#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { extractEmbeddedMarkdown, formatReviewSummary, parseReportComments } from './comments.mjs';

const [input, output] = process.argv.slice(2);
if (!input) {
  console.error('Usage: node review-summary.mjs <report.html> [output.md]');
  process.exit(1);
}

const htmlPath = path.resolve(input);
const html = fs.readFileSync(htmlPath, 'utf8');
const comments = parseReportComments(extractEmbeddedMarkdown(html))
  .map(({ raw, start, end, ...comment }) => comment);
const title = html.match(/<title>([\s\S]*?)<\/title>/)?.[1]?.trim() || path.basename(htmlPath);
const summary = formatReviewSummary(comments, title);

if (output) {
  fs.writeFileSync(path.resolve(output), summary, 'utf8');
} else {
  process.stdout.write(summary);
}


assets/report_engine/review.mjs
----------------------------------------
#!/usr/bin/env node
/*
 * review.mjs — local review server for rendered report HTML files.
 *
 * Usage:
 *   node review.mjs <report.html | reports-dir> [--port 0]
 *
 * When passed a file, the server roots at the file's parent directory and
 * uses that file as the default for `/` and for the comments API when no
 * Referer / ?file= hint is available. When passed a directory, `/` redirects
 * to /index.html.
 *
 * The server serves any *.html or *.json under the root, wraps report HTML
 * files (everything except index.html) with `data-review-mode="true"`, and
 * exposes /api/comments to read/write the embedded Markdown of whichever
 * file the request refers to.
 */

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { URL } from 'node:url';
import {
  blockIndexFromTarget,
  createCommentId,
  deleteReportComment,
  extractEmbeddedMarkdown,
  filterReportComments,
  insertReportComment,
  parseReportComments,
  replaceBodyKeepingComments,
  replaceEmbeddedMarkdown,
  updateReportComment,
} from './comments.mjs';

const args = process.argv.slice(2);
let reportArg = '';
let requestedPort = 0;

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '--port') {
    requestedPort = Number(args[++i]);
  } else if (arg.startsWith('--port=')) {
    requestedPort = Number(arg.split('=')[1]);
  } else if (!arg.startsWith('--') && !reportArg) {
    reportArg = arg;
  }
}

if (!reportArg) {
  console.error('Usage: node review.mjs <report.html | reports-dir> [--port 0]');
  process.exit(1);
}

const reportArgAbs = path.resolve(reportArg);
if (!fs.existsSync(reportArgAbs)) {
  console.error(`error: input not found: ${reportArgAbs}`);
  process.exit(1);
}

const argStat = fs.statSync(reportArgAbs);
const rootDir = argStat.isDirectory() ? reportArgAbs : path.dirname(reportArgAbs);
const startupFile = argStat.isFile() ? reportArgAbs : null;

function safeJoin(relPath) {
  // Strip leading slash, then resolve against root. Reject anything that
  // escapes the root via .. — prevents path-traversal.
  const cleaned = decodeURIComponent(relPath.replace(/^\/+/, ''));
  const resolved = path.resolve(rootDir, cleaned);
  if (resolved !== rootDir && !resolved.startsWith(rootDir + path.sep)) return null;
  return resolved;
}

function readMarkdown(filePath) {
  return extractEmbeddedMarkdown(fs.readFileSync(filePath, 'utf8'));
}

// Locate the .md source file that produced this HTML report. Prefers an
// explicit data-source-path hint stamped by render.mjs; falls back to a
// same-stem .md sibling so older reports also benefit.
function findSourceMd(htmlFilePath, html) {
  const hint = html.match(/<script id="source-md"[^>]*\bdata-source-path="([^"]+)"/);
  if (hint) {
    const candidate = path.resolve(rootDir, hint[1]);
    if (
      (candidate === rootDir || candidate.startsWith(rootDir + path.sep)) &&
      fs.existsSync(candidate)
    ) {
      return candidate;
    }
  }
  const stem = path.basename(htmlFilePath, '.html');
  const sibling = path.join(path.dirname(htmlFilePath), stem + '.md');
  if (fs.existsSync(sibling)) return sibling;
  return null;
}

function writeMarkdown(filePath, markdown) {
  const html = fs.readFileSync(filePath, 'utf8');
  fs.writeFileSync(filePath, replaceEmbeddedMarkdown(html, markdown), 'utf8');
  const mdPath = findSourceMd(filePath, html);
  if (mdPath) {
    fs.writeFileSync(mdPath, markdown, 'utf8');
  }
}

function sendJson(res, status, value) {
  const body = JSON.stringify(value);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

function sendText(res, status, value) {
  res.writeHead(status, {
    'content-type': 'text/plain; charset=utf-8',
    'content-length': Buffer.byteLength(value),
    'cache-control': 'no-store',
  });
  res.end(value);
}

function sendHtml(res, status, body) {
  res.writeHead(status, {
    'content-type': 'text/html; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

async function readJson(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks).toString('utf8');
  if (!body.trim()) return {};
  return JSON.parse(body);
}

function withReviewMode(html) {
  if (/<html\b[^>]*data-review-mode=/.test(html)) return html;
  return html.replace(/<html\b([^>]*)>/, '<html$1 data-review-mode="true">');
}

function fileFromReferer(req) {
  const referer = req.headers['referer'];
  if (!referer) return null;
  try {
    const refUrl = new URL(referer);
    const refPath = refUrl.pathname.replace(/^\/+/, '');
    if (!refPath || refPath === 'index.html' || !refPath.endsWith('.html')) return null;
    return safeJoin(refPath);
  } catch { return null; }
}

function resolveTargetFile(req, url) {
  const fromQuery = url.searchParams.get('file');
  if (fromQuery) return safeJoin(fromQuery);
  const fromRef = fileFromReferer(req);
  if (fromRef) return fromRef;
  return startupFile;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://127.0.0.1');

    // ---- Root: prefer startup file (test compat); else index.html
    if (req.method === 'GET' && url.pathname === '/') {
      if (startupFile && fs.existsSync(startupFile)) {
        sendHtml(res, 200, withReviewMode(fs.readFileSync(startupFile, 'utf8')));
        return;
      }
      res.writeHead(302, { 'location': '/index.html' });
      res.end();
      return;
    }

    // ---- Comments API
    if (url.pathname === '/api/comments' && req.method === 'GET') {
      const filePath = resolveTargetFile(req, url);
      if (!filePath || !fs.existsSync(filePath)) {
        sendText(res, 400, 'No target report file resolved.');
        return;
      }
      const comments = parseReportComments(readMarkdown(filePath)).map(({ raw, start, end, ...c }) => c);
      sendJson(res, 200, filterReportComments(comments, url.searchParams.get('status') || 'all'));
      return;
    }

    if (url.pathname === '/api/comments' && req.method === 'POST') {
      const filePath = resolveTargetFile(req, url);
      if (!filePath || !fs.existsSync(filePath)) {
        sendText(res, 400, 'No target report file resolved.');
        return;
      }
      const payload = await readJson(req);
      const markdown = readMarkdown(filePath);
      const comments = parseReportComments(markdown);
      const target = payload.target || 'block:b1';
      const id = payload.id || createCommentId(comments.map(c => c.id));
      const body = String(payload.body || '').trim();
      if (!body) { sendText(res, 400, 'Comment body is required.'); return; }
      const next = insertReportComment(markdown, {
        id,
        status: payload.status === 'resolved' ? 'resolved' : 'open',
        target,
        body,
        resolvedNote: payload.resolvedNote || '',
      }, blockIndexFromTarget(target));
      writeMarkdown(filePath, next);
      sendJson(res, 201, { id, status: 'open', target, body });
      return;
    }

    const commentMatch = url.pathname.match(/^\/api\/comments\/([^/]+)$/);
    if (commentMatch && req.method === 'PUT') {
      const filePath = resolveTargetFile(req, url);
      if (!filePath || !fs.existsSync(filePath)) {
        sendText(res, 400, 'No target report file resolved.');
        return;
      }
      const id = decodeURIComponent(commentMatch[1]);
      const payload = await readJson(req);
      const markdown = readMarkdown(filePath);
      const before = parseReportComments(markdown).find(c => c.id === id);
      if (!before) { sendText(res, 404, `Comment not found: ${id}`); return; }
      const next = updateReportComment(markdown, id, {
        status: payload.status || before.status,
        target: payload.target || before.target,
        body: payload.body ?? before.body,
        resolvedNote: payload.resolvedNote ?? before.resolvedNote,
      });
      const updated = {
        ...before,
        status: payload.status || before.status,
        target: payload.target || before.target,
        body: payload.body ?? before.body,
        resolvedNote: payload.resolvedNote ?? before.resolvedNote,
        id,
      };
      writeMarkdown(filePath, next);
      sendJson(res, 200, updated);
      return;
    }

    // ---- Source API: full-body overwrite from the browser editor.
    // Preserves existing @report-comment markers so saving an edit does not
    // wipe sidebar comments.
    if (url.pathname === '/api/source' && req.method === 'PUT') {
      const filePath = resolveTargetFile(req, url);
      if (!filePath || !fs.existsSync(filePath)) {
        sendText(res, 400, 'No target report file resolved.');
        return;
      }
      const payload = await readJson(req);
      const incoming = String(payload.markdown ?? '');
      if (!incoming.trim()) {
        sendText(res, 400, 'Markdown body is required.');
        return;
      }
      const merged = replaceBodyKeepingComments(readMarkdown(filePath), incoming);
      writeMarkdown(filePath, merged);
      sendJson(res, 200, { ok: true, file: path.relative(rootDir, filePath) || path.basename(filePath) });
      return;
    }

    if (commentMatch && req.method === 'DELETE') {
      const filePath = resolveTargetFile(req, url);
      if (!filePath || !fs.existsSync(filePath)) {
        sendText(res, 400, 'No target report file resolved.');
        return;
      }
      const id = decodeURIComponent(commentMatch[1]);
      writeMarkdown(filePath, deleteReportComment(readMarkdown(filePath), id));
      sendJson(res, 200, { id, deleted: true });
      return;
    }

    // ---- Static file routes for siblings in the same dir
    if (req.method === 'GET' && /\.(html|json)$/.test(url.pathname)) {
      const filePath = safeJoin(url.pathname);
      if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        sendText(res, 404, 'Not found.');
        return;
      }
      const raw = fs.readFileSync(filePath, 'utf8');
      if (filePath.endsWith('.json')) {
        res.writeHead(200, {
          'content-type': 'application/json; charset=utf-8',
          'content-length': Buffer.byteLength(raw),
          'cache-control': 'no-store',
        });
        res.end(raw);
        return;
      }
      // HTML: wrap report files in review mode; leave index.html as-is.
      const isIndex = path.basename(filePath) === 'index.html';
      sendHtml(res, 200, isIndex ? raw : withReviewMode(raw));
      return;
    }

    sendText(res, 404, 'Not found.');
  } catch (error) {
    sendText(res, 500, error.stack || error.message);
  }
});

server.listen(Number.isFinite(requestedPort) ? requestedPort : 0, '127.0.0.1', () => {
  const address = server.address();
  const url = `http://127.0.0.1:${address.port}/`;
  console.log(`Review server: ${url}`);
  console.log(`Root: ${rootDir}`);
  if (startupFile) console.log(`Default report: ${startupFile}`);
  console.log('Press Ctrl+C to stop.');
});


