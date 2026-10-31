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
