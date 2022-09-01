/* global define:false */
define(["lodash", "jquery", "microevent", "app/config", "app/util"], function (
  _,
  $,
  MicroEvent,
  Config,
  util
) {
  "use strict";

  var HIGHLIGHT_COLORS = Config.get("highlight.colors");
  var HIGHLIGHT_SETTINGS = Config.get("general.highlightSettings");

  var HighlightWidget = function (settings, is_exercise_view = false) {
    this.is_exercise_view = is_exercise_view || false;
    settings = settings || {};
    this.el = $('<div class="menu-widgets"></div>');
    this.state = _.merge(_.cloneDeep(HIGHLIGHT_SETTINGS), settings);
    this.init();
  };

  _.extend(HighlightWidget.prototype, {
    templateHTML: [
      '<fieldset class="settings-notation">',
      '<legend><label><input type="checkbox" name="highlight_enabled" value="1" accesskey="c"> COLORS</label></legend>',
      "<ul>",
      "<li>",
      "<label>",
      '<input type="checkbox" name="highlight_roots" value="roothighlight" accesskey="r"> Roots',
      '<div class="highlight-swatch" style="background-color: ' +
        util.toHSLString(HIGHLIGHT_COLORS.root) +
        '"></div>',
      "</label>",
      "</li>",
      "<li>",
      "<label>",
      '<input type="checkbox" name="highlight_tritones" value="tritonehighlight" accesskey="t"> Tritones',
      '<div class="highlight-swatch" style="background-color: ' +
        util.toHSLString(HIGHLIGHT_COLORS.tritone) +
        '"></div>',
      "</label>",
      "</li>",
      "<li>",
      "<label>",
      '<input type="checkbox" name="highlight_doublings" value="doublinghighlight" accesskey="w"> Doubling warnings (W)',
      '<div class="highlight-swatch" style="background-color: ' +
        util.toHSLString(HIGHLIGHT_COLORS.double) +
        '"></div>',
      "</label>",
      "</li>",
      "<li>",
      "<label>",
      '<input type="checkbox" name="highlight_modalmixture" value="modalmixturehighlight" accesskey="x"> Mixed from parallel minor (X)',
      '<div class="highlight-swatch" style="background-color: ' +
        util.toHSLString(HIGHLIGHT_COLORS.modalmixture) +
        '"></div>',
      "</label>",
      "</li>",
      "<li>",
      "<label>",
      '<input type="checkbox" name="highlight_lowered" value="loweredhighlight" accesskey="y"> Lowered pitches (Y)',
      '<div class="highlight-swatch" style="background-color: ' +
        util.toHSLString(HIGHLIGHT_COLORS.lowered) +
        '"></div>',
      "</label>",
      "</li>",
      "<li>",
      "<label>",
      '<input type="checkbox" name="highlight_solobass" value="solobass" accesskey="z"> Bass solo (Z) / hide upper parts',
      '<div class="highlight-swatch" style="background-color: ' +
        util.toHSLString(HIGHLIGHT_COLORS.solobass) +
        '"></div>',
      "</label>",
      "</li>",
      "</ul>",
      "</fieldset>",
    ].join(""),
    init: function () {
      this.initListeners();
    },
    initListeners: function () {
      var that = this;
      this.el.on("change", "input", null, function (e) {
        var target_name = e.target.name;
        if (target_name in that.handlers) {
          that.handlers[target_name].call(that, e);
        }
        e.stopPropagation();
      });
      return this;
    },
    handlers: {
      highlight_enabled: function (e) {
        this.state.enabled = e.target.checked;
        this.trigger("changeCategory", "highlight", this.state.enabled);
        this.el
          .find("input")
          .not("input[name=highlight_enabled]")
          .attr("disabled", !this.state.enabled);
      },
      highlight_roots: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "highlight", opt, this.state.mode[opt]);
      },
      highlight_tritones: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "highlight", opt, this.state.mode[opt]);
      },
      highlight_modalmixture: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "highlight", opt, this.state.mode[opt]);
      },
      highlight_lowered: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "highlight", opt, this.state.mode[opt]);
      },
      highlight_doublings: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "highlight", opt, this.state.mode[opt]);
      },
      highlight_solobass: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "highlight", opt, this.state.mode[opt]);
      },
    },
    render: function () {
      var that = this;

      // update the element content
      if (this.is_exercise_view) {
        this.el.html(
          this.templateHTML.replace(
            /type="checkbox"/gi,
            'type="checkbox" onclick="return false;"'
          )
        );
      } else {
        this.el.html(this.templateHTML);
      }

      // update the input states
      this.el.find("input[name=highlight_enabled]")[0].checked =
        this.state.enabled;
      $.each(this.state.mode, function (key, val) {
        var $input = that.el.find("input[value=" + key + "]");
        $input.attr("checked", val ? true : false);
        $input.attr("disabled", !that.state.enabled);
      });

      return this;
    },
    getState: function () {
      return this.state;
    },
  });

  MicroEvent.mixin(HighlightWidget);

  return HighlightWidget;
});
