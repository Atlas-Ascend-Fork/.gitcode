// Copyright (c) 2026 Huawei Technologies Co., Ltd.
// This file is a part of the CANN Open Software.
// Licensed under CANN Open Software License Agreement Version 2.0 (the "License").
// Please refer to the License for details. You may not use this file except in compliance with the License.

'use strict';

const assert = require('assert').strict;
const childProcess = require('child_process');
const { EventEmitter } = require('events');
const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');

// Run the shipped action, replacing only its shell workload with a local fixture.
// An optional bundle path allows the same tests to demonstrate the old failure.
const bundlePath = process.argv[2] || path.join(__dirname, '../dist/main.js');
const bundle = fs.readFileSync(bundlePath, 'utf8');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'check-pr-output-'));
const actionPath = path.join(directory, 'main.js');
const scriptPath = path.join(directory, 'check_pr.sh');
const env = {
    ...process.env,
    INPUT_WORKSPACE: directory,
    INPUT_REPO_NAME: 'local-fixture',
    INPUT_TARGET_BRANCH: 'master',
    TEST_NODE: process.execPath,
};
fs.writeFileSync(actionPath, bundle);

function runAction(script) {
    fs.writeFileSync(scriptPath, script);
    const result = childProcess.spawnSync(process.execPath, [actionPath], {
        cwd: directory,
        env,
        encoding: 'utf8',
        timeout: 5000,
        maxBuffer: 16 * 1024 * 1024,
    });
    assert.ifError(result.error);
    return result;
}

function assertPass(result) {
    assert.equal(result.status, 0, result.stdout.slice(-500));
    assert.match(result.stdout, /check_pr.sh 执行完成/);
}

function outputScript(stream, exitCode = 0) {
    return `exec "$TEST_NODE" -e 'process.${stream}.write("BEGIN_OF_OUTPUT"); process.${stream}.write("Z".repeat(2 * 1024 * 1024)); process.${stream}.write("END_OF_OUTPUT"); process.exitCode = ${exitCode};'\n`;
}

// Only timeout/error/argv controls need direct access to this internal helper.
// Extract it from the same shipped bundle; do not maintain a copied implementation.
function loadRunner(overrides = {}, info = () => {}, timer = setTimeout) {
    const start = bundle.indexOf('function execShellScript(');
    const end = bundle.indexOf('\nrun();', start);
    assert(start >= 0 && end > start, 'Cannot locate shipped process wrapper');
    const context = {
        child_process_1: { ...childProcess, ...overrides },
        core: { info, error: () => {} },
        setTimeout: timer,
        clearTimeout,
    };
    vm.createContext(context);
    vm.runInContext(bundle.slice(start, end), context);
    return context.execShellScript;
}

