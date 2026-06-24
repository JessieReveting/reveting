#!/usr/bin/env node

/**
 * AI Conversation Reader/Aggregator
 * @module ai-conversation-readers
 * @version 1.0.0
 *
 * Unified interface to read, search, export, and summarize
 * AI conversation history from Claude, ChatGPT, Perplexity, and Gemini.
 *
 * Usage:
 *   node ai-conversation-readers.js --demo
 *   node ai-conversation-readers.js --tool all --action list
 *   node ai-conversation-readers.js --tool claude --action search --query "javascript"
 *   node ai-conversation-readers.js --tool chatgpt --action export --format markdown --output export.md
 *   node ai-conversation-readers.js --tool all --action summarize --limit 5
 */

const fs = require('fs');
const path = require('path');
const { parseArgs } = require('node:util');

// ============================================================================
// CLI Argument Parsing
// ============================================================================

const options = {
  tool: { type: 'string', default: 'all' },
  action: { type: 'string', default: 'list' },
  query: { type: 'string', default: '' },
  limit: { type: 'string', default: '10' },
  format: { type: 'string', default: 'json' },
  output: { type: 'string', default: '' },
  demo: { type: 'boolean', default: false },
};

const { values } = parseArgs({ options, strict: false });

const TOOL = values.tool.toLowerCase();
const ACTION = values.action.toLowerCase();
const QUERY = values.query;
const LIMIT = parseInt(values.limit, 10);
const FORMAT = values.format.toLowerCase();
const OUTPUT = values.output;
const DEMO = values.demo;

const VALID_TOOLS = ['claude', 'chatgpt', 'perplexity', 'gemini', 'all'];
const VALID_ACTIONS = ['list', 'search', 'export', 'summarize'];
const VALID_FORMATS = ['json', 'markdown', 'csv'];

if (!VALID_TOOLS.includes(TOOL)) {
  console.error(`Invalid tool: ${TOOL}. Valid options: ${VALID_TOOLS.join(', ')}`);
  process.exit(1);
}

if (!VALID_ACTIONS.includes(ACTION)) {
  console.error(`Invalid action: ${ACTION}. Valid options: ${VALID_ACTIONS.join(', ')}`);
  process.exit(1);
}

if (!VALID_FORMATS.includes(FORMAT)) {
  console.error(`Invalid format: ${FORMAT}. Valid options: ${VALID_FORMATS.join(', ')}`);
  process.exit(1);
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toISOString().split('T')[0];
}

function truncate(str, maxLen = 150) {
  if (!str) return '';
  return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
}

function searchInText(text, query) {
  if (!query) return true;
  return text.toLowerCase().includes(query.toLowerCase());
}

function outputResult(data, format, toolName) {
  let content;
  switch (format) {
    case 'markdown':
      content = toMarkdown(data, toolName);
      break;
    case 'csv':
      content = toCSV(data);
      break;
    default:
      content = JSON.stringify(data, null, 2);
  }

  if (OUTPUT) {
    fs.writeFileSync(OUTPUT, content, 'utf-8');
    console.log(`Output written to: ${OUTPUT}`);
  } else {
    console.log(content);
  }
}

function toMarkdown(conversations, toolName) {
  let md = `# AI Conversations${toolName !== 'all' ? ` - ${toolName}` : ''}\n\n`;
  md += `> Generated on ${new Date().toISOString()}\n\n`;

  for (const conv of conversations) {
    md += `## ${conv.title || 'Untitled'}\n\n`;
    md += `- **Date:** ${conv.date}\n`;
    md += `- **Tool:** ${conv.tool}\n`;
    if (conv.tags && conv.tags.length) md += `- **Tags:** ${conv.tags.join(', ')}\n`;
    md += `\n`;

    if (conv.summary) {
      md += `### Summary\n${conv.summary}\n\n`;
    }

    if (conv.messages) {
      md += `### Messages\n`;
      for (const msg of conv.messages.slice(0, 20)) {
        md += `**${msg.role}:** ${truncate(msg.content, 300)}\n\n`;
      }
      if (conv.messages.length > 20) {
        md += `*... and ${conv.messages.length - 20} more messages*\n\n`;
      }
    }

    md += `---\n\n`;
  }

  return md;
}

