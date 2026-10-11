const { request, mapConcurrent } = require('./researchHttp');
const { stripHtml } = require('./contentExtractor');

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
    for (const provider of providers) {
        try {
            const items = await provider();
            if (items.length) return { items, warning: errors.join(' ') };
        } catch (error) {
            signal?.throwIfAborted();
            errors.push(error.message);
        }
    }
    return { items: [], warning: errors.join(' ') || 'No results. Configure TAVILY_API_KEY or SERPER_API_KEY for web/news search.' };
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
                isFixture: Boolean(item.isFixture), collectedAt: new Date()
            });
        }
    });
    return [...sources.values()].slice(0, 24);
}

module.exports = { collectSources, searchTask, normalizeUrl, restoreAbstract };
