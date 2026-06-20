/* apps/teacher/static/teacher/course_wizard.js
   Vanilla JS — no jQuery, no RequireJS.
   Depends on window.__WIZARD_DATA__ set inline by the template. */

'use strict';

import { escHtml, getCsrfToken } from './modules/utils.js';
import { spreadSchedule } from './modules/scheduler.js';
import { renderUnitPicker, sortedPlaylists } from './modules/unit_picker.js';

/* ── Data from server ───────────────────────────────────────────────── */

var DATA = window.__WIZARD_DATA__ || { unitsJson: [], factoryAvailable: false };

/* ── State ──────────────────────────────────────────────────────────── */

var state = {
  step: 1,
  // Step 1
  title: '',
  start: '',
  end: '',
  createGroup: false,
  groupName: '',
  // Step 2: map of unitNum -> { unit (raw obj), selectedPlaylistIds: Set }
  selectedUnits: {},
  // Step 3: map of unitNum -> { publish: string, due: string }
  schedule: {},
};

/* ── DOM refs ───────────────────────────────────────────────────────── */

var $ = function (id) { return document.getElementById(id); };

var els = {
  panels: [null, $('panel-1'), $('panel-2'), $('panel-3'), $('panel-4')],
  stepIndicators: [null,
    $('step-indicator-1'), $('step-indicator-2'),
    $('step-indicator-3'), $('step-indicator-4')],
  errorBanner: $('error-banner'),

  // Step 1
  fieldTitle: $('field-title'),
  fieldStart: $('field-start'),
  fieldEnd:   $('field-end'),
  fieldCreateGroup: $('field-create-group'),
  groupNameArea: $('group-name-area'),
  fieldGroupName: $('field-group-name'),
  errTitle: $('err-title'),
  errStart: $('err-start'),
  errEnd:   $('err-end'),
  errGroupName: $('err-group-name'),

  // Step 2
  unitPickerRoot: $('unit-picker-root'),
  unitSelectionHint: $('unit-selection-hint'),
  btn2Next: $('btn-2-next'),

  // Step 3
  scheduleTbody: $('schedule-tbody'),

  // Step 4
  reviewBasics: $('review-basics'),
  reviewUnits:  $('review-units'),
  createError:  $('create-error'),
  btnCreate:    $('btn-create'),
};

/* ══════════════════════════════════════════════════════════════════════
   STEP NAVIGATION
══════════════════════════════════════════════════════════════════════ */

