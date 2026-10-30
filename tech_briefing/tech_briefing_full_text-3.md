assets/report_engine/template.html
----------------------------------------
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<script>document.documentElement.classList.add('js-on');</script>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>On the Failure Modes of LLM-Generated Frontend Code</title>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap">

<style>
/* ---------- Tokens ---------- */
:root {
  /* Base palette — warm hue 85° anchors both modes */
  --bg:           oklch(0.972 0.012 85);
  --bg-elevated:  oklch(0.945 0.014 85);
  --bg-code:      oklch(0.935 0.014 85);
  --bg-mark:      oklch(0.93  0.05  35);

  --text:         oklch(0.22  0.018 85);
  --text-muted:   oklch(0.45  0.014 85);
  --text-subtle:  oklch(0.58  0.012 85);
  --text-faint:   oklch(0.72  0.010 85);

  --rule:         oklch(0.86  0.012 85);
  --rule-strong:  oklch(0.78  0.014 85);

  --accent:       oklch(0.50  0.135 35);
  --accent-soft:  oklch(0.92  0.04  35);
  --accent-ring:  oklch(0.55  0.16  35 / 0.40);

  /* Syntax — three colors only */
  --syn-keyword:  oklch(0.50  0.135 35);
  --syn-string:   oklch(0.48  0.075 200);
  --syn-comment:  oklch(0.58  0.010 85);

  /* Type */
  --font-body:  'Newsreader', 'Iowan Old Style', Georgia, 'Times New Roman', serif;
  --font-ui:    'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --font-mono:  'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;

  --fs-body:    1.125rem;   /* 18px */
  --lh-body:    1.6;
  --measure:    68ch;

  /* 4pt scale */
  --s-1: 0.25rem; --s-2: 0.5rem; --s-3: 0.75rem;
  --s-4: 1rem;    --s-6: 1.5rem; --s-8: 2rem;
  --s-12: 3rem;   --s-16: 4rem;  --s-24: 6rem;
}

[data-theme="dark"] {
  /* Ink-dark — near-black with a faint cool cast, terracotta accent kept */
  --bg:           oklch(0.135 0.008 260);
  --bg-elevated:  oklch(0.175 0.008 260);
  --bg-code:      oklch(0.185 0.008 260);
  --bg-mark:      oklch(0.32  0.08  35);

  --text:         oklch(0.94  0.006 260);
  --text-muted:   oklch(0.72  0.006 260);
  --text-subtle:  oklch(0.55  0.006 260);
  --text-faint:   oklch(0.40  0.006 260);

  --rule:         oklch(0.27  0.008 260);
  --rule-strong:  oklch(0.38  0.008 260);

  --accent:       oklch(0.74  0.13  35);
  --accent-soft:  oklch(0.30  0.08  35);
  --accent-ring:  oklch(0.74  0.14  35 / 0.45);

  --syn-keyword:  oklch(0.74  0.13  35);
  --syn-string:   oklch(0.78  0.10  175);
  --syn-comment:  oklch(0.55  0.006 260);
}

/* ---------- Reset & base ---------- */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; tab-size: 4; }
html, body { margin: 0; padding: 0; }
body {
  font-family: var(--font-body);
  font-size: var(--fs-body);
  line-height: var(--lh-body);
  font-optical-sizing: auto;
  font-variant-numeric: oldstyle-nums proportional-nums;
  background: var(--bg);
  color: var(--text);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition: background-color 200ms cubic-bezier(.22,1,.36,1), color 200ms cubic-bezier(.22,1,.36,1);
}
[data-theme="dark"] body { font-weight: 380; }

/* Selection */
::selection { background: var(--accent-soft); color: var(--text); }
[data-theme="dark"] ::selection { background: var(--accent-soft); color: var(--text); }

/* Focus */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  border-radius: 2px;
}

/* ---------- Skip link ---------- */
.skip-link {
  position: fixed;
  top: -100px; left: var(--s-4);
  z-index: 100;
  padding: var(--s-2) var(--s-4);
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-ui);
  font-size: 0.875rem;
  border: 1px solid var(--rule-strong);
  border-radius: 4px;
  text-decoration: none;
  transition: top 150ms ease-out;
}
.skip-link:focus-visible { top: var(--s-4); }

/* ---------- Reading progress ---------- */
.progress {
  position: fixed; top: 0; left: 0; right: 0;
  height: 2px;
  background: transparent;
  z-index: 50;
  pointer-events: none;
}
.progress__bar {
  height: 100%;
  width: 0;
  background: var(--accent);
  transform-origin: left;
  transition: width 90ms linear;
}

/* ---------- Top edge fade ---------- */
.page-fade-top {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 24px;
  pointer-events: none;
  background: linear-gradient(to bottom, var(--bg) 0%, transparent 100%);
  z-index: 22;
}

/* ---------- Topbar ---------- */
.topbar {
  position: fixed;
  top: var(--s-4); right: var(--s-4);
  z-index: 30;
  display: flex;
  gap: var(--s-2);
  align-items: center;
}
.topbar__btn {
  display: inline-flex;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-2) var(--s-3);
  min-height: 36px;
  background: var(--bg);
  color: var(--text-muted);
  border: 1px solid var(--rule);
  border-radius: 999px;
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: color 150ms, border-color 150ms, background 150ms;
}
.topbar__btn:hover { color: var(--text); border-color: var(--rule-strong); }
a.topbar__btn { text-decoration: none; }
.topbar__btn svg { width: 16px; height: 16px; }
.topbar__btn .label { display: none; }
.topbar__btn.is-active { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); }
#review-comment-toggle { display: none; }
[data-review-mode="true"] #review-comment-toggle { display: inline-flex; }
@media (min-width: 640px) {
  .topbar__btn .label { display: inline; }
}

/* ---------- Section indicator (phase 3) ---------- */
.section-indicator {
  position: fixed;
  top: var(--s-4); left: var(--s-4);
  z-index: 30;
  display: flex; align-items: center;
  min-height: 36px;
  padding: var(--s-2) var(--s-3);
  font-family: var(--font-ui);
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  max-width: 32ch;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  opacity: 0;
  transition: opacity 200ms cubic-bezier(.22, 1, .36, 1);
  pointer-events: none;
}
.section-indicator.is-visible { opacity: 1; }

