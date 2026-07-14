/* ═══════════════════════════════════════════════════════════════
   QUERY BUILDER
═══════════════════════════════════════════════════════════════ */
let conditionCounter = 0;

function quoteIfNeeded(term) {
  term = term.trim();
  return term.includes(' ') ? '"' + term + '"' : term;
}

function buildQuery() {
  const mainVal = document.getElementById('qbMain').value.trim();
  if (!mainVal) return '';
  const mainParts = mainVal.split(',').map(p => p.trim()).filter(Boolean);
  let query = mainParts.length === 1
    ? mainParts[0]
    : '(' + mainParts.map(quoteIfNeeded).join(' OR ') + ')';

  document.querySelectorAll('.qb-cond-row').forEach(row => {
    const type  = row.dataset.type;
    const val   = row.querySelector('.qb-input').value.trim();
    if (!val) return;
    const terms = val.split(',').map(t => t.trim()).filter(Boolean);
    if (!terms.length) return;
    const group = terms.length === 1
      ? quoteIfNeeded(terms[0])
      : '(' + terms.map(quoteIfNeeded).join(' OR ') + ')';
    query += ' ' + type + ' ' + group;
  });
  return query;
}

function updatePreview() {
  const q  = buildQuery();
  const el = document.getElementById('qbPreview');
  el.innerHTML = q
    ? '<strong>Query:</strong> ' + escapeHtml(q)
    : 'Query will appear here…';
}

function addCondition(type) {
  conditionCounter++;
  const id  = 'cond_' + conditionCounter;
  const ph  = type === 'AND'
    ? 'e.g. GIS, remote sensing, DSAS'
    : 'e.g. bankline migration';
  const div = document.createElement('div');
  div.className    = 'qb-row qb-cond-row';
  div.dataset.type = type;
  div.id = id;
  div.innerHTML =
    '<span class="qb-badge ' + type.toLowerCase() + '" onclick="toggleType(this)" title="Click to toggle">' + type + '</span>' +
    '<input class="qb-input" type="text" placeholder="' + ph + '" oninput="updatePreview()">' +
    '<button class="qb-del" onclick="removeCondition(\'' + id + '\')">&#x2715;</button>';
  document.getElementById('qbConditions').appendChild(div);
  updatePreview();
}

function toggleType(badge) {
  const row  = badge.closest('.qb-cond-row');
  const next = row.dataset.type === 'AND' ? 'OR' : 'AND';
  row.dataset.type   = next;
  badge.textContent  = next;
  badge.className    = 'qb-badge ' + next.toLowerCase();
  updatePreview();
}

function removeCondition(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
  updatePreview();
}

/* ═══════════════════════════════════════════════════════════════
   QUARTILE CHIPS
═══════════════════════════════════════════════════════════════ */
function toggleChip(btn) {
  btn.classList.toggle('active');
}

function getSelectedQuartiles() {
  return [...document.querySelectorAll('#quartileChips .chip.active')]
    .map(c => c.dataset.value);
}

/* ═══════════════════════════════════════════════════════════════
   JOURNAL / PUBLISHER DYNAMIC FIELDS
═══════════════════════════════════════════════════════════════ */
let fieldCounters = { journal: 0, publisher: 0 };

function addFilterField(type) {
  fieldCounters[type]++;
  const id = type + '_' + fieldCounters[type];
  const ph = type === 'journal'
    ? 'e.g. Natural Hazards'
    : 'e.g. Elsevier BV';
  const container = document.getElementById(type + 'Fields');
  const div = document.createElement('div');
  div.className = 'filter-input-row';
  div.id = id;
  div.innerHTML =
    '<input type="text" placeholder="' + ph + '">' +
    '<button class="qb-del" onclick="removeFilterField(\'' + id + '\')">&#x2715;</button>';
  container.appendChild(div);
}