function toCSV(conversations) {
  const headers = ['tool', 'title', 'date', 'summary', 'messageCount', 'tags'];
  const rows = [headers.join(',')];

  for (const conv of conversations) {
    const row = [
      conv.title || 'Untitled',
      conv.date,
      truncate(conv.summary || '', 100),
      conv.messages?.length || 0,
      (conv.tags || []).join('; '),
    ].map(field => `"${String(field).replace(/"/g, '""')}"`);
    rows.push(row.join(','));
  }

  return rows.join('\n');
}

// ============================================================================
// Demo Data
// ============================================================================

const DEMO_CONVERSATIONS = {
  claude: [
    {
      id: 'claude-001',
      title: 'React Performance Optimization',
      tool: 'claude',
      date: '2026-06-20',
      tags: ['react', 'performance', 'javascript'],
      summary: 'Discussed React rendering optimization techniques including useMemo, useCallback, and virtualization for large lists.',
      messages: [
        { role: 'user', content: 'How can I optimize a React component that re-renders too frequently?' },
        { role: 'assistant', content: 'There are several strategies to optimize React re-renders: 1) Use useMemo for expensive computations, 2) Use useCallback for function references passed to children, 3) Implement React.memo for component-level memoization, 4) Consider virtualization for long lists with react-window or react-virtuoso.' },
        { role: 'user', content: 'Can you show me an example of useMemo with a filtered list?' },
        { role: 'assistant', content: 'const filteredItems = useMemo(() => items.filter(item => item.name.includes(searchTerm)), [items, searchTerm]); This ensures the filtering only runs when items or searchTerm changes, not on every render.' },
      ],
    },
    {
      id: 'claude-002',
      title: 'Node.js API Design Patterns',
      tool: 'claude',
      date: '2026-06-18',
      tags: ['nodejs', 'api', 'rest'],
      summary: 'Explored RESTful API design patterns including versioning, pagination, error handling, and middleware architecture.',
      messages: [
        { role: 'user', content: 'What are the best practices for designing a REST API in Node.js?' },
        { role: 'assistant', content: 'Key REST API best practices: Use proper HTTP methods (GET, POST, PUT, DELETE), implement consistent error handling with status codes, use versioning (e.g., /api/v1/), implement pagination for list endpoints, use middleware for auth/validation, and document with OpenAPI/Swagger.' },
      ],
    },
    {
      id: 'claude-003',
      title: 'Database Schema Design',
      tool: 'claude',
      date: '2026-06-15',
      tags: ['database', 'postgresql', 'schema'],
      summary: 'Designed a PostgreSQL schema for a multi-tenant SaaS application with row-level security.',
      messages: [
        { role: 'user', content: 'I need to design a multi-tenant database schema for my SaaS app. What approach do you recommend?' },
        { role: 'assistant', content: 'For multi-tenant SaaS, you have three main approaches: 1) Separate databases per tenant (best isolation), 2) Shared database with separate schemas, 3) Shared database with tenant_id column and Row-Level Security. For most cases, option 3 with PostgreSQL RLS offers the best balance of simplicity and security.' },
      ],
    },
  ],
  chatgpt: [
    {
      id: 'chatgpt-001',
      title: 'Python Data Pipeline Architecture',
      tool: 'chatgpt',
      date: '2026-06-21',
      tags: ['python', 'data-engineering', 'pipeline'],
      summary: 'Designed a data pipeline architecture using Apache Airflow for ETL processing with error handling and monitoring.',
      messages: [
        { role: 'user', content: 'Help me design a data pipeline for processing daily sales reports from multiple sources.' },
        { role: 'assistant', content: 'I recommend using Apache Airflow with the following DAG structure: 1) Extract tasks pulling from each source (API, S3, database), 2) Transform tasks using Pandas/Polars for data cleaning and normalization, 3) Load tasks writing to your data warehouse. Add retry logic, SLA monitoring, and alerting via Slack/email.' },
        { role: 'user', content: 'How should I handle schema changes from upstream sources?' },
        { role: 'assistant', content: 'Implement schema validation at the extract step using Pydantic or Great Expectations. Add a schema registry to track versions, and create alerting when schema drift is detected. Consider using a dead-letter queue for records that fail validation.' },
      ],
    },
    {
      id: 'chatgpt-002',
      title: 'TypeScript Monorepo Setup',
      tool: 'chatgpt',
      date: '2026-06-19',
      tags: ['typescript', 'monorepo', 'tooling'],
      summary: 'Set up a TypeScript monorepo using Turborepo with shared packages and consistent tooling.',
      messages: [
        { role: 'user', content: 'What is the best way to set up a TypeScript monorepo in 2026?' },
        { role: 'assistant', content: 'Turborepo is the leading choice for TypeScript monorepos. Key setup: 1) Use pnpm workspaces for dependency management, 2) Configure Turborepo pipeline for build orchestration, 3) Create shared packages for types, utilities, and configs, 4) Use ESLint flat config and Prettier for consistency, 5) Set up changesets for versioning.' },
      ],
    },
    {
      id: 'chatgpt-003',
      title: 'Kubernetes Deployment Strategy',
      tool: 'chatgpt',
      date: '2026-06-16',
      tags: ['kubernetes', 'devops', 'deployment'],
      summary: 'Planned a blue-green deployment strategy with automated rollback for a microservices architecture.',
      messages: [
        { role: 'user', content: 'How should I implement blue-green deployments on Kubernetes?' },
        { role: 'assistant', content: 'For blue-green on Kubernetes: 1) Maintain two identical deployments (blue/green), 2) Use a Service selector to switch traffic, 3) Automate with ArgoCD or Flux, 4) Implement health checks and automated rollback with tools like Flagger, 5) Use feature flags for gradual rollout within the green environment.' },
      ],
    },
  ],
  perplexity: [
    {
      id: 'perplexity-001',
      title: 'AI Agent Frameworks Comparison',
      tool: 'perplexity',
      date: '2026-06-22',
      tags: ['ai', 'agents', 'comparison'],
      summary: 'Compared popular AI agent frameworks including LangChain, CrewAI, AutoGen, and Claude tool use patterns.',
      messages: [
        { role: 'user', content: 'What are the best AI agent frameworks available in 2026?' },
        { role: 'assistant', content: 'As of 2026, the AI agent framework landscape includes: LangChain (most mature ecosystem), CrewAI (multi-agent orchestration), AutoGen (Microsoft-backed multi-agent), Claude native tool use (simplest for Claude users), and OpenAI Assistants API. For production use, consider LangChain for complex pipelines or CrewAI for agent teams.' },
      ],
    },
    {
      id: 'perplexity-002',
      title: 'WebAssembly Performance Analysis',
      tool: 'perplexity',
      date: '2026-06-17',
      tags: ['webassembly', 'performance', 'web'],
      summary: 'Analyzed WebAssembly performance characteristics for compute-intensive web applications.',
      messages: [
        { role: 'user', content: 'When does it make sense to use WebAssembly in a web application?' },
        { role: 'assistant', content: 'WebAssembly excels for: 1) Compute-intensive tasks (image/video processing, physics simulations), 2) Porting existing C++/Rust codebases to web, 3) Cryptographic operations, 4) Gaming engines. However, for DOM manipulation and typical web UI, JavaScript is still preferred due to overhead in JS-WASM communication.' },
      ],
    },
  ],
  gemini: [
    {
      id: 'gemini-001',
      title: 'Mobile App Architecture',
      tool: 'gemini',
      date: '2026-06-21',
      tags: ['mobile', 'architecture', 'flutter'],
      summary: 'Designed a scalable mobile app architecture using Flutter with clean architecture principles.',
      messages: [
        { role: 'user', content: 'I need help designing the architecture for a cross-platform mobile app. Should I use Flutter or React Native?' },
        { role: 'assistant', content: 'Both are excellent choices. Flutter advantages: consistent UI across platforms, excellent performance via Skia rendering, strong typing with Dart, growing ecosystem. React Native advantages: larger community, JavaScript knowledge reuse, CodePush for OTA updates. For a new project in 2026, Flutter is recommended unless your team has strong React expertise.' },
      ],
    },
    {
      id: 'gemini-002',
      title: 'GraphQL vs tRPC Decision',
      tool: 'gemini',
      date: '2026-06-14',
      tags: ['graphql', 'trpc', 'api-design'],
      summary: 'Compared GraphQL and tRPC for a full-stack TypeScript application, recommending tRPC for type safety.',
      messages: [
        { role: 'user', content: 'Should I use GraphQL or tRPC for my TypeScript full-stack app?' },
        { role: 'assistant', content: 'For full-stack TypeScript apps, tRPC offers superior end-to-end type safety without code generation. GraphQL is better when: 1) You need a public API with different consumers, 2) You want partial data fetching, 3) You need a schema registry. For internal APIs or single-consumer apps, tRPC is simpler and more productive.' },
      ],
    },
  ],
};

