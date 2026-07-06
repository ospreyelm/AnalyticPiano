import $ from "jquery";
import confetti from "canvas-confetti";
import scoreCardTheme from "./exercise_score_card_theme_logic";
import ScoreCardLogic from "./exercise_score_card_logic.js";

// ---- Pure logic helpers mapped from exercise_score_card_logic.js ----
var _scorePct = ScoreCardLogic._scorePct;
var _hadCorrections = ScoreCardLogic._hadCorrections;
var _tierLabel = ScoreCardLogic._tierLabel;
var _masteryColor = ScoreCardLogic._masteryColor;
var _segmentColor = ScoreCardLogic._segmentColor;
var _primaryCta = ScoreCardLogic._primaryCta;
var _bannerState = ScoreCardLogic._bannerState;

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

  function _launchConfetti() {
    if (typeof confetti !== "function") return;

    var defaults = {
      disableForReducedMotion: true,
      zIndex: 10060,
      ticks: 300,
      gravity: 0.9,
      decay: 0.94,
      startVelocity: 32,
      scalar: 1.05,
      colors: ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]
    };

    function fire(particleRatio, opts) {
      confetti($.extend({}, defaults, opts, {
        particleCount: Math.floor(180 * particleRatio)
      }));
    }

    fire(0.22, { spread: 72, origin: { x: 0.5, y: 0.58 } });
    fire(0.18, { spread: 98, startVelocity: 42, scalar: 0.95, origin: { x: 0.32, y: 0.62 } });
    fire(0.18, { spread: 98, startVelocity: 42, scalar: 0.95, origin: { x: 0.68, y: 0.62 } });
    fire(0.14, { spread: 120, decay: 0.92, scalar: 1.2, origin: { x: 0.5, y: 0.5 } });
    fire(0.14, { angle: 60, spread: 58, origin: { x: 0, y: 0.72 } });
    fire(0.14, { angle: 120, spread: 58, origin: { x: 1, y: 0.72 } });
  }

  // ---- CSS injected once ----
  var _cssInjected = false;
  function _injectCss() {
    if (_cssInjected) return;
    _cssInjected = true;
    var css = [
      ":root {",
      "  --esc-arc-blue: " + scoreCardTheme.arc.blue + ";",
      "  --esc-arc-green: " + scoreCardTheme.arc.green + ";",
      "  --esc-arc-amber: " + scoreCardTheme.arc.amber + ";",
      "  --esc-arc-gray: " + scoreCardTheme.arc.gray + ";",
      "}",
      ".esc-overlay {",
      "  position: fixed; bottom: 0; left: 0; right: 0; z-index: 10050;",
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
      ".esc-banner-blue { background: " + scoreCardTheme.banner.blueBg + "; color: " + scoreCardTheme.banner.blueFg + "; }",
      ".esc-banner-gold { background: " + scoreCardTheme.banner.goldBg + "; color: " + scoreCardTheme.banner.goldFg + "; }",
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
      ".esc-badge-blue { background: " + scoreCardTheme.badge.blueBg + "; color: " + scoreCardTheme.badge.blueFg + "; }",
      ".esc-badge-green { background: " + scoreCardTheme.badge.greenBg + "; color: " + scoreCardTheme.badge.greenFg + "; }",
      ".esc-badge-amber { background: " + scoreCardTheme.badge.amberBg + "; color: " + scoreCardTheme.badge.amberFg + "; }",
      ".esc-badge-gray { background: " + scoreCardTheme.badge.grayBg + "; color: " + scoreCardTheme.badge.grayFg + "; }",
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
      ".esc-bar-seg-blue { background: " + scoreCardTheme.arc.blue + "; }",
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
      ".esc-btn-primary-blue { background: " + scoreCardTheme.button.blueBg + "; color: #fff; }",
      ".esc-btn-primary-blue:hover { background: " + scoreCardTheme.button.blueHover + "; }",
      ".esc-btn-primary-green { background: " + scoreCardTheme.button.greenBg + "; color: #fff; }",
      ".esc-btn-primary-green:hover { background: " + scoreCardTheme.button.greenHover + "; }",
      ".esc-btn-primary-amber { background: " + scoreCardTheme.button.amberBg + "; color: #fff; }",
      ".esc-btn-primary-amber:hover { background: " + scoreCardTheme.button.amberHover + "; }",
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

    this._data = data;
    var pct = _scorePct(data.score_numerator, data.score_denominator);
    var hadCorrections = _hadCorrections(data.error_tally);
    var color = _masteryColor(pct, data.error_tally);
    var label = _tierLabel(pct, data.error_tally);
    var banner = _bannerState(data.mastery_changes || {});
    var cta = _primaryCta(pct, data.mastery_changes || {}, data.next_skill_name || null);
    var isMastered = banner && banner.type === "mastered" && !hadCorrections;
    var isLow = pct !== null && pct < 60;

    // Banner HTML
    var bannerHtml = "";
    if (banner && banner.type === "mastered" && !hadCorrections) {
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
    if (hadCorrections) metaParts.push("After fixing " + data.error_tally + " error" + (data.error_tally === 1 ? "" : "s"));
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
    
    var isMasteredCta = (cta.indexOf("Start ") === 0);
    if (isMasteredCta && data.unit_n) {
      nextUrl = "/s/units/" + data.unit_n + "/";
    }

    var tryAgainBtn = '<button class="esc-btn esc-btn-secondary js-esc-try-again">Try Again</button>';
    var ctaBtn;
    if (nextUrl) {
      ctaBtn = '<a class="esc-btn ' + ctaClass + ' js-esc-cta" href="' + _esc(nextUrl) + '">' + _esc(cta) + '</a>';
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
        var resetLink = document.querySelector(".js-btn-pristine");
        if (resetLink) {
          $(resetLink).trigger("click");
        }
      });
    }

    var ctaEl = this._el.querySelector(".js-esc-cta");
    if (ctaEl) {
      ctaEl.addEventListener("click", function (e) {
        if (isLow) {
          e.preventDefault();
          self.hide();
          var resetLink = document.querySelector(".js-btn-pristine");
          if (resetLink) {
            $(resetLink).trigger("click");
          }
        } else if (nextUrl && nextUrl.indexOf("/play/") !== -1) {
          e.preventDefault();
          self.hide();
          var nextLink = document.querySelector(".js-btn-nextexercise");
          if (nextLink) {
            $(nextLink).trigger("click");
          }
        } else {
          self.hide();
        }
      });
    }

    // Slide up
    this._el.classList.add("esc-visible");
    if (pct === 100) {
      _launchConfetti();
    }
  };

  ExerciseScoreCard.prototype.isVisible = function () {
    return !!(this._el && this._el.classList.contains("esc-visible"));
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

export default ExerciseScoreCard;
