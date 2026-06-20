/* apps/teacher/static/teacher/modules/timeline.js */
'use strict';

import {
  escHtml,
  courseUrl,
  postJson,
  showError,
  hideError,
  modeLabel,
  unitFromTags,
  studentUnitUrl,
  copyToClipboard
} from './utils.js';

// State variables scoped to the module
let rows = [];
let dragSrcIndex = null;
let DATA = {};

function refreshSaveBtn() {
  const btn = document.getElementById('btn-save-changes');
  if (!btn) return;
  const hasDirty = rows.some(r => r._dirty && !r._removed);
  const hasRemoved = rows.some(r => r._removed);
  btn.disabled = !(hasDirty || hasRemoved);
}

function renderTimeline() {
  const tbody = document.getElementById('timeline-tbody');
  const empty = document.getElementById('timeline-empty');
  if (!tbody) return;

  tbody.innerHTML = '';

  const visible = rows.filter(r => !r._removed);

  if (visible.length === 0) {
    if (empty) empty.style.display = 'block';
    refreshSaveBtn();
    return;
  }
  if (empty) empty.style.display = 'none';

  visible.forEach((row, visIdx) => {
    const tr = document.createElement('tr');
    tr.className = 't-timeline-row';
    tr.dataset.pcoId = String(row.pcoId);
    tr.dataset.visIdx = String(visIdx);
    tr.setAttribute('draggable', 'true');

    // Drag handle
    const tdDrag = document.createElement('td');
    tdDrag.className = 't-col-drag';
    tdDrag.setAttribute('aria-hidden', 'true');
    tdDrag.innerHTML = '<span class="t-drag-handle" title="Drag to reorder">&#8597;</span>';
    tr.appendChild(tdDrag);

    // Name
    const tdName = document.createElement('td');
    tdName.className = 't-col-name';
    const nameSpan = document.createElement('span');
    nameSpan.textContent = row.playlistName;
    tdName.appendChild(nameSpan);

    const unitN = unitFromTags(row.skillTags);
    if (unitN !== null) {
      const studentUrl = studentUnitUrl(unitN);
      const linkWrap = document.createElement('span');
      linkWrap.style.cssText = 'display:inline-flex;gap:0.25rem;margin-left:0.5rem;vertical-align:middle;';

      const viewLink = document.createElement('a');
      viewLink.href = studentUrl;
      viewLink.target = '_blank';
      viewLink.rel = 'noopener noreferrer';
      viewLink.className = 't-btn t-btn-ghost t-btn-sm';
      viewLink.textContent = 'Student view ↗';
      linkWrap.appendChild(viewLink);

      const copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 't-btn t-btn-ghost t-btn-sm';
      copyBtn.textContent = 'Copy link';
      copyBtn.addEventListener('click', () => {
        copyToClipboard(studentUrl, copyBtn);
      });
      linkWrap.appendChild(copyBtn);
      tdName.appendChild(linkWrap);
    }
    tr.appendChild(tdName);

    // Mode badge
    const tdMode = document.createElement('td');
    tdMode.className = 't-col-mode';
    tdMode.innerHTML = '<span class="t-mode-badge t-mode-' + escHtml(row.mode) + '">' +
      escHtml(modeLabel(row.mode)) + '</span>';
    tr.appendChild(tdMode);

    // Publish date
    const tdPublish = document.createElement('td');
    const pubInput = document.createElement('input');
    pubInput.type = 'date';
    pubInput.className = 't-input t-input-sm';
    pubInput.value = row.publish;
    pubInput.setAttribute('aria-label', 'Publish date for ' + row.playlistName);
    pubInput.addEventListener('change', (e) => {
      row.publish = e.target.value;
      row._dirty = true;
      refreshSaveBtn();
    });
    tdPublish.appendChild(pubInput);
    tr.appendChild(tdPublish);

    // Due date
    const tdDue = document.createElement('td');
    const dueInput = document.createElement('input');
    dueInput.type = 'date';
    dueInput.className = 't-input t-input-sm';
    dueInput.value = row.due;
    dueInput.setAttribute('aria-label', 'Due date for ' + row.playlistName);
    dueInput.addEventListener('change', (e) => {
      row.due = e.target.value;
      row._dirty = true;
      refreshSaveBtn();
    });
    tdDue.appendChild(dueInput);
    tr.appendChild(tdDue);

    // Remove
    const tdRemove = document.createElement('td');
    tdRemove.className = 't-col-remove';
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 't-btn-icon t-btn-remove';
    removeBtn.setAttribute('aria-label', 'Remove ' + row.playlistName);
    removeBtn.title = 'Remove from course';
    removeBtn.innerHTML = '&#10005;';
    removeBtn.addEventListener('click', () => {
      if (!window.confirm('Remove "' + row.playlistName + '" from this course?')) return;
      row._removed = true;
      row._dirty = false;
      renderTimeline();
      refreshSaveBtn();
    });
    tdRemove.appendChild(removeBtn);
    tr.appendChild(tdRemove);

    // Drag events
    tr.addEventListener('dragstart', (e) => {
      dragSrcIndex = visIdx;
      tr.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(visIdx));
    });
    tr.addEventListener('dragend', () => {
      tr.classList.remove('is-dragging');
      const rows2 = tbody.querySelectorAll('.t-timeline-row');
      rows2.forEach(r2 => r2.classList.remove('is-drag-over'));
    });
    tr.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const all = tbody.querySelectorAll('.t-timeline-row');
      all.forEach(r2 => r2.classList.remove('is-drag-over'));
      tr.classList.add('is-drag-over');
    });
    tr.addEventListener('dragleave', () => {
      tr.classList.remove('is-drag-over');
    });
    tr.addEventListener('drop', (e) => {
      e.preventDefault();
      tr.classList.remove('is-drag-over');
      if (dragSrcIndex === null || dragSrcIndex === visIdx) return;

      const visible2 = rows.filter(r2 => !r2._removed);
      const moved = visible2.splice(dragSrcIndex, 1)[0];
      visible2.splice(visIdx, 0, moved);

      visible2.forEach((r2, i) => {
        r2.order = i + 1;
        r2._dirty = true;
      });

      const removed2 = rows.filter(r2 => r2._removed);
      rows.length = 0;
      visible2.forEach(r2 => rows.push(r2));
      removed2.forEach(r2 => rows.push(r2));

      dragSrcIndex = null;
      renderTimeline();
      refreshSaveBtn();
    });

    tbody.appendChild(tr);
  });

  refreshSaveBtn();
}