@media (max-width: 640px) { .section-indicator { display: none; } }

/* ---------- Edit mode ---------- */
[data-edit-mode="true"] .article { outline: none; }
[data-edit-mode="true"] .article :focus { outline: none; }
[data-edit-mode="true"] .article *[contenteditable="true"]:focus,
[data-edit-mode="true"] .article:focus { outline: none; }
[data-edit-mode="true"] .article h1,
[data-edit-mode="true"] .article h2,
[data-edit-mode="true"] .article h3,
[data-edit-mode="true"] .article h4,
[data-edit-mode="true"] .article p,
[data-edit-mode="true"] .article li,
[data-edit-mode="true"] .article dt,
[data-edit-mode="true"] .article dd,
[data-edit-mode="true"] .article td,
[data-edit-mode="true"] .article th,
[data-edit-mode="true"] .article figcaption,
[data-edit-mode="true"] .article blockquote,
[data-edit-mode="true"] .article pre {
  border-radius: 2px;
  transition: background 120ms;
}
[data-edit-mode="true"] .article *:hover:not(svg):not(path):not(circle):not(line):not(g) {
  background: color-mix(in oklch, var(--accent-soft) 35%, transparent);
}
[data-edit-mode="true"] .article *:focus-within:not(svg) {
  background: color-mix(in oklch, var(--accent-soft) 60%, transparent);
}
[data-edit-mode="true"] .heading-anchor,
[data-edit-mode="true"] .codeblock__copy,
[data-edit-mode="true"] .fn-back {
  display: none !important;
}
[data-edit-mode="true"] .fnref {
  pointer-events: none;
}
[data-edit-mode="true"] .article {
  caret-color: var(--accent);
}
.edit-status {
  position: fixed;
  left: var(--s-4);
  bottom: var(--s-4);
  z-index: 25;
  font-family: var(--font-ui);
  font-size: 0.75rem;
  color: var(--text-subtle);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--bg-elevated);
  padding: var(--s-2) var(--s-3);
  border: 1px solid var(--rule);
  border-radius: 999px;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 200ms, transform 200ms;
  pointer-events: none;
}
[data-edit-mode="true"] .edit-status {
  opacity: 1;
  transform: translateY(0);
}
.edit-status .dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: var(--s-2);
  border-radius: 50%;
  background: var(--accent);
  vertical-align: middle;
}

