(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.BarlinePlayerPlaceholderLogic = factory();
  }
})(globalThis, function () {
  "use strict";

  function escapeHTML(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function shouldBoot(config) {
    return !!config && config.type === "umto_barline_placement";
  }

  function buildPlaceholderHTML(config) {
    var timeSignature = config && config.time_signature ? escapeHTML(config.time_signature) : "";
    return (
      '<div class="qa-card barline-card">' +
      '<div class="qa-stem">Place the barlines.</div>' +
      '<div class="qa-prompt">' + timeSignature + "</div>" +
      "</div>"
    );
  }

  return {
    shouldBoot: shouldBoot,
    buildPlaceholderHTML: buildPlaceholderHTML
  };
});
