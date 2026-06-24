#!/usr/bin/env node
/**
 * LinkedIn Prospect Finder - GoTech Solutions
 * =============================================
 * Finds prospects on LinkedIn via Proxycurl API, scores them against ICP criteria,
 * exports a GHL-ready CSV, and optionally pushes contacts to GoHighLevel.
 *
 * USAGE:
 *   node linkedin-prospect-finder.js --industry "AI Operations" --location "San Francisco" --title "CTO" --limit 10
 *   node linkedin-prospect-finder.js --demo                         # Run with sample data
 *   node linkedin-prospect-finder.js --demo --export csv            # Export demo data to CSV
 *   node linkedin-prospect-finder.js --demo --push-to-ghl           # Send demo contacts to GHL
 *
 * SETUP INSTRUCTIONS:
 * -------------------
 * 1. PROXYCURL API KEY (LinkedIn data):
 *    - Sign up at https://nubela.co/proxycurl/
 *    - Get your API key from the dashboard
 *    - Free tier: 150 credits/month (each profile lookup = 1 credit)
 *    - Set environment variable: export PROXYCURL_API_KEY="your_key_here"
 *    - Or replace the TODO below
 *
 * 2. GHL API KEY (GoHighLevel contact creation):
 *    - In GHL: Settings → Developer → API Keys → Create API Key
 *    - Needs: Contacts scope (read/write)
 *    - Set environment variable: export GHL_API_KEY="your_key_here"
 *    - Or replace the TODO below
 *
 * 3. GHL LOCATION ID:
 *    - Found in your GHL URL: app.gohighlevel.com/location/{LOCATION_ID}
 *    - Or via API: GET /v2/locations/
 *    - Set environment variable: export GHL_LOCATION_ID="your_location_id"
 *    - Or replace the TODO below
 *
 * 4. Install dependencies:
 *    npm install axios csv-writer yargs
 *
 * PRODUCTION MODE:
 *   Set USE_DEMO=false and provide API keys above.
 *   The script will call Proxycurl for real LinkedIn data.
 *
 * DEMO MODE (default):
 *   Generates realistic sample prospects matching your ICPs.
 *   No API keys required. Perfect for testing CSV output and GHL import.
 */

'use strict';

// ---------------------------------------------------------------------------
// TODO: REPLACE WITH YOUR API KEYS (or set environment variables)
// ---------------------------------------------------------------------------
const PROXYCURL_API_KEY = process.env.PROXYCURL_API_KEY || 'TODO_PROXYCURL_API_KEY';
const GHL_API_KEY = process.env.GHL_API_KEY || 'TODO_GHL_API_KEY';
const GHL_LOCATION_ID = process.env.GHL_LOCATION_ID || 'TODO_GHL_LOCATION_ID';
const GHL_BASE_URL = 'https://services.leadconnectorhq.com';
const PROXYCURL_BASE_URL = 'https://nubela.co/proxycurl/api/v2';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const USE_DEMO = process.env.USE_DEMO !== 'false'; // Default to demo mode
const DEFAULT_LIMIT = 10;
const OUTPUT_DIR = require('path').join(process.env.HOME || '/Users/davidgo', 'Documents', 'GoTechSolutions', 'startup', 'output');

