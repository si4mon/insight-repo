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
