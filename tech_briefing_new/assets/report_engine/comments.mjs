const MARKER_RE = /<!--\s*@report-comment\s+([^\n\r]*)\r?\n([\s\S]*?)-->/g;

function escapeAttr(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function unescapeAttr(value) {
  return String(value ?? '')
    .replace(/&quot;/g, '"')
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&');
}

function parseAttrs(source) {
  const attrs = {};
  const re = /([a-zA-Z_:-]+)="([^"]*)"/g;
  let match;
  while ((match = re.exec(source))) {
    attrs[match[1]] = unescapeAttr(match[2]);
  }
  return attrs;
}

function splitResolvedNote(text) {
  const normalized = String(text ?? '').trim();
  const match = normalized.match(/(?:^|\n{2,})Resolved:\s*([\s\S]*?)\s*$/);
  if (!match) return { body: normalized, resolvedNote: '' };
  return {
    body: normalized.slice(0, match.index).trim(),
    resolvedNote: match[1].trim(),
  };
}

export function parseReportComments(markdown) {
  const comments = [];
  let match;
  MARKER_RE.lastIndex = 0;
  while ((match = MARKER_RE.exec(markdown))) {
    const attrs = parseAttrs(match[1]);
    const { body, resolvedNote } = splitResolvedNote(match[2]);
    comments.push({
      id: attrs.id || '',
      status: attrs.status === 'resolved' ? 'resolved' : 'open',
      target: attrs.target || '',
      body,
      resolvedNote,
      raw: match[0],
      start: match.index,
      end: match.index + match[0].length,
    });
  }
  return comments;
}

export function filterReportComments(comments, status = 'all') {
  if (status === 'open' || status === 'resolved') {
    return comments.filter(comment => comment.status === status);
  }
  return comments;
}

