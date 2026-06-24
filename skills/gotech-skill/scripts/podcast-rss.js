#!/usr/bin/env node
/**
 * Podcast RSS Feed Generator
 * Reads episode data from yt_seo_full.json and generates a valid RSS 2.0 feed
 * with iTunes podcast extensions for submission to Spotify, Apple Podcasts, etc.
 *
 * Usage: node podcast-rss.js [--output path] [--limit N] [--base-url url]
 */

const fs = require('fs');
const path = require('path');

// --- CLI Argument Parsing ---
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    output: '/Users/davidgo/Documents/GoTechSolutions/startup/podcast-feed.xml',
    limit: null,
    baseUrl: 'https://gotechsolutions.com',
    input: '/Users/davidgo/Documents/GoTechSolutions/startup/yt_seo_full.json',
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--output':
        options.output = args[++i];
        break;
      case '--limit':
        options.limit = parseInt(args[++i], 10);
        break;
      case '--base-url':
        options.baseUrl = args[++i];
        break;
      case '--input':
        options.input = args[++i];
        break;
      case '--help':
      case '-h':
        console.log(`
Podcast RSS Feed Generator

Usage: node podcast-rss.js [options]

Options:
  --output <path>     Output XML file path (default: podcast-feed.xml)
  --limit <N>         Limit number of episodes (default: all)
  --base-url <url>    Base URL for links (default: https://gotechsolutions.com)
  --input <path>      Input JSON file path (default: yt_seo_full.json)
  --help, -h          Show this help message
        `);
        process.exit(0);
        break;
    }
  }

  return options;
}

// --- XML Escaping ---
function escapeXml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

// --- Generate a deterministic pubDate based on episode number ---
// Episodes are daily shows, so EP001 = 60 days ago, EP060 = today
function generatePubDate(epNumber, totalEpisodes) {
  const now = new Date();
  const daysAgo = totalEpisodes - epNumber;
  const date = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000);
  // Format: RFC 822 - "Wed, 02 Oct 2002 15:00:00 GMT"
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  
  const dayName = days[date.getUTCDay()];
  const day = String(date.getUTCDate()).padStart(2, '0');
  const month = months[date.getUTCMonth()];
  const year = date.getUTCFullYear();
  const hours = String(date.getUTCHours()).padStart(2, '0');
  const minutes = String(date.getUTCMinutes()).padStart(2, '0');
  const seconds = String(date.getUTCSeconds()).padStart(2, '0');
  
  return `${dayName}, ${day} ${month} ${year} ${hours}:${minutes}:${seconds} GMT`;
}