function onSaveChanges() {
  hideError('timeline-error');
  const btn = document.getElementById('btn-save-changes');
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="t-spinner" aria-hidden="true"></span> Saving…';

  const changes = rows
    .filter(r => r._dirty && !r._removed)
    .map(r => ({
      pcoId: r.pcoId,
      publish: r.publish || null,
      due: r.due || null,
      order: r.order,
    }));

  const removals = rows
    .filter(r => r._removed)
    .map(r => r.pcoId);

  postJson(courseUrl(DATA.courseId, 'update-pco/'), { changes, removals })
    .then(result => {
      if (result.status === 200 || result.status === 201) {
        window.location.reload();
      } else {
        const msg = (result.data && result.data.error)
          ? result.data.error
          : 'Save failed (' + result.status + '). Please try again.';
        showError('timeline-error', msg);
        btn.disabled = false;
        btn.textContent = 'Save changes';
        refreshSaveBtn();
      }
    })
    .catch(err => {
      showError('timeline-error', 'Network error: ' + (err.message || 'request failed'));
      btn.disabled = false;
      btn.textContent = 'Save changes';
      refreshSaveBtn();
    });
}

function onRespread() {
  hideError('timeline-error');
  const fromOrder = parseInt(document.getElementById('respread-from-order').value, 10) || 1;
  const publishAll = document.getElementById('respread-publish-all').checked;
  const btn = document.getElementById('btn-respread');
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="t-spinner t-spinner-dark" aria-hidden="true"></span> Spreading…';

  postJson(courseUrl(DATA.courseId, 'respread/'), { fromOrder, publishAllAtStart: publishAll })
    .then(result => {
      if (result.status === 200 || result.status === 201) {
        window.location.reload();
      } else {
        const msg = (result.data && result.data.error)
          ? result.data.error
          : 'Re-spread failed (' + result.status + '). Please try again.';
        showError('timeline-error', msg);
        btn.disabled = false;
        btn.textContent = 'Re-spread remaining';
      }
    })
    .catch(err => {
      showError('timeline-error', 'Network error: ' + (err.message || 'request failed'));
      btn.disabled = false;
      btn.textContent = 'Re-spread remaining';
    });
}