// ---------------------------------------------------------------------------
// ICP Definitions (Ideal Customer Profiles)
// ---------------------------------------------------------------------------
const ICP_DEFINITIONS = {
  'AI Operations': {
    description: 'Tech companies 10-50 employees, founders/CTOs',
    industries: ['technology', 'software', 'saas', 'artificial intelligence', 'machine learning', 'data'],
    titles: ['founder', 'co-founder', 'cto', 'chief technology officer', 'ceo', 'chief executive officer', 'vp engineering', 'head of engineering', 'cto in residence'],
    companySize: { min: 10, max: 50 },
    keywords: ['ai', 'automation', 'ml', 'machine learning', 'data pipeline', 'workflow', 'artificial intelligence', 'llm', 'gpt', 'predictive'],
    idealServices: ['AI transformation', 'workflow automation', 'AI tool selection', 'data pipelines'],
    pricingAnchor: '$10K-$150K',
    scoreWeights: {
      titleMatch: 30,
      companySize: 25,
      industryMatch: 20,
      keywordMatch: 15,
      seniorityBonus: 10,
    },
  },
  Communications: {
    description: 'Marketing agencies, content creators, churches 50+ employees',
    industries: ['marketing', 'advertising', 'media', 'public relations', 'religious', 'nonprofit', 'content creation', 'digital agency', 'communications'],
    titles: ['marketing director', 'cmo', 'chief marketing officer', 'content director', 'creative director', 'pastor', 'senior pastor', 'communications director', 'media director', 'head of content', 'founder', 'ceo'],
    companySize: { min: 50, max: 1000 },
    keywords: ['marketing', 'content', 'brand', 'campaign', 'social media', 'digital', 'agency', 'media production', 'church communications', 'outreach'],
    idealServices: ['Livestream production', 'website + marketing', 'content strategy'],
    pricingAnchor: '$2K-$8K/mo',
    scoreWeights: {
      titleMatch: 25,
      companySize: 25,
      industryMatch: 25,
      keywordMatch: 15,
      seniorityBonus: 10,
    },
  },
  'Go Live Stream': {
    description: 'Churches, influencers, event companies',
    industries: ['religious', 'nonprofit', 'events', 'entertainment', 'media', 'broadcasting', 'live streaming', 'worship'],
    titles: ['pastor', 'senior pastor', 'worship leader', 'events director', 'founder', 'ceo', 'creative director', 'media director', 'content creator', 'influencer', 'producer'],
    companySize: { min: 10, max: 500 },
    keywords: ['live stream', 'livestream', 'worship', 'church', 'event', 'broadcast', 'video production', 'youtube live', 'streaming', 'influencer'],
    idealServices: ['Live video production', 'town halls', 'LinkedIn Live', 'webinar production'],
    pricingAnchor: '$3K-$8K/mo',
    scoreWeights: {
      titleMatch: 25,
      companySize: 20,
      industryMatch: 25,
      keywordMatch: 20,
      seniorityBonus: 10,
    },
  },
};