// --- Generate deterministic duration based on episode number ---
function generateDuration(epNumber) {
  // Podcast episodes between 20-60 minutes, varying by episode
  const baseMinutes = 30;
  const variation = (epNumber * 7) % 25; // 0-24 minutes variation
  const totalSeconds = (baseMinutes + variation) * 60;
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

// --- Generate a GUID for each episode ---
function generateGuid(epNumber, baseUrl) {
  return `${baseUrl}/episodes/${String(epNumber).padStart(3, '0')}#${Date.now()}`;
}

// --- Extract YouTube video ID from URL ---
function extractYouTubeId(url) {
  if (!url || url === 'N/A') return null;
  const match = url.match(/[?&]v=([^&]+)/);
  return match ? match[1] : null;
}

// --- Generate episode description ---
function generateDescription(episode) {
  let desc = episode.desc_preview || episode.topic || `${episode.title} - A episode of The David Daily Show`;
  
  if (episode.guest) {
    desc = `Join host David Goecke and guest ${episode.guest} in this episode of The David Daily Show. ${desc}`;
  }
  
  // Add tags as keywords at the bottom
  if (episode.tags) {
    const tagList = episode.tags.split(',').map(t => t.trim()).filter(t => t.length > 0);
    desc += '\n\nTopics covered: ' + tagList.join(', ');
  }
  
  return desc;
}

// --- Main RSS Generation ---
function generateRSS(episodes, options) {
  const { baseUrl, limit } = options;
  const totalEpisodes = episodes.length;
  const selectedEpisodes = limit ? episodes.slice(0, limit) : episodes;
  
  // Podcast metadata
  const podcastInfo = {
    title: 'The David Daily Show',
    description: 'The David Daily Show with David Goecke — daily conversations at the intersection of AI, frontier technology, business leadership, and faith. Featuring expert guests, market insights, and deep dives into emerging tech trends.',
    link: `${baseUrl}/podcast`,
    language: 'en-us',
    copyright: `${new Date().getFullYear()} GoTech Solutions LLC`,
    subtitle: 'Daily AI, Tech & Business Insights',
    author: 'David Goecke',
    owner: {
      name: 'David Goecke',
      email: 'david@gotechsolutions.com',
    },
    image: `${baseUrl}/images/podcast-cover.jpg`,
    category: 'Technology',
    subcategory: 'Tech News',
    explicit: 'no',
    type: 'episodic',
  };

  // Build XML
  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" 
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>${escapeXml(podcastInfo.title)}</title>
    <description>${escapeXml(podcastInfo.description)}</description>
    <link>${escapeXml(podcastInfo.link)}</link>
    <language>${podcastInfo.language}</language>
    <copyright>${escapeXml(podcastInfo.copyright)}</copyright>
    <managingEditor>${escapeXml(podcastInfo.owner.email)} (${escapeXml(podcastInfo.owner.name)})</managingEditor>
    <webMaster>${escapeXml(podcastInfo.owner.email)}</webMaster>
    <atom:link href="${escapeXml(baseUrl)}/podcast-feed.xml" rel="self" type="application/rss+xml" />
    <itunes:subtitle>${escapeXml(podcastInfo.subtitle)}</itunes:subtitle>
    <itunes:author>${escapeXml(podcastInfo.author)}</itunes:author>
    <itunes:summary>${escapeXml(podcastInfo.description)}</itunes:summary>
    <itunes:owner>
      <itunes:name>${escapeXml(podcastInfo.owner.name)}</itunes:name>
      <itunes:email>${escapeXml(podcastInfo.owner.email)}</itunes:email>
    </itunes:owner>
    <itunes:image href="${escapeXml(podcastInfo.image)}" />
    <itunes:category text="${escapeXml(podcastInfo.category)}">
      <itunes:category text="${escapeXml(podcastInfo.subcategory)}" />
    </itunes:category>
    <itunes:explicit>${podcastInfo.explicit}</itunes:explicit>
    <itunes:type>${podcastInfo.type}</itunes:type>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <pubDate>${selectedEpisodes.length > 0 ? generatePubDate(parseInt(selectedEpisodes[0].ep.replace('EP', ''), 10), totalEpisodes) : new Date().toUTCString()}</pubDate>
    <generator>Podcast RSS Generator v1.0</generator>
    <ttl>60</ttl>
    <podcast:locked owner="${escapeXml(podcastInfo.owner.email)}">yes</podcast:locked>
`;

  // Add episodes
  for (const episode of selectedEpisodes) {
    const epNum = parseInt(episode.ep.replace('EP', ''), 10);
    const pubDate = generatePubDate(epNum, totalEpisodes);
    const duration = generateDuration(epNum);
    const description = generateDescription(episode);
    const youTubeId = extractYouTubeId(episode.url);
    const episodeUrl = youTubeId ? episode.url : `${baseUrl}/episodes/${String(epNum).padStart(3, '0')}`;
    const guid = generateGuid(epNum, baseUrl);
    
    // Enclosure: use YouTube URL if available, otherwise a placeholder
    // Note: For true podcast audio, you'd host MP3 files. This uses the video URL
    // as a fallback. For production, replace with actual audio file URLs.
    const enclosureUrl = youTubeId 
      ? `https://www.youtube.com/watch?v=${youTubeId}`
      : `${baseUrl}/audio/${String(epNum).padStart(3, '0')}.mp3`;
    
    // Episode image (YouTube thumbnail or custom)
    const episodeImage = youTubeId
      ? `https://img.youtube.com/vi/${youTubeId}/maxresdefault.jpg`
      : `${baseUrl}/images/episodes/${String(epNum).padStart(3, '0')}.jpg`;
    
    // iTunes-specific description (HTML allowed)
    let itunesDescription = description;
    if (episode.guest) {
      itunesDescription = `<p>Featuring special guest <strong>${escapeXml(episode.guest)}</strong>.</p>\n<p>${escapeXml(description)}</p>`;
    } else {
      itunesDescription = `<p>${escapeXml(description)}</p>`;
    }
    
    // Convert plain text newlines to <br/> for iTunes description
    itunesDescription = itunesDescription.replace(/\n/g, '<br/>');

    xml += `
    <item>
      <title>${escapeXml(episode.title)}</title>
      <description>${escapeXml(description)}</description>
      <content:encoded><![CDATA[${description}]]></content:encoded>
      <link>${escapeXml(episodeUrl)}</link>
      <guid isPermaLink="false">${escapeXml(guid)}</guid>
      <pubDate>${pubDate}</pubDate>
      <enclosure url="${escapeXml(enclosureUrl)}" type="audio/mpeg" length="0" />
      <itunes:title>${escapeXml(episode.title)}</itunes:title>
      <itunes:summary>${escapeXml(description)}</itunes:summary>
      <itunes:subtitle>${escapeXml(episode.topic || episode.title)}</itunes:subtitle>
      <itunes:duration>${duration}</itunes:duration>
      <itunes:episode>${epNum}</itunes:episode>
      <itunes:season>1</itunes:season>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>no</itunes:explicit>
      <itunes:image href="${escapeXml(episodeImage)}" />
      <itunes:author>${escapeXml(podcastInfo.author)}</itunes:author>
      <podcast:chapters url="${escapeXml(baseUrl)}/chapters/${String(epNum).padStart(3, '0')}.json" type="application/json" />
${episode.tags ? `      <category>${escapeXml(episode.tags.split(',').map(t => t.trim()).join(', '))}</category>` : ''}
    </item>`;
  }

  xml += `
  </channel>
</rss>`;

  return xml;
}

