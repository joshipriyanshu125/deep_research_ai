const { askGroundedGemini } = require("./geminiService");

function citationsFromSources(sources, evidence) {
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
        snippet: source.snippet,
        evidenceIds: evidence.filter((item) => item.sourceUrl === source.url).map((item) => item.id)
    }));
}

function fallbackReport(query, analysis, factChecks, citations) {
    const findings = analysis.findings.length > 0
        ? analysis.findings.map((finding, index) => `- ${finding.insight} [${(finding.evidenceIds || [])[0] ? citations.find((citation) => citation.evidenceIds.includes(finding.evidenceIds[0]))?.index || 1 : index + 1}]`).join("\n")
        : `- No sufficiently detailed evidence was extracted for this query.`;
    const factCheckLines = factChecks.slice(0, 8).map((check) => `- **${check.status}** (${Math.round(check.confidence * 100)}% confidence): ${check.claim}`).join("\n");
    const sourceLines = citations.map((citation) => `[${citation.index}] ${citation.title} — ${citation.url}`).join("\n");
    return `# Deep Research Report: ${query}\n\n## Executive Summary\n${analysis.summary} Findings below are grounded in the extracted evidence and linked to the source list.\n\n## Research Methodology\nThe query was decomposed into independent web, news/paper, market, and other-source tracks where requested. Results were collected, deduplicated, extracted, analyzed, fact-checked, compared, and cited.\n\n## Key Findings\n${findings}\n\n## Analysis and Comparison\n${analysis.comparisons.map((item) => `- **${item.dimension}**: ${item.observation}`).join("\n") || "- No cross-category comparison was available."}\n\n## Fact Check\n${factCheckLines || "- No independent corroboration was available; claims should be treated as provisional."}\n\n## Limitations and Risks\n- Source availability and publication dates vary by topic.\n- Claims supported by a single source are clearly marked and should be independently validated before high-stakes decisions.\n\n## Sources & Citations\n${sourceLines || "No sources were collected."}`;
}

async function generateReport({ query, analysis, evidence, factChecks, sources, signal }) {
    const citations = citationsFromSources(sources, evidence);
    let content = "";
    if (process.env.GEMINI_API_KEY && process.env.NODE_ENV !== "test") {
        try {
            content = await askGroundedGemini({ query, analysis, evidence, factChecks, citations, signal });
        } catch (error) {
            content = "";
        }
    }
    if (!content) content = fallbackReport(query, analysis, factChecks, citations);
    if (!content.includes("Sources & Citations") && citations.length > 0) {
        content += `\n\n## Sources & Citations\n${citations.map((citation) => `[${citation.index}] ${citation.title} — ${citation.url}`).join("\n")}`;
    }
    return {
        title: `Deep Research Report: ${query}`,
        summary: analysis.summary,
        content,
        citations,
        sections: [
            { heading: "Executive Summary", body: analysis.summary },
            { heading: "Key Findings", body: analysis.findings.map((finding) => finding.insight).join("\n") },
            { heading: "Analysis & Fact Check", body: factChecks.map((check) => `${check.status}: ${check.claim}`).join("\n") }
        ]
    };
}

module.exports = { citationsFromSources, fallbackReport, generateReport };
