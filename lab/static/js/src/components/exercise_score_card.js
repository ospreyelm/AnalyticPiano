/**
 * ExerciseScoreCard — slide-up overlay shown at exercise completion.
 *
 * Usage:
 *   var card = new ExerciseScoreCard();
 *   card.init(document.getElementById('staff-area'));
 *   card.show({ score_numerator, score_denominator, mastery_changes,
 *               skill_name, exercise_num, total_exercises, unit_name,
 *               unit_bar_segments, next_exercise_url, next_skill_name, unit_n });
 *   card.hide();
 */
define(["jquery"], function ($) {
  "use strict";

  // ---- Pure logic helpers ----

  function _scorePct(numerator, denominator) {
    if (!denominator || denominator === 0) return null;
    return Math.round((numerator / denominator) * 100);
  }

  function _tierLabel(pct) {
    if (pct === null) return "—";
    if (pct === 100) return "Mastered";
    if (pct >= 80) return "Proficient";
    if (pct >= 60) return "Familiar";
    if (pct >= 40) return "Attempted";
    return "Needs Practice";
  }

  function _masteryColor(pct) {
    if (pct === null) return "gray";
    if (pct === 100) return "green";
    if (pct >= 60) return "blue";
    return "amber";
  }

  function _segmentColor(level) {
    var map = { mastered: "green", proficient: "blue", familiar: "amber", not_started: "lightgray" };
    return map[level] || "lightgray";
  }

  function _primaryCta(pct, masteryChanges, nextSkillName) {
    if (pct !== null && pct < 60) return "Try Again";
    var keys = masteryChanges ? Object.keys(masteryChanges) : [];
    for (var i = 0; i < keys.length; i++) {
      if (masteryChanges[keys[i]].new === "mastered" && nextSkillName) {
        return "Start " + nextSkillName + " →";
      }
    }
    return "Next Exercise →";
  }

  function _bannerState(masteryChanges) {
    if (!masteryChanges || Object.keys(masteryChanges).length === 0) return null;
    var keys = Object.keys(masteryChanges);
    for (var i = 0; i < keys.length; i++) {
      if (masteryChanges[keys[i]].new === "mastered") {
        return { type: "mastered", skill: keys[i], old: masteryChanges[keys[i]].old, new: "mastered" };
      }
    }
    return { type: "level_up", skill: keys[0], old: masteryChanges[keys[0]].old, new: masteryChanges[keys[0]].new };
  }

  // ---- SVG arc helper ----
  // Draws a circular progress arc using stroke-dashoffset.
  // Returns an SVG string for a ring of radius r, pct 0-100.
  function _arcSvg(pct, color) {
    var r = 28, cx = 36, cy = 36, strokeW = 6;
    var circumference = 2 * Math.PI * r;
    var offset = pct === null ? circumference : circumference - (pct / 100) * circumference;
    return (
      '<svg width="72" height="72" class="esc-arc" aria-hidden="true">' +
        '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '"' +
          ' fill="none" stroke="#e5e7eb" stroke-width="' + strokeW + '"/>' +
        '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '"' +
          ' fill="none" stroke="var(--esc-arc-' + color + ')" stroke-width="' + strokeW + '"' +
          ' stroke-linecap="round"' +
          ' stroke-dasharray="' + circumference + '"' +
          ' stroke-dashoffset="' + offset + '"' +
          ' transform="rotate(-90 ' + cx + ' ' + cy + ')"/>' +
        '<text x="' + cx + '" y="' + (cy + 5) + '" text-anchor="middle"' +
          ' class="esc-arc-label" fill="var(--esc-arc-' + color + ')">' +
          (pct === null ? "—" : pct + "%") +
        '</text>' +
      '</svg>'
    );
  }

  // ---- CSS injected once ----
  var _cssInjected = false;
  function _injectCss() {
    if (_cssInjected) return;
    _cssInjected = true;
    var css = [
      ":root {",
      "  --esc-arc-blue: #3b82f6;",
      "  --esc-arc-green: #22c55e;",
      "  --esc-arc-amber: #f59e0b;",
      "  --esc-arc-gray: #9ca3af;",
      "}",
      ".esc-overlay {",
      "  position: fixed; bottom: 0; left: 0; right: 0; z-index: 9000;",
      "  transform: translateY(100%); transition: transform 0.3s ease;",
      "  background: #fff; border-top: 1px solid #e5e7eb;",
      "  box-shadow: 0 -4px 16px rgba(0,0,0,0.10);",
      "  padding: 20px 24px 24px; font-family: inherit;",
      "  max-width: 600px; margin: 0 auto;",
      "}",
      ".esc-overlay.esc-visible { transform: translateY(0); }",
      ".esc-label-top {",
      "  font-size: 11px; font-weight: 700; letter-spacing: 0.1em;",
      "  color: #9ca3af; text-transform: uppercase; margin-bottom: 12px;",
      "}",
      ".esc-banner {",
      "  padding: 8px 12px; border-radius: 4px; margin-bottom: 12px;",
      "  font-size: 14px; font-weight: 600;",
      "}",
      ".esc-banner-blue { background: #dbeafe; color: #1d4ed8; }",
      ".esc-banner-gold { background: #fef3c7; color: #92400e; }",
      ".esc-score-row {",
      "  display: flex; align-items: center; gap: 16px; margin-bottom: 14px;",
      "}",
      ".esc-arc { flex-shrink: 0; }",
      ".esc-arc-label { font-size: 13px; font-weight: 700; }",
      ".esc-score-detail { flex: 1; }",
      ".esc-fraction {",
      "  font-size: 16px; font-weight: 600; color: #111827; margin-bottom: 2px;",
      "}",
      ".esc-meta { font-size: 12px; color: #6b7280; }",
      ".esc-badge {",
      "  display: inline-block; padding: 2px 8px; border-radius: 3px;",
      "  font-size: 11px; font-weight: 700; letter-spacing: 0.05em;",
      "  text-transform: uppercase; margin-top: 4px;",
      "}",
      ".esc-badge-blue { background: #dbeafe; color: #1d4ed8; }",
      ".esc-badge-green { background: #dcfce7; color: #15803d; }",
      ".esc-badge-amber { background: #fef3c7; color: #92400e; }",
      ".esc-badge-gray { background: #f3f4f6; color: #6b7280; }",
      ".esc-unit-bar-section {",
      "  border-top: 1px solid #e5e7eb; padding-top: 12px; margin-bottom: 14px;",
      "}",
      ".esc-unit-label {",
      "  font-size: 11px; font-weight: 700; letter-spacing: 0.08em;",
      "  color: #6b7280; text-transform: uppercase; margin-bottom: 6px;",
      "}",
      ".esc-bar {",
      "  display: flex; gap: 3px; height: 10px; border-radius: 5px; overflow: hidden;",
      "  margin-bottom: 4px;",
      "}",
      ".esc-bar-seg { flex: 1; border-radius: 2px; }",
      ".esc-bar-seg-green { background: #22c55e; }",
      ".esc-bar-seg-blue { background: #3b82f6; }",
      ".esc-bar-seg-amber { background: #f59e0b; }",
      ".esc-bar-seg-lightgray { background: #e5e7eb; }",
      ".esc-bar-summary { font-size: 11px; color: #9ca3af; }",
      ".esc-actions {",
      "  display: flex; gap: 10px; justify-content: flex-end; margin-top: 4px;",
      "}",
      ".esc-btn {",
      "  padding: 8px 18px; border-radius: 5px; font-size: 14px; font-weight: 600;",
      "  border: none; cursor: pointer; transition: background 0.15s;",
      "}",
      ".esc-btn-secondary {",
      "  background: #f3f4f6; color: #374151;",
      "}",
      ".esc-btn-secondary:hover { background: #e5e7eb; }",
      ".esc-btn-primary-blue { background: #3b82f6; color: #fff; }",
      ".esc-btn-primary-blue:hover { background: #2563eb; }",
      ".esc-btn-primary-green { background: #22c55e; color: #fff; }",
      ".esc-btn-primary-green:hover { background: #16a34a; }",
      ".esc-btn-primary-amber { background: #f59e0b; color: #fff; }",
      ".esc-btn-primary-amber:hover { background: #d97706; }",
    ].join("\n");
    var style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ---- Component ----

  var ExerciseScoreCard = function () {
    this._el = null;
    this._data = null;
  };

  /**
   * Inject card HTML into containerEl (once). Must be called before show().
   *
   * @param {HTMLElement} containerEl
   */
  ExerciseScoreCard.prototype.init = function (containerEl) {
    _injectCss();
    var wrapper = document.createElement("div");
    wrapper.innerHTML = '<div class="esc-overlay" id="esc-overlay" aria-live="polite" aria-label="Exercise result"></div>';
    document.body.appendChild(wrapper.firstChild);
    this._el = document.getElementById("esc-overlay");
  };

  /**
   * Show the score card with given data.
   *
   * @param {object} data  Keys: score_numerator, score_denominator, mastery_changes,
   *   skill_name, exercise_num, total_exercises, unit_name, unit_bar_segments,
   *   next_exercise_url, next_skill_name, unit_n
   */
  ExerciseScoreCard.prototype.show = function (data) {
    if (!this._el) return;

    // Suppress in test mode
    var identMode = (window.HarmonyLab && window.HarmonyLab.identMode) ||
                    (window.__exerciseIdentMode);  // set by exercise_context.js
    if (identMode === "test") return;

    this._data = data;
    var pct = _scorePct(data.score_numerator, data.score_denominator);
    var color = _masteryColor(pct);
    var label = _tierLabel(pct);
    var banner = _bannerState(data.mastery_changes || {});
    var cta = _primaryCta(pct, data.mastery_changes || {}, data.next_skill_name || null);
    var isMastered = banner && banner.type === "mastered";
    var isLow = pct !== null && pct < 60;

    // Banner HTML
    var bannerHtml = "";
    if (banner && banner.type === "mastered") {
      bannerHtml = '<div class="esc-banner esc-banner-gold">You\'ve mastered ' + _esc(banner.skill.replace(/_/g, " ")) + '</div>';
    } else if (banner && banner.type === "level_up") {
      var oldLabel = _capitalize(banner.old);
      var newLabel = _capitalize(banner.new);
      bannerHtml = '<div class="esc-banner esc-banner-blue">Level up! ' + oldLabel + ' → ' + newLabel + ' in ' + _esc(banner.skill.replace(/_/g, " ")) + '</div>';
    }

    // Badge
    var badgeClass = "esc-badge-" + (isMastered ? "green" : isLow ? "amber" : "blue");
    var badgeText = isMastered ? "MASTERED" : isLow ? "Needs Practice" : label.toUpperCase();

    // Arc
    var arcHtml = _arcSvg(pct, color);

    // Fraction label
    var fractionHtml;
    if (pct === null) {
      fractionHtml = '<div class="esc-fraction">—</div>';
    } else {
      fractionHtml = '<div class="esc-fraction">' + data.score_numerator + ' of ' + data.score_denominator + ' correct</div>';
    }

    // Meta line
    var metaParts = [];
    if (data.skill_name) metaParts.push("Skill: " + _esc(data.skill_name));
    if (data.exercise_num && data.total_exercises) metaParts.push("Ex " + data.exercise_num + "/" + data.total_exercises);
    var metaHtml = metaParts.length ? '<div class="esc-meta">' + metaParts.join(" · ") + '</div>' : "";

    // Unit bar
    var barHtml = "";
    if (data.unit_bar_segments && data.unit_bar_segments.length > 0) {
      var segs = data.unit_bar_segments;
      var segsHtml = segs.map(function (s) {
        var sc = _segmentColor(s.level);
        return '<div class="esc-bar-seg esc-bar-seg-' + sc + '" title="' + _esc(s.label || s.tag) + ': ' + _esc(s.level) + '"></div>';
      }).join("");
      var masteredCount = segs.filter(function (s) { return s.level === "mastered"; }).length;
      var profCount = segs.filter(function (s) { return s.level === "proficient" || s.level === "mastered"; }).length;
      var unitLabel = (data.unit_name ? "UNIT " + (data.unit_n || "") + " · " + data.unit_name.toUpperCase() : "UNIT PROGRESS");
      barHtml = [
        '<div class="esc-unit-bar-section">',
        '  <div class="esc-unit-label">' + _esc(unitLabel) + '</div>',
        '  <div class="esc-bar">' + segsHtml + '</div>',
        '  <div class="esc-bar-summary">' + profCount + ' of ' + segs.length + ' skills proficient or above</div>',
        '</div>',
      ].join("");
    }

    // Buttons
    var ctaClass = isMastered ? "esc-btn-primary-green" : isLow ? "esc-btn-primary-amber" : "esc-btn-primary-blue";
    var nextUrl = data.next_exercise_url || null;
    var tryAgainBtn = '<button class="esc-btn esc-btn-secondary js-esc-try-again">Try Again</button>';
    var ctaBtn;
    if (nextUrl) {
      ctaBtn = '<a href="' + _esc(nextUrl) + '"><button class="esc-btn ' + ctaClass + ' js-esc-cta">' + _esc(cta) + '</button></a>';
    } else {
      ctaBtn = '<button class="esc-btn ' + ctaClass + ' js-esc-cta">' + _esc(cta) + '</button>';
    }
    // Always show Try Again; only show Next/CTA when a next URL is present or CTA is Try Again
    var actionsHtml;
    if (isLow) {
      actionsHtml = '<div class="esc-actions">' + ctaBtn + '</div>';
    } else {
      actionsHtml = '<div class="esc-actions">' + tryAgainBtn + ctaBtn + '</div>';
    }

    this._el.innerHTML = [
      '<div class="esc-label-top">Exercise Complete</div>',
      bannerHtml,
      '<div class="esc-score-row">',
      '  ' + arcHtml,
      '  <div class="esc-score-detail">',
      '    ' + fractionHtml,
      '    ' + metaHtml,
      '    <span class="esc-badge ' + badgeClass + '">' + badgeText + '</span>',
      '  </div>',
      '</div>',
      barHtml,
      actionsHtml,
    ].join("");

    // Wire buttons
    var self = this;
    var tryAgainEl = this._el.querySelector(".js-esc-try-again");
    if (tryAgainEl) {
      tryAgainEl.addEventListener("click", function () {
        self.hide();
        // Reload current exercise
        if (window.location) window.location.reload();
      });
    }
    // CTA button without href (no next URL, non-low score): hide card and let auto-advance handle it
    var ctaEl = this._el.querySelector(".js-esc-cta");
    if (ctaEl && !nextUrl && !isLow) {
      ctaEl.addEventListener("click", function () {
        self.hide();
      });
    }

    // Slide up
    this._el.classList.add("esc-visible");
  };

  /**
   * Slide card down and clear content.
   */
  ExerciseScoreCard.prototype.hide = function () {
    if (!this._el) return;
    this._el.classList.remove("esc-visible");
    var el = this._el;
    setTimeout(function () { el.innerHTML = ""; }, 350);
  };

  // ---- Helpers ----

  function _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function _capitalize(str) {
    if (!str) return "";
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  return ExerciseScoreCard;
});
