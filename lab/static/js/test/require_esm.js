/**
 * ESM/CJS interop helper for Node.js require() of modules exported via ESM.
 *
 * When a module uses `export default {...}` (ESM), Node's require() returns
 * the module wrapped as { default: <export>, __esModule: true } rather than
 * spreading the export onto the returned object. This helper unwraps that.
 *
 * Usage:
 *   var mod = require("./some_module");
 *   mod = requireDefault(mod);
 *
 * Or inline:
 *   var mod = requireDefault(require("./some_module"));
 */

function requireDefault(mod) {
  return (mod && mod.default) || mod;
}

module.exports = { requireDefault: requireDefault };