const tests = [
    ['empty successful command', () => assertPass(runAction('exit 0\n'))],
    ...['stdout', 'stderr'].map(stream => [`2 MiB ${stream}`, () => {
        const result = runAction(outputScript(stream));
        assertPass(result);
        const payload = result.stdout.split("BEGIN_OF_OUTPUT")[1]?.split("END_OF_OUTPUT")[0];
        assert.notEqual(payload, undefined);
        assert.equal((payload.match(/Z/g) || []).length, 2 * 1024 * 1024);
        assert.match(result.stdout, /END_OF_OUTPUT/);
    }]),
    ...['stdout', 'stderr'].map(stream => [`split UTF-8 on ${stream}`, () => {
        const result = runAction(`exec "$TEST_NODE" -e 'process.${stream}.write(Buffer.from([0xe4])); setTimeout(() => process.${stream}.write(Buffer.from([0xb8, 0xad])), 100);'\n`);
        assertPass(result);
        assert.match(result.stdout, /中/);
        assert.doesNotMatch(result.stdout, /\uFFFD/);
    }]),
    ['large output preserves shell failure', () => {
        const result = runAction(outputScript('stdout', 23));
        assert.equal(result.status, 1);
        assert.match(result.stdout, /END_OF_OUTPUT/);
        assert.match(result.stdout, /exit code: 23/);
        assert.doesNotMatch(result.stdout, /check_pr.sh 执行完成/);
    }],
    ['signal termination remains a failure', () => {
        const result = runAction('kill -TERM $$\n');
        assert.equal(result.status, 1);
        assert.match(result.stdout, /signal: SIGTERM/);
    }],
    ['missing shell script remains a failure', () => {
        fs.unlinkSync(scriptPath);
        const result = childProcess.spawnSync(process.execPath, [actionPath], {
            cwd: directory, env, encoding: 'utf8', timeout: 5000,
        });
        assert.ifError(result.error);
        assert.equal(result.status, 1);
        assert.match(result.stdout, /ENOENT/);
    }],
    ['ten-minute timeout is retained and rejects on expiry', async () => {
        let child;
        const bounded = name => (command, args, options, ...rest) => {
            // The baseline uses the built-in execFile timeout.
            if (name === 'execFile') {
                assert.equal(options.timeout, 600000);
                options = { ...options, timeout: 100 };
            }
            child = childProcess[name](command, args, options, ...rest);
            return child;
        };
        const timer = (callback, milliseconds) => {
            assert.equal(milliseconds, 600000);
            return setTimeout(callback, 100);
        };
        const run = loadRunner({ spawn: bounded('spawn'), execFile: bounded('execFile') }, () => {}, timer);
        fs.writeFileSync(scriptPath, 'exec "$TEST_NODE" -e "setInterval(() => {}, 1000)"\n');
        await assert.rejects(run(scriptPath, [], directory, env), /signal: SIGTERM|执行超时/);
        assert.equal(child.signalCode, 'SIGTERM');
        assert.throws(() => process.kill(child.pid, 0), { code: 'ESRCH' });
    }],
    ['spawn error rejects', async () => {
        const run = loadRunner({ spawn: () => {
            const child = new EventEmitter();
            process.nextTick(() => child.emit('error', Object.assign(new Error('spawn ENOENT'), { code: 'ENOENT' })));
            return child;
        } });
        await assert.rejects(run(scriptPath, [], directory, env), { code: 'ENOENT' });
    }],
    ['timeout cannot become success when the shell handles SIGTERM', async () => {
        const timer = (callback, milliseconds) => {
            assert.equal(milliseconds, 600000);
            return setTimeout(callback, 100);
        };
        const execFile = (command, args, options) => childProcess.execFile(command, args, {
            ...options, timeout: 100,
        });
        const run = loadRunner({ execFile }, () => {}, timer);
        fs.writeFileSync(scriptPath, "trap 'exit 0' TERM\nwhile :; do :; done\n");
        await assert.rejects(run(scriptPath, [], directory, env), /执行超时/);
    }],
    ['cwd, environment and literal arguments are preserved', async () => {
        let output = '';
        const run = loadRunner({}, text => { output += text; });
        fs.writeFileSync(scriptPath, 'printf "%s|%s|%s" "$PWD" "$TEST_VALUE" "$1"\n');
        const argument = 'space ; $(not-a-command)';
        await run(scriptPath, [argument], directory, { ...env, TEST_VALUE: 'value with spaces' });
        assert.equal(output, `${fs.realpathSync(directory)}|value with spaces|${argument}`);
    }],
];

(async () => {
    let failed = 0;
    try {
        for (const [name, test] of tests) {
            try {
                await test();
                console.log(`PASS ${name}`);
            } catch (error) {
                failed += 1;
                console.error(`FAIL ${name}: ${error.message.slice(-1200)}`);
            }
        }
    } finally {
        fs.rmSync(directory, { recursive: true, force: true });
    }
    console.log(`${tests.length - failed}/${tests.length} passed`);
    process.exitCode = failed ? 1 : 0;
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
