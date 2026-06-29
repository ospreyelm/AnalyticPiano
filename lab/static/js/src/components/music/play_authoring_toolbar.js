import $ from "jquery";

// Duration palette: [quarterLength, label]
  var DURATION_ENTRIES = [
    [4,    "w"],
    [3,    "h."],
    [2,    "h"],
    [1.5,  "q."],
    [1,    "q"],
    [0.75, "8."],
    [0.5,  "8"],
    [0.25, "16"],
  ];

  /**
   * PlayAuthoringToolbar
   *
   * A small floating toolbar anchored near a selected banked chord in the
   * Play view. Provides a duration palette, a respell button, and an optional
   * token-correction input for Roman numeral / figured bass overrides.
   *
   * @constructor
   * @param {object} options
   * @param {function} options.onSetDuration  Called with (quarterLength) when a
   *   duration button is clicked.
   * @param {function} options.onRespell      Called when the Respell button is
   *   clicked.
   * @param {function} options.onClose        Called when the × button is clicked.
   * @param {function} [options.onSetToken]   Called with (value) when the token
   *   input is committed (Enter or blur). Only shown when showAt is called with
   *   a non-null currentToken.
   */
  function PlayAuthoringToolbar(options) {
    this._opts = options || {};
    this._$el = null;
    this._$tokenRow = null;
    this._$tokenInput = null;
    this._visible = false;
    this._currentQl = null;
    this._build();
  }

  PlayAuthoringToolbar.prototype = {
    /**
     * Build the DOM once and append to body (hidden).
     */
    _build: function () {
      var self = this;
      var $el = $([
        '<div class="play-authoring-toolbar" style="',
          "display:none;",
          "position:absolute;",
          "z-index:200;",
          "background:#fff;",
          "border:1px solid #aaa;",
          "border-radius:4px;",
          "box-shadow:0 2px 8px rgba(0,0,0,0.18);",
          "padding:4px 6px;",
          "white-space:nowrap;",
          "font-size:12px;",
          "line-height:1;",
        '">',
      ].join(""));

      // Duration buttons
      for (var i = 0; i < DURATION_ENTRIES.length; i++) {
        (function (ql, label) {
          var $btn = $(
            '<button class="pat-dur-btn" data-ql="' + ql + '" style="' +
              "margin:0 2px;padding:2px 5px;" +
              "border:1px solid #bbb;border-radius:3px;" +
              "background:#f5f5f5;cursor:pointer;font-size:12px;" +
            '">' + label + "</button>"
          );
          $btn.on("click", function () {
            if (typeof self._opts.onSetDuration === "function") {
              self._opts.onSetDuration(ql);
            }
            // Update highlighted state
            self._currentQl = ql;
            self._highlightCurrentDuration();
          });
          $el.append($btn);
        }(DURATION_ENTRIES[i][0], DURATION_ENTRIES[i][1]));
      }

      // Separator
      $el.append($('<span style="display:inline-block;width:1px;background:#ccc;height:16px;margin:0 4px;vertical-align:middle;">'));

      // Respell button
      var $respell = $(
        '<button class="pat-respell-btn" style="' +
          "margin:0 2px;padding:2px 5px;" +
          "border:1px solid #bbb;border-radius:3px;" +
          "background:#f5f5f5;cursor:pointer;font-size:12px;" +
        '">Respell</button>'
      );
      $respell.on("click", function () {
        if (typeof self._opts.onRespell === "function") {
          self._opts.onRespell();
        }
      });
      $el.append($respell);

      // Close button
      var $close = $(
        '<button class="pat-close-btn" style="' +
          "margin-left:6px;padding:2px 5px;" +
          "border:1px solid #bbb;border-radius:3px;" +
          "background:#f5f5f5;cursor:pointer;font-size:12px;" +
        '">×</button>'
      );
      $close.on("click", function () {
        if (typeof self._opts.onClose === "function") {
          self._opts.onClose();
        }
      });
      $el.append($close);

      // Token-correction row (hidden by default; shown when a below-zone label is present)
      var $tokenRow = $([
        '<div class="pat-token-row" style="',
          "display:none;",
          "margin-top:5px;",
          "border-top:1px solid #eee;",
          "padding-top:4px;",
        '">',
          '<span style="font-size:11px;color:#666;margin-right:4px;">Label:</span>',
          '<input class="pat-token-input" type="text" style="',
            "width:90px;",
            "font-size:12px;",
            "padding:2px 4px;",
            "border:1px solid #bbb;",
            "border-radius:3px;",
          '" placeholder="e.g. V7, I6">',
        "</div>",
      ].join(""));

      var $tokenInput = $tokenRow.find(".pat-token-input");
      $tokenInput.on("keydown", function (e) {
        if (e.which === 13) { // Enter
          e.preventDefault();
          if (typeof self._opts.onSetToken === "function") {
            self._opts.onSetToken($tokenInput.val());
          }
        }
      });
      $tokenInput.on("blur", function () {
        if (typeof self._opts.onSetToken === "function") {
          self._opts.onSetToken($tokenInput.val());
        }
      });
      $el.append($tokenRow);
      this._$tokenRow = $tokenRow;
      this._$tokenInput = $tokenInput;

      $("body").append($el);
      this._$el = $el;
    },

    /**
     * Highlight the button matching the current quarter-length.
     * @private
     */
    _highlightCurrentDuration: function () {
      var ql = this._currentQl;
      this._$el.find(".pat-dur-btn").each(function () {
        var btnQl = parseFloat($(this).data("ql"));
        if (Math.abs(btnQl - ql) < 1e-6) {
          $(this).css({ background: "#4facfe", color: "#fff", borderColor: "#4facfe" });
        } else {
          $(this).css({ background: "#f5f5f5", color: "", borderColor: "#bbb" });
        }
      });
    },

    /**
     * Show the toolbar anchored near the given page rect.
     *
     * @param {object} rect   Page-coordinate bounding box
     *   { left, top, width, height } (all in px).
     * @param {number} [currentQl]    Quarter-length of the selected chord, used
     *   to highlight the matching duration button.
     * @param {string|null} [currentToken]  Current below-zone label for the
     *   selected chord (e.g. "V7", "I6"). When non-null, reveals the token
     *   correction input pre-filled with this value. Pass null or omit to hide
     *   the token row (backward-compatible with Task 12 callers).
     */
    showAt: function (rect, currentQl, currentToken) {
      var $el = this._$el;

      // Show/hide and prefill token row based on whether a below-zone is active
      if (currentToken !== null && currentToken !== undefined) {
        this._$tokenInput.val(currentToken);
        this._$tokenRow.show();
      } else {
        this._$tokenRow.hide();
      }

      // Position toolbar just below the chord slot, centered horizontally
      // (must happen after show/hide to get correct outerWidth)
      var toolbarWidth = $el.outerWidth(true) || 280;
      var left = rect.left + rect.width / 2 - toolbarWidth / 2;
      var top  = rect.top + rect.height + 6;

      // Clamp to viewport
      var vpWidth = $(window).width();
      if (left + toolbarWidth > vpWidth - 4) {
        left = vpWidth - toolbarWidth - 4;
      }
      if (left < 4) left = 4;

      $el.css({ left: left, top: top }).show();
      this._visible = true;

      if (typeof currentQl === "number") {
        this._currentQl = currentQl;
        this._highlightCurrentDuration();
      }
    },

    /**
     * Hide the toolbar.
     */
    hide: function () {
      if (this._$el) {
        this._$el.hide();
      }
      this._visible = false;
    },

    /**
     * Returns true if the toolbar is currently visible.
     *
     * @return {boolean}
     */
    isVisible: function () {
      return this._visible;
    },
  };

export default PlayAuthoringToolbar;
