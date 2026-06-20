/* apps/teacher/static/teacher/modules/roster.js */
'use strict';

import { escHtml, courseUrl, postJson, copyToClipboard } from './utils.js';

let DATA = {};

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

  // Wire up copy-link buttons using shared copyToClipboard
  container.querySelectorAll('[data-join-link]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var link = btn.dataset.joinLink;
      copyToClipboard(link, btn);
    });
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

  postJson(courseUrl(DATA.courseId, 'groups/'), { name: name })
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

export function initRoster(courseData) {
  DATA = courseData;
  renderRoster();

  // Delegated listener for add-group form buttons
  var rosterContainer = document.getElementById('roster-content');
  if (rosterContainer) {
    rosterContainer.addEventListener('click', function (e) {
      if (e.target.id === 'btn-add-group-submit') {
        onAddGroup();
      } else if (e.target.id === 'btn-add-group-cancel') {
        document.getElementById('add-group-form').style.display = 'none';
        var addGroupBtn = document.getElementById('btn-show-add-group');
        if (addGroupBtn) addGroupBtn.style.display = '';
      }
    });
  }

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
