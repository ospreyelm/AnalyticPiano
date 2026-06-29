import _ from "lodash";
import $ from "jquery";
import EVENTS from "app/components/events";
import Component from "app/components/component";
import FeedbackCatalog from "app/config/feedback_catalog";

/**
   * FeedbackService — single funnel for student-facing feedback.
   * emit(id, opts): params, surface(override), anchorRect, controlEl, inlineEl, context
   */
  var FeedbackService = function (settings) {
    this.settings = _.extend({}, settings || {});
    this.exerciseContext = this.settings.exerciseContext || null;
    this._untilNextAttempt = [];
    _.bindAll(this, ["_onGraded"]);
  };
  FeedbackService.prototype = new Component();

  FeedbackService.prototype.initComponent = function () {
    this.$bubble = $('<div class="feedback-bubble" role="status" aria-live="polite"></div>').hide();
    $("body").append(this.$bubble);
    if (this.exerciseContext && typeof this.exerciseContext.bind === "function") {
      this.exerciseContext.bind("graded", this._onGraded);
    }
  };

  FeedbackService.prototype.renderTo = function () { /* surfaces self-position */ };

  FeedbackService.prototype.emit = function (id, opts) {
    opts = opts || {};
    var entry = FeedbackCatalog.render(id, opts.params || null);
    if (!entry) { if (window.console && console.warn) console.warn("[feedback] unknown id: " + id); return null; }
    this._logAnalytics(id, opts.context);
    var surface = opts.surface || entry.surface;
    if (surface === "global") this._routeGlobal(entry);
    else if (surface === "inline") this._routeInline(entry, opts);
    else if (surface === "control") this._routeControl(entry, opts);
    else if (surface === "anchored") this._routeAnchored(entry, opts);
    // "none" => analytics only
    return entry;
  };

  FeedbackService.prototype._routeGlobal = function (entry) {
    this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
      type: entry.category === "blocking_error" ? "error"
          : entry.category === "recoverable_mistake" ? "warning" : "info",
      title: entry.title || entry.body,
      description: entry.detail || (entry.title ? entry.body : undefined)
    });
  };

  FeedbackService.prototype._routeInline = function (entry, opts) {
    var $el = opts.inlineEl ? $(opts.inlineEl) : null;
    if (!$el || !$el.length) return;
    var html = "";
    if (entry.title) html += "<strong>" + entry.title + "</strong> ";
    html += "<span>" + entry.body + "</span>";
    $el.html(html).addClass("is-visible");
    this._scheduleFade($el, entry.timeoutMs);
  };

  FeedbackService.prototype._routeControl = function (entry, opts) {
    var $el = opts.controlEl ? $(opts.controlEl) : null;
    if (!$el || !$el.length) return;
    $el.attr("title", (entry.title ? entry.title + " " : "") + entry.body);
    $el.addClass("feedback-control-flash");
    if ($el[0]) void $el[0].offsetWidth;
    window.setTimeout(function () { $el.removeClass("feedback-control-flash"); }, 600);
  };

  FeedbackService.prototype._routeAnchored = function (entry, opts) {
    var rect = opts.anchorRect;
    if (!rect) return;
    this.$bubble
      .text((entry.title ? entry.title + " " : "") + entry.body)
      .removeClass("feedback-bubble--mistake feedback-bubble--success")
      .addClass(entry.category === "recoverable_mistake" ? "feedback-bubble--mistake"
              : entry.category === "success" ? "feedback-bubble--success" : "")
      .css({ position: "absolute", top: rect.top + (rect.height || 0) + 6 + "px", left: rect.left + "px" })
      .stop(true, true).show();
    if (entry.category === "recoverable_mistake") this._untilNextAttempt.push(this.$bubble);
    this._scheduleFade(this.$bubble, entry.timeoutMs);
  };

  FeedbackService.prototype._scheduleFade = function ($el, timeoutMs) {
    if (timeoutMs == null) return;
    window.setTimeout(function () {
      $el.removeClass("is-visible");
      if ($el.is(".feedback-bubble")) $el.fadeOut(200);
    }, timeoutMs);
  };

  FeedbackService.prototype._onGraded = function () {
    for (var i = 0; i < this._untilNextAttempt.length; i++) {
      var $el = this._untilNextAttempt[i];
      $el.removeClass("is-visible");
      if ($el.is(".feedback-bubble")) $el.hide();
    }
    this._untilNextAttempt = [];
  };

  FeedbackService.prototype._logAnalytics = function (id, context) {
    var ev = FeedbackCatalog.buildEvent(id, context || this._contextFromExercise(), Date.now());
    this.broadcast(EVENTS.BROADCAST.FEEDBACK, ev);
    if (window.console && console.debug) console.debug("[feedback]", ev.feedbackId, ev.category);
  };

  FeedbackService.prototype._contextFromExercise = function () {
    var ctx = { exerciseId: null, unit: null, complexity: null, skillTags: [] };
    var ec = this.exerciseContext;
    // NOTE: ExerciseDefinition stores the parsed exercise as a PROPERTY (this.exercise),
    // not a method. Access it directly — do NOT call it.
    if (!ec || !ec.definition || !ec.definition.exercise) return ctx;
    var ex = ec.definition.exercise;
    if (!ex) return ctx;
    ctx.exerciseId = ex.exerciseId || ex.id || ex.exercise_id || null;
    ctx.complexity = typeof ex.complexity_score === "number" ? ex.complexity_score : null;
    ctx.skillTags = ex.skill_tags || [];
    for (var i = 0; i < ctx.skillTags.length; i++) {
      var m = /^unit:(\d+)$/.exec(ctx.skillTags[i]);
      if (m) { ctx.unit = parseInt(m[1], 10); break; }
    }
    return ctx;
  };

export default FeedbackService;
