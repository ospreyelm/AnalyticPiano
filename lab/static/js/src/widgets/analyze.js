/* global define:false */
define(["lodash", "jquery", "microevent", "app/config"], function (
  _,
  $,
  MicroEvent,
  Config
) {
  "use strict";

  var ANALYSIS_SETTINGS = Config.get("general.analysisSettings");

  var AnalyzeWidget = function (settings, is_exercise_view = false) {
    this.is_exercise_view = is_exercise_view || false;
    settings = settings || {};
    this.el = $('<div class="menu-widgets"></div>');
    this.state = _.merge(_.cloneDeep(ANALYSIS_SETTINGS), settings);
    this.init();
  };

  _.extend(AnalyzeWidget.prototype, {
    templateHTML: [
      '<fieldset class="settings-notation">',
      '<legend><label><input type="checkbox" name="analysis_enabled" value="1" accesskey="a"> ANALYZE</label></legend>',
      '<ul style="display:inline-block;vertical-align:top">',
      "<li>",
      '<label><input type="checkbox" name="analysis_note_names" value="note_names" accesskey="l"> Letters</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_scientific_pitch" value="scientific_pitch" accesskey="s"> Scientific pitch</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_fixed_do" value="fixed_do" accesskey="f"> Fixed-do</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_pitch_class" value="pitch_class" accesskey="p"> Pitch class</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_scale_degrees" value="scale_degrees" accesskey="d"> Degrees</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_solfege" value="solfege"  accesskey="m"> Movable-do with LA- minor</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_do_based_solfege" value="do_based_solfege"  accesskey="m"> Movable-do with DO-minor</label>',
      "</li>",
      "</ul>",
      '<ul style="display:inline-block;vertical-align:top">',
      "<li>",
      '<label><input type="checkbox" name="analysis_intervals" value="intervals" accesskey="i"> Intervals</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_intervals_wrap_after_octave" value="intervals_wrap_after_octave"> Intervals (wrap after octave)</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_intervals_wrap_after_octave_plus_ditone" value="intervals_wrap_after_octave_plus_ditone"> Intervals (wrap after octave plus ditone)</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_generic_intervals" value="generic_intervals"> Generic intervals</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_generic_intervals_wrap_after_octave" value="generic_intervals_wrap_after_octave"> Generic intervals (wrap after octave)</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_generic_intervals_wrap_after_octave_plus_ditone" value="generic_intervals_wrap_after_octave_plus_ditone"> Generic intervals (wrap after octave plus ditone)</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_pci" value="pci"> Pitch-class intervals</label>',
      "</li>",
      "</ul>",
      '<ul style="display:inline-block;vertical-align:top">',
      '<label><input type="checkbox" name="analysis_chords" value="chord_labels" accesskey="e"> Chord labels (E)</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_harmony" value="roman_numerals" accesskey="h"> Harmony in Roman numerals</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_spacing" value="spacing"> Spacing of upper voices</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_set_class_set" value="set_class_set"> Set class—set</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_set_class_normal" value="set_class_normal"> Set class—normal order</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_set_class_prime" value="set_class_prime"> Set class—prime form</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_set_class_forte" value="set_class_forte"> Set class—Forte</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_thoroughbass" value="thoroughbass" accesskey="g"> Figured bass (G)</label>',
      "</li>",
      "<li>",
      '<label><input type="checkbox" name="analysis_abbreviate_thoroughbass" value="abbreviate_thoroughbass" accesskey="v"> Abbreviate figured bass (V)</label>',
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
    },
    toggle_analysis_option: function (e) {
      var opt = e.target.value;
      this.state.mode[opt] = e.target.checked;
      this.trigger("changeOption", "analyze", opt, this.state.mode[opt]);
      document.getElementById("staff").focus();
    },
    toggle_exclusive_analysis_option: function (e, opts = []) {
      let sel = e.target.value;
      this.state.mode[sel] = e.target.checked;

      var opts = opts;
      if (!opts.includes(sel)) {
        console.log("Error");
        return null;
      }

      if (this.state.mode[sel] === true) {
        this.trigger("changeOption", "analyze", sel, true);
        var i, len;
        for (var i = 0, len = opts.length; i < len; i++) {
          let opt = opts[i];
          if (opt === sel) continue;
          document.getElementsByName("analysis_" + opt)[0].checked = false;
          this.trigger("changeOption", "analyze", opt, false);
        }
      } else if (this.state.mode[sel] === false) {
        this.trigger("changeOption", "analyze", sel, false);
      }
      document.getElementById("staff").focus();
    },
    handlers: {
      analysis_enabled: function (e) {
        this.state.enabled = e.target.checked;
        this.trigger("changeCategory", "analyze", this.state.enabled);
        this.el
          .find("input")
          .not("input[name=analysis_enabled]")
          .attr("disabled", !this.state.enabled);
      },
      analysis_abbreviate_thoroughbass: function (e) {
        var opt = e.target.value;
        this.state.mode[opt] = e.target.checked;
        this.trigger("changeOption", "analyze", opt, this.state.mode[opt]);
        document.getElementById("staff").focus();
      },
      // TODO: consolidate duplicate functions but test thoroughly in different browsers
      analysis_note_names: function (e) {
        var opts = [
          "scientific_pitch",
          "fixed_do",
          "note_names",
          "pitch_class",
          "spacing",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_fixed_do: function (e) {
        var opts = [
          "scientific_pitch",
          "fixed_do",
          "note_names",
          "pitch_class",
          "spacing",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_pitch_class: function (e) {
        var opts = [
          "scientific_pitch",
          "fixed_do",
          "note_names",
          "pitch_class",
          "spacing",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_scientific_pitch: function (e) {
        var opts = [
          "scientific_pitch",
          "fixed_do",
          "note_names",
          "pitch_class",
          "spacing",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_spacing: function (e) {
        var opts = [
          "scientific_pitch",
          "fixed_do",
          "note_names",
          "pitch_class",
          "spacing",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_solfege: function (e) {
        var opts = ["scale_degrees", "solfege", "do_based_solfege"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_do_based_solfege: function (e) {
        var opts = ["scale_degrees", "solfege", "do_based_solfege"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_scale_degrees: function (e) {
        var opts = ["scale_degrees", "solfege", "do_based_solfege"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_intervals: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_intervals_wrap_after_octave: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_intervals_wrap_after_octave_plus_ditone: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_generic_intervals: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_generic_intervals_wrap_after_octave: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_generic_intervals_wrap_after_octave_plus_ditone: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_pci: function (e) {
        var opts = ["intervals", "intervals_wrap_after_octave", "intervals_wrap_after_octave_plus_ditone", "generic_intervals", "generic_intervals_wrap_after_octave", "generic_intervals_wrap_after_octave_plus_ditone", "pci"];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_set_class_set: function (e) {
        var opts = [
          "set_class_set",
          "set_class_normal",
          "set_class_prime",
          "set_class_forte",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_set_class_normal: function (e) {
        var opts = [
          "set_class_set",
          "set_class_normal",
          "set_class_prime",
          "set_class_forte",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_set_class_prime: function (e) {
        var opts = [
          "set_class_set",
          "set_class_normal",
          "set_class_prime",
          "set_class_forte",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_set_class_forte: function (e) {
        var opts = [
          "set_class_set",
          "set_class_normal",
          "set_class_prime",
          "set_class_forte",
        ];
        this.toggle_exclusive_analysis_option(e, opts);
      },
      analysis_harmony: function (e) {
        this.toggle_analysis_option(e);
      },
      analysis_chords: function (e) {
        this.toggle_analysis_option(e);
      },
      analysis_thoroughbass: function (e) {
        this.toggle_analysis_option(e);
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
      this.el.find("input[name=analysis_enabled]")[0].checked =
        this.state.enabled;
      $.each(this.state.mode, function (key, val) {
        var $input = that.el.find("input[value=" + key + "]");
        $input.attr("checked", val ? true : false);
        $input.attr("disabled", !that.state.enabled);
      });

      // set the "neither" option
      if (!this._eitherModeTrue("note_names", "scientific_pitch")) {
        this.el
          .find("input[value=neither][name=note_analysis]")
          .attr("checked", true)
          .attr("disabled", !this.state.enabled);
      }
      // if (!this._eitherModeTrue('scale_degrees', 'solfege')) {
      // 	this.el.find('input[value=neither][name=melodic_analysis]').attr('checked', true).attr('disabled', !this.state.enabled);
      // }

      return this;
    },
    getState: function () {
      return this.state;
    },
    _eitherModeTrue: function (a, b) {
      return this.state.mode[a] || this.state.mode[b];
    },
  });

  MicroEvent.mixin(AnalyzeWidget);

  return AnalyzeWidget;
});
