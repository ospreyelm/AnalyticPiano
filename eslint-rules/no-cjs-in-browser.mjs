export default {
  meta: {
    type: "problem",
    docs: {
      description: "Ban CommonJS and RequireJS in browser-executed source files.",
    },
    schema: [],
  },
  create(context) {
    const filename = context.getFilename();
    const allowedFiles = [
      "barline_player_logic.js",
      "exercise_score_card_logic.js",
      "harmonization_targets_logic.js",
      "harmonization_realization_logic.js",
    ];
    if (allowedFiles.some(f => filename.endsWith(f))) {
      return {};
    }

    // Helper to check if a name is declared in scope
    function isDeclaredInScope(name, scope) {
      let currentScope = scope;
      while (currentScope) {
        if (currentScope.set.has(name)) {
          return true;
        }
        currentScope = currentScope.upper;
      }
      return false;
    }

    return {
      CallExpression(node) {
        if (node.callee.type === "Identifier") {
          const name = node.callee.name;
          if (name === "require" || name === "define" || name === "requirejs") {
            // Check if it's locally declared (e.g. function require() {})
            if (isDeclaredInScope(name, context.sourceCode.getScope(node))) {
              return;
            }
            let message = "";
            if (name === "require") {
              message = "require() is banned in browser-executed source files. Use ESM import syntax instead.";
            } else if (name === "define") {
              message = "define() is banned in browser-executed source files. Use ESM export syntax instead.";
            } else {
              message = "requirejs() is banned in browser-executed source files. Use ESM import syntax instead.";
            }
            context.report({ node, message });
          }
        }
      },
      Identifier(node) {
        const name = node.name;
        if (name === "module" || name === "exports") {
          // If it is declared in the local scope, it is a local variable/parameter and is allowed.
          if (isDeclaredInScope(name, context.sourceCode.getScope(node))) {
            return;
          }
          const parent = node.parent;
          if (parent) {
            // Allow if it is an object property key that is not computed: { module: ... }
            if (parent.type === "Property" && parent.key === node && !parent.computed) {
              return;
            }
            // Allow if it is a member expression property: object.module
            if (parent.type === "MemberExpression" && parent.property === node && !parent.computed) {
              return;
            }
            // Allow variable declarations: var module = ...
            if (parent.type === "VariableDeclarator" && parent.id === node) {
              return;
            }
            // Allow function parameters: function(module)
            if (
              (parent.type === "FunctionDeclaration" ||
               parent.type === "FunctionExpression" ||
               parent.type === "ArrowFunctionExpression") &&
              parent.params.includes(node)
            ) {
              return;
            }
          }
          context.report({
            node,
            message: `${name} is banned in browser-executed source files. Use ESM export syntax instead.`,
          });
        }
      },
    };
  },
};
