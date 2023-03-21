/* global define:false */
define(["lodash", "jquery", "microevent", "app/config"], function (
  _,
  $,
  MicroEvent,
  Config
) {
  "use strict";

  const VALID_STAFF_DISTRIBUTIONS = Config.get(
    "general.validStaffDistributions"
  );
  var STAFF_DISTRIBUTION = Config.get("general.staffDistribution");

  if (false) {
    sessionStorage.removeItem("staffDistribution"); // retire this function
  } else {
    var storage_staff_dist = sessionStorage.getItem("staffDistribution");
    if (
      storage_staff_dist &&
      VALID_STAFF_DISTRIBUTIONS.includes(storage_staff_dist)
    ) {
      STAFF_DISTRIBUTION = storage_staff_dist;
    }
  }

  var StaffDistributionWidget = function (
    distribution = false,
    is_exercise_view = false
  ) {
    this.is_exercise_view = is_exercise_view || false;
    this.el = $('<div class="menu-widgets"></div>');
    this.state =
      distribution && VALID_STAFF_DISTRIBUTIONS.includes(distribution)
        ? distribution
        : STAFF_DISTRIBUTION;
    this.init();
  };

  var staff_distribution_labels = {
    // compare dashboard
    "keyboard": "Keyboard* or break solo lines at B4, C4",
    "keyboardPlusLHBias": "Keyboard* or break solo lines above F4",
    "keyboardPlusRHBias": "Keyboard* or break solo lines below G3",
    "chorale": "Chorale or break solo lines at B4, C4",
    "grandStaff": "Break at B4, C4",
    "LH": "Lower staff only, legible through G4",
    "RH": "Upper staff only, legible through F3",
  }

  _.extend(StaffDistributionWidget.prototype, {
    templateHTML:
      [
        '<fieldset class="settings-notation">',
        "<legend><label>STAFF DISTRIBUTION</label></legend>",
        "<ul>",
      ].join("") +
      VALID_STAFF_DISTRIBUTIONS.map((opt) =>
        [
          '<li><label><input type="checkbox" name="staff_distribution" value="',
          opt,
          '"> ',
          staff_distribution_labels[opt],
          "</label></li>",
        ].join("")
      ).join("") +
      [
        "</ul>",
        "<p>*SAT no lower than G3, bass no higher than F3</p>",
        "</fieldset>"
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
    handlers: {
      staff_distribution: function (e) {
        var opt = e.target.value; // e.g. "keyboard"
        this.state = opt;
        /* temporary hack */
        sessionStorage.setItem("staffDistribution", opt);
        if (e.target.checked) {
          this.trigger("changeValue", "distribute", opt);
        }
        this.render();
      },
    },
    render: function () {
      var that = this;

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
      $.each(VALID_STAFF_DISTRIBUTIONS, function (idx, val) {
        var $input = that.el.find("input[value=" + val + "]");
        $input.attr("checked", val == that.state ? true : false);
      });

      return this;
    },
    getState: function () {
      return this.state;
    },
  });

  MicroEvent.mixin(StaffDistributionWidget);

  return StaffDistributionWidget;
});
