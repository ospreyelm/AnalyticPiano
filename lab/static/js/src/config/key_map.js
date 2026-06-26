/* Key map data spelling/pitch-class configuration interface */
/* Read only */

/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(require("./key_map_data")); }
  else if (typeof define === "function" && define.amd) { define(["app/config/key_map_data"], factory); }
  else { root.KeyMap = factory(root.KeyMapData); }
})(typeof self !== "undefined" ? self : this, function (KeyMapData) {
  "use strict";

  return KeyMapData;
});
