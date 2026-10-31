#!/usr/bin/env node
/*
 * clean-comments.mjs — remove @report-comment markers from a rendered report.
 *
 * Usage:
 *   node clean-comments.mjs <input.html>
 *
 * The script extracts the embedded Markdown, strips all review comment markers,
 * and re-renders the same HTML path so visible review annotations disappear too.
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { cleanReportComments, extractEmbeddedMarkdown } from './comments.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function usage() {
  console.error('Usage: node clean-comments.mjs <input.html>');
}

const args = process.argv.slice(2);
if (args.length !== 1) {
  usage();
  process.exit(1);
}

const htmlPath = path.resolve(args[0]);
if (!fs.existsSync(htmlPath)) {
  console.error(`error: input not found: ${htmlPath}`);
  process.exit(1);
}

const html = fs.readFileSync(htmlPath, 'utf8');
let markdown;
try {
  markdown = extractEmbeddedMarkdown(html);
} catch (error) {
  console.error(`error: ${error.message}`);
  process.exit(2);
}

const cleaned = cleanReportComments(markdown).trim() + '\n';
const tempPath = path.join(os.tmpdir(), `report-clean-${process.pid}-${Date.now()}.md`);

try {
  fs.writeFileSync(tempPath, cleaned, 'utf8');
  execFileSync('node', [path.join(__dirname, 'render.mjs'), tempPath, htmlPath], { stdio: 'pipe' });
  console.log(`✓ cleaned report comments: ${htmlPath}`);
} finally {
  try {
    fs.unlinkSync(tempPath);
  } catch {
    // Best effort cleanup only.
  }
}
