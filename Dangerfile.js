// CI/Danger checks for PR hygiene and evidence
// - Enforces non-empty "What & Why"
// - Requires Rollback steps when migrations/DDL touched
// - Warns if Risk checklist left all unchecked
// - Nudges for UI screenshots when UI-like files change

/* eslint-disable @typescript-eslint/no-var-requires */
const { danger, fail, warn } = require('danger');

const pr = danger.github.pr;
const body = (pr.body || '').trim();

function stripComments(s) {
  return s.replace(/<!--[^]*?-->/g, '').trim();
}

function sectionText(titleRegex) {
  // Capture content under a heading until next H2 or end
  const re = new RegExp(
    String.raw`^\s*${titleRegex.source}\s*[\r\n]+([\s\S]*?)(?:\n\s*##\s+|$)`,
    'im'
  );
  const m = body.match(re);
  if (!m) return '';
  return stripComments(m[1]);
}

function hasRollbackDetails() {
  // Accept either a dedicated H2 or bold label as in the template
  const markers = [/(^|\n)##\s*Rollback\b/im, /(^|\n)\*\*Rollback\*\*/im];
  for (const mk of markers) {
    const idx = body.search(mk);
    if (idx !== -1) {
      const tail = stripComments(body.slice(idx));
      // Require at least some text after the marker
      return /Rollback[\s\S]{0,120}\n+([^\n]|\n(?!##))/.test(tail);
    }
  }
  return false;
}

function riskChecklistAllUnchecked() {
  const m = body.match(/\*\*Risk checklist\*\*([\s\S]*?)(?:\n##|\n\*\*Rollback\*\*|$)/i);
  if (!m) return false; // no checklist present
  const block = m[1];
  const all = block.match(/-\s*\[(?: |x|X)\]/g) || [];
  if (all.length === 0) return false;
  const unchecked = (block.match(/-\s*\[ \]/g) || []).length;
  return unchecked === all.length; // every item left unchecked
}

function bodyHasImageEvidence() {
  return /!\[[^\]]*\]\([^\)]+\)|<img\s[^>]*src=/i.test(body);
}

const changed = [
  ...danger.git.created_files,
  ...danger.git.modified_files,
];

const minChars = parseInt(process.env.DANGER_WHATWHY_MIN_CHARS || '60', 10);

// 1) Enforce non-empty What & Why
const whatWhy = sectionText(/##\s*What\s*&\s*Why/);
if (!whatWhy || whatWhy.replace(/\s+/g, '').length < minChars) {
  fail(`Please provide a meaningful "## What & Why" section (>= ${minChars} characters).`);
}

// 2) If migrations/DDL changed, require Rollback steps
const migrationTouched = changed.some((p) => /(migrat|db\/schema|ddl)/i.test(p));
if (migrationTouched && !hasRollbackDetails()) {
  fail('Migration/DDL changes detected but no "Rollback" steps found in PR body.');
}

// 3) Risk checklist left all unchecked
if (riskChecklistAllUnchecked()) {
  warn('All items in "Risk checklist" are still unchecked. Review and check applicable risks or remove irrelevant ones.');
}

// 4) UI-related changes should include screenshots/clips
const uiFileRe = /\.(tsx?|jsx?|vue|svelte|css|scss|less|png|jpe?g|gif|svg|webp)$/i;
const uiChanged = changed.some((p) => uiFileRe.test(p) || p.startsWith('docs/') || p.startsWith('site/'));
if (uiChanged && !bodyHasImageEvidence()) {
  warn('UI-related files changed but no screenshots or short clip found in PR body. Consider adding visual evidence.');
}