/* ---------- Review comments ---------- */
[data-review-mode="true"] [data-comment-mode="true"] [data-report-block-id] {
  cursor: cell;
}
[data-review-mode="true"] [data-comment-mode="true"] [data-report-block-id]:hover {
  outline: 1px solid color-mix(in oklch, var(--accent) 45%, transparent);
  outline-offset: 4px;
  background: color-mix(in oklch, var(--accent-soft) 28%, transparent);
}
.report-comment-margin {
  display: grid;
  gap: var(--s-3);
  margin: var(--s-2) 0 var(--s-6);
  padding-left: var(--s-3);
  border-left: 1px solid color-mix(in oklch, var(--accent) 48%, var(--rule));
  font-family: var(--font-ui);
}
@media (min-width: 1180px) {
  .report-comment-margin {
    float: right;
    clear: right;
    width: 15rem;
    margin: calc(-1 * var(--s-2)) calc(-15rem - var(--s-8)) var(--s-6) var(--s-8);
    padding-left: var(--s-3);
  }
}
.report-comment-note {
  position: relative;
  display: grid;
  gap: var(--s-2);
  color: var(--text-muted);
}
.report-comment-note + .report-comment-note {
  padding-top: var(--s-2);
  border-top: 1px solid color-mix(in oklch, var(--rule) 70%, transparent);
}
.report-comment-note::before {
  content: "";
  position: absolute;
  left: calc(-1 * var(--s-3) - 4px);
  top: 0.35rem;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--accent);
}
.report-comment-note[data-report-comment-status="resolved"] {
  opacity: 0.72;
}
.report-comment-note[data-report-comment-status="resolved"]::before {
  background: var(--text-subtle);
}
.report-comment-note.is-active {
  opacity: 1;
}
.report-comment-note.is-active::before {
  box-shadow: 0 0 0 4px var(--accent-ring);
}
.report-comment-note__meta {
  display: inline-flex;
  align-items: center;
  gap: var(--s-2);
  width: fit-content;
  color: var(--accent);
  font: 700 0.6875rem/1 var(--font-mono);
  letter-spacing: 0.07em;
  text-decoration: none;
  text-transform: uppercase;
}
.report-comment-note__meta[data-report-comment-status="resolved"] {
  color: var(--text-subtle);
}
.report-comment-note__meta.is-active {
  outline: 2px solid var(--accent-ring);
  outline-offset: 3px;
}
.report-comment-note__id {
  color: currentColor;
  opacity: 0.72;
}
.report-comment-note__body,
.report-comment-note__resolved {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.48;
}
.report-comment-note__resolved {
  color: var(--text-subtle);
}
[data-report-block-id].is-review-active {
  outline: 2px solid var(--accent);
  outline-offset: 4px;
}
[data-report-block-id].is-review-flash {
  animation: reviewFlash 1300ms ease-out;
}
@keyframes reviewFlash {
  0% { background: color-mix(in oklch, var(--accent-soft) 70%, transparent); }
  100% { background: transparent; }
}
.review-mode-banner {
  position: fixed;
  left: 50%;
  top: var(--s-4);
  z-index: 35;
  display: none;
  align-items: center;
  gap: var(--s-3);
  transform: translateX(-50%);
  padding: var(--s-2) var(--s-3);
  border: 1px solid var(--accent);
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--text);
  font: 600 0.8125rem/1.2 var(--font-ui);
}
[data-review-mode="true"] [data-comment-mode="true"] .review-mode-banner {
  display: inline-flex;
}
.review-mode-banner button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  border: 1px solid color-mix(in oklch, var(--accent) 45%, transparent);
  border-radius: 999px;
  background: transparent;
  color: var(--accent);
  cursor: pointer;
  font: 700 0.875rem/1 var(--font-ui);
}
.review-rail {
  display: none;
  gap: var(--s-2);
}
[data-review-mode="true"] .review-rail {
  display: inline-flex;
}
.review-rail:hover,
.review-rail[aria-expanded="true"] {
  border-color: var(--accent);
  color: var(--accent);
}
.review-rail__label {
  display: none;
}
.review-rail__counts {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--s-1);
  min-width: 0;
  padding: var(--s-1) var(--s-2);
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.6875rem;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}
@media (min-width: 640px) {
  .review-rail__label {
    display: inline;
  }
}
.review-tray {
  position: fixed;
  top: 4.75rem;
  right: var(--s-4);
  bottom: var(--s-4);
  z-index: 28;
  width: min(360px, calc(100vw - 2rem));
  padding: var(--s-4);
  overflow-y: auto;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: color-mix(in oklch, var(--bg) 96%, transparent);
  box-shadow: 0 18px 60px oklch(0 0 0 / 0.16);
  font-family: var(--font-ui);
  opacity: 0;
  pointer-events: none;
  transform: translateX(calc(100% + var(--s-6)));
  transition: opacity 180ms ease, transform 180ms ease;
}
[data-review-mode="true"] .review-tray.review-tray--open {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(0);
}
.review-tray__header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: var(--s-3);
  margin-bottom: var(--s-3);
}
.review-tray__title {
  margin: 0;
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text);
}
.review-tray__counts {
  margin: var(--s-1) 0 0;
  font-size: 0.75rem;
  color: var(--text-subtle);
}
.review-tray__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  cursor: pointer;
  font: 700 1rem/1 var(--font-ui);
}
.review-tray__close:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.review-tray__filter {
  display: flex;
  gap: var(--s-1);
  margin-bottom: var(--s-4);
}
.review-tray__filter button,
.review-tray__action {
  min-height: 30px;
  padding: var(--s-1) var(--s-2);
  border: 1px solid var(--rule);
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  font: 600 0.75rem/1 var(--font-ui);
  cursor: pointer;
}
.review-tray__filter button[aria-pressed="true"],
.review-tray__action:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.review-tray__list {
  display: grid;
  gap: var(--s-2);
}
.review-tray__empty {
  margin: var(--s-6) 0;
  color: var(--text-subtle);
  font-size: 0.875rem;
}
.review-tray__item {
  width: 100%;
  padding: var(--s-3);
  text-align: left;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
}
.review-tray__item.is-active {
  border-color: var(--accent);
  box-shadow: inset 3px 0 0 var(--accent);
}
.review-tray__item-meta {
  display: flex;
  justify-content: space-between;
  gap: var(--s-2);
  margin-bottom: var(--s-2);
  font: 600 0.6875rem/1.3 var(--font-mono);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-subtle);
}
.review-tray__item-body {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.45;
}
.review-tray__links,
.review-tray__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2);
  margin-top: var(--s-3);
}
.review-tray__links a {
  font-size: 0.75rem;
  color: var(--text-subtle);
}
@media (max-width: 900px) {
  .review-tray {
    top: auto;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    max-height: 45vh;
    border-radius: 8px 8px 0 0;
    transform: translateY(calc(100% + var(--s-4)));
  }
  [data-review-mode="true"] .review-tray.review-tray--open {
    transform: translateY(0);
  }
}
/* ---------- Comment popup (unified atom) ---------- */
.report-comment-pop {
  font-family: var(--font-ui);
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--rule-strong);
  border-radius: 6px;
  width: min(320px, 100%);
  box-sizing: border-box;
  opacity: 1;
  animation: report-comment-pop-fade 120ms ease-out;
}
@keyframes report-comment-pop-fade {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .report-comment-pop { animation: none; }
}
.report-comment-pop--rail {
  position: sticky;
  top: var(--s-4);
  bottom: var(--s-4);
  margin: var(--s-2) 0;
}
.report-comment-pop--rail::before {
  content: "";
  position: absolute;
  left: -22px;
  top: 18px;
  width: 22px;
  height: 1px;
  background: var(--rule-strong);
}
.report-comment-pop--rail::after {
  content: "";
  position: absolute;
  left: -24px;
  top: 15px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
}
.report-comment-pop--float {
  position: absolute;
  z-index: 70;
  box-shadow: 0 8px 24px oklch(0 0 0 / 0.08), 0 2px 6px oklch(0 0 0 / 0.04);
}
.report-comment-pop--float::before {
  content: "";
  position: absolute;
  top: -6px;
  left: 24px;
  width: 10px;
  height: 10px;
  background: var(--bg);
  border-top: 1px solid var(--rule-strong);
  border-left: 1px solid var(--rule-strong);
  transform: rotate(45deg);
}
.report-comment-pop--float[data-tail-side="above"]::before {
  top: auto;
  bottom: -6px;
  border-top: none;
  border-left: none;
  border-bottom: 1px solid var(--rule-strong);
  border-right: 1px solid var(--rule-strong);
}
.report-comment-pop__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--s-2) var(--s-3);
  border-bottom: 1px solid var(--rule);
  font-size: 0.7rem;
  color: var(--text-subtle);
}
.report-comment-pop__id {
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  color: var(--text-mute);
}
.report-comment-pop__status {
  color: var(--text-subtle);
}
.report-comment-pop__pill {
  border: 1px solid var(--rule);
  border-radius: 9999px;
  padding: 1px 8px;
  margin-left: var(--s-2);
  font-size: 0.66rem;
  background: var(--bg-elevated);
  color: var(--text-subtle);
  cursor: pointer;
}
.report-comment-pop__pill:hover { border-color: var(--accent); color: var(--accent); }
.report-comment-pop__body {
  padding: var(--s-3);
}
.report-comment-pop__field {
  width: 100%;
  min-height: 84px;
  border: 1px solid var(--rule);
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text);
  padding: var(--s-2) var(--s-3);
  font: 0.92rem/1.5 var(--font-ui);
  resize: vertical;
  box-sizing: border-box;
}
.report-comment-pop__field:focus { outline: none; border-color: var(--accent); }
.report-comment-pop__hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--s-2) var(--s-3) var(--s-3);
  font-size: 0.72rem;
  color: var(--text-mute);
  gap: var(--s-2);
}
.report-comment-pop__keys kbd {
  display: inline-block;
  border: 1px solid var(--rule);
  border-bottom-width: 2px;
  border-radius: 3px;
  padding: 1px 5px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  background: var(--bg-elevated);
  color: var(--text-subtle);
}
.report-comment-pop__actions {
  display: flex;
  gap: var(--s-3);
  align-items: center;
}
.report-comment-pop__actions button {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: var(--text-subtle);
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: var(--rule);
  text-underline-offset: 3px;
}
.report-comment-pop__actions button:hover {
  color: var(--accent);
  text-decoration-color: var(--accent);
}
.report-comment-pop__actions button[data-action="save"] {
  color: var(--accent);
  font-weight: 600;
}
.report-comment-pop__actions button[data-action="delete"]:hover {
  color: oklch(0.55 0.18 30);
  text-decoration-color: oklch(0.55 0.18 30);
}
.report-comment-pop__actions button[disabled] { opacity: 0.4; cursor: default; }
.report-comment-pop__message {
  min-height: 1rem;
  color: var(--text-subtle);
}
/* ---------- /Comment popup ---------- */