// ============================================================================
// Connector Interface
// ============================================================================

class BaseConnector {
  constructor(name) {
    this.name = name;
  }

  async list(limit = 10) {
    throw new Error('list() must be implemented by subclass');
  }

  async search(query, limit = 10) {
    throw new Error('search() must be implemented by subclass');
  }

  async summarize(limit = 5) {
    throw new Error('summarize() must be implemented by subclass');
  }
}

// ============================================================================
// Demo Connector
// ============================================================================

class DemoConnector extends BaseConnector {
  constructor(toolName) {
    super(toolName);
    this.conversations = DEMO_CONVERSATIONS[toolName] || [];
  }

  async list(limit = 10) {
    return this.conversations.slice(0, limit);
  }

  async search(query, limit = 10) {
    return this.conversations
      .filter(conv => {
        const text = `${conv.title} ${conv.summary} ${(conv.tags || []).join(' ')} ${(conv.messages || []).map(m => m.content).join(' ')}`;
        return searchInText(text, query);
      })
      .slice(0, limit);
  }

  async summarize(limit = 5) {
    return this.conversations.slice(0, limit).map(conv => ({
      title: conv.title,
      tool: conv.tool,
      date: conv.date,
      summary: conv.summary,
      messageCount: conv.messages?.length || 0,
      tags: conv.tags || [],
    }));
  }
}

