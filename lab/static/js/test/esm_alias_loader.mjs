// Test-only ESM resolve hook for the plain-node JS test harness
// (run_js_tests.sh → `node <file>.test.js`).
//
// exercise_definition.js (and similar app modules) use Vite-only conventions —
// the `app/...` import alias and extensionless relative imports (`./resolved_mode`)
// — plus bare npm packages (lodash, tonal, vexflow) that aren't installed under
// the node test harness. This hook lets those modules load for direct unit
// testing of `ExerciseDefinition.parse()`:
//
//   - `app/config`        → lab/static/js/src/config.js
//   - `app/...`           → lab/static/js/src/<...>.js
//   - `./rel` (no ext)    → `./rel.js` (ESM requires explicit extensions)
//   - bare npm packages   → a minimal lodash-shaped stub (data: URL) so parse()
//                           runs offline without DOM-touching deps like vexflow.
//
// The loader is registered from a .test.js via:
//   register(pathToFileURL("<...>/esm_alias_loader.mjs").href, pathToFileURL(__filename));
// with `process.env.HARMONYLAB_SRC` pointing at lab/static/js/src.
//
// NOTE: this is test infrastructure only — production builds resolve the same
// aliases via vite.config.js. The stub intentionally provides just the lodash
// functions the parse() path touches; it is NOT a full lodash replacement.

import { pathToFileURL } from "url";
import path from "path";

const SRC = process.env.HARMONYLAB_SRC
  ? path.resolve(process.env.HARMONYLAB_SRC)
  : path.resolve("lab/static/js/src");

const STUB =
  "data:text/javascript," +
  encodeURIComponent(`
function arrayColl(c){return Array.isArray(c)?c:Object.values(c||{});}
function mapColl(c,cb){if(!c)return [];if(Array.isArray(c))return c.map((v,i)=>cb(v,i));const out=[];let i=0;for(const k in c){out.push(cb(c[k],k,i));i++;}return out;}
function eachColl(c,cb){if(!c)return;if(Array.isArray(c)){c.forEach((v,i)=>cb(v,i));}else{for(const k in c)cb(c[k],k);}}
function reduceColl(c,cb,acc){if(Array.isArray(c))return c.reduce(cb,acc);let r=acc;for(const k in c)r=cb(r,c[k],k);return r;}
const h={
map:(c,cb)=>mapColl(c,cb),each:(c,cb)=>{eachColl(c,cb);return c;},forEach:(c,cb)=>{eachColl(c,cb);return c;},
reduce:(c,cb,acc)=>reduceColl(c,cb,acc),find:(c,cb)=>arrayColl(c).find(cb),findIndex:(c,cb)=>arrayColl(c).findIndex(cb),
filter:(c,cb)=>arrayColl(c).filter(cb),assign:(...a)=>Object.assign(a[0],...a.slice(1)),extend:(...a)=>Object.assign(a[0],...a.slice(1)),
merge:(t,...s)=>{s.forEach(o=>{if(o)for(const k in o)t[k]=o[k];});return t;},
cloneDeep:(x)=>JSON.parse(JSON.stringify(x)),clone:(x)=>Array.isArray(x)?x.slice():Object.assign({},x),
uniq:(c)=>[...new Set(arrayColl(c))],includes:(c,v)=>arrayColl(c).includes(v),indexOf:(c,v)=>arrayColl(c).indexOf(v),
keys:(o)=>Object.keys(o||{}),values:(o)=>Object.values(o||{}),pairs:(o)=>Object.entries(o||{}),
isUndefined:(x)=>x===undefined,isNull:(x)=>x===null,isBoolean:(x)=>typeof x==='boolean',
isString:(x)=>typeof x==='string',isNumber:(x)=>typeof x==='number',isObject:(x)=>!!x&&typeof x==='object',
isArray:Array.isArray,isFunction:(x)=>typeof x==='function',isEmpty:(x)=>!x||(typeof x==='object'&&Object.keys(x).length===0),
compact:(c)=>arrayColl(c).filter(Boolean),first:(c)=>arrayColl(c)[0],last:(c)=>{const a=arrayColl(c);return a[a.length-1];},
flatten:(c)=>arrayColl(c).flat(),flattenDeep:(c)=>{const out=[];const f=(a)=>a.forEach(x=>Array.isArray(x)?f(x):out.push(x));f(arrayColl(c));return out;},
partial:(fn,...a)=>(...r)=>fn(...a,...r),bind:(fn,...a)=>fn.bind(...a),noop:()=>{},
};
export default new Proxy(h,{get(_,p){return h[p]!==undefined?h[p]:(()=>undefined);}});
export const map=h.map;
`);

function withExt(p) {
  return p.endsWith(".js") ? p : p + ".js";
}

export async function resolve(specifier, context, nextResolve) {
  let s = specifier;
  if (s === "app/config") {
    s = pathToFileURL(path.join(SRC, "config.js")).href;
  } else if (s === "app" || s.startsWith("app/")) {
    s = pathToFileURL(path.join(SRC, withExt(s.slice(4)))).href;
  } else if (s.startsWith(".") && context.parentURL && !s.endsWith(".js")) {
    const base = new URL(s, context.parentURL);
    s = base.href.endsWith(".js") ? base.href : base.href + ".js";
  } else if (/^[a-z@][\w.-]*$/i.test(s) && !s.includes("/")) {
    // Bare npm package (lodash/tonal/vexflow/microevent) — not installed under
    // the node test harness, and vexflow touches the DOM at import. Stub it.
    return { url: STUB, shortCircuit: true };
  }
  return nextResolve(s, context);
}