#!/usr/bin/env node

/**
 * Chess Engine CLI Tool
 * 
 * Manage builds, server, and engine configuration.
 * 
 * Usage:
 *   chess-engine              # Interactive mode
 *   chess-engine build v6     # Build V6 C++ engine
 *   chess-engine build client # Build frontend
 *   chess-engine start        # Start server
 *   chess-engine run-all      # Build everything and start
 */

const { execFileSync, execSync, spawn } = require('child_process');
const readline = require('readline');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { loadConfig, saveConfig, setConfigValue } = require('./config.js');

// Project root directory
const ROOT_DIR = path.resolve(__dirname, '..', '..');
const CLIENT_DIR = path.join(ROOT_DIR, 'client');
const UV_CACHE_DIR = path.join(ROOT_DIR, '.uv-cache');

// ANSI color codes
const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    dim: '\x1b[2m',
    red: '\x1b[31m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    magenta: '\x1b[35m',
    cyan: '\x1b[36m',
    white: '\x1b[37m',
    bgBlue: '\x1b[44m',
    bgGreen: '\x1b[42m',
};

function log(message, color = colors.reset) {
    console.log(`${color}${message}${colors.reset}`);
}

function logSuccess(message) {
    log(`✓ ${message}`, colors.green);
}

function logError(message) {
    log(`✗ ${message}`, colors.red);
}

function logWarning(message) {
    log(`⚠ ${message}`, colors.yellow);
}

function printHeader(title) {
    log(`\n${'═'.repeat(60)}`, colors.cyan);
    log(`  ${title}`, colors.bright);
    log(`${'═'.repeat(60)}`, colors.cyan);
}

function printSubHeader(title) {
    log(`\n${'─'.repeat(50)}`, colors.dim);
    log(`  ${title}`, colors.bright);
    log(`${'─'.repeat(50)}`, colors.dim);
}

/**
 * Spinner class for loading animation
 */
class Spinner {
    constructor(message) {
        this.message = message;
        this.frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
        this.frameIndex = 0;
        this.interval = null;
    }

    start() {
        process.stdout.write(`${colors.cyan}${this.frames[0]}${colors.reset} ${this.message}`);
        this.interval = setInterval(() => {
            this.frameIndex = (this.frameIndex + 1) % this.frames.length;
            process.stdout.clearLine(0);
            process.stdout.cursorTo(0);
            process.stdout.write(`${colors.cyan}${this.frames[this.frameIndex]}${colors.reset} ${this.message}`);
        }, 80);
    }

    stop(success = true) {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
        process.stdout.clearLine(0);
        process.stdout.cursorTo(0);
        if (success) {
            console.log(`${colors.green}✓${colors.reset} ${this.message}`);
        } else {
            console.log(`${colors.red}✗${colors.reset} ${this.message}`);
        }
    }
}

/**
 * Execute command with spinner
 */
function execWithSpinner(command, message, cwd = ROOT_DIR) {
    const spinner = new Spinner(message);
    spinner.start();
    try {
        const output = execSync(command, {
            encoding: 'utf-8',
            stdio: 'pipe',
            cwd: cwd,
        });
        spinner.stop(true);
        return output.trim();
    } catch (error) {
        spinner.stop(false);
        throw error;
    }
}

/**
 * Prompt user for input
 */
function prompt(question) {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
    });

    return new Promise((resolve) => {
        rl.question(`${colors.yellow}${question}${colors.reset}`, (answer) => {
            rl.close();
            resolve(answer.trim());
        });
    });
}

// ============================================================
// BUILD FUNCTIONS
// ============================================================

