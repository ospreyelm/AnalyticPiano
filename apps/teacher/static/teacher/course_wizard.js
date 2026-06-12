/* apps/teacher/static/teacher/course_wizard.js
   Vanilla JS — no jQuery, no RequireJS.
   Depends on window.__WIZARD_DATA__ set inline by the template. */

(function () {
  'use strict';

  /* ── Constants ──────────────────────────────────────────────────────── */

  const MODE_ORDER = ['roman', 'figures', 'play', 'play_figures'];

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
    if (step === 2 && prev !== 2) renderUnitPicker();
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
     STEP 2 — UNIT PICKER
  ══════════════════════════════════════════════════════════════════════ */

  /** Sort playlists per unit by MODE_ORDER, then alphabetically. */
  function sortedPlaylists(playlists) {
    return playlists.slice().sort(function (a, b) {
      var ai = MODE_ORDER.indexOf(a.mode);
      var bi = MODE_ORDER.indexOf(b.mode);
      if (ai === -1) ai = 99;
      if (bi === -1) bi = 99;
      if (ai !== bi) return ai - bi;
      return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
    });
  }

  function renderUnitPicker() {
    var root = els.unitPickerRoot;
    root.innerHTML = '';

    var branches = DATA.unitsJson;
    if (!branches || branches.length === 0) {
      root.innerHTML = '<p style="color:var(--text-muted);font-family:var(--font-body);font-size:0.875rem;">No units available.</p>';
      return;
    }

    // Group by branch
    var branchMap = {};
    var branchOrder = [];
    branches.forEach(function (unit) {
      var b = unit.branch || 'Other';
      if (!branchMap[b]) { branchMap[b] = []; branchOrder.push(b); }
      branchMap[b].push(unit);
    });

    branchOrder.forEach(function (branchName) {
      var units = branchMap[branchName];
      var branchEl = document.createElement('div');
      branchEl.className = 't-branch is-open';

      // Branch header (collapsible button)
      var header = document.createElement('button');
      header.type = 'button';
      header.className = 't-branch-header';
      header.setAttribute('aria-expanded', 'true');
      header.setAttribute('aria-controls', 'branch-body-' + sanitizeId(branchName));
      header.innerHTML =
        '<span>' + escHtml(branchName) + '</span>' +
        '<span class="t-branch-chevron" aria-hidden="true">&#9660;</span>';

      var bodyId = 'branch-body-' + sanitizeId(branchName);
      var body = document.createElement('div');
      body.className = 't-branch-body';
      body.id = bodyId;

      header.addEventListener('click', function () {
        var open = branchEl.classList.toggle('is-open');
        header.setAttribute('aria-expanded', String(open));
      });
      header.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          header.click();
        }
      });

      units.forEach(function (unit) {
        body.appendChild(buildUnitCard(unit));
      });

      branchEl.appendChild(header);
      branchEl.appendChild(body);
      root.appendChild(branchEl);
    });

    refreshStep2Next();
  }

  function buildUnitCard(unit) {
    var n = unit.n;
    var playlists = sortedPlaylists(unit.playlists || []);
    var hasContent = playlists.length > 0;

    var card = document.createElement('div');
    card.className = 't-unit-card';
    card.dataset.unitN = String(n);

    // Checkbox
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = 'unit-cb-' + n;
    cb.name = 'unit-' + n;
    cb.disabled = !hasContent;
    cb.setAttribute('aria-label', 'Select unit ' + n + ': ' + unit.title);

    // If previously selected, restore
    if (state.selectedUnits[n]) cb.checked = true;

    var body = document.createElement('div');
    body.className = 't-unit-card-body';

    var titleLine = document.createElement('div');
    var countBadge = '<span class="t-unit-badge' +
      (playlists.length === 0 ? ' is-zero' : '') + '">' +
      playlists.length + ' playlist' + (playlists.length !== 1 ? 's' : '') +
      '</span>';
    titleLine.innerHTML =
      '<span class="t-unit-title">Unit ' + n + ': ' + escHtml(unit.title) + '</span>' +
      countBadge;
    titleLine.className = 't-unit-title-line';

    body.appendChild(titleLine);

    if (!hasContent) {
      var noContent = document.createElement('div');
      noContent.className = 't-unit-no-content';
      noContent.textContent = 'No official content yet — unit cannot be selected.';
      body.appendChild(noContent);
    } else {
      // Playlist sub-list (shown when unit is checked)
      var playlistContainer = document.createElement('div');
      playlistContainer.id = 'playlists-' + n;
      playlistContainer.style.display = state.selectedUnits[n] ? 'block' : 'none';

      var list = document.createElement('ul');
      list.className = 't-playlist-list';

      playlists.forEach(function (pl) {
        var li = document.createElement('li');
        li.className = 't-playlist-item';

        var plCb = document.createElement('input');
        plCb.type = 'checkbox';
        plCb.id = 'pl-cb-' + pl.id;
        plCb.value = pl.id;
        // Default: all checked; or restore previous state
        plCb.checked = !state.selectedUnits[n] ||
          state.selectedUnits[n].selectedPlaylistIds.has(pl.id);

        var plLabel = document.createElement('label');
        plLabel.htmlFor = 'pl-cb-' + pl.id;
        plLabel.textContent = pl.name;

        var modeBadge = document.createElement('span');
        modeBadge.className = 't-playlist-mode-badge';
        modeBadge.textContent = pl.mode;

        plCb.addEventListener('change', function () {
          updateUnitPlaylistSelection(n);
        });

        li.appendChild(plCb);
        li.appendChild(plLabel);
        li.appendChild(modeBadge);
        list.appendChild(li);
      });

      playlistContainer.appendChild(list);
      body.appendChild(playlistContainer);

      // Unit checkbox change handler
      cb.addEventListener('change', function () {
        playlistContainer.style.display = cb.checked ? 'block' : 'none';
        if (cb.checked) {
          // Initialise selection (all checked by default)
          updateUnitPlaylistSelection(n);
        } else {
          delete state.selectedUnits[n];
        }
        refreshStep2Next();
      });

      // Initialise state if pre-checked
      if (cb.checked) updateUnitPlaylistSelection(n);
    }

    card.appendChild(cb);
    card.appendChild(body);
    return card;
  }

  /** Read playlist checkboxes for a unit and write into state.selectedUnits. */
  function updateUnitPlaylistSelection(n) {
    var playlists = sortedPlaylists(
      (DATA.unitsJson.find(function (u) { return u.n === n; }) || { playlists: [] }).playlists
    );
    var selectedIds = new Set();
    playlists.forEach(function (pl) {
      var plCb = document.getElementById('pl-cb-' + pl.id);
      if (plCb && plCb.checked) selectedIds.add(pl.id);
    });
    state.selectedUnits[n] = {
      unit: DATA.unitsJson.find(function (u) { return u.n === n; }),
      selectedPlaylistIds: selectedIds,
    };
  }

  function refreshStep2Next() {
    var anySelected = Object.keys(state.selectedUnits).length > 0;
    els.btn2Next.disabled = !anySelected;
    els.unitSelectionHint.style.display = anySelected ? 'none' : 'inline';
  }

  /* ══════════════════════════════════════════════════════════════════════
     SCHEDULE SPREADING (client-side)
  ══════════════════════════════════════════════════════════════════════ */

  /** Parse 'YYYY-MM-DD' → Date (local noon to avoid DST issues). */
  function parseDate(str) {
    var parts = str.split('-');
    return new Date(+parts[0], +parts[1] - 1, +parts[2], 12, 0, 0);
  }

  /** Format Date → 'YYYY-MM-DD'. */
  function fmtDate(d) {
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + dd;
  }

  /** Add days to a Date (returns new Date). */
  function addDays(d, n) {
    var r = new Date(d);
    r.setDate(r.getDate() + n);
    return r;
  }

  /**
   * Spread N units evenly across [start, end].
   * Returns array of { publish: 'YYYY-MM-DD', due: 'YYYY-MM-DD' }.
   * due = last Sunday (weekday 0) on or before window end, clamped > windowStart and <= end.
   */
  function spreadSchedule(startStr, endStr, n) {
    var start = parseDate(startStr);
    var end   = parseDate(endStr);
    var totalMs = end.getTime() - start.getTime();
    var windowMs = totalMs / n;
    var result = [];

    for (var i = 0; i < n; i++) {
      var winStart = new Date(start.getTime() + i * windowMs);
      var winEnd   = new Date(start.getTime() + (i + 1) * windowMs);
      if (i === n - 1) winEnd = end; // ensure last window hits end exactly

      // publish = window start
      var publish = winStart;

      // due = last Sunday on/before winEnd, but > winStart, <= end
      var due = new Date(winEnd);
      // walk back to Sunday (getDay() === 0)
      var daysBack = due.getDay(); // 0=Sun, 1=Mon … 6=Sat
      due = addDays(due, -daysBack);

      // If due <= winStart (very short window), fall back to winEnd
      if (due.getTime() <= winStart.getTime()) due = winEnd;
      // Clamp to semester end
      if (due.getTime() > end.getTime()) due = end;

      result.push({ publish: fmtDate(publish), due: fmtDate(due) });
    }
    return result;
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

  /* ══════════════════════════════════════════════════════════════════════
     CREATE — POST
  ══════════════════════════════════════════════════════════════════════ */

  function getCsrfToken() {
    // Try cookie first (standard Django)
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    // Fallback: hidden input rendered by {% csrf_token %}
    var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return inp ? inp.value : '';
  }

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

  /* ══════════════════════════════════════════════════════════════════════
     UTILITIES
  ══════════════════════════════════════════════════════════════════════ */

  function escHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function sanitizeId(str) {
    return String(str).replace(/[^a-zA-Z0-9_-]/g, '_');
  }

  /* ══════════════════════════════════════════════════════════════════════
     WIRE UP EVENTS
  ══════════════════════════════════════════════════════════════════════ */

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

  // Run after DOM is ready (script is deferred via body_extra block)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