/* ---------- Layout ---------- */
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  max-width: 100%;
  padding: var(--s-24) var(--s-6) var(--s-16);
}
@media (min-width: 1024px) {
  .layout {
    grid-template-columns: 220px minmax(0, 68ch);
    column-gap: var(--s-12);
    justify-content: center;
    padding: var(--s-24) var(--s-8);
  }
}
@media (min-width: 1280px) {
  .layout {
    grid-template-columns: 220px minmax(0, 68ch) 240px;
    column-gap: var(--s-12);
  }
}

/* ---------- Table of contents ---------- */
.toc {
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  line-height: 1.55;
  color: var(--text-muted);
}
.toc__heading {
  font-family: var(--font-ui);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-subtle);
  margin: 0 0 var(--s-3);
}
.toc__list { list-style: none; padding: 0; margin: 0; }
.toc__list .toc__list { padding-left: var(--s-4); margin-top: var(--s-1); margin-bottom: var(--s-2); }
.toc__item { position: relative; }
.toc__link {
  display: block;
  padding: 4px 0 4px 14px;
  color: var(--text-muted);
  text-decoration: none;
  border-left: 1px solid transparent;
  transition: color 120ms, border-color 120ms;
}
.toc__link:hover { color: var(--text); }
.toc__link.is-active {
  color: var(--accent);
  font-weight: 600;
}
.toc__link.is-active::before {
  content: "▸";
  position: absolute;
  left: 0;
  top: 4px;
  color: var(--accent);
  font-size: 0.7rem;
  line-height: 1.55;
}

/* Mobile/tablet ToC = sticky accordion at top */
@media (max-width: 1023px) {
  .toc-rail {
    position: sticky;
    top: 0;
    z-index: 20;
    background: color-mix(in oklch, var(--bg) 92%, transparent);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    margin: calc(var(--s-24) * -1) calc(var(--s-6) * -1) var(--s-12);
    padding: var(--s-4) var(--s-6);
    border-bottom: 1px solid var(--rule);
  }
  .toc-rail__toggle {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: none;
    border: 0;
    padding: 0;
    color: var(--text);
    font-family: var(--font-ui);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
  }
  .toc-rail__toggle svg {
    transition: transform 200ms cubic-bezier(.22,1,.36,1);
  }
  .toc-rail[data-open="true"] .toc-rail__toggle svg {
    transform: rotate(180deg);
  }
  .toc {
    max-height: 0;
    overflow: hidden;
    transition: max-height 250ms cubic-bezier(.22,1,.36,1);
  }
  .toc-rail[data-open="true"] .toc {
    max-height: 70vh;
    overflow-y: auto;
    margin-top: var(--s-4);
    scrollbar-width: none;
  }
  .toc-rail[data-open="true"] .toc::-webkit-scrollbar { display: none; }
  .toc__heading { display: none; }
}

@media (min-width: 1024px) {
  .toc-rail {
    position: sticky;
    top: var(--s-12);
    align-self: start;
    max-height: calc(100vh - var(--s-24));
    overflow-y: auto;
    padding-right: var(--s-4);
    scrollbar-width: none;
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 32px), transparent);
            mask-image: linear-gradient(to bottom, #000 calc(100% - 32px), transparent);
  }
  .toc-rail::-webkit-scrollbar { display: none; }
  .toc-rail__toggle { display: none; }
}

/* ---------- Sidenote rail ---------- */
.sidenote-rail {
  position: relative;
}
@media (max-width: 1279px) {
  .sidenote-rail { display: none; }
}

/* ---------- Article ---------- */
.article {
  max-width: 68ch;
  margin: 0 auto;
  position: relative; /* so sidenotes can absolute-position into the right rail */
}

.article-header { margin-bottom: var(--s-16); }

.eyebrow {
  font-family: var(--font-ui);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 var(--s-4);
}

h1 {
  font-family: var(--font-body);
  font-size: clamp(2rem, 1.6rem + 1.8vw, 2.875rem);
  font-weight: 500;
  line-height: 1.12;
  letter-spacing: -0.018em;
  text-wrap: balance;
  margin: 0 0 var(--s-4);
  color: var(--text);
}

.lede {
  font-family: var(--font-body);
  font-size: 1.3125rem;
  font-style: italic;
  font-weight: 350;
  line-height: 1.5;
  color: var(--text-muted);
  margin: 0 0 var(--s-12);
  text-wrap: pretty;
  max-width: 60ch;
}

/* Metadata block */
.meta {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--s-1) var(--s-6);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.55;
  padding: var(--s-4) 0;
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  color: var(--text-muted);
  margin: 0;
}
.meta dt {
  color: var(--text-subtle);
  font-weight: 400;
  text-transform: lowercase;
  letter-spacing: 0.01em;
}
.meta dd {
  margin: 0;
  color: var(--text);
}
.meta dd .tag {
  display: inline;
  margin-right: var(--s-2);
  color: var(--text-muted);
}
.meta dd .tag::before { content: "#"; color: var(--text-subtle); }

/* Section */
section { margin-top: var(--s-16); }

