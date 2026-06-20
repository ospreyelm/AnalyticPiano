/* apps/teacher/static/teacher/modules/activity.js */
'use strict';

import { escHtml } from './utils.js';

let DATA = {};

function summarizeActivityCell(cell) {
  if (cell == null) return '—';
  if (typeof cell === 'number') return String(cell);
  if (typeof cell === 'boolean') return cell ? '✓' : '—';
  if (typeof cell === 'string') return cell || '—';
  if (typeof cell === 'object') {
    if (cell.score != null)     return String(cell.score);
    if (cell.percent != null)   return cell.percent + '%';
    if (cell.completed != null) return cell.completed ? '✓' : '—';
    if (cell.attempts != null)  return String(cell.attempts);
    if (cell.count != null)     return String(cell.count);
    var keys = Object.keys(cell);
    return keys.length > 0 ? String(keys.length) : '—';
  }
  return '—';
}

function renderActivity() {
  var container = document.getElementById('activity-content');
  if (!container) return;

  var activity = DATA.activity;
  if (!activity || typeof activity !== 'object') {
    container.innerHTML = '<p style="font-size:0.875rem;color:var(--text-muted);font-family:var(--font-body);">No activity data available.</p>';
    return;
  }

  var studentNames = Object.keys(activity);
  if (studentNames.length === 0) {
    container.innerHTML = '<p style="font-size:0.875rem;color:var(--text-muted);font-family:var(--font-body);">No activity recorded yet.</p>';
    return;
  }

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

  var pidToName = {};
  (DATA.pcoRows || []).forEach(function (r) {
    if (r.playlistId != null) pidToName[String(r.playlistId)] = r.playlistName;
  });

  var table = document.createElement('table');
  table.className = 't-activity-table';
  table.setAttribute('aria-label', 'Student activity summary');

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
    var label = pidToName[pid] || ('PL ' + pid);
    th.textContent = label.length > 14 ? label.slice(0, 13) + '…' : label;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

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

export function initActivity(courseData) {
  DATA = courseData;
  renderActivity();
}
