/******/ (() => { // webpackBootstrap
/******/ 	var __webpack_modules__ = ({
/***/ 1188:
/***/ (function(__unused_webpack_module, exports, __nccwpck_require__) {
"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", ({ value: true }));
const core = __importStar(__nccwpck_require__(7484));
const child_process_1 = __nccwpck_require__(5317);
const path_1 = __importDefault(__nccwpck_require__(6928));
const promises_1 = __importDefault(__nccwpck_require__(1943));
async function run() {
    try {
        const owner = core.getInput("owner", { required: true });
        const repo = core.getInput("repo", { required: true });
        const prNumber = core.getInput("pr_number", { required: true });
        const token = core.getInput("token", { required: true });
        const applyLabel = core.getInput("apply_label", { required: false }) || "true";
        const scriptPath = path_1.default.resolve(__dirname, "./pre_pipeline.py");
        try {
            await promises_1.default.access(scriptPath);
        }
        catch {
            throw new Error(`脚本文件不存在：${scriptPath}`);
        }
        core.info(`脚本路径：${scriptPath}`);
        core.info(`owner：${owner}`);
        core.info(`repo：${repo}`);
        core.info(`pr_number：${prNumber}`);
        core.info(`apply_label：${applyLabel}`);
        const args = [
            scriptPath,
            "--owner", owner,
            "--repo", repo,
            "--pr_number", prNumber,
            "--token", token,
            "--apply_label", applyLabel,
        ];
        await execPython(args);
        core.info("pre_pipeline 脚本执行完成");
    }
    catch (err) {
        const error = err;
        core.setFailed(error.message);
    }
}
function execPython(args) {
    return new Promise((resolve, reject) => {
        const child = (0, child_process_1.execFile)("python3", args, {
            timeout: 60000,
        });
        child.stdout?.on("data", (data) => {
            core.info(data.toString().trimEnd());
        });
        child.stderr?.on("data", (data) => {
            core.info(data.toString().trimEnd());
        });
        child.on("close", (code) => {
            if (code === 0)
                resolve();
            else
                reject(new Error(`python脚本异常退出，exit code: ${code}`));
        });
        child.on("error", (err) => reject(err));
    });
}
run();
/***/ }),
/***/ 7484:
/***/ (function(__unused_webpack_module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.getInput = exports.info = exports.setFailed = void 0;
function setFailed(message) { console.error(`::error::${message}`); process.exit(1); }
exports.setFailed = setFailed;
function info(message) { console.log(message); }
exports.info = info;
function getInput(name, options) {
    const val = process.env[`INPUT_${name.toUpperCase()}`] || "";
    if (options?.required && !val) {
        throw new Error(`Input required and not supplied: ${name}`);
    }
    return val;
}
exports.getInput = getInput;
/***/ }),
/***/ 5317:
/***/ (function(__unused_webpack_module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.execFile = void 0;
const child_process = require("child_process");
exports.execFile = child_process.execFile;
/***/ }),
/***/ 6928:
/***/ (function(__unused_webpack_module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", ({ value: true }));
const path = require("path");
exports.default = path;
/***/ }),
/***/ 1943:
/***/ (function(__unused_webpack_module, exports) {
"use strict";
Object.defineProperty(exports, "__esModule", ({ value: true }));
const fs = require("fs").promises;
exports.default = fs;
/***/ })
/******/ 	});
/******/ 	var __webpack_exports__ = {};
/******/ 	__webpack_modules__[1188](0, __webpack_exports__);
/******/ 	return __webpack_exports__;
/******/ })()
;