h2 {
  font-family: var(--font-body);
  font-size: 1.875rem;
  font-weight: 500;
  line-height: 1.18;
  letter-spacing: -0.012em;
  text-wrap: balance;
  margin: 0 0 var(--s-4);
  color: var(--text);
  scroll-margin-top: var(--s-12);
  position: relative;
}
h2::before {
  content: "";
  display: block;
  width: 56px;
  height: 1px;
  background: var(--rule-strong);
  margin-bottom: var(--s-6);
}

h3 {
  font-family: var(--font-body);
  font-size: 1.375rem;
  font-weight: 500;
  line-height: 1.25;
  letter-spacing: -0.008em;
  text-wrap: balance;
  margin: var(--s-12) 0 var(--s-3);
  color: var(--text);
  scroll-margin-top: var(--s-12);
}

h4 {
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--text-subtle);
  margin: var(--s-8) 0 var(--s-3);
}

/* Anchor link on hover */
.heading-anchor {
  position: absolute;
  left: -1.4em;
  top: 50%;
  transform: translateY(-50%);
  width: 1em; height: 1em;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  text-decoration: none;
  font-family: var(--font-ui);
  font-size: 0.875rem;
  font-weight: 500;
  opacity: 0;
  transition: opacity 150ms, color 150ms;
}
h2:hover .heading-anchor,
h3:hover .heading-anchor,
h2 .heading-anchor:focus-visible,
h3 .heading-anchor:focus-visible { opacity: 1; }
.heading-anchor:hover { color: var(--accent); }
@media (max-width: 768px) {
  .heading-anchor { display: none; }
}

/* Body text */
p, ul, ol, dl, blockquote, figure, table, pre {
  margin: 0 0 var(--s-6);
}
p {
  font-feature-settings: "kern", "liga", "onum";
  text-wrap: pretty;
  hyphens: auto;
  -webkit-hyphens: auto;
  overflow-wrap: anywhere;
}
.section-lede {
  font-style: italic;
  font-size: 1.1875rem;
  line-height: 1.55;
  color: var(--text-muted);
  margin-bottom: var(--s-8);
  max-width: 60ch;
}

a {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 0.18em;
  text-decoration-color: color-mix(in oklch, var(--accent) 50%, transparent);
  transition: text-decoration-color 120ms;
}
a:hover { text-decoration-color: var(--accent); }

strong { font-weight: 600; color: var(--text); }
em { font-style: italic; }
mark {
  background: var(--bg-mark);
  color: var(--text);
  padding: 0 0.15em;
  border-radius: 1px;
}
small { font-size: 0.875em; color: var(--text-muted); }
abbr[title] { text-decoration: underline dotted; cursor: help; }
kbd {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.8125em;
  padding: 0.1em 0.4em;
  background: var(--bg-elevated);
  border: 1px solid var(--rule);
  border-bottom-width: 2px;
  border-radius: 3px;
  color: var(--text);
}

/* Lists */
ul, ol {
  padding-left: 1.4em;
}
li {
  margin-bottom: var(--s-2);
}
li::marker { color: var(--text-faint); }
ul li::marker { content: "— "; }
ol { list-style-type: decimal; }
ol li::marker { font-family: var(--font-mono); font-size: 0.85em; }
ul ul, ol ol, ul ol, ol ul { margin-top: var(--s-2); margin-bottom: 0; }

dl.def {
  display: grid;
  grid-template-columns: minmax(8em, max-content) 1fr;
  gap: var(--s-2) var(--s-6);
  margin-bottom: var(--s-6);
}
dl.def dt {
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text);
  padding-top: 0.15em;
}
dl.def dd { margin: 0; color: var(--text-muted); }

/* Inline code */
:not(pre) > code {
  font-family: var(--font-mono);
  font-size: 0.875em;
  font-feature-settings: "ss01", "calt" off;
  font-variant-ligatures: none;
  background: var(--bg-code);
  color: var(--text);
  padding: 0.12em 0.35em;
  border-radius: 3px;
  border: 1px solid var(--rule);
  white-space: nowrap;
}

/* Code blocks */
.codeblock {
  position: relative;
  margin: var(--s-8) 0;
  background: var(--bg-code);
  border: 1px solid var(--rule);
  border-radius: 4px;
  overflow: hidden;
}
.codeblock__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-3);
  padding: var(--s-2) var(--s-4);
  border-bottom: 1px solid var(--rule);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-subtle);
  letter-spacing: 0.02em;
}
.codeblock__path {
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.codeblock__meta {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  flex-shrink: 0;
}
.codeblock__lang {
  font-family: var(--font-ui);
  font-weight: 600;
  font-size: 0.6875rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}
.codeblock__copy {
  display: inline-flex;
  align-items: center;
  gap: var(--s-2);
  background: transparent;
  border: 1px solid var(--rule);
  color: var(--text-muted);
  padding: var(--s-1) var(--s-3);
  font-family: var(--font-ui);
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-radius: 3px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 200ms cubic-bezier(.22,1,.36,1), color 150ms, border-color 150ms;
}
.codeblock__copy svg { width: 12px; height: 12px; }
.codeblock:hover .codeblock__copy,
.codeblock:focus-within .codeblock__copy { opacity: 1; }
@media (hover: none) {
  .codeblock__copy { opacity: 1; }
}
.codeblock__copy:hover { color: var(--text); border-color: var(--rule-strong); }
.codeblock__copy.is-copied { color: var(--accent); border-color: var(--accent); }
.codeblock pre {
  margin: 0;
  padding: var(--s-4) 0;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.65;
  color: var(--text);
  font-variant-ligatures: none;
}
.codeblock pre code {
  display: block;
  padding: 0 var(--s-4);
  font-family: inherit;
  font-size: inherit;
  background: none;
  border: 0;
  white-space: pre;
}

/* Syntax (3 colors) */
.tk-kw { color: var(--syn-keyword); font-weight: 500; }
.tk-str { color: var(--syn-string); }
.tk-com { color: var(--syn-comment); font-style: italic; }
.tk-num { color: var(--syn-keyword); }
.tk-fn { color: var(--text); font-weight: 500; }

/* Diff hints */
.tk-add { background: color-mix(in oklch, var(--accent-soft) 50%, transparent); display: inline-block; width: 100%; }
.tk-del { background: color-mix(in oklch, var(--bg-mark) 25%, transparent); display: inline-block; width: 100%; opacity: 0.85; }

/* Blockquote */
blockquote {
  margin: var(--s-8) 0;
  padding-left: var(--s-6);
  border-left: 1px solid var(--rule-strong);
  font-style: italic;
  color: var(--text-muted);
  font-size: 1.125rem;
}
blockquote cite {
  display: block;
  margin-top: var(--s-2);
  font-style: normal;
  font-family: var(--font-ui);
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-subtle);
}