async function buildV6() {
    printSubHeader('Building V6 C++ Engine');

    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    let command = 'uv';
    let args = ['run', '--extra', 'build', 'python', '-m', 'chess_engine.engine.v6.native_build'];

    try {
        execSync('uv --version', { stdio: 'pipe' });
    } catch {
        command = pythonCmd;
        args = ['-m', 'uv', 'run', '--extra', 'build', 'python', '-m', 'chess_engine.engine.v6.native_build'];
    }

    try {
        execFileSync(command, args, {
            cwd: ROOT_DIR,
            stdio: 'inherit',
            env: {
                ...process.env,
                PYTHONPATH: path.join(ROOT_DIR, 'src'),
                UV_CACHE_DIR,
            },
        });

        setConfigValue('v6Built', true);
        setConfigValue('lastBuildTime', new Date().toISOString());

        log('\n' + '═'.repeat(50), colors.green);
        logSuccess('V6 Engine built successfully!');
        log('═'.repeat(50), colors.green);

        return true;
    } catch (error) {
        logError(`Build failed: ${error.message}`);
        return false;
    }
}

async function buildV7() {
    // INT-05 — mirrors buildV6() shape. Invokes:
    //   uv run --extra build python -m chess_engine.engine.v7.native_build
    printSubHeader('Building V7 C++ Engine');

    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    let command = 'uv';
    let args = ['run', '--extra', 'build', 'python', '-m', 'chess_engine.engine.v7.native_build'];

    try {
        execSync('uv --version', { stdio: 'pipe' });
    } catch {
        command = pythonCmd;
        args = ['-m', 'uv', 'run', '--extra', 'build', 'python', '-m', 'chess_engine.engine.v7.native_build'];
    }

    try {
        execFileSync(command, args, {
            cwd: ROOT_DIR,
            stdio: 'inherit',
            env: {
                ...process.env,
                PYTHONPATH: path.join(ROOT_DIR, 'src'),
                UV_CACHE_DIR,
            },
        });

        setConfigValue('v7Built', true);
        setConfigValue('lastBuildTime', new Date().toISOString());

        log('\n' + '═'.repeat(50), colors.green);
        logSuccess('V7 Engine built successfully!');
        log('═'.repeat(50), colors.green);

        return true;
    } catch (error) {
        logError(`Build failed: ${error.message}`);
        return false;
    }
}

// ============================================================
// SYZYGY DOWNLOAD (TB-09)
// ============================================================

/**
 * Resolve the default destination directory for Syzygy tablebases.
 * Falls back to OS-specific user-data paths when config.syzygyPath is null.
 */
function defaultSyzygyPath() {
    const config = loadConfig();
    if (config.syzygyPath) return config.syzygyPath;

    if (process.platform === 'win32') {
        const base = process.env.LOCALAPPDATA
            || path.join(os.homedir(), 'AppData', 'Local');
        return path.join(base, 'chess-engine', 'syzygy');
    }
    if (process.platform === 'darwin') {
        return path.join(os.homedir(), 'Library', 'Application Support',
                         'chess-engine', 'syzygy');
    }
    // linux + freebsd + other
    const xdg = process.env.XDG_DATA_HOME
        || path.join(os.homedir(), '.local', 'share');
    return path.join(xdg, 'chess-engine', 'syzygy');
}

/**
 * Syzygy download subcommand (TB-09 / INT-05).
 *
 * Phase 1 scope (per plan 06): script presence is the requirement. We provide
 * a working dry-run that resolves the destination + announces the upstream
 * mirror, and a real-fetch path that streams a curated 3-4-5 men file list
 * from the published Lichess mirror. The real download is intentionally
 * implemented as a thin wrapper around `wget` (when on PATH) to avoid
 * pulling a heavy node fetch lib into the CLI — keeps the CLI dependency
 * footprint at zero (consistent with existing CLI style). Polite-use note:
 * tablebase.lichess.ovh hosts a free mirror — please run this once and
 * cache locally; do NOT loop the download from CI.
 *
 * --dry-run prints destination + file count without downloading; this is
 * what the plan-06 verify gate exercises so a host without wget can still
 * validate the wiring.
 */