// ---------------------------------------------------------------------------
// Demo Data Generator
// ---------------------------------------------------------------------------
const DEMO_PROSPECTS = {
  'AI Operations': [
    { name: 'Sarah Chen', title: 'CTO', company: 'DataSync AI', linkedinUrl: 'https://linkedin.com/in/sarahchen-ds', companySize: 32, industry: 'artificial intelligence', description: 'Building predictive analytics platform for e-commerce' },
    { name: 'Marcus Williams', title: 'Co-Founder & CTO', company: 'AutomateFlow', linkedinUrl: 'https://linkedin.com/in/marcusw-af', companySize: 18, industry: 'saas', description: 'Workflow automation for professional services' },
    { name: 'Priya Patel', title: 'VP Engineering', company: 'NeuralPath Labs', linkedinUrl: 'https://linkedin.com/in/priyapatel-np', companySize: 45, industry: 'machine learning', description: 'ML-powered supply chain optimization' },
    { name: 'James Rodriguez', title: 'Founder', company: 'CodePilot AI', linkedinUrl: 'https://linkedin.com/in/jamesrodriguez-cp', companySize: 12, industry: 'software', description: 'AI code review and testing platform' },
    { name: 'Emily Zhang', title: 'Chief Technology Officer', company: 'PredictiveOps', linkedinUrl: 'https://linkedin.com/in/emilyzhang-po', companySize: 28, industry: 'data', description: 'Predictive maintenance for manufacturing' },
    { name: 'David Kim', title: 'CEO', company: 'LLM Bridge', linkedinUrl: 'https://linkedin.com/in/davidkim-lb', companySize: 22, industry: 'artificial intelligence', description: 'Enterprise LLM integration consulting' },
    { name: 'Rachel Torres', title: 'Head of Engineering', company: 'DataPipeline Pro', linkedinUrl: 'https://linkedin.com/in/racheltorres-dp', companySize: 38, industry: 'data', description: 'Real-time data pipeline solutions' },
    { name: 'Alex Novak', title: 'Founder', company: 'SmartWorkflow', linkedinUrl: 'https://linkedin.com/in/alexnovak-sw', companySize: 15, industry: 'saas', description: 'AI-powered business process automation' },
    { name: 'Lisa Chang', title: 'CTO', company: 'ModelMetrics', linkedinUrl: 'https://linkedin.com/in/lisachang-mm', companySize: 41, industry: 'machine learning', description: 'MLOps and model monitoring platform' },
    { name: 'Tom Bradley', title: 'Co-Founder', company: 'AutoScale AI', linkedinUrl: 'https://linkedin.com/in/tombradley-as', companySize: 25, industry: 'artificial intelligence', description: 'AI infrastructure for scaling startups' },
  ],
  Communications: [
    { name: 'Michael Foster', title: 'Marketing Director', company: 'Elevate Agency', linkedinUrl: 'https://linkedin.com/in/michaelfoster-ea', companySize: 85, industry: 'marketing', description: 'Full-service digital marketing agency' },
    { name: 'Jennifer Adams', title: 'CMO', company: 'Grace Community Church', linkedinUrl: 'https://linkedin.com/in/jenniferadams-gcc', companySize: 120, industry: 'religious', description: 'Multi-campus church with media production' },
    { name: 'Carlos Mendez', title: 'Creative Director', company: 'ContentCraft Media', linkedinUrl: 'https://linkedin.com/in/carlosmenendez-cc', companySize: 65, industry: 'media', description: 'Content creation for mid-market brands' },
    { name: 'Amanda Brooks', title: 'Communications Director', company: 'NewSpring Church', linkedinUrl: 'https://linkedin.com/in/abrooks-nsc', companySize: 200, industry: 'religious', description: 'Church communications and media outreach' },
    { name: 'Ryan Mitchell', title: 'Head of Content', company: 'BrandForward Agency', linkedinUrl: 'https://linkedin.com/in/ryanmitchell-bf', companySize: 72, industry: 'advertising', description: 'Brand strategy and content marketing' },
    { name: 'Nicole Harris', title: 'Senior Pastor', company: 'LifePoint Church', linkedinUrl: 'https://linkedin.com/in/nicoleharris-lp', companySize: 350, industry: 'religious', description: 'Growing church with weekly livestream' },
    { name: 'Jason Park', title: 'Media Director', company: 'Victory World Church', linkedinUrl: 'https://linkedin.com/in/jasonpark-vw', companySize: 180, industry: 'religious', description: 'Multi-site church media production' },
    { name: 'Stephanie Clark', title: 'Content Director', company: 'Influence Media Group', linkedinUrl: 'https://linkedin.com/in/stephanieclark-im', companySize: 55, industry: 'media', description: 'Influencer marketing and content production' },
    { name: 'Brian Walsh', title: 'CEO', company: 'Digital Reach Agency', linkedinUrl: 'https://linkedin.com/in/brianwalsh-dr', companySize: 90, industry: 'marketing', description: 'Digital marketing for mid-market companies' },
    { name: 'Karen Thompson', title: 'Marketing Director', company: 'River Valley Church', linkedinUrl: 'https://linkedin.com/in/karentompson-rv', companySize: 95, industry: 'religious', description: 'Church marketing and community outreach' },
  ],
  'Go Live Stream': [
    { name: 'Pastor Mike Johnson', title: 'Senior Pastor', company: 'Crossroads Community Church', linkedinUrl: 'https://linkedin.com/in/mikejohnson-xc', companySize: 280, industry: 'religious', description: 'Weekly livestream services with 5K+ viewers' },
    { name: 'Chris Taylor', title: 'Events Director', company: 'Summit Events Co', linkedinUrl: 'https://linkedin.com/in/christaylor-se', companySize: 45, industry: 'events', description: 'Corporate and nonprofit event production' },
    { name: 'Jessica Rivera', title: 'Content Creator', company: 'JR Media', linkedinUrl: 'https://linkedin.com/in/jessicarivera-jr', companySize: 15, industry: 'media', description: 'YouTube influencer with 50K subscribers' },
    { name: 'Pastor David Lee', title: 'Founder', company: 'Victory Church Network', linkedinUrl: 'https://linkedin.com/in/davidlee-vn', companySize: 420, industry: 'religious', description: 'Multi-campus church with broadcast needs' },
    { name: 'Megan Carter', title: 'Producer', company: 'LiveStream Pro', linkedinUrl: 'https://linkedin.com/in/megancarter-ls', companySize: 30, industry: 'broadcasting', description: 'Professional livestream production company' },
    { name: 'Robert Smith', title: 'Worship Leader', company: 'Hillsong Austin', linkedinUrl: 'https://linkedin.com/in/robertsmith-ha', companySize: 150, industry: 'worship', description: 'Worship ministry with live production' },
    { name: 'Aisha Williams', title: 'Creative Director', company: 'StageLight Events', linkedinUrl: 'https://linkedin.com/in/aishawilliams-sl', companySize: 55, industry: 'events', description: 'Live event production for conferences' },
    { name: 'Daniel Brown', title: 'Media Pastor', company: 'Elevation Church Plant', linkedinUrl: 'https://linkedin.com/in/danielbrown-ep', companySize: 85, industry: 'religious', description: 'Church plant with video-first strategy' },
    { name: 'Samantha Davis', title: 'Influencer', company: 'SamDavis Media', linkedinUrl: 'https://linkedin.com/in/samanthadavis-sd', companySize: 12, industry: 'entertainment', description: 'Faith-based content creator, 100K followers' },
    { name: 'Kevin Nguyen', title: 'CEO', company: 'StreamNow Studios', linkedinUrl: 'https://linkedin.com/kevinnguyen-sn', companySize: 38, industry: 'live streaming', description: 'White-glove livestream service provider' },
  ],
};