/* Pull quote */
.pullquote {
  font-family: var(--font-body);
  font-style: italic;
  font-weight: 350;
  font-size: clamp(1.5rem, 1.3rem + 0.7vw, 1.875rem);
  line-height: 1.3;
  text-wrap: balance;
  letter-spacing: -0.01em;
  color: var(--text);
  text-align: left;
  margin: var(--s-12) 0;
  padding: 0;
  border: 0;
  max-width: 22em;
}

/* Callouts — typographic only (NOTE / INSIGHT / CAUTION / ASIDE) */
.callout {
  margin: var(--s-8) 0;
  padding-left: var(--s-6);
  border: 0;
  border-left: 1px solid var(--rule-strong);
  font-style: normal;
  color: var(--text);
}
.callout__label {
  display: block;
  font-family: var(--font-ui);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: var(--s-2);
}
.callout[data-callout="caution"] .callout__label { color: oklch(0.50 0.13 25); }
[data-theme="dark"] .callout[data-callout="caution"] .callout__label { color: oklch(0.78 0.12 25); }
.callout[data-callout="aside"] .callout__label { color: var(--text-subtle); }
.callout p:last-child { margin-bottom: 0; }
.callout em { color: var(--text-muted); }

/* Callouts — boxed variants (INFO / WARNING / TIP / DANGER)
   Subtle low-chroma tinted bg + thin colored border + icon. Not alert boxes. */
.callout-box {
  --cb-bg:     oklch(0.96 0.025 240);
  --cb-border: oklch(0.78 0.06  240);
  --cb-fg:     oklch(0.45 0.13  240);
  margin: var(--s-8) 0;
  padding: var(--s-4) var(--s-6);
  background: var(--cb-bg);
  border: 1px solid var(--cb-border);
  border-radius: 6px;
  display: grid;
  grid-template-columns: 22px 1fr;
  column-gap: var(--s-4);
  align-items: start;
  color: var(--text);
}
.callout-box__icon {
  width: 22px; height: 22px;
  color: var(--cb-fg);
  margin-top: 1px;
  flex-shrink: 0;
}
.callout-box__icon svg { width: 100%; height: 100%; }
.callout-box__body { min-width: 0; }
.callout-box__body > :first-child { margin-top: 0; }
.callout-box__body > :last-child  { margin-bottom: 0; }
.callout-box__body p { margin-bottom: var(--s-3); }
.callout-box__body p:last-child { margin-bottom: 0; }
.callout-box__body strong { color: var(--cb-fg); }
.callout-box__body code {
  background: color-mix(in oklch, var(--cb-fg) 8%, transparent);
  border-color: color-mix(in oklch, var(--cb-fg) 22%, transparent);
}
.callout-box__body a { color: var(--cb-fg); }

/* WARNING — amber */
.callout-box[data-callout="warning"] {
  --cb-bg:     oklch(0.96 0.045 75);
  --cb-border: oklch(0.78 0.10  75);
  --cb-fg:     oklch(0.50 0.13  75);
}
/* TIP — green */
.callout-box[data-callout="tip"] {
  --cb-bg:     oklch(0.96 0.030 145);
  --cb-border: oklch(0.75 0.08  145);
  --cb-fg:     oklch(0.45 0.12  145);
}
/* DANGER — rose */
.callout-box[data-callout="danger"] {
  --cb-bg:     oklch(0.96 0.040 25);
  --cb-border: oklch(0.78 0.10  25);
  --cb-fg:     oklch(0.48 0.15  25);
}

/* Dark — deeper, lower-saturation panels with brighter ink for readability */
[data-theme="dark"] .callout-box {
  --cb-bg:     oklch(0.20 0.04 240);
  --cb-border: oklch(0.40 0.08 240);
  --cb-fg:     oklch(0.80 0.10 240);
}
[data-theme="dark"] .callout-box[data-callout="warning"] {
  --cb-bg:     oklch(0.22 0.04 75);
  --cb-border: oklch(0.42 0.10 75);
  --cb-fg:     oklch(0.84 0.13 75);
}
[data-theme="dark"] .callout-box[data-callout="tip"] {
  --cb-bg:     oklch(0.20 0.04 145);
  --cb-border: oklch(0.40 0.08 145);
  --cb-fg:     oklch(0.80 0.12 145);
}
[data-theme="dark"] .callout-box[data-callout="danger"] {
  --cb-bg:     oklch(0.22 0.06 25);
  --cb-border: oklch(0.45 0.10 25);
  --cb-fg:     oklch(0.80 0.14 25);
}

/* Tables. Premise: tables are document figures, not prose. They claim more
   width than the 68ch body column whenever the layout grid offers room, and
   prose inside them wraps on word boundaries — only inline code and links
   are allowed to break anywhere. */
.table-wrap {
  margin: var(--s-8) 0;
  position: relative;
}
@media (max-width: 767px) {
  .table-wrap { overflow-x: auto; }
}
/* By default at ≥1280px tables breakout into the empty right rail.
   Opt out per-table with <table class="narrow">.
   Assumes no sidenote rendered at the same vertical span. */
@media (min-width: 1280px) {
  .table-wrap:not(:has(> table.narrow)):not(.narrow) {
    margin-right: calc((240px + var(--s-12)) * -1);
  }
  /* The right rail is shared territory: when a row inside this table is the
     target of a review comment, the pin lives in that rail. Stay inside the
     article so the OPEN/RESOLVED pins don't sit on top of cell content. */
  .table-wrap[data-report-has-comment="true"]:not(:has(> table.narrow)):not(.narrow) {
    margin-right: 0;
  }
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
  line-height: 1.5;
  table-layout: auto;
}
th, td {
  text-align: left;
  padding: var(--s-3) var(--s-4) var(--s-3) 0;
  border-bottom: 1px solid var(--rule);
  vertical-align: top;
}
/* Long unbreakable tokens (inline code, URLs) are allowed to split.
   Plain prose stays on word boundaries. */