async function syzygyDownload(opts) {
    printSubHeader('Syzygy Tablebase Download');

    const dest = defaultSyzygyPath();
    const config = loadConfig();
    const maxPieces = config.syzygyMaxPieces || 6;

    // Phase-1-scope file list: 3-4-5 men tables (per plan-06 default).
    // Authoritative public mirror: https://tablebase.lichess.ovh/tables/standard/3-4-5/
    // Source for the file list: chessprogramming.org/Syzygy_Bases (3-4-5 men set
    // ~290 files, ~1GB). We avoid hardcoding the full list here to keep this
    // CLI source small; the dry-run prints the URL the real download walks.
    const mirror = `https://tablebase.lichess.ovh/tables/standard/3-4-5/`;
    const approxFileCount = 290;
    const approxSizeGB = 1;

    log(`  Destination:  ${colors.cyan}${dest}${colors.reset}`);
    log(`  Mirror:       ${colors.cyan}${mirror}${colors.reset}`);
    log(`  Max pieces:   ${colors.cyan}${maxPieces}${colors.reset}`);
    log(`  Approx files: ${colors.cyan}${approxFileCount} (.rtbw + .rtbz)${colors.reset}`);
    log(`  Approx size:  ${colors.cyan}~${approxSizeGB} GB${colors.reset}`);

    if (opts && opts.dryRun) {
        log('');
        log('  [dry-run] Would create destination directory + fetch tables.', colors.yellow);
        log('  [dry-run] No bytes downloaded; no config mutation.', colors.yellow);
        return true;
    }

    // Real download path: prefer wget (supports recursive directory mirror).
    let downloader = null;
    try { execSync('wget --version', { stdio: 'pipe' }); downloader = 'wget'; }
    catch {
        try {
            execSync('curl --version', { stdio: 'pipe' });
            downloader = 'curl';  // recognized, but recursive mirror not implemented in Phase 1
        }
        catch {
            logError('Neither wget nor curl found on PATH. Install wget and re-run, or download manually.');
            log('  Manual fallback: visit ' + mirror + ' and copy .rtbw/.rtbz files to');
            log('    ' + dest);
            return false;
        }
    }

    try {
        fs.mkdirSync(dest, { recursive: true });
    } catch (e) {
        logError(`Failed to create destination ${dest}: ${e.message}`);
        return false;
    }

    log(`  Using ${downloader} for download…`, colors.cyan);
    log('  This will take several minutes on a typical connection.', colors.yellow);

    let downloadOk = false;
    try {
        if (downloader === 'wget') {
            // -np: no parent ascent, -r: recurse the index, -nd: flatten dirs,
            // -A: file pattern filter. Polite-use: single-run only.
            execSync(
                `wget -q --show-progress -np -r -nd -A "*.rtbw,*.rtbz" -P "${dest}" "${mirror}"`,
                { stdio: 'inherit' }
            );
            downloadOk = true;
        } else {
            // curl can't recurse a directory listing easily; Phase 1 prefers wget.
            log('  curl recursive mirror not implemented in Phase 1.', colors.yellow);
            log('  Phase 1 supported path: install wget for real fetch, or use --dry-run for wiring smoke.');
            log(`  Or manually: visit ${mirror} and copy .rtbw/.rtbz files into ${dest}`);
            return false;
        }
    } catch (error) {
        logError(`Download failed: ${error.message}`);
        return false;
    }

    if (downloadOk) {
        setConfigValue('syzygyPath', dest);
        logSuccess(`Syzygy tables downloaded to ${dest}`);
        logSuccess(`Config updated: syzygyPath = ${dest}`);
    }
    return downloadOk;
}

async function buildClient() {
    printSubHeader('Building Frontend');

    try {
        // Check if node_modules exists
        if (!fs.existsSync(path.join(CLIENT_DIR, 'node_modules'))) {
            log('  Installing dependencies...', colors.cyan);
            execSync('npm install', { cwd: CLIENT_DIR, stdio: 'inherit' });
        }

        log('  Building production bundle...', colors.cyan);
        execSync('npm run build', { cwd: CLIENT_DIR, stdio: 'inherit' });

        logSuccess('Frontend built successfully!');
        return true;
    } catch (error) {
        logError(`Build failed: ${error.message}`);
        return false;
    }
}

async function startServer() {
    printSubHeader('Starting Server');

    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    log(`  Starting server with ${pythonCmd}...`, colors.cyan);
    log('  Press Ctrl+C to stop\n', colors.dim);

    const server = spawn(pythonCmd, ['run_ui.py'], {
        cwd: ROOT_DIR,
        stdio: 'inherit',
    });

    server.on('error', (err) => {
        logError(`Failed to start server: ${err.message}`);
    });

    // Keep running until Ctrl+C
    await new Promise((resolve) => {
        server.on('close', resolve);
    });
}

