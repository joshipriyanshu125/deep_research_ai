const assert = require('node:assert/strict');
const test = require('node:test');

const {
    parseDuckDuckGoHtml,
    parseNewsRss,
    decodeSearchUrl
} = require('../src/services/sourceCollector');
const {
    sourceSupportsClaim,
    sourceContradictsClaim,
    verificationQuery
} = require('../src/services/verificationEngine');
const { citationsFromSources, fallbackReport } = require('../src/services/reportGenerator');

test('decodes public search redirect URLs before persistence', () => {
    const target = 'https://example.org/report?utm_source=search';
    const redirect = `//duckduckgo.com/l/?uddg=${encodeURIComponent(target)}&rut=abc`;
    assert.equal(decodeSearchUrl(redirect), target);
});

test('parses DuckDuckGo result pages into source records', () => {
    const html = `
      <div class="result">
        <a class="result__a" href="https://example.org/ev">Electric vehicle report</a>
        <a class="result__snippet">Independent market evidence <b>for EVs</b>.</a>
      </div>`;
    assert.deepEqual(parseDuckDuckGoHtml(html), [{
        title: 'Electric vehicle report',
        url: 'https://example.org/ev',
        snippet: 'Independent market evidence for EVs.',
        provider: 'duckduckgo'
    }]);
});

test('parses Google News RSS into source records', () => {
    const xml = `<?xml version="1.0"?><rss><channel><item>
      <title>EV adoption expands</title>
      <link>https://news.example.org/ev</link>
      <description>Registrations rose by 42%.</description>
      <pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>`;
    const [item] = parseNewsRss(xml);
    assert.equal(item.title, 'EV adoption expands');
    assert.equal(item.url, 'https://news.example.org/ev');
    assert.equal(item.snippet, 'Registrations rose by 42%.');
    assert.equal(item.provider, 'google-news');
});

test('only treats a fetched independent passage with matching metrics as support', () => {
    const claim = { claim: 'EV registrations increased by 42% in 2026' };
    assert.equal(sourceSupportsClaim(claim, {
        title: 'Registration data',
        extractionStatus: 'fetched',
        content: 'The 2026 report records EV registrations increased by 42%.'
    }), true);
    assert.equal(sourceSupportsClaim(claim, {
        title: 'Unrelated overview',
        extractionStatus: 'fetched',
        content: 'Electric mobility is growing across several regions.'
    }), false);
    assert.equal(sourceContradictsClaim(claim, {
        extractionStatus: 'fetched',
        content: 'The 2026 report records EV registrations increased by 35%.'
    }), true);
    assert.equal(sourceSupportsClaim(claim, {
        extractionStatus: 'snippet',
        content: 'The 2026 report records EV registrations increased by 42%.'
    }), false);
});

test('keeps verification queries claim-specific', () => {
    const query = verificationQuery({ claim: 'EV registrations increased by 42% in 2026' }, 'Indian EV market');
    assert.match(query, /EV registrations increased by 42% in 2026/);
    assert.match(query, /Indian EV market/);
});

test('marks verification sources in citation output and fallback reports', () => {
    const evidence = [{ id: 'e1', sourceUrl: 'https://source.example/report' }];
    const checks = [{
        claimId: 'e1',
        claim: 'EV registrations increased by 42%',
        status: 'verified',
        independentSourceUrls: ['https://verify.example/check'],
        verificationMethod: 'independent_web_search'
    }];
    const citations = citationsFromSources([
        { title: 'Original report', url: 'https://source.example/report', sourceType: 'web' },
        { title: 'Independent check', url: 'https://verify.example/check', sourceType: 'web', isVerificationSource: true }
    ], evidence, checks);
    assert.equal(citations[1].isVerificationSource, true);
    assert.deepEqual(citations[1].verificationFor, ['e1']);

    const report = fallbackReport('Indian EV market', {
        summary: 'One evidence item was analyzed.',
        findings: [{ insight: 'EV registrations increased by 42%', evidenceIds: ['e1'] }],
        comparisons: []
    }, checks, citations, {
        independentVerification: true,
        attemptedClaims: 1,
        verifiedClaims: 1
    });
    assert.match(report, /Independent web verification was attempted/);
    assert.match(report, /verification source/);
});