// ============================================================================
// Claude Connector
// ============================================================================

class ClaudeConnector extends BaseConnector {
  constructor() {
    super('claude');
    this.apiKey = process.env.CLAUDE_API_KEY;
    this.exportPath = process.env.CLAUDE_EXPORT_PATH;
  }

  async list(limit = 10) {
    if (DEMO) return new DemoConnector('claude').list(limit);
    if (this.apiKey) return this._listFromAPI(limit);
    if (this.exportPath) return this._listFromExport(limit);
    throw new Error('Set CLAUDE_API_KEY or CLAUDE_EXPORT_PATH. Run --demo for sample output.');
  }

  async _listFromAPI(limit) {
    console.error('Note: Claude conversation history API requires Team/Enterprise plan.');
    return [];
  }

  async _listFromExport(limit) {
    const exportDir = this.exportPath;
    if (!fs.existsSync(exportDir)) {
      throw new Error(`Export directory not found: ${exportDir}`);
    }
    const files = fs.readdirSync(exportDir)
      .filter(f => f.endsWith('.json'))
      .slice(0, limit);
    return files.map(file => {
      const data = JSON.parse(fs.readFileSync(path.join(exportDir, file), 'utf-8'));
      return {
        id: file.replace('.json', ''),
        title: data.title || 'Untitled',
        tool: 'claude',
        date: data.created_at ? data.created_at.split('T')[0] : 'unknown',
        tags: data.tags || [],
        summary: data.summary || '',
        messages: data.messages || data.conversation || [],
      };
    });
  }

  async search(query, limit = 10) {
    const all = await this.list(1000);
    return all.filter(conv => {
      const text = `${conv.title} ${conv.summary} ${(conv.messages || []).map(m => m.content || '').join(' ')}`;
      return searchInText(text, query);
    }).slice(0, limit);
  }

  async summarize(limit = 5) {
    const convs = await this.list(limit);
    return convs.map(conv => ({
      title: conv.title,
      tool: conv.tool,
      date: conv.date,
      summary: conv.summary || truncate(conv.messages?.[0]?.content || '', 200),
      messageCount: conv.messages?.length || 0,
      tags: conv.tags || [],
    }));
  }
}

// ============================================================================
// ChatGPT Connector
// ============================================================================

