/* apps/teacher/static/teacher/modules/unit_picker.js */
'use strict';

import { escHtml } from './utils.js';

const MODE_ORDER = ['roman', 'figures', 'play', 'play_figures'];

function sanitizeId(str) {
  return String(str).replace(/[^a-zA-Z0-9_-]/g, '_');
}

/** Sort playlists per unit by MODE_ORDER, then alphabetically. */
export function sortedPlaylists(playlists) {
  return playlists.slice().sort(function (a, b) {
    var ai = MODE_ORDER.indexOf(a.mode);
    var bi = MODE_ORDER.indexOf(b.mode);
    if (ai === -1) ai = 99;
    if (bi === -1) bi = 99;
    if (ai !== bi) return ai - bi;
    return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  });
}

/** Read playlist checkboxes for a unit and write into selectedUnits. */
export function updateUnitPlaylistSelection(unit, selectedUnits) {
  var n = unit.n;
  var playlists = sortedPlaylists(unit.playlists || []);
  var selectedIds = new Set();
  playlists.forEach(function (pl) {
    var plCb = document.getElementById('pl-cb-' + pl.id);
    if (plCb && plCb.checked) selectedIds.add(pl.id);
  });
  selectedUnits[n] = {
    unit: unit,
    selectedPlaylistIds: selectedIds,
  };
}

export function buildUnitCard(unit, selectedUnits, onSelectionChange) {
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
  if (selectedUnits[n]) cb.checked = true;

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
    playlistContainer.style.display = selectedUnits[n] ? 'block' : 'none';

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
      plCb.checked = !selectedUnits[n] ||
        selectedUnits[n].selectedPlaylistIds.has(pl.id);

      var plLabel = document.createElement('label');
      plLabel.htmlFor = 'pl-cb-' + pl.id;
      plLabel.textContent = pl.name;

      var modeBadge = document.createElement('span');
      modeBadge.className = 't-playlist-mode-badge';
      modeBadge.textContent = pl.mode;

      plCb.addEventListener('change', function () {
        updateUnitPlaylistSelection(unit, selectedUnits);
        onSelectionChange();
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
        updateUnitPlaylistSelection(unit, selectedUnits);
      } else {
        delete selectedUnits[n];
      }
      onSelectionChange();
    });

    // Initialise state if pre-checked
    if (cb.checked) updateUnitPlaylistSelection(unit, selectedUnits);
  }

  card.appendChild(cb);
  card.appendChild(body);
  return card;
}

export function renderUnitPicker(root, unitsJson, selectedUnits, onSelectionChange) {
  root.innerHTML = '';

  if (!unitsJson || unitsJson.length === 0) {
    root.innerHTML = '<p style="color:var(--text-muted);font-family:var(--font-body);font-size:0.875rem;">No units available.</p>';
    return;
  }

  // Group by branch
  var branchMap = {};
  var branchOrder = [];
  unitsJson.forEach(function (unit) {
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
      body.appendChild(buildUnitCard(unit, selectedUnits, onSelectionChange));
    });

    branchEl.appendChild(header);
    branchEl.appendChild(body);
    root.appendChild(branchEl);
  });
}