// ---------------------------------------------------------------------------
// Scoring Engine
// ---------------------------------------------------------------------------
function scoreProspect(prospect, icpKey) {
  const icp = ICP_DEFINITIONS[icpKey];
  if (!icp) return { score: 0, breakdown: {} };

  const weights = icp.scoreWeights;
  let titleScore = 0;
  let sizeScore = 0;
  let industryScore = 0;
  let keywordScore = 0;
  let seniorityScore = 0;

  // Title match scoring
  const prospectTitleLower = prospect.title.toLowerCase();
  const titleMatches = icp.titles.filter(t => prospectTitleLower.includes(t.toLowerCase()));
  titleScore = Math.min(titleMatches.length * (weights.titleMatch / 3), weights.titleMatch);

  // Company size scoring
  const size = prospect.companySize;
  if (size >= icp.companySize.min && size <= icp.companySize.max) {
    sizeScore = weights.companySize; // Perfect fit
  } else if (size >= icp.companySize.min * 0.5 && size <= icp.companySize.max * 1.5) {
    sizeScore = weights.companySize * 0.6; // Close fit
  } else if (size >= icp.companySize.min * 0.25) {
    sizeScore = weights.companySize * 0.3; // Stretch fit
  }

  // Industry match scoring
  const prospectIndustry = prospect.industry.toLowerCase();
  const industryMatches = icp.industries.filter(i => prospectIndustry.includes(i.toLowerCase()) || i.toLowerCase().includes(prospectIndustry));
  industryScore = industryMatches.length > 0 ? weights.industryMatch : 0;

  // Keyword match scoring
  const prospectDesc = (prospect.description || '').toLowerCase();
  const prospectCompany = (prospect.company || '').toLowerCase();
  const keywordMatches = icp.keywords.filter(kw => {
    const kwLower = kw.toLowerCase();
    return prospectDesc.includes(kwLower) || prospectCompany.includes(kwLower) || prospectTitleLower.includes(kwLower);
  });
  keywordScore = Math.min((keywordMatches.length / Math.max(icp.keywords.length * 0.3, 1)) * weights.keywordMatch, weights.keywordMatch);

  // Seniority bonus
  const seniorTitles = ['cto', 'ceo', 'cmo', 'chief', 'founder', 'co-founder', 'senior pastor', 'director', 'vp', 'head of'];
  const hasSeniorTitle = seniorTitles.some(st => prospectTitleLower.includes(st));
  seniorityScore = hasSeniorTitle ? weights.seniorityBonus : weights.seniorityBonus * 0.3;

  const totalScore = Math.round(titleScore + sizeScore + industryScore + keywordScore + seniorityScore);

  return {
    score: Math.min(Math.max(totalScore, 1), 100),
    breakdown: {
      titleScore: Math.round(titleScore),
      sizeScore: Math.round(sizeScore),
      industryScore: Math.round(industryScore),
      keywordScore: Math.round(keywordScore),
      seniorityScore: Math.round(seniorityScore),
    },
    matchedKeywords: keywordMatches,
    matchedTitles: titleMatches,
    fit: totalScore >= 75 ? 'STRONG' : totalScore >= 50 ? 'GOOD' : totalScore >= 25 ? 'WEAK' : 'POOR',
  };
}

