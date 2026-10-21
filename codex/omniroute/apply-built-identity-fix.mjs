import fs from "node:fs";

const paths = process.argv.slice(2);
if (paths.length === 0) {
  throw new Error("usage: node apply-built-identity-fix.mjs <chunk> [...]");
}

const collisionVirgin =
  /if\(i\(d,f,a\)\)\{let b=d\?\.get\(f\);f=h\(c,a,8\);let e=10;for\(;i\(d,f,a\)&&e<=32;\)f=h\(c,a,e\),e\+=2;i\(d,f,a\)&&\(f=h\("tool",`\$\{a\}:\$\{Date\.now\(\)\}`,12\)\),console\.warn\(`\[GeminiTools\] Tool name collision after sanitization: "\$\{a\}" conflicts with "\$\{b\}"\. Using "\$\{f\}"\.`\)\}/g;

const collisionPatchedMarker = 'a.includes("__")&&!String(b).includes("__")';

const collisionReplacement =
  'if(i(d,f,a)){let b=d?.get(f);let n=s=>String(s||"").trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"");if(b&&n(b)===n(a)){a.includes("__")&&!String(b).includes("__")&&d.set(f,a);return f}f=h(c,a,8);let e=10;for(;i(d,f,a)&&e<=32;)f=h(c,a,e),e+=2;i(d,f,a)&&(f=h("tool",`${a}:${Date.now()}`,12)),console.warn(`[GeminiTools] Tool name collision after sanitization: "${a}" conflicts with "${b}". Using "${f}".`)}';

const restoreVirgin =
  /let c=b\.get\(a\.name\);if\(!c\)return!1;let d=a\.namespace!==c\.namespace\|\|a\.name!==c\.name;return a\.namespace=c\.namespace,a\.name=c\.name,d/g;

const restorePatchedMarker = "1===o.length&&(c=o[0])";

const restoreReplacement =
  'let c=b.get(a.name);if(!c){let n=String(a.name).trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"").replace(/_[0-9a-f]{8,32}$/i,"");let o=[];for(let[e,t]of b){if(!t||"object"!=typeof t||"string"!=typeof t.namespace||"string"!=typeof t.name)continue;let s=[t.namespace+"__"+t.name,t.namespace+"_"+t.name,t.namespace+"."+t.name,t.name,e].some(e=>String(e).trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"").replace(/_[0-9a-f]{8,32}$/i,"")===n);s&&o.push(t)}1===o.length&&(c=o[0])}if(!c)return!1;let d=a.namespace!==c.namespace||a.name!==c.name;return a.namespace=c.namespace,a.name=c.name,d';

// OmniRoute 3.8.x: resolveNamespaceIdentity only splits __ for mcp__* names.
// Gemini sanitizes multi_agent_v1__spawn_agent → multi_agent_v1_spawn_agent, so
// Codex gets a flat name and tools router returns unsupported call.
const resolveVirgin =
  /function ([A-Za-z_$][\w$]*)\(([A-Za-z_$][\w$]*),([A-Za-z_$][\w$]*)\)\{if\(!\3\)return null;let ([A-Za-z_$][\w$]*)=([A-Za-z_$][\w$]*)\(\2 instanceof Map\?\2\.get\(\3\):\2&&"object"==typeof \2&&!Array\.isArray\(\2\)\?\2\[\3\]:void 0\);if\(\4\)return \4;for\(let \4 of \2 instanceof Map\?\2\.values\(\):\2&&"object"==typeof \2&&!Array\.isArray\(\2\)\?Object\.values\(\2\):\[\]\)\{let \2=\5\(\4\);if\(\2&&`\$\{\2\.namespace\}\.\$\{\2\.name\}`===\3\)return \2\}if\(!\3\.startsWith\("mcp__"\)\)return null;let ([A-Za-z_$][\w$]*)=\3\.lastIndexOf\("__"\);if\(\6<=0\)return null;let ([A-Za-z_$][\w$]*)=\3\.slice\(0,\6\),([A-Za-z_$][\w$]*)=\3\.slice\(\6\+2\);return \7&&\8\?\{namespace:\7,name:\8\}:null\}/g;

const resolvePatchedMarker = "devhub_normalize_tool_identity";

function buildResolveReplacement(fn, map, key, asId, validator, _idx, nsVar, leafVar) {
  return (
    `function ${fn}(${map},${key}){` +
    `if(!${key})return null;` +
    `let ${asId}=${validator}(${map} instanceof Map?${map}.get(${key}):${map}&&"object"==typeof ${map}&&!Array.isArray(${map})?${map}[${key}]:void 0);` +
    `if(${asId})return ${asId};` +
    `for(let ${asId} of ${map} instanceof Map?${map}.values():${map}&&"object"==typeof ${map}&&!Array.isArray(${map})?Object.values(${map}):[]){` +
    `let id=${validator}(${asId});` +
    `if(id&&\`\$\{id.namespace\}.\$\{id.name\}\`===${key})return id` +
    `}` +
    `let devhub_normalize_tool_identity=s=>String(s||"").trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"").replace(/_[0-9a-f]{8,32}$/i,"");` +
    `let q=devhub_normalize_tool_identity(${key}),o=[];` +
    `for(let[e,t]of ${map} instanceof Map?${map}.entries():Object.entries(${map}&&"object"==typeof ${map}&&!Array.isArray(${map})?${map}:{})){` +
    `let id=${validator}(t);if(!id)continue;` +
    `let cands=[e,id.namespace+"__"+id.name,id.namespace+"_"+id.name,id.namespace+"."+id.name,id.name];` +
    `cands.some(x=>devhub_normalize_tool_identity(x)===q)&&o.push(id)` +
    `}` +
    `if(1===o.length)return o[0];` +
    `let devhub_ns_idx=${key}.lastIndexOf("__");` +
    `if(devhub_ns_idx>0){let devhub_ns=${key}.slice(0,devhub_ns_idx),devhub_leaf=${key}.slice(devhub_ns_idx+2);if(devhub_ns&&devhub_leaf)return{namespace:devhub_ns,name:devhub_leaf}}` +
    `return null}`
  );
}

let totalCollision = 0;
let totalRestore = 0;
let totalResolve = 0;

for (const path of paths) {
  let source = fs.readFileSync(path, "utf8");
  let updated = source;
  let collisionHits = 0;
  let restoreHits = 0;
  let resolveHits = 0;

  if (!updated.includes(collisionPatchedMarker)) {
    updated = updated.replace(collisionVirgin, () => {
      collisionHits += 1;
      return collisionReplacement;
    });
  }

  if (!updated.includes(restorePatchedMarker)) {
    updated = updated.replace(restoreVirgin, () => {
      restoreHits += 1;
      return restoreReplacement;
    });
  }

  if (!updated.includes(resolvePatchedMarker)) {
    updated = updated.replace(
      resolveVirgin,
      (_full, fn, map, key, asId, validator, idx, ns, leaf) => {
        resolveHits += 1;
        return buildResolveReplacement(fn, map, key, asId, validator, idx, ns, leaf);
      }
    );
  }

  if (updated !== source) {
    fs.writeFileSync(path, updated);
  }
  totalCollision += collisionHits;
  totalRestore += restoreHits;
  totalResolve += resolveHits;
}

console.log(
  JSON.stringify({
    files: paths.length,
    collision: totalCollision,
    restore: totalRestore,
    resolve: totalResolve,
  })
);