function renderAddPlaylistSelect() {
  const sel = document.getElementById('add-playlist-select');
  if (!sel) return;

  const playlists = DATA.addablePlaylists || [];
  const mine = playlists.filter(p => p.source === 'mine');
  const official = playlists.filter(p => p.source === 'official');

  sel.innerHTML = '<option value="">— choose —</option>';

  if (mine.length > 0) {
    const grpMine = document.createElement('optgroup');
    grpMine.label = 'My playlists';
    mine.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      grpMine.appendChild(opt);
    });
    sel.appendChild(grpMine);
  }

  if (official.length > 0) {
    const grpOfficial = document.createElement('optgroup');
    grpOfficial.label = 'Official playlists';
    official.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      grpOfficial.appendChild(opt);
    });
    sel.appendChild(grpOfficial);
  }

  if (playlists.length === 0) {
    const opt = document.createElement('option');
    opt.disabled = true;
    opt.textContent = 'No playlists available';
    sel.appendChild(opt);
  }
}

function onAddPlaylist() {
  hideError('add-playlist-error');
  const sel = document.getElementById('add-playlist-select');
  const publish = document.getElementById('add-playlist-publish').value;
  const due = document.getElementById('add-playlist-due').value;
  const playlistId = sel ? parseInt(sel.value, 10) : NaN;

  if (!playlistId) {
    showError('add-playlist-error', 'Please choose a playlist.');
    return;
  }

  const btn = document.getElementById('btn-add-playlist');
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="t-spinner" aria-hidden="true"></span> Adding…';

  postJson(courseUrl(DATA.courseId, 'add-playlist/'), {
    playlistId: playlistId,
    publish: publish || null,
    due: due || null,
  })
    .then(result => {
      if (result.status === 200 || result.status === 201) {
        window.location.reload();
      } else {
        const msg = (result.data && result.data.error)
          ? result.data.error
          : 'Add failed (' + result.status + '). Please try again.';
        showError('add-playlist-error', msg);
        btn.disabled = false;
        btn.textContent = 'Add to course';
      }
    })
    .catch(err => {
      showError('add-playlist-error', 'Network error: ' + (err.message || 'request failed'));
      btn.disabled = false;
      btn.textContent = 'Add to course';
    });
}

export function initTimeline(courseData) {
  DATA = courseData;
  rows = (DATA.pcoRows || []).map(r => ({
    pcoId: r.pcoId,
    playlistId: r.playlistId,
    playlistName: r.playlistName,
    mode: r.mode,
    skillTags: r.skillTags || [],
    publish: r.publish || '',
    due: r.due || '',
    order: r.order,
    _dirty: false,
    _removed: false,
  }));

  renderTimeline();
  renderAddPlaylistSelect();

  const saveBtn = document.getElementById('btn-save-changes');
  if (saveBtn) saveBtn.addEventListener('click', onSaveChanges);

  const respreadBtn = document.getElementById('btn-respread');
  if (respreadBtn) respreadBtn.addEventListener('click', onRespread);

  const addBtn = document.getElementById('btn-add-playlist');
  if (addBtn) addBtn.addEventListener('click', onAddPlaylist);
}