function removeFilterField(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function getFilterValues(type) {
  return [...document.querySelectorAll('#' + type + 'Fields input')]
    .map(i => i.value.trim()).filter(Boolean);
}

/* ═══════════════════════════════════════════════════════════════
   SCRAPER CONTROL
═══════════════════════════════════════════════════════════════ */
let paperCount   = 0;
let activeSource = null;
let isRunning    = false;

function setIPStatus(state, text) {
  document.getElementById('liveDot').className = 'live-dot ' + state;
  document.getElementById('liveText').textContent = text;
}
function setBottomStatus(active, text) {
  const dot = document.getElementById('statusDot');
  if (active) dot.classList.add('active'); else dot.classList.remove('active');
  document.getElementById('statusText').textContent = text;
}

async function handleMainButton() {
  isRunning ? await stopScrape() : await startScrape();
}

async function stopScrape() {
  const btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.innerText = 'STOPPING...';
  try { await fetch('/stop', { method: 'POST' }); } catch(e) {}
}

async function startScrape() {
  const query = buildQuery();
  if (!query) {
    alert('Please enter at least one keyword in the MUST field.');
    return;
  }

  const btn    = document.getElementById('startBtn');
  const termSt = document.getElementById('termStatus');
  isRunning    = true;
  paperCount   = 0;
  document.getElementById('paperCount').textContent = '';

  btn.innerText = '■ STOP';
  btn.className = 'btn btn-stop';
  termSt.textContent = 'ACTIVE';
  setBottomStatus(true, 'Scraping in progress...');
  setIPStatus('ok', 'IP: STABLE — Connected via Tor');

  document.getElementById('terminal').innerHTML = '';
  appendLine('$ Query: ' + query, false, 't-muted');
  appendLine('$ Initializing Tor proxy...', false, 't-muted');

  // ── Collect all filter values ──────────────────────────────────────────────
  const payload = {
    query:        query,
    max_results:  document.getElementById('max_results').value,
    year_low:     document.getElementById('year_low').value   || null,
    year_high:    document.getElementById('year_high').value  || null,
    open_access:  document.getElementById('open_access').checked,
    quartiles:    getSelectedQuartiles(),
    min_h_index:  document.getElementById('min_h_index').value  || null,
    min_sjr:      document.getElementById('min_sjr').value      || null,
    min_citations:document.getElementById('min_citations').value || null,
    journals:     getFilterValues('journal'),
    publishers:   getFilterValues('publisher')
  };

  try {
    await fetch('/start-scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch(e) {
    appendLine('ERROR: Could not reach backend.', false, 't-error');
    resetUI('idle');
    return;
  }

  if (activeSource) { activeSource.close(); activeSource = null; }
  const source = new EventSource('/stream');
  activeSource = source;

  source.onmessage = function(event) {
    const raw = event.data;

    if (raw === 'DONE') {
      source.close(); activeSource = null;
      appendLine('');
      appendLine('EXTRACTION COMPLETE — ' + paperCount + ' papers saved.', false, 't-done');
      setIPStatus('idle', 'IP: IDLE — Task complete');
      resetUI('done');
      return;
    }
    if (raw === 'STOPPED') {
      source.close(); activeSource = null;
      appendLine('');
      appendLine('[STOPPED] Cancelled — ' + paperCount + ' papers saved.', false, 't-error');
      setIPStatus('idle', 'IP: IDLE — Task stopped');
      resetUI('idle');
      return;
    }

    // IP noise → top bar only
    if (raw.includes('Blocked') || raw.includes("codec can't encode") || raw.includes('charmap') || raw.includes('character maps to')) {
      setIPStatus('blocked', 'IP: BLOCKED — Rotating circuit...');
      return;
    }
    if (raw.includes('Requesting new Tor IP')) {
      setIPStatus('rotating', 'IP: ROTATING — Requesting new circuit...');
      return;
    }
    if ((raw.includes('Switched') && raw.includes('circuit')) || raw.includes('New IP assigned')) {
      setIPStatus('ok', 'IP: ROTATED — New circuit active');
      return;
    }

    // Normal output
    const isIndented = raw.startsWith('    ') || raw.startsWith('\t') || raw.startsWith('[SKIP');
    let cssClass = '';
    if (raw.includes('Title:')) {
      paperCount++;
      document.getElementById('paperCount').textContent = paperCount + ' papers';
      cssClass = 't-title';
    } else if (raw.includes('[SKIP')) {
      cssClass = 't-error';
    } else if (raw.includes('[STOPPED]')) {
      cssClass = 't-error';
    } else if (raw.includes('Configuring') || raw.includes('Proxy') || raw.includes('Searching') || raw.startsWith('$')) {
      cssClass = 't-muted';
    }
    appendLine(escapeHtml(raw), isIndented, cssClass);
  };

  source.onerror = function() {
    source.close(); activeSource = null;
    appendLine('Stream disconnected.', false, 't-error');
    resetUI('idle');
  };
}

function appendLine(text, isIndented, cssClass) {
  const term = document.getElementById('terminal');
  const div  = document.createElement('div');
  div.className = 'term-line' + (isIndented ? '' : ' no-indent');
  if (cssClass && text) {
    const span = document.createElement('span');
    span.className = cssClass;
    span.textContent = text;
    div.appendChild(span);
  } else {
    div.textContent = text;
  }
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function resetUI(state) {
  isRunning = false;
  const btn    = document.getElementById('startBtn');
  const termSt = document.getElementById('termStatus');
  btn.disabled = false;
  btn.innerText = '▶ RUN';
  btn.className = 'btn btn-primary';
  termSt.textContent = 'IDLE';
  setBottomStatus(false, state === 'done'
    ? 'Done — ' + paperCount + ' qualifying papers saved'
    : 'Idle — ready for next run');
}

document.addEventListener('DOMContentLoaded', function() {
  appendLine('$ Waiting for execution command...', false, 't-muted');
  setIPStatus('idle', 'IP: IDLE — Not connected');
  updatePreview();
  // Start with one default journal and publisher slot hidden (add on demand)
});