// ---------------------------------------------------------------------------
// LinkedIn API (Proxycurl) Integration
// ---------------------------------------------------------------------------
async function fetchProspectsFromProxycurl(industry, location, title, limit) {
  // In production, Proxycurl's /search endpoint is used for LinkedIn Search
  // Docs: https://nubela.co/proxycurl/docs#linkedin-search-api-endpoint
  const axios = require('axios');

  const params = {
    keyword_title: title || undefined,
    keyword_company_industry: industry || undefined,
    location: location || undefined,
    page_size: limit,
    use_cache: 'if-present',
  };

  // Remove undefined params
  Object.keys(params).forEach(key => params[key] === undefined && delete params[key]);

  try {
    const response = await axios.get(`${PROXYCURL_BASE_URL}/search`, {
      params,
      headers: {
        'Authorization': `Bearer ${PROXYCURL_API_KEY}`,
      },
      timeout: 30000,
    });

    return response.data.map(profile => ({
      name: profile.full_name || `${profile.first_name || ''} ${profile.last_name || ''}`.trim(),
      title: profile.title || '',
      company: profile.company || '',
      linkedinUrl: profile.public_identifier ? `https://linkedin.com/in/${profile.public_identifier}` : '',
      companySize: profile.company_size || estimateCompanySize(profile.company),
      industry: profile.company_industry || '',
      description: profile.headline || '',
      city: profile.city || '',
      country: profile.country_full_name || '',
    }));
  } catch (error) {
    if (error.response?.status === 403 || error.response?.status === 401) {
      console.error('ERROR: Invalid Proxycurl API key. Check PROXYCURL_API_KEY.');
    } else if (error.response?.status === 429) {
      console.error('ERROR: Proxycurl rate limit exceeded. Try again later.');
    } else {
      console.error(`ERROR: Proxycurl API call failed: ${error.message}`);
    }
    process.exit(1);
  }
}

function estimateCompanySize(companyName) {
  // Fallback heuristic when Proxycurl doesn't return company size
  // In production, enrich with /company endpoint
  return 25; // Default to small company
}

// ---------------------------------------------------------------------------
// GHL (GoHighLevel) Integration
// ---------------------------------------------------------------------------
async function pushContactToGHL(prospect, scoring, icpKey) {
  const axios = require('axios');

  // GHL Contact API payload
  // Docs: https://highlevel.api.guide/reference/create-contact
  const payload = {
    locationId: GHL_LOCATION_ID,
    firstName: prospect.name.split(' ')[0] || prospect.name,
    lastName: prospect.name.split(' ').slice(1).join(' ') || '',
    name: prospect.name,
    email: prospect.email || '', // LinkedIn doesn't expose email via Proxycurl
    phone: prospect.phone || '',
    companyName: prospect.company,
    website: prospect.website || '',
    tags: [
      `ICP:${icpKey}`,
      `Score:${scoring.score}`,
      `Fit:${scoring.fit}`,
      'Source:LinkedIn',
      'ProspectFinder',
    ],
    customFields: [
      { key: 'linkedin_url', value: prospect.linkedinUrl },
      { key: 'icp_score', value: scoring.score },
      { key: 'icp_fit', value: scoring.fit },
      { key: 'icp_breakdown', value: JSON.stringify(scoring.breakdown) },
      { key: 'company_size', value: prospect.companySize },
      { key: 'industry', value: prospect.industry },
      { key: 'matched_keywords', value: scoring.matchedKeywords.join(', ') },
      { key: 'prospect_title', value: prospect.title },
      { key: 'service_line', value: icpKey },
      { key: 'pricing_anchor', value: ICP_DEFINITIONS[icpKey]?.pricingAnchor || '' },
    ],
    source: 'LinkedIn Prospect Finder',
  };

  try {
    const response = await axios.post(
      `${GHL_BASE_URL}/contacts/`,
      payload,
      {
        headers: {
          'Authorization': `Bearer ${GHL_API_KEY}`,
          'Content-Type': 'application/json',
          'Version': '2021-07-28',
        },
        timeout: 15000,
      }
    );

    return {
      success: true,
      contactId: response.data?.contact?.id || response.data?.id,
      message: `Contact created: ${prospect.name} (${response.data?.contact?.id || 'ID pending'})`,
    };
  } catch (error) {
    if (error.response?.status === 401) {
      return { success: false, message: 'Invalid GHL API key' };
    }
    return {
      success: false,
      message: `Failed: ${error.response?.data?.message || error.message}`,
    };
  }
}

