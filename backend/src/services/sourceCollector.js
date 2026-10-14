const { request, mapConcurrent } = require('./researchHttp');
const { stripHtml } = require('./contentExtractor');
const cheerio = require('cheerio');

function normalizeUrl(value) {
    try {
        const url = new URL(value);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return '';
        url.hash = '';
        for (const key of [...url.searchParams.keys()]) if (/^(utm_|fbclid|gclid)/i.test(key)) url.searchParams.delete(key);
        url.searchParams.sort();
        return url.href.replace(/\/$/, '');
    } catch { return ''; }
}

async function json(url, options) {
    return JSON.parse((await request(url, options)).text);
}

function decodeSearchUrl(value) {
    try {
        const parsed = new URL(value, 'https://html.duckduckgo.com');
        if (parsed.pathname === '/l/' && parsed.searchParams.get('uddg')) {
            return decodeURIComponent(parsed.searchParams.get('uddg'));
        }
        return parsed.href;
    } catch {
        return value;
    }
}

function parseDuckDuckGoHtml(html) {
    const $ = cheerio.load(html || '');
    return $('.result').map((_index, element) => {
        const result = $(element);
        const link = result.find('a.result__a').first();
        const url = decodeSearchUrl(link.attr('href') || '');
        return {
            title: stripHtml(link.text()),
            url,
            snippet: stripHtml(result.find('.result__snippet').first().text()),
            provider: 'duckduckgo'
        };
    }).get().filter((item) => item.url && item.title);
}

function parseNewsRss(xml) {
    const $ = cheerio.load(xml || '', { xmlMode: true });
    return $('item').map((_index, element) => {
        const item = $(element);
        const publisherUrl = item.find('source').attr('url') || '';
        return {
            title: stripHtml(item.find('title').text()),
            url: item.find('link').text().trim(),
            snippet: stripHtml(item.find('description').text()),
            publicationYear: item.find('pubDate').text().trim(),
            provider: 'google-news',
            ...(publisherUrl ? { publisherUrl } : {})
        };
    }).get().filter((item) => item.url && item.title);
}

async function searchTask(task, signal) {
    if (process.env.NODE_ENV === 'test') {
        return {
            items: [{
                title: `Test fixture source for ${task.query}`,
                url: `https://fixtures.deep-research.test/${task.id}`,
                snippet: `Test fixture evidence for ${task.question || task.query}. The fixture exists only to exercise the persisted pipeline without making network calls.`,
                sourceType: task.category,
                relevanceScore: 0.82,
                isFixture: true
            }],
            warning: ''
        };
    }
    if (process.env.RESEARCH_LIVE_SEARCH === 'false') return { items: [], warning: 'Live search is disabled.' };
    const errors = [];
    const providers = [];
    
    // Market research uses news and general search
    if (process.env.TAVILY_API_KEY) providers.push(async () => {
        const data = await json('https://api.tavily.com/search', {
            method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: process.env.TAVILY_API_KEY, query: task.query,
                topic: 'news', max_results: 5 })
        });
        return (data.results || []).map((item) => ({ title: item.title, url: item.url,
            snippet: item.content, relevanceScore: item.score, provider: 'tavily' }));
    });
    if (process.env.SERPER_API_KEY) providers.push(async () => {
        const data = await json(`https://google.serper.dev/news`, {
            method: 'POST', signal,
            headers: { 'Content-Type': 'application/json', 'X-API-KEY': process.env.SERPER_API_KEY },
            body: JSON.stringify({ q: task.query, num: 5 })
        });
        return (data.news || []).map((item) => ({ title: item.title,
            url: item.link, snippet: item.snippet, provider: 'serper' }));
    });
    // Public providers keep the research engine useful without requiring a
    // paid search key. They are intentionally queried server-side so browser
    // clients never need to bypass CORS or expose provider credentials.
    providers.push(async () => {
        const response = await request(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(task.query)}`, {
            signal,
            headers: { 'Accept': 'text/html', 'Accept-Language': 'en-US,en;q=0.8' }
        });
        return parseDuckDuckGoHtml(response.text).map((item) => ({
            ...item,
            sourceType: 'news',
            relevanceScore: 0.62
        }));
    });
    // Google News RSS for market research
    providers.push(async () => {
        const rssUrl = `https://news.google.com/rss/search?q=${encodeURIComponent(task.query)}&hl=en-US&gl=US&ceid=US:en`;
        const response = await request(rssUrl, {
            signal,
            headers: { 'Accept': 'application/rss+xml, application/xml, text/xml' }
        });
        return parseNewsRss(response.text).slice(0, 3).map((item) => ({
            ...item,
            sourceType: 'news',
            relevanceScore: 0.6
        }));
    });

    const collected = [];
    for (const provider of providers) {
        try {
            const items = await provider();
            collected.push(...items.slice(0, 5));
            // One provider is enough for a quick track, but retaining a small
            // sample from later providers gives verification a real chance to
            // find a source from a different domain.
            if (collected.length >= 12) break;
        } catch (error) {
            signal?.throwIfAborted();
            errors.push(error.message);
        }
    }
    const unique = new Map();
    for (const item of collected) {
        const url = normalizeUrl(item.url);
        if (url && !unique.has(url)) unique.set(url, item);
    }
    return {
        items: [...unique.values()],
        warning: errors.length && !unique.size ? errors.join(' ') : ''
    };
}

async function collectSources(tasks, signal) {
    const batches = await mapConcurrent(tasks, 3, (task) => module.exports.searchTask(task, signal), signal);
    const sources = new Map();
    tasks.forEach((task, index) => {
        const { items, warning } = batches[index];
        task.status = items.length ? 'completed' : 'failed';
        task.warning = warning;
        task.resultsCount = items.length;
        for (const item of items.slice(0, 5)) {
            const url = normalizeUrl(item.url);
            if (!url || sources.has(url)) continue;
            sources.set(url, {
                ...item, url, title: stripHtml(item.title || task.query).slice(0, 500),
                snippet: stripHtml(item.snippet || '').slice(0, 12000),
                sourceType: item.sourceType || (task.category === 'market' ? 'news' : task.category),
                searchQuery: task.query, taskId: task.id, category: task.category,
                provider: item.provider || 'unknown',
                publisherUrl: item.publisherUrl,
                publicationYear: item.publicationYear,
                isFixture: Boolean(item.isFixture),
                isVerificationSource: Boolean(item.isVerificationSource),
                collectedAt: new Date()
            });
        }
    });
    return [...sources.values()].slice(0, 24);
}

module.exports = {
    collectSources,
    searchTask,
    normalizeUrl,
    parseDuckDuckGoHtml,
    parseNewsRss,
    decodeSearchUrl
};
