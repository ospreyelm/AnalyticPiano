/* apps/teacher/static/teacher/course_detail.js
   Modern ES Modules entry point. */
'use strict';

import { initTimeline } from './modules/timeline.js';
import { initRoster } from './modules/roster.js';
import { initActivity } from './modules/activity.js';

const DATA = window.__COURSE_DATA__ || {
  courseId: 0,
  pcoRows: [],
  groups: [],
  activity: {},
  addablePlaylists: [],
  dashboardEditUrl: '',
  dashboardActivityUrl: '',
};

/* ── Init ───────────────────────────────────────────────────────────── */

function init() {
  initTimeline(DATA);
  initRoster(DATA);
  initActivity(DATA);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