function goTo(step) {
  var prev = state.step;
  state.step = step;

  // Hide all panels, show target
  for (var i = 1; i <= 4; i++) {
    els.panels[i].classList.toggle('is-active', i === step);
  }

  // Update stepper
  for (var j = 1; j <= 4; j++) {
    var ind = els.stepIndicators[j];
    ind.classList.remove('is-active', 'is-done');
    if (j < step) ind.classList.add('is-done');
    else if (j === step) ind.classList.add('is-active');
  }

  // Step-specific entry actions
  if (step === 2 && prev !== 2) {
    renderUnitPicker(els.unitPickerRoot, DATA.unitsJson, state.selectedUnits, refreshStep2Next);
    refreshStep2Next();
  }
  if (step === 3) renderScheduleTable();
  if (step === 4) renderReview();

  // Scroll to top of wizard
  els.panels[step].scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ══════════════════════════════════════════════════════════════════════
   STEP 1 — VALIDATION
══════════════════════════════════════════════════════════════════════ */

function showFieldError(errEl, inputEl, show) {
  errEl.classList.toggle('is-visible', show);
  inputEl.classList.toggle('t-input-error', show);
  if (show) inputEl.setAttribute('aria-invalid', 'true');
  else inputEl.removeAttribute('aria-invalid');
}

function validateStep1() {
  var title = els.fieldTitle.value.trim();
  var start = els.fieldStart.value;
  var end   = els.fieldEnd.value;
  var createGroup = els.fieldCreateGroup.checked;
  var groupName = els.fieldGroupName.value.trim();

  var ok = true;

  if (!title) {
    showFieldError(els.errTitle, els.fieldTitle, true);
    ok = false;
  } else {
    showFieldError(els.errTitle, els.fieldTitle, false);
  }

  if (!start) {
    showFieldError(els.errStart, els.fieldStart, true);
    ok = false;
  } else {
    showFieldError(els.errStart, els.fieldStart, false);
  }

  if (!end || (start && end && end <= start)) {
    showFieldError(els.errEnd, els.fieldEnd, true);
    ok = false;
  } else {
    showFieldError(els.errEnd, els.fieldEnd, false);
  }

  if (createGroup && !groupName) {
    showFieldError(els.errGroupName, els.fieldGroupName, true);
    ok = false;
  } else {
    showFieldError(els.errGroupName, els.fieldGroupName, false);
  }

  if (ok) {
    state.title = title;
    state.start = start;
    state.end   = end;
    state.createGroup = createGroup;
    state.groupName = createGroup ? groupName : '';
  }
  return ok;
}

/* ══════════════════════════════════════════════════════════════════════
   STEP 2 — HELPERS
══════════════════════════════════════════════════════════════════════ */

function refreshStep2Next() {
  var anySelected = Object.keys(state.selectedUnits).length > 0;
  els.btn2Next.disabled = !anySelected;
  els.unitSelectionHint.style.display = anySelected ? 'none' : 'inline';
}

/* ══════════════════════════════════════════════════════════════════════
   STEP 3 — SCHEDULE TABLE
══════════════════════════════════════════════════════════════════════ */

function selectedUnitList() {
  // Return in taxonomy order (ascending unit number)
  return Object.keys(state.selectedUnits)
    .map(Number)
    .sort(function (a, b) { return a - b; })
    .map(function (n) { return state.selectedUnits[n]; });
}

function renderScheduleTable() {
  var units = selectedUnitList();
  var windows = spreadSchedule(state.start, state.end, units.length);
  var tbody = els.scheduleTbody;
  tbody.innerHTML = '';

  // Merge pre-existing schedule edits where unit number matches
  units.forEach(function (entry, idx) {
    var n = entry.unit.n;
    var win = state.schedule[n] || windows[idx];

    var tr = document.createElement('tr');

    // Unit name cell
    var tdName = document.createElement('td');
    tdName.textContent = 'Unit ' + n + ': ' + entry.unit.title;
    tdName.style.fontFamily = 'var(--font-body)';
    tdName.style.fontSize = '0.875rem';
    tdName.style.fontWeight = '600';
    tr.appendChild(tdName);

    // Publish date
    var tdPublish = document.createElement('td');
    var pubInput = document.createElement('input');
    pubInput.type = 'date';
    pubInput.className = 't-input';
    pubInput.value = win.publish;
    pubInput.setAttribute('aria-label', 'Publish date for Unit ' + n);
    pubInput.dataset.unitN = String(n);
    pubInput.dataset.field = 'publish';
    pubInput.addEventListener('change', onScheduleChange);
    tdPublish.appendChild(pubInput);
    tr.appendChild(tdPublish);

    // Due date
    var tdDue = document.createElement('td');
    var dueInput = document.createElement('input');
    dueInput.type = 'date';
    dueInput.className = 't-input';
    dueInput.value = win.due;
    dueInput.setAttribute('aria-label', 'Due date for Unit ' + n);
    dueInput.dataset.unitN = String(n);
    dueInput.dataset.field = 'due';
    dueInput.addEventListener('change', onScheduleChange);
    tdDue.appendChild(dueInput);
    tr.appendChild(tdDue);

    tbody.appendChild(tr);

    // Persist initial spread to state
    if (!state.schedule[n]) {
      state.schedule[n] = { publish: win.publish, due: win.due };
    }
  });
}

function onScheduleChange(e) {
  var input = e.currentTarget;
  var n = Number(input.dataset.unitN);
  var field = input.dataset.field;
  if (!state.schedule[n]) state.schedule[n] = {};
  state.schedule[n][field] = input.value;
}

/* ══════════════════════════════════════════════════════════════════════
   STEP 4 — REVIEW
══════════════════════════════════════════════════════════════════════ */

function renderReview() {
  // Basics
  var basicsHtml =
    '<div class="t-review-field"><span class="t-review-key">Title</span><span class="t-review-val">' + escHtml(state.title) + '</span></div>' +
    '<div class="t-review-field"><span class="t-review-key">Start</span><span class="t-review-val">' + escHtml(state.start) + '</span></div>' +
    '<div class="t-review-field"><span class="t-review-key">End</span><span class="t-review-val">' + escHtml(state.end) + '</span></div>';
  if (state.createGroup && state.groupName) {
    basicsHtml += '<div class="t-review-field"><span class="t-review-key">Student group</span><span class="t-review-val">' + escHtml(state.groupName) + '</span></div>';
  }
  els.reviewBasics.innerHTML = basicsHtml;

  // Units
  var units = selectedUnitList();
  els.reviewUnits.innerHTML = '';

  if (units.length === 0) {
    els.reviewUnits.innerHTML = '<li style="color:var(--text-muted);font-family:var(--font-body);font-size:0.875rem;">No units selected.</li>';
    return;
  }

  // Header row
  var headerLi = document.createElement('li');
  headerLi.className = 't-review-unit-row';
  headerLi.style.fontWeight = '700';
  headerLi.style.fontSize = '0.75rem';
  headerLi.style.color = 'var(--text-muted)';
  headerLi.style.textTransform = 'uppercase';
  headerLi.style.letterSpacing = '0.04em';
  headerLi.innerHTML =
    '<span>Unit</span><span>Playlists</span><span>Publish</span><span>Due</span>';
  els.reviewUnits.appendChild(headerLi);

  units.forEach(function (entry) {
    var n = entry.unit.n;
    var sched = state.schedule[n] || {};
    var playlistNames = sortedPlaylists(entry.unit.playlists || [])
      .filter(function (pl) { return entry.selectedPlaylistIds.has(pl.id); })
      .map(function (pl) { return pl.name; })
      .join(', ') || '(none)';

    var li = document.createElement('li');
    li.className = 't-review-unit-row';

    li.innerHTML =
      '<span class="t-review-unit-name">Unit ' + n + ': ' + escHtml(entry.unit.title) + '</span>' +
      '<span class="t-review-unit-playlists">' + escHtml(playlistNames) + '</span>' +
      '<span class="t-review-unit-date">' + escHtml(sched.publish || '—') + '</span>' +
      '<span class="t-review-unit-date">' + escHtml(sched.due || '—') + '</span>';

    els.reviewUnits.appendChild(li);
  });
}

/* ── Create Payload & Submit ────────────────────────────────────────── */

function buildPayload() {
  var units = selectedUnitList().map(function (entry) {
    var n = entry.unit.n;
    var sched = state.schedule[n] || {};
    return {
      unit: n,
      playlistIds: Array.from(entry.selectedPlaylistIds),
      publish: sched.publish || '',
      due: sched.due || '',
    };
  });

  return {
    title: state.title,
    start: state.start,
    end:   state.end,
    groupName: state.createGroup ? state.groupName : null,
    units: units,
  };
}

function showCreateError(msg) {
  els.createError.textContent = msg;
  els.createError.classList.add('is-visible');
}

function hideCreateError() {
  els.createError.classList.remove('is-visible');
  els.createError.textContent = '';
}

function onClickCreate() {
  hideCreateError();
  var btn = els.btnCreate;
  btn.disabled = true;
  btn.innerHTML = '<span class="t-spinner" aria-hidden="true"></span> Creating…';

  var payload = buildPayload();
  var csrf = getCsrfToken();

  fetch('/teacher/courses/create/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf,
    },
    body: JSON.stringify(payload),
  })
    .then(function (res) {
      return res.json().then(function (data) {
        return { status: res.status, data: data };
      });
    })
    .then(function (result) {
      if (result.status === 201) {
        var courseId = result.data.courseId;
        window.location.href = '/teacher/courses/' + courseId + '/';
      } else {
        var msg = (result.data && result.data.error) ?
          result.data.error :
          'An error occurred (' + result.status + '). Please try again.';
        showCreateError(msg);
        btn.disabled = false;
        btn.innerHTML = 'Create course';
      }
    })
    .catch(function (err) {
      showCreateError('Network error: ' + (err.message || 'request failed'));
      btn.disabled = false;
      btn.innerHTML = 'Create course';
    });
}

/* ── Wire Up Events ─────────────────────────────────────────────────── */

function init() {
  // Step 1 — group name toggle
  els.fieldCreateGroup.addEventListener('change', function () {
    var show = els.fieldCreateGroup.checked;
    els.groupNameArea.style.display = show ? 'block' : 'none';
    if (!show) {
      els.fieldGroupName.value = '';
      showFieldError(els.errGroupName, els.fieldGroupName, false);
    }
  });

  // Step 1 — next
  $('btn-1-next').addEventListener('click', function () {
    if (validateStep1()) goTo(2);
  });

  // Step 2 — back / next
  $('btn-2-back').addEventListener('click', function () { goTo(1); });
  $('btn-2-next').addEventListener('click', function () {
    if (Object.keys(state.selectedUnits).length > 0) goTo(3);
  });

  // Step 3 — back / next
  $('btn-3-back').addEventListener('click', function () { goTo(2); });
  $('btn-3-next').addEventListener('click', function () { goTo(4); });

  // Step 4 — back / create
  $('btn-4-back').addEventListener('click', function () { goTo(3); });
  els.btnCreate.addEventListener('click', onClickCreate);
}

// Run after DOM is ready (script is deferred via type="module")
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
