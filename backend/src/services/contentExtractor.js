const cheerio = require('cheerio');
const { request, mapConcurrent } = require('./researchHttp');

function stripHtml(value) {
    const $ = cheerio.load(String(value || ''));
    $('script,style,nav,header,footer,noscript,svg,form,iframe').remove();
    $('p,div,li,br,h1,h2,h3,tr').append(' ');
    return $.text().replace(/\s+/g, ' ').trim();
}

async function extractContent(source, signal) {
    let content = '';
    let extractionStatus = 'unavailable';
    let extractionError;
    if (source.isFixture) {
        return { ...source, content: stripHtml(source.snippet || ''), extractionStatus: 'fixture', extractedAt: new Date() };
    }
    try {
        const response = await request(source.url, { signal, timeoutMs: 7000 });
        const type = response.headers['content-type'] || '';
        if (!/text\/html|text\/plain|application\/xhtml/i.test(type)) throw new Error('Unsupported document format; using available abstract/snippet');
        const $ = cheerio.load(response.text);
        const main = $('article,main,[role="main"]').first();
        content = stripHtml(main.length ? main.html() : response.text).slice(0, 24000);
        if (/captcha|access denied|enable javascript|subscribe to read/i.test(content.slice(0, 500)) || content.length < 80) content = '';
        if (content) extractionStatus = 'fetched';
    } catch (error) {
        signal?.throwIfAborted();
        extractionError = error.message;
    }
    if (!content && source.snippet) {
        content = stripHtml(source.snippet).slice(0, 12000);
        extractionStatus = source.sourceType === 'academic' ? 'abstract' : 'snippet';
    }
    return { ...source, content, extractionStatus, extractionError, extractedAt: new Date() };
}

async function extractSources(sources, signal) {
    return mapConcurrent(sources, 4, (source) => module.exports.extractContent(source, signal), signal);
}

module.exports = { stripHtml, extractContent, extractSources };