// ---------------------------------------------------------------------------
// CSV Export (GHL Import Format)
// ---------------------------------------------------------------------------
function generateCSV(prospects, scoringResults) {
  const headers = [
    'First Name',
    'Last Name',
    'Full Name',
    'Email',
    'Phone',
    'Company Name',
    'Title',
    'LinkedIn URL',
    'Company Size',
    'Industry',
    'ICP Score (1-100)',
    'ICP Fit',
    'Service Line',
    'Pricing Anchor',
    'Matched Keywords',
    'ICP Breakdown',
    'Tags',
    'Source',
    'Notes',
  ];

  const rows = prospects.map((p, i) => {
    const scoring = scoringResults[i];
    const nameParts = p.name.split(' ');
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';

    return [
      firstName,
      lastName,
      p.name,
      p.email || '',
      p.phone || '',
      p.company || '',
      p.title || '',
      p.linkedinUrl || '',
      p.companySize || '',
      p.industry || '',
      scoring.score,
      scoring.fit,
      scoring.icpKey || '',
      ICP_DEFINITIONS[scoring.icpKey]?.pricingAnchor || '',
      scoring.matchedKeywords.join('; '),
      JSON.stringify(scoring.breakdown),
      `Source:LinkedIn;ICP:${scoring.icpKey};Fit:${scoring.fit}`,
      'LinkedIn Prospect Finder',
      p.description || '',
    ];
  });

  // Escape CSV fields
  const escapeCSV = (field) => {
    const str = String(field ?? '');
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const headerLine = headers.map(escapeCSV).join(',');
  const dataLines = rows.map(row => row.map(escapeCSV).join(','));

  return [headerLine, ...dataLines].join('\n');
}

function writeCSVFile(csvContent, filename) {
  const fs = require('fs');
  const path = require('path');

  // Ensure output directory exists
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const filepath = path.join(OUTPUT_DIR, filename);
  fs.writeFileSync(filepath, csvContent, 'utf-8');
  return filepath;
}

// ---------------------------------------------------------------------------
// CLI Argument Parsing (no external dependency)
// ---------------------------------------------------------------------------
function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const nextArg = argv[i + 1];
      if (nextArg && !nextArg.startsWith('--')) {
        args[key] = nextArg;
        i++;
      } else {
        args[key] = true;
      }
    }
  }
  return args;
}

// ---------------------------------------------------------------------------
// Display Helpers
// ---------------------------------------------------------------------------
function printBanner() {
  console.log(`
╔══════════════════════════════════════════════════════════════╗
║           LinkedIn Prospect Finder - GoTech Solutions        ║
║                                                              ║
║  Find, score, and import ICP-matched prospects into GHL      ║
╚══════════════════════════════════════════════════════════════╝
`);
}

function printProspectTable(prospects, scoringResults) {
  console.log('\n📊 PROSPECT RESULTS');
  console.log('─'.repeat(100));
  console.log(
    `${'#'.padStart(2)} | ${'Name'.padEnd(22)} | ${'Title'.padEnd(22)} | ${'Company'.padEnd(22)} | ${'Size'.padStart(5)} | ${'Score'.padStart(5)} | ${'Fit'.padEnd(8)}`
  );
  console.log('─'.repeat(100));

  prospects.forEach((p, i) => {
    const s = scoringResults[i];
    const scoreColor = s.score >= 75 ? '🟢' : s.score >= 50 ? '🟡' : s.score >= 25 ? '🟠' : '🔴';
    console.log(
      `${String(i + 1).padStart(2)} | ${p.name.padEnd(22)} | ${p.title.padEnd(22)} | ${p.company.padEnd(22)} | ${String(p.companySize).padStart(5)} | ${scoreColor} ${String(s.score).padStart(3)} | ${s.fit.padEnd(8)}`
    );
  });

  console.log('─'.repeat(100));

  // Summary stats
  const scores = scoringResults.map(s => s.score);
  const avgScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  const strongCount = scoringResults.filter(s => s.fit === 'STRONG').length;
  const goodCount = scoringResults.filter(s => s.fit === 'GOOD').length;

  console.log(`\n📈 Summary: ${prospects.length} prospects | Avg Score: ${avgScore} | Strong: ${strongCount} | Good: ${goodCount}`);
}

