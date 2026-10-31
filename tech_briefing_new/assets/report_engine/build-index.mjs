/*
 * build-index.mjs — scan a reports/ directory, build index.json + index.html,
 * and sweep the inline <script id="report-index"> block in every report.
 *
 * Used by render.mjs at end-of-render. Pure Node, no dependencies.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Windows: new URL(...).pathname gives "/D:/...", and path.join turns that into "D:\D:\...".
// fileURLToPath handles drive letters and percent-decoding.
const INDEX_TEMPLATE_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), 'index-template.html');

// ---------- frontmatter extraction ----------

const SOURCE_MD_RE = /<script id="source-md"[^>]*>([\s\S]*?)<\/script>/;
const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---/;

export function extractFrontmatterFromHtml(html) {
  const scriptMatch = SOURCE_MD_RE.exec(html);
  if (!scriptMatch) return null;
  const mdBody = scriptMatch[1].trim();
  const fmMatch = FRONTMATTER_RE.exec(mdBody);
  if (!fmMatch) return null;
  const meta = {};
  for (const line of fmMatch[1].split(/\r?\n/)) {
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
  return meta;
}

// ---------- entry projection ----------

const OPTIONAL_KEYS = ['tags', 'version', 'eyebrow', 'generated_by', 'sources'];

function deriveSlug(filename) {
  return filename
    .replace(/\.html$/, '')
    .replace(/-\d{4}-\d{2}-\d{2}$/, '');
}

function countWords(html) {
  const stripped = html
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<[^>]+>/g, ' ');
  const tokens = stripped.split(/\s+/).filter(Boolean);
  return tokens.length;
}

function projectEntry(filename, html, stat, fm) {
  const slug = deriveSlug(filename);
  const wordCount = countWords(html);
  const readingTime = Math.max(1, Math.round(wordCount / 220));
  const entry = {
    slug,
    href: filename,
    title: fm.title || '(untitled)',
    summary: fm.summary || '',
    date: fm.date || '1970-01-01',
    status: fm.status || 'draft',
    reading_time_min: readingTime,
    word_count: wordCount,
    last_modified: stat.mtime.toISOString(),
  };
  for (const key of OPTIONAL_KEYS) {
    if (fm[key] !== undefined && fm[key] !== '' && !(Array.isArray(fm[key]) && fm[key].length === 0)) {
      entry[key] = fm[key];
    }
  }
  return entry;
}

// ---------- buildIndex ----------

export function buildIndex(reportsDir) {
  const entries = [];
  if (!fs.existsSync(reportsDir)) {
    return { generated_at: new Date().toISOString(), report_count: 0, reports: [] };
  }
  for (const name of fs.readdirSync(reportsDir)) {
    if (!name.endsWith('.html')) continue;
    if (name === 'index.html') continue;
    const full = path.join(reportsDir, name);
    const stat = fs.statSync(full);
    if (!stat.isFile()) continue;
    const html = fs.readFileSync(full, 'utf8');
    const fm = extractFrontmatterFromHtml(html);
    if (!fm) {
      process.stderr.write(`skipped: ${name} — no embedded source\n`);
      continue;
    }
    entries.push(projectEntry(name, html, stat, fm));
  }
  entries.sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    if (a.last_modified !== b.last_modified) return a.last_modified < b.last_modified ? 1 : -1;
    return a.slug < b.slug ? -1 : (a.slug > b.slug ? 1 : 0);
  });
  return {
    generated_at: new Date().toISOString(),
    report_count: entries.length,
    reports: entries,
  };
}

// ---------- JSON-in-script-tag safety ----------

export function safeJsonForScript(obj) {
  // JSON.stringify does not escape "<", which means an attacker-controlled or
  // accidentally-included "</script>" inside any string field would close the
  // surrounding <script> tag and break the page. Escape the slash inside any
  // closing-tag-like sequence so the JSON parses identically but the HTML
  // tokenizer cannot exit the script element early.
  return JSON.stringify(obj, null, 2).replace(/<\/(script)/gi, '<\\/$1');
}

// ---------- write index.json and (Task 8) index.html ----------

export function writeIndexArtifacts(reportsDir, index) {
  const jsonPath = path.join(reportsDir, 'index.json');
  const tmpJsonPath = jsonPath + '.tmp';
  fs.writeFileSync(tmpJsonPath, JSON.stringify(index, null, 2) + '\n', 'utf8');
  fs.renameSync(tmpJsonPath, jsonPath);

  const htmlPath = path.join(reportsDir, 'index.html');
  const tmpHtmlPath = htmlPath + '.tmp';
  fs.writeFileSync(tmpHtmlPath, renderIndexHtml(index), 'utf8');
  fs.renameSync(tmpHtmlPath, htmlPath);
}

const STATUS_LABEL = { 'draft': 'Draft', 'in-review': 'In review', 'reviewed': 'Reviewed', 'final': 'Final' };

function escAttr(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
}
function escText(s) {
  return String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[c]));
}

function renderRow(r) {
  const tags = Array.isArray(r.tags) ? r.tags.join(' · ') : '';
  const status = r.status || 'draft';
  const label = STATUS_LABEL[status] || status;
  return `<tr tabindex="0" data-href="${escAttr(r.href)}">` +
    `<td class="col-date">${escText(r.date)}</td>` +
    `<td class="col-title"><a href="${escAttr(r.href)}">${escText(r.title)}</a></td>` +
    `<td class="col-tags">${escText(tags)}</td>` +
    `<td class="col-read">${escText(r.reading_time_min + 'm')}</td>` +
    `<td class="col-status"><span class="status-dot status-dot--${escAttr(status)}"></span>${escText(label)}</td>` +
  `</tr>`;
}

export function renderIndexHtml(index) {
  const template = fs.readFileSync(INDEX_TEMPLATE_PATH, 'utf8');
  const countLabel = index.report_count === 1
    ? '1 report'
    : `${index.report_count} reports`;
  const tbodyHtml = (index.reports || []).map(renderRow).join('\n');
  return template
    .replace('{{REPORT_COUNT_LABEL}}', countLabel)
    .replace('{{REPORTS_TBODY}}', tbodyHtml)
    .replace('{{REPORTS_JSON}}', safeJsonForScript(index));
}

// ---------- sweep inline snapshots ----------

const REPORT_INDEX_RE = /<script id="report-index" type="application\/json">[\s\S]*?<\/script>/;

export function sweepInlineIndex(reportsDir, index) {
  if (!fs.existsSync(reportsDir)) return;
  for (const name of fs.readdirSync(reportsDir)) {
    if (!name.endsWith('.html')) continue;
    if (name === 'index.html') continue;
    const full = path.join(reportsDir, name);
    try {
      const stat = fs.statSync(full);
      if (!stat.isFile()) continue;
      const html = fs.readFileSync(full, 'utf8');
      if (!REPORT_INDEX_RE.test(html)) continue;
      const slug = deriveSlug(name);
      const snapshot = { ...index, current_slug: slug };
      const block = `<script id="report-index" type="application/json">\n${safeJsonForScript(snapshot)}\n</script>`;
      const next = html.replace(REPORT_INDEX_RE, block);
      if (next !== html) {
        fs.writeFileSync(full, next, 'utf8');
      }
    } catch (err) {
      process.stderr.write(`sweep: ${name} — ${err.message}\n`);
    }
  }
}