th code, td code, th a, td a { overflow-wrap: anywhere; }
th {
  font-family: var(--font-ui);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--text-subtle);
  border-bottom: 1px solid var(--rule-strong);
  padding-bottom: var(--s-2);
  min-width: 7ch;
}
td.num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; text-align: right; padding-right: var(--s-6); }

/* Figures */
figure { margin: var(--s-8) 0; }
figure img, figure svg {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 2px;
}
figcaption {
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  color: var(--text-subtle);
  margin-top: var(--s-3);
  font-style: normal;
  line-height: 1.5;
  max-width: 60ch;
  text-align: center;
  margin-left: auto;
  margin-right: auto;
}

/* Framed figure — subtle panel + click-to-zoom */
figure.framed {
  background: var(--bg-elevated);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: var(--s-6) var(--s-6) var(--s-4);
  margin: var(--s-8) 0;
}
figure.framed > figcaption {
  margin-top: var(--s-4);
  padding-top: var(--s-3);
  border-top: 1px solid var(--rule);
}
figure.framed .zoomable {
  cursor: zoom-in;
  transition: opacity 200ms cubic-bezier(.22,1,.36,1);
}
figure.framed .zoomable:hover { opacity: 0.92; }
figure.framed .zoomable:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 4px;
  border-radius: 4px;
}

/* Lightbox */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: color-mix(in oklch, var(--bg) 6%, oklch(0 0 0));
  display: none;
  align-items: center;
  justify-content: center;
  padding: var(--s-8);
  cursor: zoom-out;
  opacity: 0;
  transition: opacity 220ms cubic-bezier(.22,1,.36,1);
}
.lightbox[data-open="true"] {
  display: flex;
  opacity: 1;
}
.lightbox__inner {
  max-width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--s-4);
}
.lightbox__stage {
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: min(1200px, 100%);
  max-height: calc(100vh - 8rem);
  width: 100%;
  background: var(--bg-elevated);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: var(--s-8);
  box-shadow: 0 24px 64px -16px color-mix(in oklch, oklch(0 0 0) 40%, transparent);
}
.lightbox__stage img,
.lightbox__stage svg {
  max-width: 100%;
  max-height: calc(100vh - 12rem);
  width: 100%;
  height: auto;
  object-fit: contain;
  display: block;
}
.lightbox__caption {
  font-family: var(--font-ui);
  font-size: 0.875rem;
  color: oklch(0.85 0.005 260);
  text-align: center;
  max-width: 60ch;
}
.lightbox__close {
  position: absolute;
  top: var(--s-6);
  right: var(--s-6);
  background: transparent;
  border: 1px solid color-mix(in oklch, oklch(1 0 0) 40%, transparent);
  color: oklch(0.92 0.005 260);
  width: 36px; height: 36px;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-ui);
  transition: border-color 150ms, color 150ms, background 150ms;
}
.lightbox__close:hover { background: color-mix(in oklch, oklch(1 0 0) 14%, transparent); border-color: color-mix(in oklch, oklch(1 0 0) 70%, transparent); }
.lightbox__close svg { width: 16px; height: 16px; }

/* Drop cap on the first paragraph of an article */
.dropcap::first-letter {
  font-family: var(--font-body);
  font-size: 3.4em;
  font-weight: 500;
  line-height: 0.85;
  float: left;
  padding: 0.05em 0.08em 0 0;
  color: var(--text);
}

/* Sidenote fade-in motion (phase 2) — degrades to opacity 1 without JS */
.sidenote { transition: opacity 240ms cubic-bezier(.22, 1, .36, 1); }
.js-on .sidenote { opacity: 0; }
.js-on .sidenote.is-revealed { opacity: 1; }

@media (prefers-reduced-motion: reduce) {
  .js-on .sidenote { opacity: 1; }
}

/* Sidenotes — desktop wide */
.sidenote {
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  line-height: 1.55;
  color: var(--text-muted);
  font-style: italic;
}
.sidenote .sidenote__num {
  font-family: var(--font-mono);
  font-style: normal;
  font-weight: 600;
  font-size: 0.6875rem;
  color: var(--accent);
  margin-right: var(--s-2);
  letter-spacing: 0.05em;
}
@media (min-width: 1280px) {
  .sidenote {
    position: absolute;
    left: calc(100% + var(--s-8));
    width: 240px;
    max-width: calc(100vw - 68ch - 220px - 12rem);
    margin: 0;
    padding: 0;
  }
}
@media (max-width: 1279px) {
  .sidenote {
    display: block;
    margin: var(--s-4) 0 var(--s-6) var(--s-4);
    padding-left: var(--s-4);
    border-left: 1px solid var(--rule);
  }
}

/* Footnote refs / hover popovers */
.fnref {
  font-family: var(--font-mono);
  font-size: 0.7em;
  font-weight: 600;
  color: var(--accent);
  text-decoration: none;
  vertical-align: super;
  line-height: 0;
  padding: 0 0.15em;
  letter-spacing: 0.02em;
  position: relative;
}
.fnref:hover { color: var(--text); }
.fnref-popover {
  position: absolute;
  z-index: 40;
  max-width: 360px;
  padding: var(--s-3) var(--s-4);
  background: var(--bg);
  border: 1px solid var(--rule-strong);
  border-radius: 4px;
  box-shadow: 0 8px 24px -8px color-mix(in oklch, var(--text) 12%, transparent);
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  font-weight: 400;
  line-height: 1.55;
  color: var(--text-muted);
  letter-spacing: 0;
  vertical-align: baseline;
  pointer-events: none;
}
.fnref-popover[data-visible="true"] { pointer-events: auto; }

/* Footnotes block */
.footnotes ol { padding-left: 1.6em; }
.footnotes li {
  font-size: 0.9375rem;
  line-height: 1.55;
  color: var(--text-muted);
  margin-bottom: var(--s-3);
}
.footnotes li:target { color: var(--text); }
.fn-back {
  font-family: var(--font-mono);
  font-size: 0.85em;
  margin-left: 0.4em;
  text-decoration: none;
  color: var(--text-faint);
}
.fn-back:hover { color: var(--accent); }

