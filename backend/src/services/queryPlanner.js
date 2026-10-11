const DEFAULT_CATEGORIES = ["web", "academic", "market"];

const CATEGORY_TEMPLATES = {
    web: {
        label: "Web search",
        question: (topic) => `What is the current landscape, background, and key developments for ${topic}?`,
        query: (topic) => `${topic} current overview key developments`
    },
    academic: {
        label: "News and papers",
        question: (topic) => `What do recent research papers and news coverage say about ${topic}, including methods, results, and open questions?`,
        query: (topic) => `${topic} recent research papers evidence`
    },
    market: {
        label: "Market and comparison",
        question: (topic) => `What are the important organizations, market signals, comparisons, risks, and opportunities related to ${topic}?`,
        query: (topic) => `${topic} market analysis companies trends risks opportunities`
    },
    other: {
        label: "Other sources",
        question: (topic) => `What official datasets, documentation, or public records provide useful evidence about ${topic}?`,
        query: (topic) => `${topic} official data documentation public records`
    }
};

function normalizeCategories(categories) {
    if (!Array.isArray(categories) || categories.length === 0) return DEFAULT_CATEGORIES;
    const allowed = new Set(Object.keys(CATEGORY_TEMPLATES));
    const normalized = categories
        .map((category) => String(category).trim().toLowerCase())
        .filter((category) => allowed.has(category));
    return [...new Set(normalized)].length > 0 ? [...new Set(normalized)] : DEFAULT_CATEGORIES;
}

function normalizeDepth(depth) {
    if (depth === "quick" || depth === 1 || depth === "1") return 1;
    if (depth === "deep" || depth === 3 || depth === "3") return 3;
    return 2;
}

function normalizeBreadth(breadth) {
    const value = Number(breadth);
    return Number.isFinite(value) ? Math.max(1, Math.min(8, Math.round(value))) : 3;
}

function createPlan({ query, depth, breadth, categories }) {
    const topic = query.trim().replace(/[?.!]+$/, "");
    const normalizedDepth = normalizeDepth(depth);
    const normalizedBreadth = normalizeBreadth(breadth);
    const selectedCategories = normalizeCategories(categories);
    const target = Math.max(selectedCategories.length, Math.min(8, normalizedBreadth + normalizedDepth - 1));
    const tasks = [];

    for (let index = 0; index < target; index += 1) {
        const category = selectedCategories[index % selectedCategories.length];
        const template = CATEGORY_TEMPLATES[category];
        const iteration = Math.floor(index / selectedCategories.length) + 1;
        tasks.push({
            id: `task_${index + 1}`,
            question: iteration === 1
                ? template.question(topic)
                : `What independent evidence or counterpoint should be checked for ${topic} (${template.label.toLowerCase()}, pass ${iteration})?`,
            query: iteration === 1
                ? template.query(topic)
                : `${template.query(topic)} independent evidence pass ${iteration}`,
            category,
            status: "queued",
            depth: normalizedDepth,
            sourceType: category === "academic" ? "papers" : category === "market" ? "news" : category
        });
    }

    return {
        researchGoal: query.trim(),
        depth: normalizedDepth,
        breadth: normalizedBreadth,
        categories: selectedCategories,
        tasks,
        createdAt: new Date().toISOString()
    };
}

module.exports = {
    CATEGORY_TEMPLATES,
    DEFAULT_CATEGORIES,
    normalizeCategories,
    normalizeDepth,
    normalizeBreadth,
    createPlan
};
