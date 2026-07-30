import * as core from '@actions/core';
import { execFile } from 'child_process';
import { resolve } from 'path';
import { access } from 'fs/promises';

async function run(): Promise<void> {
  try {
    const owner = core.getInput('owner', { required: true });
    const repo = core.getInput('repo', { required: true });
    const prNumber = core.getInput('pr_number', { required: true });
    const token = core.getInput('token', { required: true });
    const applyLabel = core.getInput('apply_label', { required: false }) || 'true';

    const scriptPath = resolve(__dirname, './pre_pipeline.py');
    try {
      await access(scriptPath);
    } catch {
      throw new Error(`脚本文件不存在：${scriptPath}`);
    }

    core.info(`脚本路径：${scriptPath}`);
    core.info(`owner：${owner}`);
    core.info(`repo：${repo}`);
    core.info(`pr_number：${prNumber}`);
    core.info(`apply_label：${applyLabel}`);

    await execPython(scriptPath, [
      '--owner', owner,
      '--repo', repo,
      '--pr_number', prNumber,
      '--token', token,
      '--apply_label', applyLabel,
    ]);
    core.info('pre_pipeline 脚本执行完成');
  } catch (err) {
    const error = err as Error;
    core.setFailed(error.message);
  }
}

function execPython(script: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = execFile('python3', [script, ...args], {
      timeout: 60000,
    });
    child.stdout?.on('data', (data) => {
      core.info(data.toString().trimEnd());
    });
    child.stderr?.on('data', (data) => {
      core.info(data.toString().trimEnd());
    });
    child.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`python脚本异常退出，exit code: ${code}`));
      }
    });
    child.on('error', (err) => reject(err));
  });
}

run();