/* Sources block */
.sources ol { padding-left: 1.6em; }
.sources li {
  font-size: 0.9375rem;
  line-height: 1.55;
  color: var(--text-muted);
  margin-bottom: var(--s-3);
}
.sources li::marker { font-family: var(--font-mono); font-size: 0.85em; }

/* Glossary */
.glossary-list dt {
  font-family: var(--font-ui);
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--text);
}
dfn { font-style: italic; border-bottom: 1px dotted var(--text-faint); cursor: help; }

/* End-of-doc CTA */
.end-actions {
  margin: var(--s-16) 0 var(--s-12);
  padding-top: var(--s-8);
  border-top: 1px solid var(--rule);
  text-align: left;
}
.end-actions a {
  font-family: var(--font-ui);
  font-size: 0.9375rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--accent);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: var(--s-2);
}
.end-actions a:hover { text-decoration: underline; }
.end-actions a svg { width: 14px; height: 14px; }

/* Toast */
.toast {
  position: fixed;
  bottom: var(--s-6);
  right: var(--s-6);
  z-index: 60;
  padding: var(--s-3) var(--s-4);
  background: var(--text);
  color: var(--bg);
  border-radius: 4px;
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  box-shadow: 0 12px 32px -12px color-mix(in oklch, var(--text) 30%, transparent);
  opacity: 0;
  transform: translateY(8px);
  pointer-events: none;
  transition: opacity 220ms cubic-bezier(.22,1,.36,1), transform 220ms cubic-bezier(.22,1,.36,1);
}
.toast[data-visible="true"] {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}
.toast code {
  font-family: var(--font-mono);
  font-size: 0.875em;
  background: color-mix(in oklch, var(--bg) 18%, transparent);
  padding: 0 0.35em;
  border-radius: 2px;
  color: var(--bg);
  border: 0;
  white-space: nowrap;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
  html { scroll-behavior: auto; }
}

@media (prefers-reduced-motion: no-preference) {
  html { scroll-behavior: smooth; }
}

/* ---------- Print ---------- */
@media print {
  :root {
    --bg: #ffffff;
    --text: #1a1a1a;
    --text-muted: #444;
    --text-subtle: #666;
    --rule: #ddd;
    --accent: #6b3a23;
  }
  .topbar, .progress, .page-fade-top, .section-indicator, .skip-link, .toc-rail, .sidenote-rail,
  .codeblock__copy, .end-actions, .toast, .lightbox { display: none !important; }
  .layout { display: block !important; padding: 0 !important; }
  .article { max-width: 100% !important; }
  body { font-size: 11pt; line-height: 1.5; }
  h1 { font-size: 24pt; }
  h2 { font-size: 16pt; page-break-after: avoid; }
  h3 { font-size: 13pt; page-break-after: avoid; }
  pre, table, figure { page-break-inside: avoid; }
  a { color: var(--text); text-decoration: underline; }
  a[href^="http"]::after {
    content: " (" attr(href) ")";
    font-size: 0.85em;
    color: #666;
    word-break: break-all;
  }
  .sidenote { display: block; margin: 0.5em 0; padding-left: 1em; border-left: 1px solid #ccc; }
  .fnref-popover { display: none !important; }
}

/* ---------- Report switcher (Cmd-O overlay) ---------- */
.sr-only {
  position: absolute !important; width: 1px; height: 1px;
  padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0);
  white-space: nowrap; border: 0;
}
.report-switcher {
  position: fixed; inset: 0; z-index: 60;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 14vh;
  background: oklch(0.10 0.008 260 / 0.18);
  backdrop-filter: blur(1.5px);
  animation: rsw-fade 120ms cubic-bezier(.22,1,.36,1);
}
.report-switcher[hidden] { display: none; }
.report-switcher__panel {
  width: min(92vw, 540px);
  background: var(--bg);
  border: 1px solid var(--rule-strong);
  border-radius: 8px;
  box-shadow: 0 24px 60px -20px oklch(0.10 0.008 260 / 0.40);
  overflow: hidden;
}
.report-switcher__input-row {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.7rem 0.9rem;
  border-bottom: 1px solid var(--rule);
}
.report-switcher__kbd {
  font-family: var(--font-mono); font-size: 0.7rem;
  color: var(--text-subtle);
  border: 1px solid var(--rule-strong);
  padding: 1px 5px; border-radius: 3px;
}
.report-switcher__input {
  flex: 1;
  border: 0; outline: 0; background: transparent;
  font-family: var(--font-ui); font-size: 0.95rem;
  color: var(--text);
}
.report-switcher__close {
  border: 0; background: transparent; cursor: pointer;
  color: var(--text-subtle); font-size: 1.1rem; padding: 0 0.2rem;
}
.report-switcher__close:hover { color: var(--text); }
.report-switcher__list { margin: 0; padding: 0.3rem 0; list-style: none; max-height: 50vh; overflow-y: auto; }
.report-switcher__item {
  display: grid;
  grid-template-columns: 5rem 1fr auto;
  gap: 0.7rem;
  padding: 0.5rem 0.9rem;
  font-family: var(--font-body);
  align-items: baseline;
  cursor: pointer;
}
.report-switcher__item.is-active { background: var(--accent-soft); }
.report-switcher__item-date { font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-subtle); }
.report-switcher__item-title { font-size: 0.92rem; color: var(--text); }
.report-switcher__item-key { font-family: var(--font-mono); font-size: 0.65rem; color: var(--text-subtle); }
.report-switcher__empty {
  padding: 1rem; text-align: center; font-style: italic; color: var(--text-subtle);
}
.report-switcher__hint {
  display: flex; justify-content: space-between;
  padding: 0.5rem 0.9rem;
  border-top: 1px solid var(--rule);
  font-family: var(--font-ui); font-size: 0.68rem;
  color: var(--text-subtle); letter-spacing: 0.04em;
}
.report-switcher__count { font-family: var(--font-mono); }
@media (prefers-reduced-motion: reduce) {
  .report-switcher { animation: none; }
}
@keyframes rsw-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@media (max-width: 640px) {
  .report-switcher { padding-top: 0; }
  .report-switcher__panel {
    width: 100vw;
    min-height: 100dvh;
    border-radius: 0;
    border: 0;
  }
  .report-switcher__item-key { display: none; }
}
</style>
</head>
