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

const { execSync, spawn } = require('child_process');
const readline = require('readline');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { loadConfig, saveConfig, setConfigValue, getConfigValue } = require('./config.js');

// Project root directory
const ROOT_DIR = path.resolve(__dirname, '..', '..');
const V6_DIR = path.join(ROOT_DIR, 'main', 'engine', 'v6');
const CLIENT_DIR = path.join(ROOT_DIR, 'main', 'client');

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

function logInfo(message) {
    log(`ℹ ${message}`, colors.cyan);
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
// CMAKE DETECTION
// ============================================================

function findCMake() {
    // Check if already in path
    try {
        execSync('cmake --version', { stdio: 'pipe' });
        return 'cmake';
    } catch { }

    // Check common Visual Studio locations
    const vsLocations = [
        'C:\\Program Files\\Microsoft Visual Studio',
        'C:\\Program Files (x86)\\Microsoft Visual Studio',
    ];

    for (const vsBase of vsLocations) {
        if (!fs.existsSync(vsBase)) continue;

        try {
            const years = fs.readdirSync(vsBase);
            for (const year of years.reverse()) {  // Newest first
                const editions = ['BuildTools', 'Enterprise', 'Professional', 'Community'];
                for (const edition of editions) {
                    const cmakePath = path.join(
                        vsBase, year, edition,
                        'Common7', 'IDE', 'CommonExtensions', 'Microsoft', 'CMake', 'CMake', 'bin', 'cmake.exe'
                    );
                    if (fs.existsSync(cmakePath)) {
                        return cmakePath;
                    }
                }
            }
        } catch { }
    }

    return null;
}

// ============================================================
// BUILD FUNCTIONS
// ============================================================

async function buildV6() {
    printSubHeader('Building V6 C++ Engine');

    const cmakePath = findCMake();
    if (!cmakePath) {
        logError('CMake not found! Please install Visual Studio Build Tools or add CMake to PATH.');
        return false;
    }

    logInfo(`Using CMake: ${cmakePath}`);
    setConfigValue('cmakePath', cmakePath);

    const buildDir = path.join(V6_DIR, 'build');

    // Create build directory
    if (!fs.existsSync(buildDir)) {
        fs.mkdirSync(buildDir, { recursive: true });
    }

    try {
        // Run CMake configure
        log('\n  [1/3] Configuring CMake...', colors.cyan);
        execSync(`"${cmakePath}" .. -DCMAKE_BUILD_TYPE=Release`, {
            cwd: buildDir,
            stdio: 'inherit',
        });
        logSuccess('CMake configuration complete');

        // Run build
        log('\n  [2/3] Building...', colors.cyan);
        execSync(`"${cmakePath}" --build . --config Release`, {
            cwd: buildDir,
            stdio: 'inherit',
        });
        logSuccess('Build complete');

        // Copy Python module
        log('\n  [3/3] Installing Python module...', colors.cyan);
        const pydFiles = fs.readdirSync(path.join(buildDir, 'Release'))
            .filter(f => f.endsWith('.pyd'));

        if (pydFiles.length > 0) {
            const srcFile = path.join(buildDir, 'Release', pydFiles[0]);
            const dstFile = path.join(V6_DIR, 'v6_engine.pyd');
            fs.copyFileSync(srcFile, dstFile);
            logSuccess(`Installed ${pydFiles[0]}`);
        }

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
                `python -c "import sys; sys.path.insert(0, r'${V6_DIR}'); import v6_engine; print(v6_engine.perft('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 1))"`,
                { encoding: 'utf-8', stdio: 'pipe' }
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
  chess-engine              Interactive mode
  chess-engine build v6     Build V6 C++ engine
  chess-engine build client Build frontend
  chess-engine start        Start server
  chess-engine run-all      Build everything and start
  chess-engine config       Configure engine settings
  chess-engine stats        View statistics

Options:
  --version, -v    Show version
  --help, -h       Show this help
            `);
            break;
        case 'build':
            if (args[1] === 'v6') {
                await buildV6();
            } else if (args[1] === 'client') {
                await buildClient();
            } else {
                logError('Usage: chess-engine build [v6|client]');
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