// --- Main Execution ---
function main() {
  const options = parseArgs();
  
  // Read input data
  let rawData;
  try {
    rawData = fs.readFileSync(options.input, 'utf8');
  } catch (err) {
    console.error(`Error reading input file: ${options.input}`);
    console.error(err.message);
    process.exit(1);
  }

  let episodes;
  try {
    episodes = JSON.parse(rawData);
  } catch (err) {
    console.error('Error parsing JSON input:');
    console.error(err.message);
    process.exit(1);
  }

  if (!Array.isArray(episodes) || episodes.length === 0) {
    console.error('Error: Input JSON must be a non-empty array of episodes.');
    process.exit(1);
  }

  console.log(`Loaded ${episodes.length} episodes from ${options.input}`);
  
  if (options.limit) {
    console.log(`Limiting output to ${options.limit} episodes`);
  }

  // Generate RSS
  const rssXml = generateRSS(episodes, options);

  // Ensure output directory exists
  const outputDir = path.dirname(options.output);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Write output
  try {
    fs.writeFileSync(options.output, rssXml, 'utf8');
    console.log(`✅ RSS feed generated successfully: ${options.output}`);
    console.log(`   Episodes included: ${options.limit || episodes.length}`);
    console.log(`   File size: ${(Buffer.byteLength(rssXml) / 1024).toFixed(1)} KB`);
  } catch (err) {
    console.error(`Error writing output file: ${options.output}`);
    console.error(err.message);
    process.exit(1);
  }
}

main();
