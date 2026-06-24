#!/usr/bin/env node

/**
 * YouTube Thumbnail Generator
 * Generates 1280x720 PNG thumbnails for The David Daily Show episodes
 * Uses sharp for image composition and SVG-based text rendering
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

// === Configuration ===
const CONFIG = {
  width: 1280,
  height: 720,
  outputDir: path.join(__dirname, '..', 'thumbnails'),
  dataFile: path.join(__dirname, '..', 'yt_seo_full.json'),
  colors: {
    primary: '#0D1B3E',
    gold: '#D4AF37',
    goldLight: '#F0D060',
    white: '#FFFFFF',
    black: '#000000',
  },
  // Use system fonts - fallback chain
  fontPath: '/Library/Fonts/Arial Unicode.ttf',
  fontPathBold: '/Library/Fonts/Arial Unicode.ttf', // macOS doesn't always have bold variant separate
};

// === Parse CLI Args ===
function parseArgs() {
  const args = process.argv.slice(2);
  const result = { mode: null, episode: null };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--episode' && args[i + 1]) {
      result.mode = 'single';
      result.episode = args[i + 1].toUpperCase();
      i++;
    } else if (args[i] === '--all') {
      result.mode = 'all';
    } else if (args[i] === '--help' || args[i] === '-h') {
      console.log(`
YouTube Thumbnail Generator

Usage:
  node youtube-thumbnails.js --episode EP001    Generate thumbnail for EP001
  node youtube-thumbnails.js --all              Generate thumbnails for all episodes
  node youtube-thumbnails.js --help             Show this help
`);
      process.exit(0);
    }
  }

  if (!result.mode) {
    console.error('Error: Please specify --episode EPXXX or --all');
    process.exit(1);
  }

  return result;
}

// === Load Episode Data ===
function loadEpisodeData() {
  try {
    const raw = fs.readFileSync(CONFIG.dataFile, 'utf-8');
    const data = JSON.parse(raw);
    // Build a map by episode number
    const map = {};
    data.forEach((ep) => {
      map[ep.ep] = ep;
    });
    return map;
  } catch (err) {
    console.error(`Warning: Could not load ${CONFIG.dataFile}: ${err.message}`);
    console.error('Using fallback episode data.');
    return {};
  }
}

// === Generate SVG text for the thumbnail ===
// We use SVG overlay approach for reliable cross-platform text rendering
function generateThumbnailSVG(epNum, title, guest) {
  const { width, height, colors } = CONFIG;
  const num = epNum.replace('EP', '');
  const epDisplay = `EP${num}`;

  // Truncate title if needed (max 60 chars for display)
  const displayTitle = title.length > 60 ? title.substring(0, 57) + '...' : title;

  // Word wrap title - split into lines of max ~30 chars
  const wrapText = (text, maxCharsPerLine) => {
    const words = text.split(' ');
    const lines = [];
    let currentLine = '';

    for (const word of words) {
      if ((currentLine + ' ' + word).trim().length > maxCharsPerLine) {
        if (currentLine) lines.push(currentLine.trim());
        currentLine = word;
      } else {
        currentLine = currentLine ? currentLine + ' ' + word : word;
      }
    }
    if (currentLine) lines.push(currentLine.trim());
    return lines;
  };

  const titleLines = wrapText(displayTitle, 30);
  const lineHeight = 56;
  const totalTextHeight = titleLines.length * lineHeight;
  const startY = (height - totalTextHeight) / 2 + 20;

  // Build SVG text elements
  const textElements = titleLines
    .map((line, i) => {
      const y = startY + i * lineHeight;
      return `<text x="${width / 2}" y="${y}" 
        font-family="Arial, Helvetica, sans-serif" 
        font-size="44" 
        font-weight="bold" 
        fill="${colors.white}" 
        text-anchor="middle" 
        dominant-baseline="middle">${escapeXml(line)}</text>`;
    })
    .join('\n    ');

  // Guest line if present
  const guestLine = guest
    ? `<text x="${width / 2}" y="${startY + totalTextHeight + 30}" 
        font-family="Arial, Helvetica, sans-serif" 
        font-size="28" 
        font-weight="500" 
        fill="${colors.goldLight}" 
        text-anchor="middle" 
        dominant-baseline="middle">with ${escapeXml(guest)}</text>`
    : '';

  // Cross pattern overlay (subtle)
  const crossPattern = `
    <pattern id="crosses" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
      <line x1="20" y1="10" x2="20" y2="30" stroke="${colors.gold}" stroke-width="0.5" opacity="0.08"/>
      <line x1="10" y1="20" x2="30" y2="20" stroke="${colors.gold}" stroke-width="0.5" opacity="0.08"/>
    </pattern>
  `;

  const svg = `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="${colors.primary}"/>
      <stop offset="100%" stop-color="${colors.black}"/>
    </linearGradient>
    <linearGradient id="goldShine" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="${colors.gold}" stop-opacity="0.8"/>
      <stop offset="50%" stop-color="${colors.goldLight}" stop-opacity="1"/>
      <stop offset="100%" stop-color="${colors.gold}" stop-opacity="0.8"/>
    </linearGradient>
    ${crossPattern}
  </defs>
  
  <!-- Background gradient -->
  <rect width="${width}" height="${height}" fill="url(#bgGradient)"/>
  
  <!-- Cross pattern overlay for texture -->
  <rect width="${width}" height="${height}" fill="url(#crosses)"/>
  
  <!-- Top gold accent bar -->
  <rect x="0" y="0" width="${width}" height="8" fill="url(#goldShine)"/>
  
  <!-- Episode number badge -->
  <rect x="60" y="40" width="140" height="48" rx="6" fill="${colors.gold}" opacity="0.9"/>
  <text x="130" y="64" 
    font-family="Arial, Helvetica, sans-serif" 
    font-size="26" 
    font-weight="bold" 
    fill="${colors.primary}" 
    text-anchor="middle" 
    dominant-baseline="middle">${epDisplay}</text>
  
  <!-- Title text -->
  ${textElements}
  
  <!-- Guest line -->
  ${guestLine}
  
  <!-- Bottom gold accent bar -->
  <rect x="0" y="${height - 8}" width="${width}" height="8" fill="url(#goldShine)"/>
  
  <!-- Host name -->
  <text x="${width / 2}" y="${height - 50}" 
    font-family="Arial, Helvetica, sans-serif" 
    font-size="24" 
    font-weight="600" 
    fill="${colors.gold}" 
    text-anchor="middle" 
    dominant-baseline="middle">David Goecke</text>
  
  <!-- Subtle bottom accent line -->
  <rect x="${width / 2 - 100}" y="${height - 30}" width="200" height="2" fill="${colors.gold}" opacity="0.5"/>
</svg>`;

  return svg;
}

function escapeXml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

// === Generate Thumbnail for One Episode ===
async function generateThumbnail(epNum, episodeData) {
  const title = episodeData?.title || `The David Daily Show - ${epNum}`;
  const guest = episodeData?.guest || null;

  console.log(`  Generating ${epNum}: ${title}${guest ? ` (feat. ${guest})` : ''}`);

  const svg = generateThumbnailSVG(epNum, title, guest);
  const outputPath = path.join(CONFIG.outputDir, `${epNum}.png`);

  try {
    await sharp(Buffer.from(svg))
      .png()
      .toFile(outputPath);
    console.log(`    ✓ Saved: ${outputPath}`);
    return true;
  } catch (err) {
    console.error(`    ✗ Failed: ${err.message}`);
    return false;
  }
}

// === Main ===
async function main() {
  const args = parseArgs();
  const episodeData = loadEpisodeData();

  // Ensure output directory exists
  if (!fs.existsSync(CONFIG.outputDir)) {
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
  }

  console.log('=== YouTube Thumbnail Generator ===\n');

  let episodesToGenerate = [];

  if (args.mode === 'all') {
    // Generate EP001 through EP060
    for (let i = 1; i <= 60; i++) {
      episodesToGenerate.push(`EP${String(i).padStart(3, '0')}`);
    }
    console.log(`Generating thumbnails for all 60 episodes...\n`);
  } else {
    const epNum = args.episode;
    if (!epNum.match(/^EP\d{3}$/i)) {
      console.error(`Error: Invalid episode format "${epNum}". Use format like EP001.`);
      process.exit(1);
    }
    episodesToGenerate.push(epNum);
    console.log(`Generating thumbnail for ${epNum}...\n`);
  }

  let success = 0;
  let failed = 0;

  for (const ep of episodesToGenerate) {
    const data = episodeData[ep] || null;
    const result = await generateThumbnail(ep, data);
    if (result) success++;
    else failed++;
  }

  console.log(`\n=== Summary ===`);
  console.log(`Total: ${episodesToGenerate.length} | Success: ${success} | Failed: ${failed}`);
  console.log(`Output directory: ${CONFIG.outputDir}`);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
