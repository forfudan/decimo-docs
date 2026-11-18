// Makes the search find a method by its own name.
//
//   node scripts/patch_search.js book
//
// mdBook splits the text into words only at spaces and dashes, so
// `x.bit_length()` and `BInt.from_string()` are stored as the single words
// `x.bit_length` and `bint.from_string`, and a search for `bit_length` finds
// neither. This adds, for every stored word, the parts that start after a
// dot or an underscore: `bit_length` and `length` for `x.bit_length`,
// `divmod` for `a.__divmod__`. Each part points at the same pages as the whole
// word. It runs after `mdbook build` and rewrites book/searchindex-*.js in
// place. It needs only Node and the elasticlunr that mdBook ships in book/.

"use strict";
const fs = require("fs");
const path = require("path");

const dir = process.argv[2] || "book";
const find = (prefix) => {
  const name = fs.readdirSync(dir).find((f) => f.startsWith(prefix) && f.endsWith(".js"));
  if (!name) throw new Error(`no ${prefix}*.js in ${dir}`);
  return path.join(dir, name);
};

// elasticlunr is a UMD file; give it a `module` to fill.
const lunr = { exports: {} };
new Function("module", "exports", fs.readFileSync(find("elasticlunr"), "utf8"))(lunr, lunr.exports);
const elasticlunr = lunr.exports;

// The index file assigns to `window.search`; run it against a stand-in.
const indexFile = find("searchindex");
const window = { search: {} };
new Function("window", fs.readFileSync(indexFile, "utf8"))(window);
const search = window.search;
const idx = elasticlunr.Index.load(search.index);

// The parts of a word that start after a `.` or a `_`, without leading
// underscores, at least two characters long.
function parts(word) {
  const out = new Set();
  for (let i = 0; i < word.length; i++) {
    if (word[i] !== "." && word[i] !== "_") continue;
    const rest = word.slice(i + 1).replace(/^_+/, "").replace(/_+$/, "");
    if (rest.length >= 2 && rest !== word) out.add(rest);
  }
  return out;
}

// Every word stored in a field's tree of characters.
function allWords(node, prefix, out) {
  if (node.docs && Object.keys(node.docs).length) out.push(prefix);
  for (const key of Object.keys(node)) {
    if (key !== "docs" && key !== "df") allWords(node[key], prefix + key, out);
  }
  return out;
}

let added = 0;
for (const field of idx.getFields()) {
  const inverted = idx.index[field];
  const words = allWords(inverted.root, "", []);
  for (const word of words) {
    if (!/[._]/.test(word)) continue;
    const docs = inverted.getDocs(word);
    for (const part of parts(word)) {
      for (const token of idx.pipeline.run([part])) {
        for (const ref of Object.keys(docs)) {
          const tf = docs[ref].tf + inverted.getTermFrequency(token, ref);
          if (!Object.keys(inverted.getDocs(token)).length) added++;
          inverted.addToken(token, { ref, tf });
        }
      }
    }
  }
}

search.index = idx.toJSON();
fs.writeFileSync(
  indexFile,
  "window.search = Object.assign(window.search, JSON.parse(" +
    JSON.stringify(JSON.stringify(search)) +
    "));\n",
);
console.log(`patch_search: ${added} words added to ${path.basename(indexFile)}`);
