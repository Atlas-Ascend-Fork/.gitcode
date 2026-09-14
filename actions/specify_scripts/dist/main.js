const crypto = require('crypto');
const fs = require('fs');
const https = require('https');
const path = require('path');
const { execFileSync } = require('child_process');

const CI_REPO_URL = 'https://gitcode.com/opencann/.gitcode.git';
const CLONE_TIMEOUT_MS = 5 * 60 * 1000;
const OBS_TIMEOUT_MS = 60 * 1000;

function getInput(name, required) {
    const val = (process.env[`INPUT_${name.replace(/ /g, '_').toUpperCase()}`] || '').trim();
    if (required && !val) throw new Error(`Input required and not supplied: ${name}`);
    return val;
}

function setFailed(msg) {
    console.log(`::error::${String(msg).replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A')}`);
    process.exitCode = 1;
}

function collectFiles(rootDir, relDir = '', acc = []) {
    for (const entry of fs.readdirSync(relDir ? path.join(rootDir, relDir) : rootDir, { withFileTypes: true })) {
        const rel = relDir ? `${relDir}/${entry.name}` : entry.name;
        if (entry.isDirectory()) collectFiles(rootDir, rel, acc);
        else if (entry.isFile()) acc.push(rel);
    }
    return acc;
}

function obsPutFile(endpoint, bucket, ak, sk, key, filePath) {
    return new Promise((resolve, reject) => {
        const host = new URL(endpoint).hostname;
        const date = new Date().toUTCString();
        const stringToSign = `PUT\n\n\n${date}\n/${bucket}/${key}`;
        const signature = crypto.createHmac('sha1', sk).update(stringToSign).digest('base64');
        const req = https.request({
            hostname: `${bucket}.${host}`,
            path: '/' + key.split('/').map(encodeURIComponent).join('/'),
            method: 'PUT',
            headers: {
                Date: date,
                Authorization: `OBS ${ak}:${signature}`,
                'Content-Length': fs.statSync(filePath).size
            },
            timeout: OBS_TIMEOUT_MS
        }, res => {
            let body = '';
            res.on('data', c => { body += c; });
            res.on('end', () => {
                if (res.statusCode < 300) return resolve(res.statusCode);
                const m = /<Message>([^<]*)<\/Message>/.exec(body);
                reject(new Error(`OBS 上传失败，status=${res.statusCode}${m ? '，' + m[1] : ''}，key=${key}`));
            });
        });
        req.on('error', reject);
        req.on('timeout', () => req.destroy(new Error(`OBS 上传超时（${OBS_TIMEOUT_MS / 1000}s），key=${key}`)));
        fs.createReadStream(filePath).pipe(req);
    });
}

async function run() {
    let ciBranch = '';
    let scriptsRoot = '';
    let specifiedCount = 0;
    try {
        const repoName = getInput('repo_name', true);
        const comment = getInput('comment');
        const token = getInput('token');
        const endpoint = getInput('endpoint', true);
        const bucket = getInput('bucket', true);
        const ak = getInput('access-key', true);
        const sk = getInput('secret-key', true);
        const objectPrefix = getInput('object-prefix', true).replace(/^\/+|\/+$/g, '');

        const m = comment.match(/compile[^@]*@(\S+)/i);
        ciBranch = m ? m[1] : '';
        if (!ciBranch) {
            console.log('comment 中未解析到 compile 后的 @<分支>，跳过脚本指定');
            return;
        }
        console.log(`拉取分支：${ciBranch}（使用 ci 仓库分支脚本）`);
        console.log(`仓库名：${repoName}`);
        if (token) {
            execFileSync('git', ['config', '--global', `url.https://cann-robot:${token}@gitcode.com/.insteadOf`, 'https://gitcode.com/']);
        }
        try {
            execFileSync('git', ['clone', '-b', ciBranch, CI_REPO_URL, 'cann-ci', '--depth', '1'], { stdio: 'inherit', timeout: CLONE_TIMEOUT_MS });
        } catch (e) {
            console.log(`::warning::分支 ${ciBranch} 拉取失败（请检查 opencann/.gitcode 上是否存在该分支、token 是否有权限、网络是否超时），本次使用默认上传的脚本`);
            return;
        }

        scriptsRoot = path.resolve('cann-ci', 'scripts', repoName);
        if (!fs.existsSync(scriptsRoot) || !fs.statSync(scriptsRoot).isDirectory()) {
            console.log(`::warning::分支 ${ciBranch} 上不存在脚本目录 scripts/${repoName}，本次使用默认上传的脚本`);
            return;
        }
        const files = collectFiles(scriptsRoot);
        if (files.length === 0) {
            console.log(`::warning::分支 ${ciBranch} 上脚本目录 scripts/${repoName} 为空，本次使用默认上传的脚本`);
            return;
        }

        console.log(`开始上传 ${files.length} 个脚本到 obs://${bucket}/${objectPrefix} ...`);
        const failed = [];
        for (const rel of files) {
            const key = objectPrefix ? `${objectPrefix}/${rel}` : rel;
            try {
                await obsPutFile(endpoint, bucket, ak, sk, key, path.join(scriptsRoot, ...rel.split('/')));
                specifiedCount++;
                console.log(`上传成功：${key}`);
            } catch (e) {
                failed.push(`${key}: ${e.message}`);
            }
        }
        if (failed.length > 0) throw new Error(`以下脚本上传失败：\n${failed.join('\n')}`);
        console.log(`全部脚本上传完成（${specifiedCount}/${files.length}）`);
    } catch (e) {
        setFailed(e.message);
    } finally {
        const filePath = process.env.ATOMGIT_OUTPUT;
        if (filePath) fs.appendFileSync(filePath, `ci_branch=${ciBranch}\nscripts_path=${scriptsRoot}\nspecified_files=${specifiedCount}\n`, 'utf8');
        else console.error('获取输出路径失败: ATOMGIT_OUTPUT');
    }
}

run();
