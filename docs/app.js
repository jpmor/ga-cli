'use strict';

const $nav   = document.getElementById('breadcrumbs');
const $main  = document.getElementById('content');
const $pages = document.getElementById('pagination');

// ── Utilities ─────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function load(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} fetching ${url}`);
  return r.text();
}

function firstHeading(md, fallback) {
  const m = md.match(/^# (.+)/m);
  return m ? m[1] : fallback;
}

// ── Breadcrumbs ───────────────────────────────────────────────────────────────

function setBreadcrumbs(items) {
  // items: [{label, href?}] — last item is current page (no href)
  $nav.innerHTML = items.map((item, i) => {
    const sep = i === 0 ? '' : '<span class="sep">›</span>';
    return i < items.length - 1
      ? `${sep}<a href="${item.href}">${esc(item.label)}</a>`
      : `${sep}<span>${esc(item.label)}</span>`;
  }).join('');
}

// ── Index parsers ─────────────────────────────────────────────────────────────

// "- 01  GENERAL PROVISIONS, OCGA"  →  { num: "1", name: "GENERAL PROVISIONS, OCGA" }
function parseTitles(md) {
  return md.split('\n')
    .map(l => l.match(/^- (\d+)\s{2,}(.+)/))
    .filter(Boolean)
    .map(m => ({ num: String(parseInt(m[1], 10)), name: m[2] }));
}

// "- Chapter 4 - HOLIDAYS AND OBSERVANCES (§§ 1-4-1 — 1-4-26)"
function parseChapters(md) {
  return md.split('\n')
    .map(l => l.match(/^- Chapter (\S+) - (.+)/))
    .filter(Boolean)
    .map(m => ({ num: m[1], name: m[2] }));
}

// "- Section 1-4-1 - Public and legal holidays..."
function parseSections(md) {
  return md.split('\n')
    .map(l => l.match(/^- Section (\S+) - (.+)/))
    .filter(Boolean)
    .map(m => ({ id: m[1], name: m[2] }));
}

// ── Index list renderer ───────────────────────────────────────────────────────

function renderIndexList(heading, items) {
  // items: [{href, label, name}]
  // name may contain HTML entities from the source (e.g. &quot;) — use directly as innerHTML
  const lis = items.map(x =>
    `<li><a href="${x.href}"><span class="item-label">${esc(x.label)}</span>${x.name}</a></li>`
  ).join('');
  return `<h1>${esc(heading)}</h1><ul class="index-list">${lis}</ul>`;
}

// ── Citation linker ───────────────────────────────────────────────────────────

function linkifyStatuteCitations(html) {
  // OCGA section ID: 1-2 digit title, alnum chapter, digit-starting section,
  // optional decimal suffix, optional letter suffix, optional deeper hyphenated parts
  const ID = String.raw`\d{1,2}-[0-9A-Za-z]+-\d+(?:\.\d+)?[A-Za-z]*(?:-[0-9A-Za-z]+)*`;
  // Connectors that may appear between multiple IDs in one citation
  const SEP = String.raw`(?:\s*(?:through|and|or|,)\s*)`;
  const CITE = new RegExp(
    `((?:O\\.C\\.G\\.A\\.\\s*)?§§?\\s*|Code\\s+[Ss]ections?\\s+)((?:${ID})(?:${SEP}(?:${ID}))*)`,
    'g'
  );
  const ID_RE = new RegExp(ID, 'g');

  return html.replace(CITE, (_, prefix, ids) =>
    prefix + ids.replace(ID_RE, id => {
      const lower = id.toLowerCase();
      const parts = lower.split('-');
      if (parts.length < 3) return id;
      return `<a href="#/${parts[0]}/${parts[1]}/${lower}">${id}</a>`;
    })
  );
}

// ── Section text renderer ─────────────────────────────────────────────────────

function renderSectionText(md) {
  const parts = [];
  let inHistory = false;

  for (const raw of md.split('\n')) {
    const line = raw.trimEnd();
    if (!line) continue;

    if (line.startsWith('# ')) {
      parts.push(`<h1>${esc(line.slice(2))}</h1>`);
      inHistory = false;

    } else if (line.startsWith('## ')) {
      const title = line.slice(3).trim();
      parts.push(`<h2>${esc(title)}</h2>`);
      inHistory = title === 'History';

    } else if (line.startsWith('- ')) {
      parts.push(`<li>${linkifyStatuteCitations(line.slice(2))}</li>`);

    } else if (inHistory) {
      parts.push(`<p class="history-entry">${esc(line)}</p>`);

    } else {
      // Highlight subsection labels like (a), (b), (1), (2), (4.1) at the start of a line
      const escaped = esc(line);
      const styled = escaped.replace(
        /^(\s*)(\([a-z0-9.]+\))(\s)/,
        (_, ws, lbl, sp) => `${ws}<span class="label">${lbl}</span>${sp}`
      );
      parts.push(`<p${line.match(/^\s+/) ? ' class="sub"' : ''}>${linkifyStatuteCitations(styled)}</p>`);
    }
  }

  // Wrap consecutive <li> items in <ul>
  let html = '';
  let inUl = false;
  for (const part of parts) {
    if (part.startsWith('<li>')) {
      if (!inUl) { html += '<ul>'; inUl = true; }
    } else if (inUl) {
      html += '</ul>';
      inUl = false;
    }
    html += part;
  }
  if (inUl) html += '</ul>';
  return html;
}

// ── Pages ─────────────────────────────────────────────────────────────────────

async function showRoot() {
  document.title = 'Georgia Code';
  setBreadcrumbs([{ label: 'OCGA' }]);
  $pages.innerHTML = '';

  const md = await load('ocga/index.md');
  const heading = firstHeading(md, 'Official Code of Georgia Annotated');
  const items = parseTitles(md).map(t => ({
    href: `#/${t.num}/`,
    label: `Title ${t.num}`,
    name: t.name,
  }));
  $main.innerHTML = renderIndexList(heading, items);
}

async function showTitle(t) {
  const md = await load(`ocga/${t}/index.md`);
  const heading = firstHeading(md, `Title ${t}`);
  document.title = `${heading} — Georgia Code`;

  setBreadcrumbs([
    { label: 'OCGA', href: '#/' },
    { label: heading },
  ]);
  $pages.innerHTML = '';

  const items = parseChapters(md).map(c => ({
    href: `#/${t}/${c.num}/`,
    label: `Chapter ${c.num}`,
    name: c.name,
  }));
  $main.innerHTML = renderIndexList(heading, items);
}

async function showChapter(t, c) {
  const [titleMd, chapMd] = await Promise.all([
    load(`ocga/${t}/index.md`),
    load(`ocga/${t}/${c}/index.md`),
  ]);

  const titleHeading = firstHeading(titleMd, `Title ${t}`);
  const chapHeading  = firstHeading(chapMd,  `Chapter ${c}`);
  document.title = `${chapHeading} — Georgia Code`;

  setBreadcrumbs([
    { label: 'OCGA', href: '#/' },
    { label: titleHeading, href: `#/${t}/` },
    { label: chapHeading },
  ]);
  $pages.innerHTML = '';

  const items = parseSections(chapMd).map(s => ({
    href: `#/${t}/${c}/${s.id}`,
    label: `§ ${s.id}`,
    name: s.name,
  }));
  $main.innerHTML = renderIndexList(chapHeading, items);
}

async function showSection(t, c, s) {
  const [titleMd, chapMd, secMd] = await Promise.all([
    load(`ocga/${t}/index.md`),
    load(`ocga/${t}/${c}/index.md`),
    load(`ocga/${t}/${c}/${s}.md`),
  ]);

  const titleHeading = firstHeading(titleMd, `Title ${t}`);
  const chapHeading  = firstHeading(chapMd,  `Chapter ${c}`);
  const secHeading   = firstHeading(secMd,   `§ ${s}`);
  document.title = `${secHeading} — Georgia Code`;

  setBreadcrumbs([
    { label: 'OCGA', href: '#/' },
    { label: titleHeading, href: `#/${t}/` },
    { label: chapHeading,  href: `#/${t}/${c}/` },
    { label: `§ ${s}` },
  ]);

  // Prev / next within the chapter
  const sections = parseSections(chapMd);
  const idx  = sections.findIndex(x => x.id === s);
  const prev = idx > 0                  ? sections[idx - 1] : null;
  const next = idx < sections.length - 1 ? sections[idx + 1] : null;

  $pages.innerHTML = [
    prev ? `<a href="#/${t}/${c}/${prev.id}">← § ${esc(prev.id)}</a>` : '<span></span>',
    next ? `<a href="#/${t}/${c}/${next.id}">§ ${esc(next.id)} →</a>` : '<span></span>',
  ].join('');

  $main.innerHTML = renderSectionText(secMd);
}

// ── Router ────────────────────────────────────────────────────────────────────

async function route() {
  const hash  = location.hash.replace(/^#\/?/, '');
  const parts = hash ? hash.split('/').filter(Boolean) : [];

  $main.innerHTML  = '<p class="loading">Loading…</p>';
  $pages.innerHTML = '';

  try {
    if      (parts.length === 0) await showRoot();
    else if (parts.length === 1) await showTitle(parts[0]);
    else if (parts.length === 2) await showChapter(parts[0], parts[1]);
    else                         await showSection(parts[0], parts[1], parts[2]);
  } catch (e) {
    $main.innerHTML = `<p class="error">Could not load content: ${esc(e.message)}</p>`;
    console.error(e);
  }
}

window.addEventListener('hashchange', route);
document.addEventListener('DOMContentLoaded', route);
