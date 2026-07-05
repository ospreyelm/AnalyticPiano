import globals from "globals";
import noRawPipelineDiscriminator from "./eslint-rules/no-raw-pipeline-discriminator.mjs";

// Flat ESLint config. Primary purpose: catch implicit globals (assignments
// to undeclared variables) that the RequireJS/AMD -> Vite migration turned
// from silent sloppy-mode globals into hard ReferenceErrors under ESM strict
// mode. Keep `no-undef` green and that whole bug class stays dead.
//
// Secondary: the `harmonylab-pipelines/no-raw-pipeline-discriminator` rule
// (Phase 1.3) bans raw pipeline-discriminator comparisons outside the
// resolver/factory/axis modules, killing the agent grep-confusion that the
// pipeline-isolation refactor targets. See eslint-rules/no-raw-pipeline-discriminator.mjs.
export default [
  {
    ignores: [
      "node_modules/**",
      "lab/static/dist/**",
      "lab/static/js/lib/**",
    ],
  },
  {
    files: ["lab/static/js/src/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.es2021,
        // Vendored libraries / app-level globals provided at runtime.
        _: "readonly",
        $: "readonly",
        jQuery: "readonly",
        Raphael: "readonly",
        Vex: "readonly",
        Tone: "readonly",
        Tonal: "readonly",
        cytoscape: "readonly",
        define: "readonly",
        require: "readonly",
        module: "readonly",
        process: "readonly",
      },
    },
    linterOptions: {
      // Leftover eslint-disable comments from a fuller config are harmless here.
      reportUnusedDisableDirectives: "off",
    },
    plugins: {
      "harmonylab-pipelines": {
        rules: {
          "no-raw-pipeline-discriminator": noRawPipelineDiscriminator,
        },
      },
    },
    rules: {
      "no-undef": "error",
      "harmonylab-pipelines/no-raw-pipeline-discriminator": "error",
    },
  },
  {
    // Test files are run directly under Node, not bundled as browser ESM.
    files: ["lab/static/js/src/**/*.test.js"],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
];
