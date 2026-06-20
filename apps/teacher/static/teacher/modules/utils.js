/* apps/teacher/static/teacher/modules/utils.js */
'use strict';

export function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function getCsrfToken() {
  var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  if (match) return decodeURIComponent(match[1]);
  var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return inp ? inp.value : '';
}

export function courseUrl(courseId, suffix) {
  return '/teacher/courses/' + courseId + '/' + suffix;
}

export function postJson(url, payload) {
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

export function showError(bannerId, msg) {
  var el = document.getElementById(bannerId);
  if (!el) return;
  el.textContent = msg;
  el.classList.add('is-visible');
}

export function hideError(bannerId) {
  var el = document.getElementById(bannerId);
  if (!el) return;
  el.textContent = '';
  el.classList.remove('is-visible');
}

export function modeLabel(mode) {
  var MAP = {
    roman:        'Roman',
    figures:      'Figures',
    play:         'Play',
    play_figures: 'Play+Fig',
    identify:     'Identify',
  };
  return MAP[mode] || (mode || '—');
}

export function unitFromTags(skillTags) {
  for (var i = 0; i < skillTags.length; i++) {
    var m = /^unit:(\d+)$/.exec(skillTags[i]);
    if (m) return m[1];
  }
  return null;
}

export function studentUnitUrl(unitN) {
  return window.location.origin + '/s/units/' + unitN + '/play/';
}

export function fallbackCopy(text, btn) {
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

export function copyToClipboard(text, btn) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () {
      var orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(function () { btn.textContent = orig; }, 1800);
    }).catch(function () { fallbackCopy(text, btn); });
  } else {
    fallbackCopy(text, btn);
  }
}