export function formatReviewSummary(comments, title = 'Report') {
  const open = comments.filter(comment => comment.status !== 'resolved');
  const resolved = comments.filter(comment => comment.status === 'resolved');
  const sections = comments.map(comment => {
    const resolvedText = comment.resolvedNote
      ? `\n\nResolved: ${comment.resolvedNote}`
      : '';
    return `## ${comment.id} — ${comment.status || 'open'} — ${comment.target}\n\n${comment.body || ''}${resolvedText}\n`;
  });

  return [
    `# Review Comments: ${title}`,
    '',
    `Open comments: ${open.length}`,
    `Resolved comments: ${resolved.length}`,
    `Total comments: ${comments.length}`,
    '',
    ...sections,
  ].join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

export function serializeReportComment(comment) {
  const id = comment.id || createCommentId();
  const status = comment.status === 'resolved' ? 'resolved' : 'open';
  const target = comment.target || '';
  const body = String(comment.body ?? '').trim();
  const resolvedNote = String(comment.resolvedNote ?? '').trim();
  const resolvedText = status === 'resolved' && resolvedNote
    ? `\n\nResolved: ${resolvedNote}`
    : '';

  return `<!-- @report-comment id="${escapeAttr(id)}" status="${status}" target="${escapeAttr(target)}"\n${body}${resolvedText}\n-->`;
}

export function cleanReportComments(markdown) {
  return String(markdown).replace(MARKER_RE, '').replace(/\n{3,}/g, '\n\n');
}

export function deleteReportComment(markdown, id) {
  const comment = parseReportComments(markdown).find(c => c.id === id);
  if (!comment) return markdown;
  return markdown.slice(0, comment.start) + markdown.slice(comment.end);
}

export function updateReportComment(markdown, id, patch = {}) {
  const comment = parseReportComments(markdown).find(c => c.id === id);
  if (!comment) return markdown;
  const next = serializeReportComment({ ...comment, ...patch, id });
  return markdown.slice(0, comment.start) + next + markdown.slice(comment.end);
}

// Replace the prose body of `currentMarkdown` with `newBody`, preserving any
// existing @report-comment markers re-anchored to their original target
// blocks. Used by the review server's PUT /api/source so an in-browser edit
// does not wipe comments that live alongside the source.
export function replaceBodyKeepingComments(currentMarkdown, newBody) {
  const comments = parseReportComments(currentMarkdown);
  const incoming = cleanReportComments(newBody);
  if (!comments.length) return incoming;
  let result = incoming;
  for (const c of comments) {
    result = insertReportComment(result, {
      id: c.id,
      status: c.status,
      target: c.target,
      body: c.body,
      resolvedNote: c.resolvedNote,
    }, blockIndexFromTarget(c.target));
  }
  return result;
}

export function insertReportComment(markdown, comment, blockIndex = 0) {
  const starts = findMarkdownBlockStarts(markdown);
  const index = Math.max(0, Math.min(Number(blockIndex) || 0, starts.length));
  const offset = starts[index] ?? markdown.length;
  const marker = serializeReportComment(comment);
  const before = markdown.slice(0, offset).replace(/[ \t]+$/u, '');
  const after = markdown.slice(offset).replace(/^\n*/u, '');
  const separatorBefore = before.endsWith('\n\n') || before.length === 0 ? '' : '\n\n';
  const separatorAfter = after.length ? '\n\n' : '\n';
  return `${before}${separatorBefore}${marker}${separatorAfter}${after}`;
}

export function extractEmbeddedMarkdown(html) {
  const match = String(html).match(/<script id="source-md"[^>]*>([\s\S]*?)<\/script>/);
  if (!match) {
    throw new Error('No <script id="source-md"> block found.');
  }
  return match[1].replace(/^\r?\n/, '');
}

export function replaceEmbeddedMarkdown(html, markdown) {
  const source = String(html);
  const match = source.match(/(<script id="source-md"[^>]*>)([\s\S]*?)(<\/script>)/);
  if (!match) {
    throw new Error('No <script id="source-md"> block found.');
  }
  const normalized = String(markdown).replace(/\s*$/u, '\n');
  return source.slice(0, match.index)
    + `${match[1]}\n${normalized}${match[3]}`
    + source.slice(match.index + match[0].length);
}

export function createCommentId(existingIds = []) {
  const used = new Set(existingIds);
  for (let i = 1; i < 100000; i++) {
    const id = `c${i}`;
    if (!used.has(id)) return id;
  }
  return `c${Date.now().toString(36)}`;
}

export function blockIndexFromTarget(target) {
  const match = String(target || '').match(/^block:b(\d+)$/);
  if (!match) return 0;
  return Math.max(0, Number(match[1]) - 1);
}

export function findMarkdownBlockStarts(markdown) {
  const text = String(markdown);
  const lineMatches = [...text.matchAll(/^.*(?:\n|$)/gm)].filter(m => m[0].length > 0);
  const lines = lineMatches.map(match => ({
    text: match[0].replace(/\n$/u, ''),
    start: match.index,
  }));
  const starts = [];
  let i = 0;

  if (lines[0]?.text.trim() === '---') {
    i = 1;
    while (i < lines.length && lines[i].text.trim() !== '---') i++;
    if (i < lines.length) i++;
  }

  while (i < lines.length) {
    const line = lines[i].text;

    if (/^\s*$/.test(line)) {
      i++;
      continue;
    }

    if (/^\s*<!--\s*@report-comment\b/.test(line)) {
      i++;
      while (i < lines.length && !/-->\s*$/.test(lines[i - 1].text)) i++;
      continue;
    }

    starts.push(lines[i].start);

    if (/^```\s*/.test(line)) {
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i].text)) i++;
      if (i < lines.length) i++;
      continue;
    }

    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      i++;
      while (i < lines.length && /^\s{2,}\S/.test(lines[i].text)) i++;
      continue;
    }

    if (/^>\s?/.test(line)) {
      i++;
      while (i < lines.length && /^>\s?/.test(lines[i].text)) i++;
      continue;
    }

    if (line.includes('|') && i + 1 < lines.length && /^[\s|:\-]+$/.test(lines[i + 1].text) && lines[i + 1].text.includes('-')) {
      i += 2;
      while (i < lines.length && lines[i].text.includes('|') && !/^\s*$/.test(lines[i].text)) {
        starts.push(lines[i].start);
        i++;
      }
      continue;
    }

    if (i + 1 < lines.length && /^:\s+/.test(lines[i + 1].text)) {
      i += 2;
      while (i < lines.length && /^\s{2,}\S/.test(lines[i].text)) i++;
      continue;
    }

    i++;
    while (
      i < lines.length
      && !/^\s*$/.test(lines[i].text)
      && !/^(#{1,4})\s+/.test(lines[i].text)
      && !/^[-*]\s+/.test(lines[i].text)
      && !/^\d+\.\s+/.test(lines[i].text)
      && !/^>\s?/.test(lines[i].text)
      && !/^!\[.*\]\(.*\)\s*$/.test(lines[i].text)
      && !/^```/.test(lines[i].text)
    ) {
      i++;
    }
  }

  return starts;
}
