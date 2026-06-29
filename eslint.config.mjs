import globals from "globals";

// Flat ESLint config. Primary purpose: catch implicit globals (assignments
// to undeclared variables) that the RequireJS/AMD -> Vite migration turned
// from silent sloppy-mode globals into hard ReferenceErrors under ESM strict
// mode. Keep `no-undef` green and that whole bug class stays dead.
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
    rules: {
      "no-undef": "error",
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
