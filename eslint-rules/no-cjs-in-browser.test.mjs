import { RuleTester } from "eslint";
import rule from "./no-cjs-in-browser.mjs";

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2021,
    sourceType: "module",
  },
});

ruleTester.run("no-cjs-in-browser", rule, {
  valid: [
    { code: 'import foo from "foo"; export default foo;' },
    { code: 'var a = 1;' },
    { code: 'var module = {};' },
    { code: 'function test(module) {}' },
    { code: 'var obj = { module: 1 };' },
    { code: 'var x = obj.module;' },
    { code: 'var obj2 = { exports: 1 };' },
    { code: 'var y = obj2.exports;' },
    // Allowlisted file should pass even with CJS syntax.
    // (RuleTester passes the filename in options to match)
    {
      code: 'module.exports = {};',
      filename: "barline_player_logic.js"
    },
    {
      code: 'var x = require("foo");',
      filename: "exercise_score_card_logic.js"
    }
  ],
  invalid: [
    {
      code: 'var foo = require("foo");',
      errors: [{ message: "require() is banned in browser-executed source files. Use ESM import syntax instead." }],
    },
    {
      code: 'module.exports = {};',
      errors: [{ message: "module is banned in browser-executed source files. Use ESM export syntax instead." }],
    },
    {
      code: 'exports.foo = 1;',
      errors: [{ message: "exports is banned in browser-executed source files. Use ESM export syntax instead." }],
    },
    {
      code: 'define(["a"], function(a) {});',
      errors: [{ message: "define() is banned in browser-executed source files. Use ESM export syntax instead." }],
    },
    {
      code: 'requirejs(["a"], function(a) {});',
      errors: [{ message: "requirejs() is banned in browser-executed source files. Use ESM import syntax instead." }],
    }
  ],
});

console.log("ESLint no-cjs-in-browser rule tests passed successfully.");
