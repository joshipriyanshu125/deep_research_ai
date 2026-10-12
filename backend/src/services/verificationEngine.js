const crypto = require('node:crypto');
const { searchTask, normalizeUrl } = require('./sourceCollector');
const { extractSources } = require('./contentExtractor');
const { mapConcurrent } = require('./researchHttp');
const { overlap } = require('./evidenceEngine');

function domainOf(value) {
    try {
        return new URL(value).hostname.replace(/^www\./i, '').toLowerCase();
    } catch {
        return '';
    }
}

function sourceDomain(source) {
    return domainOf(source?.publisherUrl || source?.url);
}

function numbers(value) {
    return new Set((String(value || '').match(/\d+(?:[.,]\d+)?/g) || [])
        .map((item) => item.replace(/,/g, '')));
}

function metricNumbers(value) {
    return new Set([...numbers(value)].filter((number) => {
        const numeric = Number(number);
        return numeric < 1900 || numeric > 2100;
    }));
}

function sourceSupportsClaim(claim, source) {
    if (source.extractionStatus !== 'fetched') return false;
    const claimNumbers = numbers(claim.claim);
    return String(source.content || '').split(/(?<=[.!?])\s+/).some((passage) => {
        const tokenOverlap = overlap(claim.claim, passage);
        if (claimNumbers.size === 0) return tokenOverlap >= 0.72;
        const passageNumbers = numbers(passage);
        return tokenOverlap >= 0.6 && [...claimNumbers].every((number) => passageNumbers.has(number));
    });
}

function sourceContradictsClaim(claim, source) {
    if (source.extractionStatus !== 'fetched') return false;
    const claimMetrics = metricNumbers(claim.claim);
    if (claimMetrics.size === 0) return false;
    return String(source.content || '').split(/(?<=[.!?])\s+/).some((passage) => {
        const passageMetrics = metricNumbers(passage);
        const claimWithoutNumbers = claim.claim.replace(/\d+(?:[.,]\d+)?/g, ' ');
        const passageWithoutNumbers = passage.replace(/\d+(?:[.,]\d+)?/g, ' ');
        return passageMetrics.size > 0 &&
            overlap(claimWithoutNumbers, passageWithoutNumbers) >= 0.6 &&
            [...claimMetrics].every((number) => !passageMetrics.has(number));
    });
}

function verificationQuery(claim, query) {
    // Long exact quotations are rarely indexed verbatim. Search a compact
    // assertion with its metric instead, then inspect actual retrieved pages.
    const compactClaim = claim.claim.replace(/[\r\n]+/g, ' ').split(/\s+/).slice(0, 14).join(' ');
    return `${compactClaim} ${String(query || '').split(/\s+/).slice(0, 6).join(' ')}`.slice(0, 190);
}

function verificationTaskId(claim) {
    return `verification_${crypto.createHash('sha1').update(claim.id || claim.claim).digest('hex').slice(0, 12)}`;
}

/**
 * Performs an independent web pass for evidence claims. The original source
 * domain is excluded, and a result is only considered corroboration after its
 * page has been fetched and its text has been compared with the claim.
 */
async function verifyEvidence(evidence, originalSources, query, signal, options = {}) {
    if (process.env.NODE_ENV === 'test' || process.env.RESEARCH_LIVE_SEARCH === 'false') {
        return { checks: [], sources: [], attempted: false };
    }

    const maxClaims = Math.max(1, Math.min(12, Number(options.maxClaims) || 8));
    const candidates = [...(evidence || [])]
        .filter((item) => item.claim && item.verificationStatus !== 'unverified')
        .sort((left, right) => (right.confidence || 0) - (left.confidence || 0))
        .slice(0, maxClaims);
    const originalDomains = new Set((originalSources || []).map(sourceDomain).filter(Boolean));

    const results = await mapConcurrent(candidates, 2, async (claim) => {
        const task = {
            id: verificationTaskId(claim),
            query: verificationQuery(claim, query),
            category: 'web'
        };
        let result;
        try {
            result = await searchTask(task, signal);
        } catch (error) {
            signal?.throwIfAborted();
            return {
                claimId: claim.id,
                claim: claim.claim,
                status: 'unverified',
                confidence: Number((claim.confidence || 0.45).toFixed(3)),
                sourceUrls: [claim.sourceUrl],
                independentSourceUrls: [],
                searchQuery: task.query,
                verificationMethod: 'independent_web_search',
                error: error.message,
                _sources: []
            };
        }

        const candidatesFromSearch = (result.items || []).filter((item) => {
            const url = normalizeUrl(item.url);
            return url && url !== normalizeUrl(claim.sourceUrl) &&
                !originalDomains.has(sourceDomain(item));
        }).slice(0, 8).map((item) => ({
            ...item,
            url: normalizeUrl(item.url),
            category: 'verification',
            isVerificationSource: true,
            verificationFor: claim.id,
            searchQuery: task.query,
            taskId: task.id
        }));
        let fetched = [];
        try {
            fetched = candidatesFromSearch.length ? await extractSources(candidatesFromSearch, signal) : [];
        } catch (error) {
            signal?.throwIfAborted();
        }
        const supporting = fetched.filter((source) => sourceSupportsClaim(claim, source));
        const contradictory = fetched.filter((source) => sourceContradictsClaim(claim, source));
        const independentSourceUrls = supporting.map((source) => source.url);
        const status = supporting.length > 0
            ? 'verified'
            : contradictory.length > 0
                ? 'contradicted'
                : 'unverified';
        const confidence = Math.min(
            0.98,
            Math.max(0.35, (claim.confidence || 0.45) + supporting.length * 0.1 - contradictory.length * 0.12)
        );
        return {
            claimId: claim.id,
            claim: claim.claim,
            status,
            supported: status === 'verified',
            confidence: Number(confidence.toFixed(3)),
            sourceUrls: [claim.sourceUrl, ...independentSourceUrls, ...contradictory.map((source) => source.url)]
                .filter((url, index, all) => url && all.indexOf(url) === index),
            independentSourceUrls,
            contradictionSourceUrls: contradictory.map((source) => source.url),
            searchQuery: task.query,
            verificationMethod: 'independent_web_search',
            verifiedAt: new Date(),
            _sources: fetched
        };
    }, signal);

    const sourceMap = new Map();
    for (const result of results) {
        // Only pages actually used to support or dispute a claim are cited.
        const citedUrls = new Set([...(result.independentSourceUrls || []), ...(result.contradictionSourceUrls || [])]);
        for (const source of result._sources || []) {
            if (citedUrls.has(source.url)) sourceMap.set(source.url, source);
        }
        delete result._sources;
    }
    return {
        checks: results.filter(Boolean),
        sources: [...sourceMap.values()],
        attempted: candidates.length > 0,
        attemptedClaims: candidates.length
    };
}

module.exports = {
    verifyEvidence,
    sourceSupportsClaim,
    sourceContradictsClaim,
    verificationQuery,
    domainOf
};
