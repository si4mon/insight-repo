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
 *   - # / ## / ### headings (auto-ids, # anchor links); #### / ##### / ###### without ids
 *     (card titles and repeated sub-labels would otherwise collide on the same id)
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
 *   - images: ![caption](url) → framed + zoomable figure. Local paths (relative to the .md)
 *     are inlined as data: URIs so the page stays self-contained; a missing local image
 *     fails the render. Remote http(s) images are left as links (the gate rejects them).
 *
 * Conventions:
 *   - The first italic-only paragraph immediately after an H2 becomes a section lede.
 *   - The first paragraph of the very first section gets a drop-cap, but only when it
 *     starts with a Latin letter: an enlarged CJK glyph splits the first word into an
 *     orphan ("窗" + "口统计"), so CJK openings render without one.
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
    stash(`<img src="${escapeHtml(embedImage(src))}" alt="${escapeHtml(alt)}" loading="lazy">`));

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
  if (level >= 4) return { html: `<h${level}${attrs}>${inline(text)}</h${level}>`, id, level };
  return { html: `<h${level} id="${id}"${attrs}>${inline(text)}${anchor}</h${level}>`, id, level };
}

// Local images are inlined as data: URIs so the report stays self-contained when it is
// moved or shared; anything that cannot be read is collected and fails the render.
let IMAGE_BASE_DIR = process.cwd();
const IMAGE_ERRORS = [];
const IMAGE_MIME = { '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
                     '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp' };
function embedImage(src) {
  const s = String(src).trim();
  if (/^(https?:|data:|#)/i.test(s)) return s;
  const file = path.resolve(IMAGE_BASE_DIR, decodeURI(s));
  const mime = IMAGE_MIME[path.extname(file).toLowerCase()];
  if (!mime) { IMAGE_ERRORS.push(`unsupported image type: ${s}`); return s; }
  if (!fs.existsSync(file)) { IMAGE_ERRORS.push(`image not found: ${s} (looked in ${file})`); return s; }
  return `data:${mime};base64,${fs.readFileSync(file).toString('base64')}`;
}

// Drop caps only suit alphabetic scripts: skip leading markup, then require A–Z.
function startsWithLatin(text) {
  const first = String(text).replace(/^[\s*_`~=\[("'“‘]+/u, '').charAt(0);
  return /[A-Za-z]/.test(first);
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
    const h = line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
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
      if (!dropCapApplied && lastHeadingLevel === 2 && startsWithLatin(t.text)) {
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
        : `<img src="${escapeHtml(embedImage(t.src))}" alt="${escapeHtml(t.caption)}" loading="lazy">`;
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
IMAGE_BASE_DIR = path.dirname(inputPath);
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
if (IMAGE_ERRORS.length) {
  for (const e of IMAGE_ERRORS) console.error(`error: ${e}`);
  console.error('error: local images must exist (paths are relative to the .md); nothing was written');
  process.exit(1);
}
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
