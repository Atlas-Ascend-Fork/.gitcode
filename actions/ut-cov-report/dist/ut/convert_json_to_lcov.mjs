import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const [,, inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error('Usage: node convert_json_to_lcov.mjs <input.json> <output.lcov>');
  process.exit(1);
}

const coverageJson = JSON.parse(readFileSync(inputPath, 'utf8'));

let lcov = '';
for (const [fileKey, cov] of Object.entries(coverageJson)) {
  const filePath = cov.path || fileKey;
  const fnMap = cov.fnMap || {};
  const f = cov.f || {};
  const branchMap = cov.branchMap || {};
  const b = cov.b || {};
  const statementMap = cov.statementMap || {};
  const s = cov.s || {};

  lcov += `TN:\nSF:${filePath}\n`;

  let fnf = 0;
  let fnh = 0;
  for (const [id, fn] of Object.entries(fnMap)) {
    const declLine = (fn.decl && fn.decl.start && fn.decl.start.line) || fn.line || 0;
    lcov += `FN:${declLine},${fn.name}\n`;
  }
  for (const [id, fn] of Object.entries(fnMap)) {
    const count = f[id] || 0;
    if (count > 0) fnh += 1;
    fnf += 1;
    lcov += `FNDA:${count},${fn.name}\n`;
  }
  lcov += `FNF:${fnf}\nFNH:${fnh}\n`;

  let brf = 0;
  let brh = 0;
  for (const [id, br] of Object.entries(branchMap)) {
    const locations = br.locations || [];
    locations.forEach((loc, i) => {
      const taken = (b[id] && b[id][i] !== undefined) ? b[id][i] : '-';
      if (taken !== '-' && taken > 0) brh += 1;
      brf += 1;
      const branchLine = (loc && loc.start && loc.start.line) || br.line || 0;
      lcov += `BRDA:${branchLine},${id},${i},${taken}\n`;
    });
  }
  lcov += `BRF:${brf}\nBRH:${brh}\n`;

  const lineHits = new Map();
  for (const [id, st] of Object.entries(statementMap)) {
    const count = s[id] || 0;
    if (!st || !st.start || !st.end) continue;
    for (let line = st.start.line; line <= st.end.line; line += 1) {
      if (count > (lineHits.get(line) || 0)) {
        lineHits.set(line, count);
      } else if (!lineHits.has(line)) {
        lineHits.set(line, 0);
      }
    }
  }
  const lines = [...lineHits.keys()].sort((x, y) => x - y);
  for (const line of lines) {
    lcov += `DA:${line},${lineHits.get(line)}\n`;
  }
  lcov += `LF:${lines.length}\n`;
  lcov += `LH:${lines.filter((line) => lineHits.get(line) > 0).length}\n`;
  lcov += 'end_of_record\n';
}

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, lcov);
console.log(`Converted ${inputPath} -> ${outputPath}`);
