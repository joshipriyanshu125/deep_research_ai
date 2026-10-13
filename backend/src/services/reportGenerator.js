const { askGroundedGemini, getGeminiModel } = require("./geminiService");

function citationsFromSources(sources, evidence, factChecks = []) {
    const seen = new Set();
    return sources.filter((source) => {
        if (!source.url || seen.has(source.url)) return false;
        seen.add(source.url);
        return true;
    }).map((source, index) => ({
        index: index + 1,
        citationId: `REF-${index + 1}`,
        title: source.title,
        sourceUrl: source.url,
        url: source.url,
        sourceType: source.sourceType || source.category || "web",
        publisherUrl: source.publisherUrl,
        snippet: source.snippet,
        evidenceIds: evidence.filter((item) => item.sourceUrl === source.url).map((item) => item.id),
        verificationFor: factChecks
            .filter((check) => (check.independentSourceUrls || []).includes(source.url))
            .map((check) => check.claimId || check.claim),
        verificationStatus: factChecks.find((check) => (check.independentSourceUrls || []).includes(source.url))?.status,
        isVerificationSource: Boolean(source.isVerificationSource)
    }));
}

function fallbackReport(query, analysis, factChecks, citations, verificationSummary = {}) {
    const findings = analysis.findings.length > 0
        ? analysis.findings.map((finding, index) => `- ${finding.insight} [${(finding.evidenceIds || [])[0] ? citations.find((citation) => citation.evidenceIds.includes(finding.evidenceIds[0]))?.index || 1 : index + 1}]`).join("\n")
        : `- No sufficiently detailed evidence was extracted for this query.`;
    const factCheckLines = factChecks.slice(0, 8).map((check) => {
        const independent = (check.independentSourceUrls || []).length;
        const refs = (check.sourceUrls || []).map((url) => citations.find((citation) => citation.url === url)?.index)
            .filter(Boolean).map((index) => `[${index}]`).join(' ');
        const method = check.verificationMethod === "independent_web_search"
            ? `; ${independent} independent web source${independent === 1 ? "" : "s"}`
            : "";
        return `- **${check.status}** (${Math.round((check.confidence || 0) * 100)}% confidence${method}): ${check.claim} ${refs}`;
    }).join("\n");
    const sourceLines = citations.map((citation) => {
        const kind = citation.isVerificationSource ? "verification source" : citation.sourceType;
        return `[${citation.index}] ${citation.title} — ${citation.url} (${kind})`;
    }).join("\n");
    const verificationLine = verificationSummary.independentVerification
        ? `Independent web verification was attempted for ${verificationSummary.attemptedClaims || 0} claims and verified ${verificationSummary.verifiedClaims || 0}.`
        : (verificationSummary.verificationAttempted || (verificationSummary.attemptedClaims || 0) > 0)
            ? `Independent web verification was attempted for ${verificationSummary.attemptedClaims || 0} claims, but no usable independent corroboration was recorded.`
        : "Independent web verification was not available for this run; claims remain provisional.";
    const methodology = verificationSummary.liveWebResearch
        ? 'Search providers were queried and source URLs were collected, deduplicated, and fetched when accessible.'
        : 'Live web retrieval was not confirmed for this run.';
    return `# Deep Research Report: ${query}\n\n## Executive Summary\n${analysis.summary} Findings below are grounded in the available evidence and linked to the source list. ${verificationLine}\n\n## Research Methodology\n${methodology} Extracted passages were analyzed, and independent web checks were attempted where available. Unavailable or snippet-only pages are not independently verified.\n\n## Key Findings\n${findings}\n\n## Analysis and Comparison\n${analysis.comparisons.map((item) => `- **${item.dimension}**: ${item.observation}`).join("\n") || "- No cross-category comparison was available."}\n\n## Fact Check\n${factCheckLines || "- No claims were extracted for verification."}\n\n## Limitations and Risks\n- Source availability, publication dates, and access restrictions vary by topic.\n- A claim marked single-source or unverified was not confirmed by an independent fetched web page.\n\n## Sources & Citations\n${sourceLines || "No sources were collected."}`;
}

async function generateReport({ query, analysis, evidence, factChecks, sources, verificationSummary = {}, signal }) {
    const citations = citationsFromSources(sources, evidence, factChecks);
    let content = "";
    let reportWriter = "Deterministic Grounded Generator";
    let reportEngine = "deterministic";
    if (process.env.GEMINI_API_KEY && process.env.NODE_ENV !== "test") {
        try {
            content = await askGroundedGemini({ query, analysis, evidence, factChecks, citations, verificationSummary, signal });
            reportWriter = `Gemini (${getGeminiModel()})`;
            reportEngine = "gemini";
        } catch (error) {
            if (signal?.aborted || error.name === "AbortError" || error.code === "ABORT_ERR") throw error;
            content = "";
        }
    }
    if (!content) content = fallbackReport(query, analysis, factChecks, citations, verificationSummary);
    if (!content.includes("Sources & Citations") && citations.length > 0) {
        content += `\n\n## Sources & Citations\n${citations.map((citation) => `[${citation.index}] ${citation.title} — ${citation.url}`).join("\n")}`;
    }
    return {
        title: `Deep Research Report: ${query}`,
        summary: analysis.summary,
        content,
        citations,
        verificationSummary,
        reportWriter,
        reportEngine,
        sections: [
            { heading: "Executive Summary", body: analysis.summary },
            { heading: "Key Findings", body: analysis.findings.map((finding) => finding.insight).join("\n") },
            { heading: "Analysis & Fact Check", body: factChecks.map((check) => `${check.status}: ${check.claim}`).join("\n") }
        ]
    };
}

module.exports = { citationsFromSources, fallbackReport, generateReport };