async function runAll() {
    printHeader('Building and Starting Chess Engine');

    // Build V6
    const v6Success = await buildV6();
    if (!v6Success) {
        const cont = await prompt('V6 build failed. Continue anyway? (y/N): ');
        if (cont.toLowerCase() !== 'y') return;
    }

    // Build client
    await buildClient();

    // Start server
    await startServer();
}

// ============================================================
// CONFIGURATION
// ============================================================

async function configureEngine() {
    const config = loadConfig();

    while (true) {
        printSubHeader('Engine Configuration');

        const threads = config.threads || os.cpus().length;

        log(`\n  Current Settings:`, colors.bright);
        log(`    [1] Threads:      ${colors.cyan}${threads}${colors.reset} ${config.threads ? '' : '(auto)'}`);
        log(`    [2] TT Size:      ${colors.cyan}${config.ttSize} MB${colors.reset}`);
        log(`    [3] Max Memory:   ${colors.cyan}${config.maxMemory} MB${colors.reset}`);
        log(`    [4] Time Limit:   ${colors.cyan}${config.timeLimit} ms${colors.reset}`);
        log('');
        log('    [0] Back to main menu');

        const choice = await prompt('\n  Select option to change: ');

        switch (choice) {
            case '1':
                const newThreads = await prompt(`  Enter number of threads (1-${os.cpus().length}, or 'auto'): `);
                if (newThreads.toLowerCase() === 'auto') {
                    config.threads = null;
                } else {
                    const t = parseInt(newThreads);
                    if (!isNaN(t) && t >= 1) {
                        config.threads = t;
                    }
                }
                break;
            case '2':
                const newTT = await prompt('  Enter TT size in MB (16-2048): ');
                const tt = parseInt(newTT);
                if (!isNaN(tt) && tt >= 16 && tt <= 2048) {
                    config.ttSize = tt;
                }
                break;
            case '3':
                const newMem = await prompt('  Enter max memory in MB: ');
                const mem = parseInt(newMem);
                if (!isNaN(mem) && mem >= 64) {
                    config.maxMemory = mem;
                }
                break;
            case '4':
                const newTime = await prompt('  Enter time limit in ms (1000-60000): ');
                const time = parseInt(newTime);
                if (!isNaN(time) && time >= 1000 && time <= 60000) {
                    config.timeLimit = time;
                }
                break;
            case '0':
            case '':
                saveConfig(config);
                logSuccess('Configuration saved');
                return;
        }

        saveConfig(config);
    }
}

async function viewStatistics() {
    printSubHeader('Engine Statistics');

    const config = loadConfig();
    const threads = config.threads || os.cpus().length;

    log(`\n  Configuration:`, colors.bright);
    log(`    Threads:      ${colors.cyan}${threads}${colors.reset}`);
    log(`    TT Size:      ${colors.cyan}${config.ttSize} MB${colors.reset}`);
    log(`    Max Memory:   ${colors.cyan}${config.maxMemory} MB${colors.reset}`);
    log(`    Time Limit:   ${colors.cyan}${config.timeLimit} ms${colors.reset}`);

    log(`\n  Build Status:`, colors.bright);
    if (config.v6Built) {
        logSuccess(`  V6 Engine built on ${new Date(config.lastBuildTime).toLocaleString()}`);

        // Try to get version info from the engine
        try {
            const result = execSync(
                `python -c "from chess_engine.engine.v6 import chess_algorithm as v6; print(v6.v6_engine.perft('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 1))"`,
                {
                    encoding: 'utf-8',
                    stdio: 'pipe',
                    env: {
                        ...process.env,
                        PYTHONPATH: path.join(ROOT_DIR, 'src'),
                    },
                }
            );
            log(`    Perft(1) test: ${colors.green}✓ ${result.trim()} nodes${colors.reset}`);
        } catch {
            logWarning('  Could not verify engine');
        }
    } else {
        logWarning('  V6 Engine not built yet');
    }

    log(`\n  System:`, colors.bright);
    log(`    CPU:          ${colors.cyan}${os.cpus()[0].model}${colors.reset}`);
    log(`    Cores:        ${colors.cyan}${os.cpus().length}${colors.reset}`);
    log(`    Total RAM:    ${colors.cyan}${Math.round(os.totalmem() / 1024 / 1024 / 1024)} GB${colors.reset}`);
    log(`    Free RAM:     ${colors.cyan}${Math.round(os.freemem() / 1024 / 1024 / 1024)} GB${colors.reset}`);

    await prompt('\n  Press Enter to continue...');
}

