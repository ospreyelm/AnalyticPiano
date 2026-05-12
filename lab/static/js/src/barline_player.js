import "./barline_player_placeholder_logic.js";

document.addEventListener("DOMContentLoaded", function () {
  var config = window.__EXERCISE_CONFIG__;
  var logic = window.BarlinePlayerPlaceholderLogic;
  if (!logic || !logic.shouldBoot(config)) {
    return;
  }

  var root = document.getElementById("qa-root");
  if (!root) {
    return;
  }

  root.innerHTML = logic.buildPlaceholderHTML(config);
});