// ---------------------------------------------------------------------------
// Main Execution
// ---------------------------------------------------------------------------
async function main() {
  const args = parseArgs(process.argv);

  printBanner();

  // Parse CLI arguments
  const industry = args.industry || args.i;
  const location = args.location || args.l;
  const title = args.title || args.t;
  const limit = parseInt(args.limit || args.n || args.count || args.c || DEFAULT_LIMIT, 10);
  const isDemo = args.demo || USE_DEMO;
  const shouldExportCSV = args['export-csv'] || args['export'] || args.csv || args.e;
  const shouldPushToGHL = args['push-to-ghl'] || args['push'] || args['ghl'];
  const showHelp = args.help || args.h;
  const listICPs = args['list-icps'] || args['icps'];

  // Help
  if (showHelp) {
    console.log(`
USAGE:
  node linkedin-prospect-finder.js [OPTIONS]

OPTIONS:
  --industry, -i     Industry/ICP to search (AI Operations | Communications | Go Live Stream)
  --location, -l     Location filter (city, state, or country)
  --title, -t        Job title keyword (CTO, Founder, Pastor, etc.)
  --limit, -n        Number of results (default: 10)
  --demo              Run in demo mode with sample data (default: ON)
  --export-csv, -e    Export results to CSV file
  --push-to-ghl, -g   Push contacts to GoHighLevel (requires API key)
  --list-icps         Show available ICP definitions
  --help, -h          Show this help message

EXAMPLES:
  node linkedin-prospect-finder.js --demo
  node linkedin-prospect-finder.js --demo --industry "AI Operations" --export-csv
  node linkedin-prospect-finder.js --demo --push-to-ghl
  node linkedin-prospect-finder.js --industry "AI Operations" --location "Austin" --title "CTO" --limit 20
  node linkedin-prospect-finder.js --list-icps

ENVIRONMENT VARIABLES:
  PROXYCURL_API_KEY    Your Proxycurl API key (nubela.co/proxycurl)
  GHL_API_KEY           Your GoHighLevel API key
  GHL_LOCATION_ID      Your GHL location ID
  USE_DEMO             Set to 'false' to disable demo mode
`);
    return;
  }

  // List ICPs
  if (listICPs) {
    console.log('\n📋 AVAILABLE ICP DEFINITIONS:\n');
    Object.entries(ICP_DEFINITIONS).forEach(([key, icp]) => {
      console.log(`  🔹 ${key}`);
      console.log(`     ${icp.description}`);
      console.log(`     Company Size: ${icp.companySize.min}-${icp.companySize.max} employees`);
      console.log(`     Pricing: ${icp.pricingAnchor}`);
      console.log(`     Key Titles: ${icp.titles.slice(0, 5).join(', ')}...`);
      console.log('');
    });
    return;
  }

  // Validate ICP
  const icpKey = industry || 'AI Operations';
  if (!ICP_DEFINITIONS[icpKey]) {
    console.error(`ERROR: Unknown ICP "${icpKey}". Available: ${Object.keys(ICP_DEFINITIONS).join(', ')}`);
    console.error('Run with --list-icps to see all definitions.');
    process.exit(1);
  }

  console.log(`\n🎯 ICP: ${icpKey} — ${ICP_DEFINITIONS[icpKey].description}`);
  if (location) console.log(`📍 Location: ${location}`);
  if (title) console.log(`👤 Title: ${title}`);
  console.log(`📊 Limit: ${limit}`);
  console.log(`🔧 Mode: ${isDemo ? 'DEMO (sample data)' : 'PRODUCTION (Proxycurl API)'}`);

  // Fetch prospects
  let prospects = [];

  if (isDemo) {
    console.log('\n🎭 Generating demo prospects...');
    prospects = DEMO_PROSPECTS[icpKey] || [];

    // Apply limit
    if (limit < prospects.length) {
      prospects = prospects.slice(0, limit);
    }

    // Apply title filter if specified
    if (title) {
      const titleLower = title.toLowerCase();
      prospects = prospects.filter(p => p.title.toLowerCase().includes(titleLower));
    }

    console.log(`✅ Generated ${prospects.length} demo prospects`);
  } else {
    // Production mode - call Proxycurl
    if (PROXYCURL_API_KEY === 'TODO_PROXYCURL_API_KEY') {
      console.error('\nERROR: Proxycurl API key not configured!');
      console.error('Set PROXYCURL_API_KEY environment variable or edit the TODO in the script.');
      console.error('Get your key at: https://nubela.co/proxycurl/');
      process.exit(1);
    }

    console.log('\n🔍 Searching LinkedIn via Proxycurl...');
    prospects = await fetchProspectsFromProxycurl(icpKey, location, title, limit);
    console.log(`✅ Found ${prospects.length} prospects`);
  }

  if (prospects.length === 0) {
    console.log('\n⚠️  No prospects found matching your criteria.');
    return;
  }

  // Score all prospects
  console.log('\n🧮 Scoring prospects against ICP criteria...');
  const scoringResults = prospects.map(p => {
    const scoring = scoreProspect(p, icpKey);
    scoring.icpKey = icpKey;
    return scoring;
  });

  // Sort by score descending
  const combined = prospects.map((p, i) => ({ prospect: p, scoring: scoringResults[i] }));
  combined.sort((a, b) => b.scoring.score - a.scoring.score);

  const sortedProspects = combined.map(c => c.prospect);
  const sortedScoring = combined.map(c => c.scoring);

  // Display results
  printProspectTable(sortedProspects, sortedScoring);

  // Export to CSV
  if (shouldExportCSV || isDemo) {
    const timestamp = new Date().toISOString().slice(0, 10);
    const filename = `prospects_${icpKey.replace(/\s+/g, '_').toLowerCase()}_${timestamp}.csv`;
    const csvContent = generateCSV(sortedProspects, sortedScoring);
    const filepath = writeCSVFile(csvContent, filename);

    console.log(`\n📁 CSV exported: ${filepath}`);
    console.log(`   Ready for GHL import (Contacts → Import Contacts)`);
    console.log(`   Fields mapped: ${csvContent.split('\n')[0].split(',').length} columns`);
  }

  // Push to GHL
  if (shouldPushToGHL) {
    if (GHL_API_KEY === 'TODO_GHL_API_KEY' || GHL_LOCATION_ID === 'TODO_GHL_LOCATION_ID') {
      console.error('\nERROR: GHL API key or Location ID not configured!');
      console.error('Set GHL_API_KEY and GHL_LOCATION_ID environment variables.');
      console.error('Get your API key: GHL → Settings → Developer → API Keys');
      console.error('Get your Location ID: Check your GHL URL or call GET /v2/locations/');
      process.exit(1);
    }

    console.log(`\n📤 Pushing ${sortedProspects.length} contacts to GHL...`);

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < sortedProspects.length; i++) {
      const result = await pushContactToGHL(sortedProspects[i], sortedScoring[i], icpKey);
      if (result.success) {
        successCount++;
        console.log(`   ✅ ${sortedProspects[i].name} → ${result.contactId}`);
      } else {
        failCount++;
        console.log(`   ❌ ${sortedProspects[i].name} → ${result.message}`);
      }

      // Rate limiting: GHL allows 120 req/min
      if (i < sortedProspects.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }

    console.log(`\n📤 GHL Import Complete: ${successCount} created, ${failCount} failed`);
  }

  // Final summary
  console.log('\n' + '═'.repeat(60));
  console.log('  ✅ LinkedIn Prospect Finder Complete');
  console.log('═'.repeat(60));
  console.log(`  Prospects found: ${sortedProspects.length}`);
  console.log(`  Avg ICP Score: ${Math.round(sortedScoring.reduce((a, s) => a + s.score, 0) / sortedScoring.length)}`);
  console.log(`  Strong fit: ${sortedScoring.filter(s => s.fit === 'STRONG').length}`);
  console.log(`  Good fit: ${sortedScoring.filter(s => s.fit === 'GOOD').length}`);
  if (shouldExportCSV || isDemo) {
    console.log(`  CSV: ${OUTPUT_DIR}`);
  }
  console.log('═'.repeat(60));
  console.log('\n💡 Next Steps:');
  console.log('   1. Review CSV and import into GHL (Contacts → Import)');
  console.log('   2. Tag high-scored prospects for immediate outreach');
  console.log('   3. Use SALES-PLAYBOOK.md templates for LinkedIn DMs');
  console.log('   4. Schedule discovery calls with STRONG fit prospects\n');
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------
main().catch(err => {
  console.error('FATAL ERROR:', err.message);
  process.exit(1);
});
