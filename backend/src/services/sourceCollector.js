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

function restoreAbstract(index) {
    const words = [];
    for (const [word, positions] of Object.entries(index || {})) {
        for (const position of positions) if (position < 10000) words[position] = word;
    }
    return words.join(' ');
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
    if (task.category === 'academic') {
        providers.push(async () => {
            const data = await json(`https://api.openalex.org/works?search=${encodeURIComponent(task.query)}&per-page=5&select=title,doi,publication_year,primary_location,abstract_inverted_index`, { signal });
            return (data.results || []).map((item) => ({
                title: item.title, url: item.doi || item.primary_location?.landing_page_url,
                snippet: restoreAbstract(item.abstract_inverted_index),
                sourceType: 'academic', provider: 'openalex', publicationYear: item.publication_year
            }));
        });
    }
    if (process.env.TAVILY_API_KEY) providers.push(async () => {
        const data = await json('https://api.tavily.com/search', {
            method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: process.env.TAVILY_API_KEY, query: task.query,
                topic: task.category === 'market' ? 'news' : 'general', max_results: 5 })
        });
        return (data.results || []).map((item) => ({ title: item.title, url: item.url,
            snippet: item.content, relevanceScore: item.score, provider: 'tavily' }));
    });
    if (process.env.SERPER_API_KEY) providers.push(async () => {
        const news = task.category === 'market';
        const data = await json(`https://google.serper.dev/${news ? 'news' : 'search'}`, {
            method: 'POST', signal,
            headers: { 'Content-Type': 'application/json', 'X-API-KEY': process.env.SERPER_API_KEY },
            body: JSON.stringify({ q: task.query, num: 5 })
        });
        return (data[news ? 'news' : 'organic'] || []).map((item) => ({ title: item.title,
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
            sourceType: task.category === 'market' ? 'news' : task.category,
            relevanceScore: 0.62
        }));
    });
    // Google News RSS is also used for general and verification queries. It
    // gives the engine a second public discovery path when a search API is not
    // configured and, importantly, usually returns publisher domains that can
    // be independent of an original Wikipedia or academic result.
    providers.push(async () => {
        const rssUrl = `https://news.google.com/rss/search?q=${encodeURIComponent(task.query)}&hl=en-US&gl=US&ceid=US:en`;
        const response = await request(rssUrl, {
            signal,
            headers: { 'Accept': 'application/rss+xml, application/xml, text/xml' }
        });
        return parseNewsRss(response.text).slice(0, 3).map((item) => ({
            ...item,
            sourceType: task.category === 'market' ? 'news' : task.category,
            relevanceScore: 0.6
        }));
    });
    if (task.category === 'web' || task.category === 'other') providers.push(async () => {
        const data = await json(`https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(task.query)}&srlimit=5&format=json&origin=*`, { signal });
        return (data.query?.search || []).map((item) => ({
            title: item.title,
            url: `https://en.wikipedia.org/wiki/${encodeURIComponent(item.title.replace(/ /g, '_'))}`,
            snippet: stripHtml(item.snippet),
            sourceType: 'web',
            relevanceScore: 0.55,
            provider: 'wikipedia'
        }));
    });
    if (task.category === 'academic') providers.push(async () => {
        const data = await json(`https://api.crossref.org/works?query=${encodeURIComponent(task.query)}&rows=5&select=title,URL,DOI,abstract,published`, { signal });
        return (data.message?.items || []).map((item) => ({
            title: Array.isArray(item.title) ? item.title[0] : item.title,
            url: item.URL || (item.DOI ? `https://doi.org/${item.DOI}` : ''),
            snippet: stripHtml(item.abstract || ''),
            sourceType: 'academic',
            provider: 'crossref',
            publicationYear: item.published?.['date-parts']?.[0]?.[0],
            relevanceScore: 0.65
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
    restoreAbstract,
    parseDuckDuckGoHtml,
    parseNewsRss,
    decodeSearchUrl
};
