import fs from "node:fs";

const paths = process.argv.slice(2);
if (paths.length === 0) {
  throw new Error("usage: node apply-built-identity-fix.mjs <chunk> [...]");
}

const resolverPattern =
  /function ([A-Za-z_$][\w$]*)\(e,t\)\{if\(!t\)return null;let ([A-Za-z_$][\w$]*)=([A-Za-z_$][\w$]*)\(e instanceof Map\?e\.get\(t\):e&&"object"==typeof e&&!Array\.isArray\(e\)\?e\[t\]:void 0\);if\(\2\)return \2;for\(let \2 of e instanceof Map\?e\.values\(\):e&&"object"==typeof e&&!Array\.isArray\(e\)\?Object\.values\(e\):\[\]\)\{let e=\3\(\2\);if\(e&&`\$\{e\.namespace\}\.\$\{e\.name\}`===t\)return e\}return null\}/g;
const restorePattern =
  "let r=t.get(e.name);if(!r)return!1;let n=e.namespace!==r.namespace||e.name!==r.name;";
const restoreReplacement =
  'let r=t.get(e.name);if(!r){let n=e.name.trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"");let o=[];for(let[e,t]of t){if(!t||"object"!=typeof t||"string"!=typeof t.namespace||"string"!=typeof t.name)continue;let s=[t.namespace+"__"+t.name,t.namespace+"_"+t.name,t.namespace+"."+t.name,t.name].some(e=>e.trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"")===n);s&&o.push(t)}1===o.length&&(r=o[0])}if(!r)return!1;let n=e.namespace!==r.namespace||e.name!==r.name;';

for (const path of paths) {
  const source = fs.readFileSync(path, "utf8");
  let matches = 0;
  const updated = source.replace(resolverPattern, (_full, resolverName, validatorName, validator) => {
    matches += 1;
    return `function ${resolverName}(e,t){if(!t)return null;let n=${validator}(e instanceof Map?e.get(t):e&&"object"==typeof e&&!Array.isArray(e)?e[t]:void 0);if(n)return n;let o=[],s=e instanceof Map?e.values():e&&"object"==typeof e&&!Array.isArray(e)?Object.values(e):[];for(let e of s){let n=${validator}(e);if(!n)continue;let s=[n.namespace+"__"+n.name,n.namespace+"_"+n.name,n.namespace+"."+n.name,n.name].some(e=>e.trim().replace(/[^a-zA-Z0-9_]/g,"_").replace(/_+/g,"_").replace(/^_+|_+$/g,"")===t);s&&o.push(n)}return 1===o.length?o[0]:null}`;
  });
  const restored = updated.split(restorePattern).join(restoreReplacement);
  if (matches > 0 || restored !== updated) fs.writeFileSync(path, restored);
}
