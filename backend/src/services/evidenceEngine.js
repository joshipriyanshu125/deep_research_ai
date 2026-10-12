const NUMBER_PATTERN = /(?:[$€£₹]\s?\d[\d,.]*\s?(?:million|billion|crore|lakh|k|m|bn)?|\d[\d,.]*\s?(?:%|percent|million|billion|units|users|companies|years?))/gi;

function sentences(text) {
    return String(text || "")
        .split(/(?<=[.!?])\s+/)
        .map((sentence) => sentence.trim())
        .filter((sentence) => sentence.length >= 35);
}

function evidenceFromSources(sources, query) {
    const evidence = [];
    for (const source of sources) {
        const candidates = sentences(source.content || source.snippet);
        const selected = candidates.length > 0 ? candidates.slice(0, 3) : [source.snippet || query];
        for (const quote of selected) {
            const metrics = [...new Set(quote.match(NUMBER_PATTERN) || [])];
            const confidence = Math.min(
                0.96,
                Math.max(0.45, Number(source.relevanceScore || 0.6) * 0.65 + (source.extractionStatus === "fetched" ? 0.25 : ["metadata", "fixture", "abstract", "snippet"].includes(source.extractionStatus) ? 0.2 : 0.12))
            );
            evidence.push({
                id: `evidence_${evidence.length + 1}`,
                claim: quote.replace(/[.!?]+$/, ""),
                quote,
                sourceId: source.url,
                sourceUrl: source.url,
                sourceTitle: source.title,
                category: source.category,
                metrics,
                confidence: Number(confidence.toFixed(3)),
                verificationStatus: source.isFallback ? "unverified" : "pending",
                evidenceType: metrics.length > 0 ? "quantitative" : "contextual"
            });
        }
    }
    return evidence;
}

function normalizeTokens(value) {
    return new Set(String(value || "").toLowerCase().match(/[a-z0-9]{3,}/g) || []);
}

function overlap(left, right) {
    const a = normalizeTokens(left);
    const b = normalizeTokens(right);
    if (a.size === 0 || b.size === 0) return 0;
    let shared = 0;
    for (const token of a) if (b.has(token)) shared += 1;
    return shared / Math.max(1, Math.min(a.size, b.size));
}

function factCheckEvidence(evidence, independentChecks = []) {
    const checks = [];
    const groups = new Map();
    const independentByClaim = new Map((independentChecks || []).map((check) => [check.claimId || check.claim, check]));
    for (const item of evidence) {
        const key = [...normalizeTokens(item.claim)].sort().slice(0, 8).join(" ") || item.claim;
        const group = groups.get(key) || [];
        group.push(item);
        groups.set(key, group);
    }
    for (const item of evidence) {
        const independent = independentByClaim.get(item.id) || independentByClaim.get(item.claim);
        const related = evidence.filter((candidate) => candidate.id !== item.id && overlap(item.claim, candidate.claim) >= 0.55);
        const supported = related.length > 0 && related.some((candidate) => candidate.sourceUrl !== item.sourceUrl);
        if (independent) {
            checks.push({
                claim: item.claim,
                claimId: item.id,
                supported: independent.supported === true,
                confidence: independent.confidence,
                status: independent.status,
                sourceUrls: independent.sourceUrls || [item.sourceUrl],
                independentSourceUrls: independent.independentSourceUrls || [],
                contradictionSourceUrls: independent.contradictionSourceUrls || [],
                searchQuery: independent.searchQuery,
                verificationMethod: independent.verificationMethod,
                verifiedAt: independent.verifiedAt,
                contradictions: independent.contradictionSourceUrls || []
            });
            continue;
        }
        checks.push({
            claim: item.claim,
            claimId: item.id,
            supported,
            confidence: Number(Math.min(0.98, item.confidence + (supported ? 0.08 : 0)).toFixed(3)),
            status: item.verificationStatus === "unverified" ? "unverified" : "single-source",
            sourceUrls: [item.sourceUrl, ...related.map((candidate) => candidate.sourceUrl)].filter((url, index, all) => all.indexOf(url) === index),
            contradictions: []
        });
    }
    return checks;
}

function analyzeEvidence(evidence, sources, query) {
    const byCategory = sources.reduce((result, source) => {
        result[source.category || "other"] = (result[source.category || "other"] || 0) + 1;
        return result;
    }, {});
    const highConfidence = evidence.filter((item) => item.confidence >= 0.7 && item.verificationStatus !== "unverified");
    const numeric = highConfidence.filter((item) => item.metrics.length > 0);
    const findings = highConfidence.slice(0, 8).map((item) => ({
        topic: item.category || "general",
        insight: item.claim,
        confidence: item.confidence,
        evidenceIds: [item.id],
        status: "extracted"
    }));
    const comparisons = Object.entries(byCategory).map(([category, count]) => ({
        dimension: category,
        sourceCount: count,
        evidenceCount: highConfidence.filter((item) => item.category === category).length,
        observation: `${count} ${category} source${count === 1 ? "" : "s"} contributed to the evidence base.`
    }));
    const trends = numeric.length > 0
        ? numeric.slice(0, 4).map((item) => item.claim)
        : [`The available sources describe current developments and unresolved questions around ${query}.`];
    return {
        findings,
        comparisons,
        trends,
        evidenceCount: evidence.length,
        sourceCount: sources.length,
        highConfidenceCount: highConfidence.length,
        numericEvidenceCount: numeric.length,
        summary: `Analysis combined ${sources.length} sources and ${evidence.length} extracted evidence items across ${Object.keys(byCategory).length || 1} source categories.`
    };
}

module.exports = { evidenceFromSources, factCheckEvidence, analyzeEvidence, overlap };