class ChatGPTConnector extends BaseConnector {
  constructor() {
    super('chatgpt');
    this.apiKey = process.env.OPENAI_API_KEY;
    this.exportPath = process.env.CHATGPT_EXPORT_PATH;
  }

  async list(limit = 10) {
    if (DEMO) return new DemoConnector('chatgpt').list(limit);
    if (this.apiKey) return this._listFromAPI(limit);
    if (this.exportPath) return this._listFromExport(limit);
    throw new Error('Set OPENAI_API_KEY or CHATGPT_EXPORT_PATH. Run --demo for sample output.');
  }

  async _listFromAPI(limit) {
    console.error('Note: ChatGPT conversation history via API requires Plus or higher.');
    return [];
  }

  async _listFromExport(limit) {
    const filePath = this.exportPath;
    if (!fs.existsSync(filePath)) {
      throw new Error(`Export file not found: ${filePath}`);
    }
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const conversations = Array.isArray(data) ? data : data.conversations || data.data || [];
    return conversations.slice(0, limit).map(conv => ({
      id: conv.id || conv.conversation_id || 'unknown',
      title: conv.title || 'Untitled',
      tool: 'chatgpt',
      date: conv.create_time ? new Date(conv.create_time * 1000).toISOString().split('T')[0] : 'unknown',
      tags: conv.tags || [],
      summary: truncate(
        (conv.messages || conv.mapping || []).filter(m => m.role === 'assistant')
          .slice(0, 1).map(m => (m.content || []).map(c => c.text || '').join('') || '').join('') || '',
        200
      ),
      messages: (conv.messages || []).map(m => ({
        role: m.role,
        content: typeof m.content === 'string' ? m.content :
          (m.content || []).map(c => c.text || '').join('') || '',
      })),
    }));
  }

  async search(query, limit = 10) {
    const all = await this.list(1000);
    return all.filter(conv => {
      const text = `${conv.title} ${conv.summary} ${(conv.messages || []).map(m => m.content || '').join(' ')}`;
      return searchInText(text, query);
    }).slice(0, limit);
  }

  async summarize(limit = 5) {
    const convs = await this.list(limit);
    return convs.map(conv => ({
      title: conv.title,
      tool: conv.tool,
      date: conv.date,
      summary: conv.summary || truncate(conv.messages?.[0]?.content || '', 200),
      messageCount: conv.messages?.length || 0,
      tags: conv.tags || [],
    }));
  }
}

// ============================================================================
// Perplexity Connector
// ============================================================================

class PerplexityConnector extends BaseConnector {
  constructor() {
    super('perplexity');
    this.apiKey = process.env.PERPLEXITY_API_KEY;
    this.exportPath = process.env.PERPLEXITY_EXPORT_PATH;
  }

  async list(limit = 10) {
    if (DEMO) return new DemoConnector('perplexity').list(limit);
    if (this.apiKey) return this._listFromAPI(limit);
    if (this.exportPath) return this._listFromExport(limit);
    throw new Error('Set PERPLEXITY_API_KEY or PERPLEXITY_EXPORT_PATH. Run --demo for sample output.');
  }

  async _listFromAPI(limit) {
    console.error('Note: Perplexity conversation history API is limited. Export recommended.');
    return [];
  }

  async _listFromExport(limit) {
    const filePath = this.exportPath;
    if (!fs.existsSync(filePath)) {
      throw new Error(`Export file not found: ${filePath}`);
    }
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const conversations = Array.isArray(data) ? data : data.conversations || data.history || [];
    return conversations.slice(0, limit).map(conv => ({
      id: conv.id || conv.uuid || 'unknown',
      title: conv.title || conv.query || 'Untitled',
      tool: 'perplexity',
      date: conv.created_at || conv.timestamp || 'unknown',
      tags: conv.tags || conv.topics || [],
      summary: truncate(conv.answer || conv.summary || '', 200),
      messages: [
        { role: 'user', content: conv.query || '' },
        { role: 'assistant', content: conv.answer || '' },
      ],
    }));
  }

  async search(query, limit = 10) {
    const all = await this.list(1000);
    return all.filter(conv => {
      const text = `${conv.title} ${conv.summary} ${(conv.messages || []).map(m => m.content || '').join(' ')}`;
      return searchInText(text, query);
    }).slice(0, limit);
  }