// ============================================================
// MAIN MENU
// ============================================================

async function mainMenu() {
    while (true) {
        console.clear();
        printHeader('Chess Engine Manager');

        const config = loadConfig();
        const threads = config.threads || os.cpus().length;

        // Status line
        log('\n  Status:', colors.bright);
        if (config.v6Built) {
            log(`    V6 Engine: ${colors.green}✓ Built${colors.reset}`);
        } else {
            log(`    V6 Engine: ${colors.yellow}Not built${colors.reset}`);
        }
        log(`    Threads: ${colors.cyan}${threads}${colors.reset} | TT: ${colors.cyan}${config.ttSize}MB${colors.reset} | Time: ${colors.cyan}${config.timeLimit}ms${colors.reset}`);

        log('\n  Options:', colors.bright);
        log('    [1] Build V6 C++ Engine');
        log('    [2] Build Frontend');
        log('    [3] Start Server');
        log('    [4] View Statistics');
        log('    [5] Configure Engine');
        log('    [6] Run All (Build + Start)');
        log('    [0] Exit');

        const choice = await prompt('\n  Enter choice: ');

        switch (choice) {
            case '1':
                await buildV6();
                await prompt('\n  Press Enter to continue...');
                break;
            case '2':
                await buildClient();
                await prompt('\n  Press Enter to continue...');
                break;
            case '3':
                await startServer();
                break;
            case '4':
                await viewStatistics();
                break;
            case '5':
                await configureEngine();
                break;
            case '6':
                await runAll();
                break;
            case '0':
            case 'q':
            case 'exit':
                log('\nGoodbye!', colors.cyan);
                process.exit(0);
        }
    }
}

// ============================================================
// CLI ARGUMENT HANDLING
// ============================================================

async function main() {
    const args = process.argv.slice(2);

    if (args.length === 0) {
        // Interactive mode
        await mainMenu();
        return;
    }

    const command = args[0].toLowerCase();

    switch (command) {
        case '--version':
        case '-v':
            log('chess-engine-cli v1.0.0');
            break;
        case '--help':
        case '-h':
            log(`
Chess Engine CLI

Usage:
  chess-engine                       Interactive mode
  chess-engine build v6              Build V6 C++ engine
  chess-engine build v7              Build V7 C++ engine
  chess-engine build client          Build frontend
  chess-engine syzygy download [--dry-run]
                                     Download Syzygy 3-4-5 men tablebases
  chess-engine start                 Start server
  chess-engine run-all               Build everything and start
  chess-engine config                Configure engine settings
  chess-engine stats                 View statistics

Options:
  --version, -v    Show version
  --help, -h       Show this help
            `);
            break;
        case 'build':
            if (args[1] === 'v6') {
                await buildV6();
            } else if (args[1] === 'v7') {
                await buildV7();
            } else if (args[1] === 'client') {
                await buildClient();
            } else {
                logError('Usage: chess-engine build [v6|v7|client]');
            }
            break;
        case 'syzygy':
            if (args[1] === 'download') {
                const dryRun = args.includes('--dry-run');
                await syzygyDownload({ dryRun });
            } else {
                logError('Usage: chess-engine syzygy download [--dry-run]');
            }
            break;
        case 'start':
            await startServer();
            break;
        case 'run-all':
            await runAll();
            break;
        case 'config':
            await configureEngine();
            break;
        case 'stats':
            await viewStatistics();
            break;
        default:
            logError(`Unknown command: ${command}`);
            log('Run "chess-engine --help" for usage information.');
    }
}

main().catch(console.error);
