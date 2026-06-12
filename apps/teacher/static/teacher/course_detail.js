/* apps/teacher/static/teacher/course_detail.js
   Vanilla JS — no jQuery, no RequireJS.
   Depends on window.__COURSE_DATA__ set inline by the template. */

(function () {
  'use strict';

  /* ── Data from server ───────────────────────────────────────────────── */

  var DATA = window.__COURSE_DATA__ || {
    courseId: 0,
    pcoRows: [],
    groups: [],
    activity: {},
    addablePlaylists: [],
    dashboardEditUrl: '',
    dashboardActivityUrl: '',
  };

  /* ── State ──────────────────────────────────────────────────────────── */

  // Working copy of rows (shallow clone so we can mutate safely)
  var rows = (DATA.pcoRows || []).map(function (r) {
    return {
      pcoId:        r.pcoId,
      playlistId:   r.playlistId,
      playlistName: r.playlistName,
      mode:         r.mode,
      publish:      r.publish || '',
      due:          r.due     || '',
      order:        r.order,
      _dirty:       false,
      _removed:     false,
    };
  });

  /* ── Utilities ──────────────────────────────────────────────────────── */

  function escHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return inp ? inp.value : '';
  }

  function courseUrl(suffix) {
    return '/teacher/courses/' + DATA.courseId + '/' + suffix;
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(payload),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { status: res.status, data: data };
      });
    });
  }

  function showError(bannerId, msg) {
    var el = document.getElementById(bannerId);
    if (!el) return;
    el.textContent = msg;
    el.classList.add('is-visible');
  }

  function hideError(bannerId) {
    var el = document.getElementById(bannerId);
    if (!el) return;
    el.textContent = '';
    el.classList.remove('is-visible');
  }

  function modeLabel(mode) {
    var MAP = {
      roman:        'Roman',
      figures:      'Figures',
      play:         'Play',
      play_figures: 'Play+Fig',
      identify:     'Identify',
    };
    return MAP[mode] || (mode || '—');
  }

  /* ── Save-button state ──────────────────────────────────────────────── */

  function refreshSaveBtn() {
    var btn = document.getElementById('btn-save-changes');
    if (!btn) return;
    var hasDirty  = rows.some(function (r) { return r._dirty && !r._removed; });
    var hasRemoved = rows.some(function (r) { return r._removed; });
    btn.disabled = !(hasDirty || hasRemoved);
  }

  /* ── Timeline rendering ─────────────────────────────────────────────── */

  var dragSrcIndex = null; // index of row being dragged

  function renderTimeline() {
    var tbody = document.getElementById('timeline-tbody');
    var empty = document.getElementById('timeline-empty');
    if (!tbody) return;

    tbody.innerHTML = '';

    var visible = rows.filter(function (r) { return !r._removed; });

    if (visible.length === 0) {
      if (empty) empty.style.display = 'block';
      refreshSaveBtn();
      return;
    }
    if (empty) empty.style.display = 'none';

    visible.forEach(function (row, visIdx) {
      var tr = document.createElement('tr');
      tr.className = 't-timeline-row';
      tr.dataset.pcoId = String(row.pcoId);
      tr.dataset.visIdx = String(visIdx);
      tr.setAttribute('draggable', 'true');

      // ── Drag handle ──
      var tdDrag = document.createElement('td');
      tdDrag.className = 't-col-drag';
      tdDrag.setAttribute('aria-hidden', 'true');
      tdDrag.innerHTML = '<span class="t-drag-handle" title="Drag to reorder">&#8597;</span>';
      tr.appendChild(tdDrag);

      // ── Name ──
      var tdName = document.createElement('td');
      tdName.className = 't-col-name';
      tdName.textContent = row.playlistName;
      tr.appendChild(tdName);

      // ── Mode badge ──
      var tdMode = document.createElement('td');
      tdMode.className = 't-col-mode';
      tdMode.innerHTML = '<span class="t-mode-badge t-mode-' + escHtml(row.mode) + '">' +
        escHtml(modeLabel(row.mode)) + '</span>';
      tr.appendChild(tdMode);

      // ── Publish date ──
      var tdPublish = document.createElement('td');
      tdPublish.className = 't-col-date';
      var pubInput = document.createElement('input');
      pubInput.type = 'date';
      pubInput.className = 't-input t-input-sm';
      pubInput.value = row.publish;
      pubInput.setAttribute('aria-label', 'Publish date for ' + row.playlistName);
      pubInput.addEventListener('change', (function (r) {
        return function (e) {
          r.publish = e.target.value;
          r._dirty = true;
          refreshSaveBtn();
        };
      }(row)));
      tdPublish.appendChild(pubInput);
      tr.appendChild(tdPublish);

      // ── Due date ──
      var tdDue = document.createElement('td');
      tdDue.className = 't-col-date';
      var dueInput = document.createElement('input');
      dueInput.type = 'date';
      dueInput.className = 't-input t-input-sm';
      dueInput.value = row.due;
      dueInput.setAttribute('aria-label', 'Due date for ' + row.playlistName);
      dueInput.addEventListener('change', (function (r) {
        return function (e) {
          r.due = e.target.value;
          r._dirty = true;
          refreshSaveBtn();
        };
      }(row)));
      tdDue.appendChild(dueInput);
      tr.appendChild(tdDue);

      // ── Remove ──
      var tdRemove = document.createElement('td');
      tdRemove.className = 't-col-remove';
      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 't-btn-icon t-btn-remove';
      removeBtn.setAttribute('aria-label', 'Remove ' + row.playlistName);
      removeBtn.title = 'Remove from course';
      removeBtn.innerHTML = '&#10005;';
      removeBtn.addEventListener('click', (function (r) {
        return function () {
          if (!window.confirm('Remove "' + r.playlistName + '" from this course?')) return;
          r._removed = true;
          r._dirty = false;
          renderTimeline();
          refreshSaveBtn();
        };
      }(row)));
      tdRemove.appendChild(removeBtn);
      tr.appendChild(tdRemove);

      // ── Drag events ──
      tr.addEventListener('dragstart', function (e) {
        dragSrcIndex = visIdx;
        tr.classList.add('is-dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(visIdx));
      });
      tr.addEventListener('dragend', function () {
        tr.classList.remove('is-dragging');
        // Remove all drag-over highlights
        var rows2 = tbody.querySelectorAll('.t-timeline-row');
        rows2.forEach(function (r2) { r2.classList.remove('is-drag-over'); });
      });
      tr.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        var all = tbody.querySelectorAll('.t-timeline-row');
        all.forEach(function (r2) { r2.classList.remove('is-drag-over'); });
        tr.classList.add('is-drag-over');
      });
      tr.addEventListener('dragleave', function () {
        tr.classList.remove('is-drag-over');
      });
      tr.addEventListener('drop', function (e) {
        e.preventDefault();
        tr.classList.remove('is-drag-over');
        if (dragSrcIndex === null || dragSrcIndex === visIdx) return;

        // Reorder the `rows` array (visible indices only)
        var visible2 = rows.filter(function (r2) { return !r2._removed; });
        var moved = visible2.splice(dragSrcIndex, 1)[0];
        visible2.splice(visIdx, 0, moved);

        // Write back new order integers and mark dirty
        visible2.forEach(function (r2, i) {
          r2.order = i + 1;
          r2._dirty = true;
        });

        // Rebuild rows array preserving removed entries at end
        var removed2 = rows.filter(function (r2) { return r2._removed; });
        rows.length = 0;
        visible2.forEach(function (r2) { rows.push(r2); });
        removed2.forEach(function (r2) { rows.push(r2); });

        dragSrcIndex = null;
        renderTimeline();
        refreshSaveBtn();
      });

      tbody.appendChild(tr);
    });

    refreshSaveBtn();
  }

  /* ── Save changes (update-pco) ──────────────────────────────────────── */

  function onSaveChanges() {
    hideError('timeline-error');
    var btn = document.getElementById('btn-save-changes');
    btn.disabled = true;
    btn.innerHTML = '<span class="t-spinner" aria-hidden="true"></span> Saving…';

    var changes = rows
      .filter(function (r) { return r._dirty && !r._removed; })
      .map(function (r) {
        return {
          pcoId:   r.pcoId,
          publish: r.publish || null,
          due:     r.due     || null,
          order:   r.order,
        };
      });

    var removals = rows
      .filter(function (r) { return r._removed; })
      .map(function (r) { return r.pcoId; });

    postJson(courseUrl('update-pco/'), { changes: changes, removals: removals })
      .then(function (result) {
        if (result.status === 200 || result.status === 201) {
          window.location.reload();
        } else {
          var msg = (result.data && result.data.error) ?
            result.data.error :
            'Save failed (' + result.status + '). Please try again.';
          showError('timeline-error', msg);
          btn.disabled = false;
          btn.textContent = 'Save changes';
          refreshSaveBtn();
        }
      })
      .catch(function (err) {
        showError('timeline-error', 'Network error: ' + (err.message || 'request failed'));
        btn.disabled = false;
        btn.textContent = 'Save changes';
        refreshSaveBtn();
      });
  }

  /* ── Re-spread ──────────────────────────────────────────────────────── */

  function onRespread() {
    hideError('timeline-error');
    var fromOrder = parseInt(document.getElementById('respread-from-order').value, 10) || 1;
    var publishAll = document.getElementById('respread-publish-all').checked;
    var btn = document.getElementById('btn-respread');
    btn.disabled = true;
    btn.innerHTML = '<span class="t-spinner t-spinner-dark" aria-hidden="true"></span> Spreading…';

    postJson(courseUrl('respread/'), { fromOrder: fromOrder, publishAllAtStart: publishAll })
      .then(function (result) {
        if (result.status === 200 || result.status === 201) {
          window.location.reload();
        } else {
          var msg = (result.data && result.data.error) ?
            result.data.error :
            'Re-spread failed (' + result.status + '). Please try again.';
          showError('timeline-error', msg);
          btn.disabled = false;
          btn.textContent = 'Re-spread remaining';
        }
      })
      .catch(function (err) {
        showError('timeline-error', 'Network error: ' + (err.message || 'request failed'));
        btn.disabled = false;
        btn.textContent = 'Re-spread remaining';
      });
  }

  /* ── Add playlist ───────────────────────────────────────────────────── */

  function renderAddPlaylistSelect() {
    var sel = document.getElementById('add-playlist-select');
    if (!sel) return;

    var playlists = DATA.addablePlaylists || [];
    var mine     = playlists.filter(function (p) { return p.source === 'mine'; });
    var official = playlists.filter(function (p) { return p.source === 'official'; });

    sel.innerHTML = '<option value="">— choose —</option>';

    if (mine.length > 0) {
      var grpMine = document.createElement('optgroup');
      grpMine.label = 'My playlists';
      mine.forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        grpMine.appendChild(opt);
      });
      sel.appendChild(grpMine);
    }

    if (official.length > 0) {
      var grpOfficial = document.createElement('optgroup');
      grpOfficial.label = 'Official playlists';
      official.forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        grpOfficial.appendChild(opt);
      });
      sel.appendChild(grpOfficial);
    }

    if (playlists.length === 0) {
      var opt = document.createElement('option');
      opt.disabled = true;
      opt.textContent = 'No playlists available';
      sel.appendChild(opt);
    }
  }

  function onAddPlaylist() {
    hideError('add-playlist-error');
    var sel     = document.getElementById('add-playlist-select');
    var publish = document.getElementById('add-playlist-publish').value;
    var due     = document.getElementById('add-playlist-due').value;
    var playlistId = sel ? parseInt(sel.value, 10) : NaN;

    if (!playlistId) {
      showError('add-playlist-error', 'Please choose a playlist.');
      return;
    }

    var btn = document.getElementById('btn-add-playlist');
    btn.disabled = true;
    btn.innerHTML = '<span class="t-spinner" aria-hidden="true"></span> Adding…';

    postJson(courseUrl('add-playlist/'), {
      playlistId: playlistId,
      publish: publish || null,
      due:     due     || null,
    })
      .then(function (result) {
        if (result.status === 200 || result.status === 201) {
          window.location.reload();
        } else {
          var msg = (result.data && result.data.error) ?
            result.data.error :
            'Add failed (' + result.status + '). Please try again.';
          showError('add-playlist-error', msg);
          btn.disabled = false;
          btn.textContent = 'Add to course';
        }
      })
      .catch(function (err) {
        showError('add-playlist-error', 'Network error: ' + (err.message || 'request failed'));
        btn.disabled = false;
        btn.textContent = 'Add to course';
      });
  }

  /* ── Roster panel ───────────────────────────────────────────────────── */

  function renderRoster() {
    var container = document.getElementById('roster-content');
    if (!container) return;

    var groups = DATA.groups || [];
    var html = '';

    if (groups.length === 0) {
      html += '<p style="font-size:0.875rem;color:var(--text-muted);font-family:var(--font-body);">No groups linked to this course.</p>';
    } else {
      groups.forEach(function (group) {
        var joinLink = window.location.origin + '/s/join/?code=' + encodeURIComponent(group.join_code || '');
        html += '<div class="t-roster-group">';
        html += '<div class="t-roster-group-header">';
        html += '<span class="t-roster-group-name">' + escHtml(group.name) + '</span>';
        html += '<span class="t-unit-badge">' + (group.member_count || 0) + ' member' +
                ((group.member_count || 0) !== 1 ? 's' : '') + '</span>';
        html += '</div>';

        if (group.join_code) {
          html += '<div class="t-roster-join-row">';
          html += '<span class="t-roster-join-code">Join code: <code>' + escHtml(group.join_code) + '</code></span>';
          html += '<button class="t-btn t-btn-ghost t-btn-sm" type="button" data-join-link="' +
                  escHtml(joinLink) + '">Copy join link</button>';
          html += '</div>';
        }

        var members = group.members || [];
        if (members.length > 0) {
          html += '<ul class="t-roster-member-list">';
          members.forEach(function (m) {
            html += '<li class="t-roster-member">' +
                    escHtml(m.name || m.email) +
                    (m.name && m.email ? ' <span class="t-muted">(' + escHtml(m.email) + ')</span>' : '') +
                    '</li>';
          });
          html += '</ul>';
        }

        html += '</div>';
      });
    }

    // Add group inline form (always rendered, shown/hidden via JS)
    html += '<div id="add-group-form" style="display:none;margin-top:0.75rem;">';
    html += '<div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;">';
    html += '<input id="add-group-name" type="text" class="t-input t-input-sm" placeholder="Group name" maxlength="100" style="flex:1;min-width:120px;" />';
    html += '<button id="btn-add-group-submit" class="t-btn t-btn-primary t-btn-sm" type="button">Create</button>';
    html += '<button id="btn-add-group-cancel" class="t-btn t-btn-ghost t-btn-sm" type="button">Cancel</button>';
    html += '</div>';
    html += '<p id="add-group-error" class="t-error" style="margin-top:0.25rem;display:none;font-size:0.8125rem;color:var(--color-danger,#c0392b);"></p>';
    html += '</div>';

    container.innerHTML = html;

    // Wire up copy-link buttons
    container.querySelectorAll('[data-join-link]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var link = btn.dataset.joinLink;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(link).then(function () {
            var orig = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(function () { btn.textContent = orig; }, 1800);
          }).catch(function () {
            fallbackCopy(link, btn);
          });
        } else {
          fallbackCopy(link, btn);
        }
      });
    });

    // Wire up add-group form buttons
    var submitBtn = document.getElementById('btn-add-group-submit');
    var cancelBtn = document.getElementById('btn-add-group-cancel');
    if (submitBtn) submitBtn.addEventListener('click', onAddGroup);
    if (cancelBtn) cancelBtn.addEventListener('click', function () {
      document.getElementById('add-group-form').style.display = 'none';
      var addGroupBtn = document.getElementById('btn-show-add-group');
      if (addGroupBtn) addGroupBtn.style.display = '';
    });
  }

  function onAddGroup() {
    var nameInput = document.getElementById('add-group-name');
    var errorEl = document.getElementById('add-group-error');
    var submitBtn = document.getElementById('btn-add-group-submit');
    var name = nameInput ? nameInput.value.trim() : '';

    if (errorEl) { errorEl.textContent = ''; errorEl.style.display = 'none'; }

    if (!name) {
      if (errorEl) { errorEl.textContent = 'Group name is required.'; errorEl.style.display = ''; }
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="t-spinner" aria-hidden="true"></span> Creating…';
    }

    postJson(courseUrl('groups/'), { name: name })
      .then(function (result) {
        if (result.status === 200 || result.status === 201) {
          DATA.groups = result.data.groups || DATA.groups;
          renderRoster();
          var addGroupBtn = document.getElementById('btn-show-add-group');
          if (addGroupBtn) addGroupBtn.style.display = '';
        } else {
          var msg = (result.data && result.data.error) ?
            result.data.error :
            'Failed to create group (' + result.status + '). Please try again.';
          if (errorEl) { errorEl.textContent = msg; errorEl.style.display = ''; }
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Create'; }
        }
      })
      .catch(function (err) {
        if (errorEl) { errorEl.textContent = 'Network error: ' + (err.message || 'request failed'); errorEl.style.display = ''; }
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Create'; }
      });
  }

  function fallbackCopy(text, btn) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      var orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(function () { btn.textContent = orig; }, 1800);
    } catch (e) {
      // silent failure — browser may block
    }
    document.body.removeChild(ta);
  }

  /* ── Activity panel ─────────────────────────────────────────────────── */

  function renderActivity() {
    var container = document.getElementById('activity-content');
    if (!container) return;

    var activity = DATA.activity;
    if (!activity || typeof activity !== 'object') {
      container.innerHTML = '<p style="font-size:0.875rem;color:var(--text-muted);font-family:var(--font-body);">No activity data available.</p>';
      return;
    }

    // Collect all student names and playlist ids from activity dict
    var studentNames = Object.keys(activity);
    if (studentNames.length === 0) {
      container.innerHTML = '<p style="font-size:0.875rem;color:var(--text-muted);font-family:var(--font-body);">No activity recorded yet.</p>';
      return;
    }

    // Collect all playlist ids across all students
    var playlistIdSet = {};
    studentNames.forEach(function (name) {
      var studentData = activity[name];
      if (studentData && typeof studentData === 'object') {
        Object.keys(studentData).forEach(function (pid) {
          playlistIdSet[pid] = true;
        });
      }
    });
    var playlistIds = Object.keys(playlistIdSet).sort();

    if (playlistIds.length === 0) {
      container.innerHTML = '<p style="font-size:0.875rem;color:var(--text-muted);font-family:var(--font-body);">No activity recorded yet.</p>';
      return;
    }

    // Build playlist id → name lookup from pcoRows
    var pidToName = {};
    (DATA.pcoRows || []).forEach(function (r) {
      if (r.playlistId != null) pidToName[String(r.playlistId)] = r.playlistName;
    });

    var table = document.createElement('table');
    table.className = 't-activity-table';
    table.setAttribute('aria-label', 'Student activity summary');

    // Header row
    var thead = document.createElement('thead');
    var headerRow = document.createElement('tr');
    var thStudent = document.createElement('th');
    thStudent.scope = 'col';
    thStudent.textContent = 'Student';
    headerRow.appendChild(thStudent);

    playlistIds.forEach(function (pid) {
      var th = document.createElement('th');
      th.scope = 'col';
      th.className = 't-activity-playlist-header';
      th.title = pidToName[pid] || ('Playlist ' + pid);
      // Truncate long names
      var label = pidToName[pid] || ('PL ' + pid);
      th.textContent = label.length > 14 ? label.slice(0, 13) + '…' : label;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body rows
    var tbody = document.createElement('tbody');
    studentNames.sort().forEach(function (name) {
      var tr = document.createElement('tr');
      var tdName = document.createElement('td');
      tdName.className = 't-activity-student';
      tdName.textContent = name;
      tr.appendChild(tdName);

      var studentData = activity[name];
      playlistIds.forEach(function (pid) {
        var td = document.createElement('td');
        td.className = 't-activity-cell';
        var cellData = null;
        try {
          cellData = (studentData && typeof studentData === 'object') ? studentData[pid] : null;
        } catch (e) {
          cellData = null;
        }
        td.textContent = summarizeActivityCell(cellData);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.innerHTML = '';
    container.appendChild(table);
  }

  /** Given a single cell value from activity_json (shape loose), return display string. */
  function summarizeActivityCell(cell) {
    if (cell == null) return '—';
    if (typeof cell === 'number') return String(cell);
    if (typeof cell === 'boolean') return cell ? '✓' : '—';
    if (typeof cell === 'string') return cell || '—';
    if (typeof cell === 'object') {
      // Try common shapes: { score, attempts, completed, percent, count }
      if (cell.score != null)     return String(cell.score);
      if (cell.percent != null)   return cell.percent + '%';
      if (cell.completed != null) return cell.completed ? '✓' : '—';
      if (cell.attempts != null)  return String(cell.attempts);
      if (cell.count != null)     return String(cell.count);
      // Fallback: count of keys
      var keys = Object.keys(cell);
      return keys.length > 0 ? String(keys.length) : '—';
    }
    return '—';
  }

  /* ── Init ───────────────────────────────────────────────────────────── */

  function init() {
    // Timeline
    renderTimeline();

    var saveBtn = document.getElementById('btn-save-changes');
    if (saveBtn) saveBtn.addEventListener('click', onSaveChanges);

    var respreadBtn = document.getElementById('btn-respread');
    if (respreadBtn) respreadBtn.addEventListener('click', onRespread);

    // Add playlist
    renderAddPlaylistSelect();
    var addBtn = document.getElementById('btn-add-playlist');
    if (addBtn) addBtn.addEventListener('click', onAddPlaylist);

    // Panels
    renderRoster();
    renderActivity();

    // Show add-group form when button clicked
    var showAddGroupBtn = document.getElementById('btn-show-add-group');
    if (showAddGroupBtn) {
      showAddGroupBtn.addEventListener('click', function () {
        showAddGroupBtn.style.display = 'none';
        var form = document.getElementById('add-group-form');
        if (form) {
          form.style.display = '';
          var inp = document.getElementById('add-group-name');
          if (inp) inp.focus();
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