  async summarize(limit = 5) {
    const convs = await this.list(limit);
    return convs.map(conv => ({
      title: conv.title,
      tool: conv.tool,
      date: conv.date,
      summary: conv.summary || truncate(conv.messages?.[0]?.content || '', 200),
      messageCount: conv.messages?.length || 0,
      tags: conv.tags || [],
    }));
  }
}

// ============================================================================
// Gemini Connector
// ============================================================================

class GeminiConnector extends BaseConnector {
  constructor() {
    super('gemini');
    this.apiKey = process.env.GEMINI_API_KEY;
    this.exportPath = process.env.GEMINI_EXPORT_PATH;
  }

  async list(limit = 10) {
    if (DEMO) return new DemoConnector('gemini').list(limit);
    if (this.apiKey) return this._listFromAPI(limit);
    if (this.exportPath) return this._listFromExport(limit);
    throw new Error('Set GEMINI_API_KEY or GEMINI_EXPORT_PATH. Run --demo for sample output.');
  }

  async _listFromAPI(limit) {
    console.error('Note: Gemini conversation history via API is limited. Google Takeout recommended.');
    return [];
  }

  async _listFromExport(limit) {
    const filePath = this.exportPath;
    if (!fs.existsSync(filePath)) {
      throw new Error(`Export file not found: ${filePath}`);
    }
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const conversations = Array.isArray(data) ? data : data.conversations || data.chats || [];
    return conversations.slice(0, limit).map(conv => ({
      id: conv.id || conv.conversationId || 'unknown',
      title: conv.title || (conv.messages?.[0]?.content || '').substring(0, 50) || 'Untitled',
      tool: 'gemini',
      date: conv.createTime || conv.timestamp || 'unknown',
      tags: conv.tags || [],
      summary: truncate(
        (conv.messages || []).filter(m => m.role === 'model' || m.role === 'assistant')
          .slice(-1).map(m => m.content || '').join('') || '',
        200
      ),
      messages: (conv.messages || []).map(m => ({
        role: m.role === 'model' ? 'assistant' : m.role,
        content: m.content || (m.parts || []).map(p => p.text || '').join('') || '',
      })),
    }));
  }

  async search(query, limit = 10) {
    const all = await this.list(1000);
    return all.filter(conv => {
      const text = `${conv.title} ${conv.summary} ${(conv.messages || []).map(m => m.content || '').join(' ')}`;
      return searchInText(text, query);
    }).slice(0, limit);
  }

  async summarize(limit = 5) {
    const convs = await this.list(limit);
    return convs.map(conv => ({
      title: conv.title,
      tool: conv.tool,
      date: conv.date,
      summary: conv.summary || truncate(conv.messages?.[0]?.content || '', 200),
      messageCount: conv.messages?.length || 0,
      tags: conv.tags || [],
    }));
  }
}

// ============================================================================
// Connector Factory
// ============================================================================

function getConnector(tool) {
  switch (tool) {
    case 'claude': return new ClaudeConnector();
    case 'chatgpt': return new ChatGPTConnector();
    case 'perplexity': return new PerplexityConnector();
    case 'gemini': return new GeminiConnector();
    default: throw new Error(`Unknown tool: ${tool}`);
  }
}

function getConnectors(tool) {
  if (tool === 'all') {
    return [
      new ClaudeConnector(),
      new ChatGPTConnector(),
      new PerplexityConnector(),
      new GeminiConnector(),
    ];
  }
  return [getConnector(tool)];
}

// ============================================================================
// Action Handlers
// ============================================================================

async function handleList() {
  const connectors = getConnectors(TOOL);
  let allConversations = [];
  for (const connector of connectors) {
    try {
      const convs = await connector.list(LIMIT);
      allConversations = allConversations.concat(convs);
    } catch (err) {
      console.error(`[${connector.name}] Error: ${err.message}`);
    }
  }
  return allConversations;
}

async function handleSearch() {
  if (!QUERY) {
    console.error('Search requires --query parameter');
    process.exit(1);
  }
  const connectors = getConnectors(TOOL);
  let allResults = [];
  for (const connector of connectors) {
    try {
      const results = await connector.search(QUERY, LIMIT);
      allResults = allResults.concat(results);
    } catch (err) {
      console.error(`[${connector.name}] Error: ${err.message}`);
    }
  }
  return allResults;
}

