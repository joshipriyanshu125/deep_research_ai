const API_BASE = "/api/v1";

let currentJobId = null;
let currentReport = null;

// DOM Elements
const researchQuery = document.getElementById("researchQuery");
const depthSelect = document.getElementById("depthSelect");
const breadthSelect = document.getElementById("breadthSelect");
const catWeb = document.getElementById("catWeb");
const catAcademic = document.getElementById("catAcademic");
const catMarket = document.getElementById("catMarket");
const startResearchBtn = document.getElementById("startResearchBtn");

const missionControl = document.getElementById("missionControl");
const currentStepText = document.getElementById("currentStepText");
const activeJobId = document.getElementById("activeJobId");
const progressBarFill = document.getElementById("progressBarFill");
const progressPercent = document.getElementById("progressPercent");
const tasksContainer = document.getElementById("tasksContainer");
const sourcesContainer = document.getElementById("sourcesContainer");
const tasksCountBadge = document.getElementById("tasksCountBadge");
const sourcesCountBadge = document.getElementById("sourcesCountBadge");

const reportSection = document.getElementById("reportSection");
const reportTitle = document.getElementById("reportTitle");
const reportMarkdownBody = document.getElementById("reportMarkdownBody");
const citationCountBadge = document.getElementById("citationCountBadge");
const copyMarkdownBtn = document.getElementById("copyMarkdownBtn");
const downloadHtmlBtn = document.getElementById("downloadHtmlBtn");
const historyList = document.getElementById("historyList");

// Fetch history on load
async function loadHistory() {
    try {
        const res = await fetch(`${API_BASE}/history/`);
        if (res.ok) {
            const jobs = await res.json();
            renderHistory(jobs);
        }
    } catch (e) {
        console.warn("Could not fetch history:", e);
    }
}

function renderHistory(jobs) {
    if (!jobs || jobs.length === 0) {
        historyList.innerHTML = `<div class="empty-state-text">No research runs yet</div>`;
        return;
    }
    historyList.innerHTML = jobs.map(j => `
        <div class="history-item" onclick="loadJobDetails('${j.id}')" title="${j.query}">
            ${j.query}
        </div>
    `).join('');
}

// Start research handler
startResearchBtn.addEventListener("click", async () => {
    const query = researchQuery.value.trim();
    if (!query) {
        alert("Please enter a research query.");
        return;
    }

    const categories = [];
    if (catWeb.checked) categories.push("web");
    if (catAcademic.checked) categories.push("academic");
    if (catMarket.checked) categories.push("market");

    startResearchBtn.disabled = true;
    startResearchBtn.innerHTML = `<span>Synthesizing Plan...</span>`;

    missionControl.classList.remove("hidden");
    reportSection.classList.add("hidden");
    tasksContainer.innerHTML = `<div class="loading-state">Initializing planner agent...</div>`;
    sourcesContainer.innerHTML = `<div class="loading-state">Awaiting search & extraction results...</div>`;

    try {
        const res = await fetch(`${API_BASE}/research/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query: query,
                depth: parseInt(depthSelect.value),
                breadth: parseInt(breadthSelect.value),
                categories: categories
            })
        });

        if (!res.ok) throw new Error("Failed to start research job");
        const job = await res.json();
        currentJobId = job.id;
        activeJobId.textContent = `Job ID: ${job.id}`;

        // Connect SSE stream
        connectStream(job.id);
    } catch (err) {
        alert(`Error: ${err.message}`);
        startResearchBtn.disabled = false;
        startResearchBtn.innerHTML = `<span>Launch Deep Research</span>`;
    }
});

function connectStream(jobId) {
    const eventSource = new EventSource(`${API_BASE}/research/${jobId}/stream`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleAgentEvent(data);
        } catch (e) {
            console.error("SSE parse error:", e);
        }
    };

    eventSource.onerror = (err) => {
        console.error("SSE error, closing stream:", err);
        eventSource.close();
        startResearchBtn.disabled = false;
        startResearchBtn.innerHTML = `<span>Launch Deep Research</span>`;
    };
}

function handleAgentEvent(payload) {
    const { event, data } = payload;

    if (event === "status") {
        currentStepText.textContent = data.current_step;
        const pct = data.progress_percentage || 10;
        progressBarFill.style.width = `${pct}%`;
        progressPercent.textContent = `${pct}%`;
    } else if (event === "plan_ready") {
        renderTasks(data.tasks);
    } else if (event === "sources_collected") {
        renderSources(data.sources);
    } else if (event === "report_ready") {
        progressBarFill.style.width = `100%`;
        progressPercent.textContent = `100%`;
        currentStepText.textContent = "Research complete.";
        renderReport(data.report);
        startResearchBtn.disabled = false;
        startResearchBtn.innerHTML = `<span>Launch Deep Research</span>`;
        loadHistory();
    }
}

function renderTasks(tasks) {
    tasksCountBadge.textContent = `${tasks.length} Tracks`;
    tasksContainer.innerHTML = tasks.map((t, idx) => `
        <div class="task-item-card">
            <div style="display:flex; justify-content:space-between;">
                <strong>Track #${idx+1} [${t.category.toUpperCase()}]</strong>
                <span class="badge">${t.status}</span>
            </div>
            <div>${t.query}</div>
        </div>
    `).join('');
}

function renderSources(sources) {
    sourcesCountBadge.textContent = `${sources.length} Sources`;
    sourcesContainer.innerHTML = sources.map((s, idx) => `
        <div class="source-item-card">
            <div style="display:flex; justify-content:space-between;">
                <a href="${s.url}" target="_blank" rel="noopener noreferrer">${s.title || s.url}</a>
                <span class="badge success">Score: ${s.credibility_score}</span>
            </div>
            <div style="color: var(--text-muted); font-size: 0.8rem;">${s.snippet || ""}</div>
        </div>
    `).join('');
}

function renderReport(report) {
    currentReport = report;
    reportSection.classList.remove("hidden");
    reportTitle.textContent = report.title;
    citationCountBadge.textContent = `${report.citations ? report.citations.length : 0} Citations`;

    let fullMarkdown = `# ${report.title}\n\n`;
    fullMarkdown += `> **Executive Summary**: ${report.executive_summary}\n\n`;
    fullMarkdown += report.markdown_content;

    if (report.citations && report.citations.length > 0) {
        fullMarkdown += `\n\n## References & Sources\n`;
        report.citations.forEach(c => {
            fullMarkdown += `\n[${c.index}] **[${c.title}](${c.url})** - *${c.source_type}*\n> ${c.snippet || ""}\n`;
        });
    }

    reportMarkdownBody.innerHTML = marked.parse(fullMarkdown);
    reportSection.scrollIntoView({ behavior: 'smooth' });
}

// Copy Markdown
copyMarkdownBtn.addEventListener("click", () => {
    if (!currentReport) return;
    navigator.clipboard.writeText(reportMarkdownBody.innerText);
    copyMarkdownBtn.textContent = "Copied!";
    setTimeout(() => { copyMarkdownBtn.textContent = "Copy Markdown"; }, 2000);
});

// Download HTML
downloadHtmlBtn.addEventListener("click", () => {
    if (!currentReport) return;
    const blob = new Blob([`<html><body>${reportMarkdownBody.innerHTML}</body></html>`], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `deep_research_${currentReport.id || 'report'}.html`;
    a.click();
    URL.revokeObjectURL(url);
});

// Init
loadHistory();
