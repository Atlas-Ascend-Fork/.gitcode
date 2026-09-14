/**
 * setup-python (GitCode action) — 参考 actions/setup-python 的语义实现。
 *
 * 实现细节澄清（与 GitHub 原版对齐/差异点）：
 *
 * 1. 版本解析（对齐原版 getInput 语义 + SemVer 范围）：
 *    - 优先级: python-version 输入 > python-version-file > .python-version > PATH 默认
 *    - 支持: '3.12' / '3.12.x' / '>=3.10,<3.13' / '~3.11'
 *    - GitHub 原版从 actions/python-versions releases 下载构建好的解释器；
 *      GitCode 自托管 runner 多为内网，本版改为「本地候选集解析」：
 *      a) /opt/buildtools/python-<v>/bin（CANN CI 镜像预装位）
 *      b) /usr/local/bin/python<v> / /usr/bin/python<v>（deadsnakes 常见位）
 *      c) uv 管理的 ~/.local/share/uv/python/cpython-<v>（若装了 uv）
 *    - 不做在线下载（内网约束 + 供应链安全），缺失时按 allow-missing 决策
 *
 * 2. PATH 注入（对齐 toolkit core.addPath）：
 *    - 命中目录加入 GITHUB_PATH（GitCode runner 同样消费该文件）
 *    - 同时 exportVariable 指针变量 PYTHON_<X>_<Y>_ROOT 供后续步骤引用
 *
 * 3. venv（原版没有，CANN 场景增量）：
 *    - create-venv: true 时用命中解释器 python -m venv <venv-path>
 *    - venv bin 目录同样 addPath，并 export VIRTUAL_ENV（pip 语义对齐）
 *
 * 4. 输出（对齐原版 outputs）：
 *    - python-path / python-version / installed
 */
const core = require('@actions/core');
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

// ---------- 版本范围匹配（SemVer 子集，无外部依赖） ----------
function parseSpec(raw) {
  // 返回 [{op, ver}]；'3.12' 精确主次；'3.12.x' 补丁任意
  if (!raw) return [];
  return raw.split(',').map((s) => s.trim()).filter(Boolean).map((atom) => {
    const m = atom.match(/^(>=|<=|>|<|~|\^|=)?\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?$|^(\d+)\.x$|^(\d+)\.(\d+)\.x$/);
    if (!m) return { op: '=', ver: [0, 0, 0], raw: atom };
    if (m[4]) return { op: '=', ver: [parseInt(m[4]), -1, -1], raw: atom };        // 3.x → 主版本任意次
    if (m[7]) return { op: '=', ver: [parseInt(m[5]), parseInt(m[6]), -1], raw: atom }; // 3.12.x
    const op = m[1] || '=';
    const ver = [parseInt(m[2] || 0), m[3] !== undefined ? parseInt(m[3]) : -1, m[4] !== undefined && m[4] !== null && m[4] !== '' ? parseInt(m[4]) : -1];
    return { op, ver, raw: atom };
  });
}

