#!/usr/bin/env node
/**
 * postinstall: download the correct platform binary from GitHub Releases
 * and place it at ./bin/hivo (or ./bin/hivo.exe on Windows)
 */

const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const pkg = require('./package.json');
const version = pkg.version;

const PLATFORMS = {
  'linux-x64':   'hivo-linux-amd64',
  'darwin-x64':  'hivo-darwin-amd64',
  'darwin-arm64':'hivo-darwin-arm64',
  'win32-x64':   'hivo-windows-amd64.exe',
};

const platform = `${process.platform}-${process.arch}`;
const binaryName = PLATFORMS[platform];

if (!binaryName) {
  console.error(`Unsupported platform: ${platform}`);
  process.exit(1);
}

const binDir = path.join(__dirname, 'bin');
if (!fs.existsSync(binDir)) fs.mkdirSync(binDir, { recursive: true });

const isWindows = process.platform === 'win32';
const dest = path.join(binDir, isWindows ? 'hivo.exe' : 'hivo');

// Write a wrapper script at ./bin/hivo that points to the real binary
// (the real binary is downloaded to ./bin/<binaryName>)
const realBin = path.join(binDir, binaryName);
const url = `https://github.com/zhiyuzi/Hivo/releases/download/v${version}/${binaryName}`;

console.log(`Downloading hivo v${version} for ${platform}...`);

function download(url, dest, cb) {
  const file = fs.createWriteStream(dest);
  https.get(url, (res) => {
    if (res.statusCode === 302 || res.statusCode === 301) {
      file.close();
      fs.unlinkSync(dest);
      return download(res.headers.location, dest, cb);
    }
    if (res.statusCode !== 200) {
      file.close();
      fs.unlinkSync(dest);
      return cb(new Error(`HTTP ${res.statusCode}`));
    }
    res.pipe(file);
    file.on('finish', () => file.close(cb));
  }).on('error', (err) => {
    fs.unlinkSync(dest);
    cb(err);
  });
}

download(url, realBin, (err) => {
  if (err) {
    console.error(`Failed to download hivo binary: ${err.message}`);
    console.error(`You can manually download from: ${url}`);
    process.exit(1);
  }

  if (!isWindows) {
    fs.chmodSync(realBin, 0o755);
    // Create symlink or copy to ./bin/hivo
    if (fs.existsSync(dest)) fs.unlinkSync(dest);
    fs.symlinkSync(realBin, dest);
  } else {
    // On Windows, copy to hivo.exe
    fs.copyFileSync(realBin, dest);
  }

  console.log(`hivo installed successfully.`);
});
