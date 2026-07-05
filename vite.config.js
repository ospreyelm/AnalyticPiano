import { defineConfig } from "vite";
import { resolve } from "path";
import fs from "fs";

// Vite emits HTML entries preserving their source path relative to the
// project root, so the triads-circle-of-thirds entry would land at
// dist/lab/static/reference/triads-circle-of-thirds/index.html. The asset
// references inside are absolute (/static/dist/assets/...), so the HTML is
// location-independent — relocate it to a clean dist/ subdirectory and prune
// the empty nested tree. Served URL becomes /static/dist/triads-circle-of-thirds/index.html.
function flattenReferenceHtml() {
  return {
    name: "flatten-reference-html",
    closeBundle() {
      const distDir = resolve(__dirname, "lab/static/dist");
      const nested = resolve(distDir, "lab/static/reference/triads-circle-of-thirds/index.html");
      const flatDir = resolve(distDir, "triads-circle-of-thirds");
      const flat = resolve(flatDir, "index.html");
      if (!fs.existsSync(nested)) return;
      fs.mkdirSync(flatDir, { recursive: true });
      fs.copyFileSync(nested, flat);
      // Remove the now-duplicated nested lab/ tree Vite created under dist/.
      fs.rmSync(resolve(distDir, "lab"), { recursive: true, force: true });
    },
  };
}

export default defineConfig({
  base: "/static/dist/",
  plugins: [flattenReferenceHtml()],
  resolve: {
    alias: [
      { find: /^app\/config$/, replacement: resolve(__dirname, "lab/static/js/src/config.js") },
      { find: "app", replacement: resolve(__dirname, "lab/static/js/src") },
      { find: "microevent", replacement: resolve(__dirname, "lab/static/js/lib/microevent.js") },
      { find: "vexflow", replacement: resolve(__dirname, "lab/static/js/lib/vexflow.js") },
      { find: "tonal", replacement: resolve(__dirname, "lab/static/js/lib/tonal.min.js") },
      { find: "Tone", replacement: resolve(__dirname, "lab/static/js/lib/Tone.js") },
      { find: /^lodash$/, replacement: resolve(__dirname, "lab/static/js/lib/lodash.js") },
      { find: "jquery", replacement: resolve(__dirname, "lab/static/js/lib/jquery.js") },
      { find: "raphael", replacement: resolve(__dirname, "lab/static/js/lib/raphael.js") },
      { find: "canvas-confetti", replacement: resolve(__dirname, "lab/static/js/lib/canvas-confetti.js") },
      { find: "file-saver", replacement: resolve(__dirname, "lab/static/js/lib/file-saver.js") },
      { find: "jquery-ui", replacement: resolve(__dirname, "lab/static/js/lib/jquery-ui.js") }
    ]
  },
  build: {
    manifest: true,
    outDir: resolve(__dirname, "lab/static/dist"),
    rollupOptions: {
      input: {
        key_signature: resolve(__dirname, "lab/static/js/src/models/key_signature.js"),
        chord: resolve(__dirname, "lab/static/js/src/models/chord.js"),
        key: resolve(__dirname, "lab/static/js/src/models/key_context_logic.js"),
        exercise_grader: resolve(__dirname, "lab/static/js/src/models/exercise_grader.js"),
        chorale_grader: resolve(__dirname, "lab/static/js/src/models/chorale_grader.js"),
        identification_grader: resolve(__dirname, "lab/static/js/src/models/identification_grader.js"),
        voice_leading: resolve(__dirname, "lab/static/js/src/models/voice_leading_logic.js"),
        exercise_definition: resolve(__dirname, "lab/static/js/src/models/exercise_definition.js"),
        exercise_definition_logic: resolve(__dirname, "lab/static/js/src/models/exercise_definition_logic.js"),
        exercise_definition_label_logic: resolve(__dirname, "lab/static/js/src/models/exercise_definition_label_logic.js"),
        exercise_chord: resolve(__dirname, "lab/static/js/src/models/exercise_chord.js"),
        exercise_chord_bank: resolve(__dirname, "lab/static/js/src/models/exercise_chord_bank.js"),
        midi_device: resolve(__dirname, "lab/static/js/src/models/midi_device.js"),
        metronome: resolve(__dirname, "lab/static/js/src/models/metronome.js"),
        score_player: resolve(__dirname, "lab/static/js/src/models/score_player.js"),
        barline_player: resolve(__dirname, "lab/static/js/src/barline_player_logic.js"),
        instruments: resolve(__dirname, "lab/static/js/src/config/instruments.js"),
        instruments_map: resolve(__dirname, "lab/static/js/src/config/instruments_map.js"),
        exercise_context: resolve(__dirname, "lab/static/js/src/models/exercise_context.js"),
        vexflow_adapter: resolve(__dirname, "lab/static/js/src/components/music/rendering/vexflow_adapter.js"),
        click_note: resolve(__dirname, "lab/static/js/src/components/input/click_note.js"),
        piano: resolve(__dirname, "lab/static/js/src/components/piano.js"),
        main: resolve(__dirname, "lab/static/js/src/main.js"),
        // Reference lesson page. render-lesson.js imports the real VexFlow
        // engine (`vexflow`, `app/...`) via bare specifiers that only resolve
        // through the aliases below, so this page MUST be Vite-built — it
        // cannot be served raw from /static/reference/. The built HTML lands
        // in lab/static/dist/ and is the canonical URL linked from the hints.
        triads_circle_of_thirds: resolve(__dirname, "lab/static/reference/triads-circle-of-thirds/index.html")
      }
    }
  },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    headers: {
      "Access-Control-Allow-Origin": "*"
    }
  }
});