function cmpVer(a, b) {
  for (let i = 0; i < 3; i++) {
    const x = a[i] === -1 ? 0 : a[i];
    const y = b[i] === -1 ? 0 : b[i];
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

function matches(actual, specAtoms) {
  if (specAtoms.length === 0) return true;
  return specAtoms.every((a) => {
    // 精确语义: 声明的每一位必须相等（未声明位任意）
    if (a.op === '=') {
      if (a.ver[0] !== -1 && a.ver[0] !== actual[0]) return false;
      if (a.ver[1] !== -1 && a.ver[1] !== actual[1]) return false;
      if (a.ver[2] !== -1 && a.ver[2] !== actual[2]) return false;
      return true;
    }
    if (a.op === '~') { // ~3.11 → >=3.11.0,<3.12.0
      const lo = [a.ver[0], a.ver[1] === -1 ? 0 : a.ver[1], 0];
      const hi = [a.ver[0], (a.ver[1] === -1 ? 0 : a.ver[1]) + 1, 0];
      return cmpVer(actual, lo) >= 0 && cmpVer(actual, hi) < 0;
    }
    if (a.op === '^') { // ^3.11 → >=3.11.0,<4.0.0
      const lo = [a.ver[0], a.ver[1] === -1 ? 0 : a.ver[1], 0];
      const hi = [a.ver[0] + 1, 0, 0];
      return cmpVer(actual, lo) >= 0 && cmpVer(actual, hi) < 0;
    }
    const c = cmpVer(actual, a.ver.map((v) => (v === -1 ? 0 : v)));
    if (a.op === '>=') return c >= 0;
    if (a.op === '<=') return c <= 0;
    if (a.op === '>') return c > 0;
    if (a.op === '<') return c < 0;
    return true;
  });
}

// ---------- 本地候选集扫描 ----------
function scanCandidates() {
  const found = []; // {exe, ver:[x,y,z], root}
  const roots = [
    '/opt/buildtools',                       // CANN CI 预装位 python-3.10.2/
    '/usr/local/bin',
    '/usr/bin',
  ];
  // uv 管理的 python
  const uvPy = path.join(os.homedir(), '.local/share/uv/python');
  if (fs.existsSync(uvPy)) roots.push(uvPy);

  for (const root of roots) {
    let entries = [];
    try { entries = fs.readdirSync(root); } catch { continue; }
    for (const e of entries) {
      let exe = null, ver = null;
      // 形式1: <root>/python-3.10.2/bin/python3
      let m = e.match(/^python-(3)(\d+)$/);
      if (m && fs.statSync(path.join(root, e)).isDirectory()) {
        const p = path.join(root, e, 'bin', 'python3');
        if (fs.existsSync(p)) { exe = p; ver = [3, parseInt(m[2] / 10), parseInt(m[2] % 10)]; }
      }
      // uv 形式: cpython-3.12.7-.../bin/python3
      m = e.match(/^cpython-(\d+)\.(\d+)\.(\d+)/);
      if (m && fs.statSync(path.join(root, e)).isDirectory()) {
        const p = path.join(root, e, 'bin', 'python3');
        if (fs.existsSync(p)) { exe = p; ver = [+m[1], +m[2], +m[3]]; }
      }
      // 形式2: <root>/python3.12
      m = e.match(/^python3\.(\d+)$/);
      if (m) {
        const p = path.join(root, e);
        if (fs.existsSync(p)) { exe = p; ver = [3, parseInt(m[1]), 0]; }
      }
      if (exe && !found.some((f) => f.exe === exe)) {
        // 实测精确版本（patch 位）
        try {
          const out = execSync(`"${exe}" -c "import sys;print('%d.%d.%d'%sys.version_info[:3])"`, { encoding: 'utf8', timeout: 15000 }).trim();
          const v = out.match(/^(\d+)\.(\d+)\.(\d+)$/);
          if (v) ver = [+v[1], +v[2], +v[3]];
        } catch { /* 用扫描位近似 */ }
        found.push({ exe, ver, root: path.dirname(path.dirname(exe)) });
      }
    }
  }
  // 形式3: PATH 上的 python3（保底）
  try {
    const p = execSync('command -v python3', { encoding: 'utf8', shell: '/bin/bash' }).trim();
    const out = execSync(`"${p}" -c "import sys;print('%d.%d.%d'%sys.version_info[:3])"`, { encoding: 'utf8' }).trim();
    const v = out.match(/^(\d+)\.(\d+)\.(\d+)$/);
    if (v && !found.some((f) => f.exe === p)) found.push({ exe: p, ver: [+v[1], +v[2], +v[3]], root: path.dirname(p) });
  } catch { /* 无 python3 极端场景 */ }
  return found;
}

// ---------- 主流程 ----------
async function run() {
  let specRaw = core.getInput('python-version');
  const specFile = core.getInput('python-version-file');
  const registerAll = core.getInput('register-all') === 'true';
  const createVenv = core.getInput('create-venv') === 'true';
  const venvPath = core.getInput('venv-path') || '.venv';
  const allowMissing = core.getInput('allow-missing') === 'false' ? false : true;
  const archInput = core.getInput('architecture');

  if (archInput && archInput !== 'x64' && archInput !== process.arch) {
    core.info(`architecture=${archInput} 与宿主 ${process.arch} 不一致（本版按宿主处理，交叉解释器需自行预装）`);
  }

  // 1. 版本声明解析（input > file > .python-version > 默认）
  if (!specRaw) {
    const file = specFile || '.python-version';
    if (fs.existsSync(file)) {
      specRaw = fs.readFileSync(file, 'utf8').split('\n').map((l) => l.trim()).filter(Boolean)[0] || '';
      core.info(`从 ${file} 读取版本: ${specRaw}`);
    }
  }
  if (!specRaw) {
    core.warning('未指定 python-version 且无 .python-version 文件，使用 PATH 默认 python3');
  }

  // 2. 候选集解析
  const candidates = scanCandidates();
  core.info(`本地候选: ${candidates.map((c) => c.ver.join('.')).join(', ') || '(仅 PATH)'}`);

  const specAtoms = parseSpec(specRaw);
  let hits = candidates.filter((c) => matches(c.ver, specAtoms));
  hits.sort((a, b) => cmpVer(b.ver, a.ver)); // 高版本优先

  if (hits.length === 0) {
    const sysPy = candidates[candidates.length - 1];
    if (allowMissing) {
      core.warning(`未找到满足 "${specRaw}" 的本地 Python，回退系统 ${sysPy ? sysPy.ver.join('.') : 'python3'}`);
      hits = sysPy ? [sysPy] : [];
    } else {
      core.setFailed(`未找到满足 "${specRaw}" 的 Python。可用: ${candidates.map((c) => c.ver.join('.')).join(', ')}。
本地解析范围: /opt/buildtools, /usr/local/bin, /usr/bin, uv python 目录。
在线安装未启用（内网/供应链安全约束）；如需精确版本请预装到上述位置或安装 uv。`);
      return;
    }
  }

  const picked = hits[0];
  core.info(`命中 Python ${picked.ver.join('.')} → ${picked.exe}`);

  // 3. PATH 注入（GITHUB_PATH 由 runner 消费；GITHUB_ENV 同理）
  const binDir = path.dirname(picked.exe);
  if (registerAll) {
    for (const h of hits) core.addPath(path.dirname(h.exe));
    core.info(`register-all: ${hits.map((h) => h.ver.join('.')).join(', ')} 均已加入 PATH`);
  } else {
    core.addPath(binDir);
  }
  const majorMinor = `${picked.ver[0]}${picked.ver[1]}`;
  core.exportVariable(`PYTHON_${picked.ver[0]}${picked.ver[1]}_ROOT`, picked.root);
  core.exportVariable('PYTHON_VERSION', picked.ver.join('.'));
  core.setOutput('python-path', picked.exe);
  core.setOutput('python-version', picked.ver.join('.'));
  core.setOutput('installed', 'true'); // 本地复用语义

  // 4. 可选 venv（原版没有，CANN 多 python 生态隔离需要）
  if (createVenv) {
    const vp = path.resolve(venvPath);
    if (!fs.existsSync(vp)) {
      core.info(`创建 venv: ${vp}`);
      execSync(`"${picked.exe}" -m venv "${vp}"`, { stdio: 'inherit', timeout: 120000 });
    } else {
      core.info(`venv 已存在，复用: ${vp}`);
    }
    const venvBin = path.join(vp, 'bin');
    core.addPath(venvBin);
    core.exportVariable('VIRTUAL_ENV', vp);
    core.info(`venv bin 已加入 PATH: ${venvBin}`);
  }

  // 5. 环境摘要
  core.info(`== setup-python 完成 ==`);
  core.info(`python-path : ${picked.exe}`);
  core.info(`python-ver  : ${picked.ver.join('.')}`);
  core.info(`PATH+       : ${binDir}${createVenv ? ' , ' + path.resolve(venvPath, 'bin') : ''}`);
  core.info(`majorMinor  : ${majorMinor} (PYTHON_${majorMinor}_ROOT 已导出)`);
}

run().catch((e) => core.setFailed(e.message));
