define(["jquery", "app/components/component"], function ($, Component) {
  /**
   * TargetSelectorComponent presents a small panel after a Play Save that
   * lets the teacher choose where the new exercise should go.
   *
   * v1: "My library" is the only enabled target. "Assign to a class" is
   * disabled (coming soon). Auto-transpose defaults to off.
   *
   * Emits the Threads 2/3 seam contract via the onChoose callback:
   *   { exerciseId, targetIntent, sectionId, autoTranspose }
   *
   * @param {object} settings
   * @param {function} settings.onChoose  Called with the seam-contract payload.
   * @constructor
   */
  var TargetSelectorComponent = function (settings) {
    this.settings = settings || {};
    this._onChoose = (settings && settings.onChoose) || function () {};
    this._exerciseId = null;
    this._el = null;
  };

  TargetSelectorComponent.prototype = new Component();

  /**
   * Builds the DOM panel and attaches event handlers.
   * Called by the component framework after the parent is initialised.
   *
   * @return undefined
   */
  TargetSelectorComponent.prototype.initComponent = function () {
    var self = this;

    var panel = $(
      '<div id="target-selector-panel" style="display:none;position:fixed;top:50%;left:50%;' +
        "transform:translate(-50%,-50%);z-index:9999;background:#fff;border:1px solid #ccc;" +
        'border-radius:6px;padding:24px 28px;min-width:320px;box-shadow:0 4px 16px rgba(0,0,0,.18);">' +
        '<h3 style="margin:0 0 16px;font-size:1.1em;">Where should this go?</h3>' +
        '<div style="margin-bottom:12px;">' +
        '<label style="display:block;margin-bottom:8px;cursor:pointer;">' +
        '<input type="radio" name="target-intent" value="library" checked ' +
        'style="margin-right:6px;" />' +
        "My library" +
        "</label>" +
        '<label style="display:block;color:#aaa;cursor:not-allowed;">' +
        '<input type="radio" name="target-intent" value="assign" disabled ' +
        'style="margin-right:6px;" />' +
        "Assign to a class <em style=\"font-size:.85em;\">(coming soon)</em>" +
        "</label>" +
        "</div>" +
        '<div style="margin-bottom:20px;">' +
        '<label style="cursor:pointer;">' +
        '<input type="checkbox" id="target-auto-transpose" style="margin-right:6px;" />' +
        "Auto-transpose for varied keys" +
        "</label>" +
        "</div>" +
        '<button id="target-selector-file-btn" ' +
        'style="padding:8px 20px;background:#2563eb;color:#fff;border:none;' +
        'border-radius:4px;cursor:pointer;font-size:1em;">File it</button>' +
        '<button id="target-selector-cancel-btn" ' +
        'style="margin-left:12px;padding:8px 14px;background:transparent;' +
        "color:#555;border:1px solid #ccc;border-radius:4px;cursor:pointer;" +
        'font-size:1em;">Cancel</button>' +
        "</div>"
    );

    $("body").append(panel);
    this._el = panel;

    panel.find("#target-selector-file-btn").on("click", function () {
      self._handleFileIt();
    });

    panel.find("#target-selector-cancel-btn").on("click", function () {
      self.close();
    });
  };

  /**
   * Reads the form state, builds the seam-contract payload, calls onChoose,
   * and closes the panel.
   *
   * @return undefined
   */
  TargetSelectorComponent.prototype._handleFileIt = function () {
    var targetIntent = this._el
      .find("input[name='target-intent']:checked")
      .val() || "library";
    var autoTranspose = this._el
      .find("#target-auto-transpose")[0].checked;

    var payload = {
      exerciseId: this._exerciseId,
      targetIntent: targetIntent,
      sectionId: null,
      autoTranspose: autoTranspose,
    };

    this._onChoose(payload);
    this.close();
  };

  /**
   * Stores the exerciseId, resets form fields to defaults, and shows the panel.
   *
   * @param {number|string} exerciseId
   * @return undefined
   */
  TargetSelectorComponent.prototype.open = function (exerciseId) {
    this._exerciseId = exerciseId;

    // Reset to defaults: "library" selected, auto-transpose unchecked.
    if (this._el) {
      this._el
        .find("input[name='target-intent'][value='library']")
        .prop("checked", true);
      this._el.find("#target-auto-transpose").prop("checked", false);
      this._el.show();
    }
  };

  /**
   * Hides the panel.
   *
   * @return undefined
   */
  TargetSelectorComponent.prototype.close = function () {
    if (this._el) {
      this._el.hide();
    }
  };

  /**
   * Removes DOM and cleans up.
   *
   * @return undefined
   */
  TargetSelectorComponent.prototype.destroy = function () {
    if (this._el) {
      this._el.remove();
      this._el = null;
    }
    Component.prototype.destroy.call(this);
  };

  return TargetSelectorComponent;
});
