/**
 * Chess Engine Configuration Manager
 * 
 * Handles saving/loading configuration to .chess-engine.json
 */

const fs = require('fs');
const path = require('path');

const CONFIG_FILE = '.chess-engine.json';

const DEFAULT_CONFIG = {
    threads: null,  // null = auto-detect (os.cpus().length)
    ttSize: 64,     // MB
    maxMemory: 512, // MB
    timeLimit: 5000, // ms
    v6Built: false,
    lastBuildTime: null,
    cmakePath: null,  // Auto-detected
};

function getConfigPath() {
    return path.join(process.cwd(), CONFIG_FILE);
}

function loadConfig() {
    try {
        const configPath = getConfigPath();
        if (fs.existsSync(configPath)) {
            const data = fs.readFileSync(configPath, 'utf-8');
            return { ...DEFAULT_CONFIG, ...JSON.parse(data) };
        }
    } catch (e) {
        // Ignore errors, use defaults
    }
    return { ...DEFAULT_CONFIG };
}

function saveConfig(config) {
    try {
        const configPath = getConfigPath();
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
        return true;
    } catch (e) {
        return false;
    }
}

function setConfigValue(key, value) {
    const config = loadConfig();
    config[key] = value;
    return saveConfig(config);
}

function getConfigValue(key) {
    const config = loadConfig();
    return config[key];
}

module.exports = {
    loadConfig,
    saveConfig,
    setConfigValue,
    getConfigValue,
    DEFAULT_CONFIG,
};