async function handleExport() {
  return handleList();
}

async function handleSummarize() {
  const connectors = getConnectors(TOOL);
  let summaries = [];
  for (const connector of connectors) {
    try {
      const summary = await connector.summarize(LIMIT);
      summaries = summaries.concat(summary);
    } catch (err) {
      console.error(`[${connector.name}] Error: ${err.message}`);
    }
  }
  return summaries;
}

// ============================================================================
// Demo Mode
// ============================================================================

function printDemoHeader() {
  console.log('='.repeat(70));
  console.log('  AI Conversation Reader/Aggregator - DEMO MODE');
  console.log('='.repeat(70));
  console.log();
  console.log('This demo shows the expected output format using sample data.');
  console.log('To use with real data, set the appropriate environment variables:');
  console.log('  CLAUDE_API_KEY / CLAUDE_EXPORT_PATH');
  console.log('  OPENAI_API_KEY / CHATGPT_EXPORT_PATH');
  console.log('  PERPLEXITY_API_KEY / PERPLEXITY_EXPORT_PATH');
  console.log('  GEMINI_API_KEY / GEMINI_EXPORT_PATH');
  console.log();
  console.log('-'.repeat(70));
}

async function runDemo() {
  printDemoHeader();

  // Demo: List all conversations
  console.log('\nDEMO: List all conversations (limit 10)\n');
  const listResult = await handleList();
  console.log(`Found ${listResult.length} conversations across all tools.\n`);
  for (const conv of listResult) {
    console.log(`  [${conv.tool}] ${conv.title} (${conv.date}) - ${conv.messages?.length || 0} messages`);
  }

  // Demo: Search
  console.log('\n' + '-'.repeat(70));
  console.log('\nDEMO: Search for "performance"\n');
  const allConvs = DEMO_CONVERSATIONS.claude.concat(DEMO_CONVERSATIONS.chatgpt)
    .concat(DEMO_CONVERSATIONS.perplexity).concat(DEMO_CONVERSATIONS.gemini);
  const searchMatches = allConvs.filter(conv => {
    const text = `${conv.title} ${conv.summary} ${(conv.tags || []).join(' ')}`;
    return text.toLowerCase().includes('performance');
  });
  console.log(`Found ${searchMatches.length} matches for "performance":\n`);
  for (const conv of searchMatches) {
    console.log(`  [${conv.tool}] ${conv.title}`);
    console.log(`    ${truncate(conv.summary, 120)}`);
  }

  // Demo: Summarize
  console.log('\n' + '-'.repeat(70));
  console.log('\nDEMO: Summarize recent conversations\n');
  const summaries = await handleSummarize();
  for (const s of summaries) {
    console.log(`  [${s.tool}] ${s.title} (${s.date})`);
    console.log(`    Summary: ${truncate(s.summary, 100)}`);
    console.log(`    Messages: ${s.messageCount} | Tags: ${(s.tags || []).join(', ')}`);
    console.log();
  }

  // Demo: Export formats
  console.log('-'.repeat(70));
  console.log('\nDEMO: Export formats\n');

  console.log('--- JSON format (first 2 conversations) ---');
  console.log(JSON.stringify(listResult.slice(0, 2), null, 2));

  console.log('\n--- Markdown format (first conversation) ---');
  console.log(toMarkdown(listResult.slice(0, 1), 'all'));

  console.log('--- CSV format (all conversations) ---');
  console.log(toCSV(listResult));

  console.log('\n' + '='.repeat(70));
  console.log('Demo complete! Use --tool, --action, --format, --output for real usage.');
  console.log('='.repeat(70));
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  if (DEMO) {
    await runDemo();
    return;
  }

  let result;

  switch (ACTION) {
    case 'list':
      result = await handleList();
      break;
    case 'search':
      result = await handleSearch();
      break;
    case 'export':
      result = await handleExport();
      break;
    case 'summarize':
      result = await handleSummarize();
      break;
    default:
      console.error(`Unknown action: ${ACTION}`);
      process.exit(1);
  }

  if (result.length === 0) {
    console.log('No conversations found. Use --demo to see sample output.');
    return;
  }

  outputResult(result, FORMAT, TOOL);
}

main().catch(err => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
