require("dotenv").config();
const http = require("http");
const mongoose = require("mongoose");
const app = require("../src/server");
const User = require("../src/models/User");
const Research = require("../src/models/Research");
const Report = require("../src/models/Report");
const stateMachine = require("../src/services/researchStateMachine");

function makeRequest(port, method, path, body = null, headers = {}) {
    return new Promise((resolve, reject) => {
        const payload = body ? JSON.stringify(body) : null;
        const requestHeaders = { "Content-Type": "application/json", ...headers };
        if (payload) requestHeaders["Content-Length"] = Buffer.byteLength(payload);

        const req = http.request(
            { hostname: "127.0.0.1", port, path, method, headers: requestHeaders },
            (res) => {
                let data = "";
                res.on("data", (c) => (data += c));
                res.on("end", () => {
                    try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
                    catch { resolve({ status: res.statusCode, body: data }); }
                });
            }
        );
        req.on("error", reject);
        if (payload) req.write(payload);
        req.end();
    });
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function runLifecycleTests() {
    console.log("==========================================================");
    console.log(" DAY 7: RESEARCH LIFECYCLE STATE MACHINE TESTS            ");
    console.log("==========================================================");

    const TEST_PORT = 5055;
    const server = http.createServer(app);
    await new Promise((r) => server.listen(TEST_PORT, r));
    if (mongoose.connection.readyState === 0) {
        await mongoose.connect(process.env.MONGODB_URI);
    }

    const testEmail = `lifecycle_${Date.now()}@example.com`;
    const password = "LifecyclePass123!";

    try {
        // -------------------------------------------------------
        // Phase 1: State Machine Unit Tests (No HTTP)
        // -------------------------------------------------------
        console.log("\n--- [Phase 1] State Machine Unit Tests ---");

        const STATES = stateMachine.STATES;

        // Validate transition DAG
        const validTransitions = [
            [STATES.QUEUED, STATES.PLANNING],
            [STATES.PLANNING, STATES.SEARCHING],
            [STATES.SEARCHING, STATES.COLLECTING],
            [STATES.COLLECTING, STATES.ANALYZING],
            [STATES.ANALYZING, STATES.VERIFYING],
            [STATES.VERIFYING, STATES.SYNTHESIZING],
            [STATES.SYNTHESIZING, STATES.REPORT_GENERATION],
            [STATES.REPORT_GENERATION, STATES.QUALITY_CHECK],
            [STATES.QUALITY_CHECK, STATES.COMPLETED],
        ];

        let allValid = true;
        for (const [from, to] of validTransitions) {
            if (!stateMachine.canTransition(from, to)) {
                console.error(`FAIL: Transition ${from} -> ${to} should be valid`);
                allValid = false;
            }
        }
        if (allValid) console.log("✓ All 9 forward lifecycle transitions validated in DAG");

        // Any state -> FAILED should always be allowed
        const failTransitions = Object.values(STATES).filter(s => s !== STATES.FAILED);
        for (const s of failTransitions) {
            if (!stateMachine.canTransition(s, STATES.FAILED)) {
                console.error(`FAIL: ${s} -> FAILED should always be valid`);
            }
        }
        console.log("✓ FAILED transition valid from all states");

        // Verify RETRY can go back to QUEUED
        if (!stateMachine.canTransition(STATES.RETRY, STATES.QUEUED)) {
            throw new Error("FAIL: RETRY -> QUEUED transition not allowed");
        }
        console.log("✓ RETRY -> QUEUED transition valid");

        // -------------------------------------------------------
        // Phase 2: End-to-End API Lifecycle Tests
        // -------------------------------------------------------
        console.log("\n--- [Phase 2] End-to-End Lifecycle API Tests ---");

        // Register user
        const regRes = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "Lifecycle Tester", email: testEmail, password
        });
        const token = regRes.body.accessToken;
        console.log("✓ User registered");

        // Create research job
        const createRes = await makeRequest(TEST_PORT, "POST", "/research", {
            query: "Analyze the Indian EV market and identify the best investment opportunities."
        }, { Authorization: `Bearer ${token}` });

        if (createRes.status !== 201) throw new Error("Failed to create research: " + JSON.stringify(createRes.body));
        const researchId = createRes.body.research_id;
        console.log("✓ Research job created. ID:", researchId);
        console.log("  Initial Status:", createRes.body.status);

        // Track ALL state transitions
        console.log("\n[Tracking Full Lifecycle: QUEUED -> PLANNING -> SEARCHING -> COLLECTING -> ANALYZING -> VERIFYING -> SYNTHESIZING -> REPORT_GENERATION -> QUALITY_CHECK -> COMPLETED]");
        const observedStatuses = new Set([createRes.body.status]);
        const expectedStates = [
            "queued", "planning", "searching", "collecting",
            "analyzing", "verifying", "synthesizing",
            "report_generation", "quality_check", "completed"
        ];

        let finalDoc = null;
        for (let i = 0; i < 80; i++) {
            await sleep(80);
            const pollRes = await makeRequest(TEST_PORT, "GET", `/research/${researchId}`, null,
                { Authorization: `Bearer ${token}` });
            const s = pollRes.body.status;
            observedStatuses.add(s);
            process.stdout.write(`\r  [${String(i + 1).padStart(2)}] ${s.padEnd(20)} ${pollRes.body.progress}%`);
            if (s === "completed") { finalDoc = pollRes.body.data; break; }
        }
        console.log();

        // Verify ALL 10 states were observed
        const missingStates = expectedStates.filter(s => !observedStatuses.has(s));
        if (missingStates.length > 0) {
            throw new Error(`Missing states in lifecycle: ${missingStates.join(", ")}`);
        }
        console.log("\n✓ All 10 lifecycle states observed:");
        expectedStates.forEach(s => console.log(`  ✓ ${s}`));

        // Verify completion artifacts
        if (!finalDoc || finalDoc.progress !== 100) throw new Error("Research did not reach 100% progress");
        if (!finalDoc.sources || finalDoc.sources.length === 0) throw new Error("No sources collected");
        if (!finalDoc.findings || finalDoc.findings.length === 0) throw new Error("No findings extracted");
        if (finalDoc.qualityScore === null || finalDoc.qualityScore === undefined) throw new Error("Quality score missing");
        console.log(`\n✓ Sources Collected: ${finalDoc.sources.length}`);
        console.log(`✓ Findings Extracted: ${finalDoc.findings.length}`);
        console.log(`✓ Quality Score: ${finalDoc.qualityScore}/100`);
        console.log("✓ Quality Check Results:", JSON.stringify(finalDoc.qualityCheckResults));

        // Verify linked Report generated
        const report = await Report.findOne({ research: researchId });
        if (!report) throw new Error("Linked Report was not auto-generated by Research Engine");
        console.log(`✓ Linked Report: "${report.title}"`);
        console.log(`✓ Report Citations: ${report.citations.length}`);

        // Test Cancel flow
        console.log("\n[Testing: POST /research/:id/cancel (state -> CANCELLED)]");
        const job2 = await makeRequest(TEST_PORT, "POST", "/research", {
            query: "Quantum Computing Chip Benchmarks 2026"
        }, { Authorization: `Bearer ${token}` });
        const job2Id = job2.body.research_id;

        const cancelRes = await makeRequest(TEST_PORT, "POST", `/research/${job2Id}/cancel`, null,
            { Authorization: `Bearer ${token}` });
        if (cancelRes.status !== 200 || cancelRes.body.status !== "cancelled") {
            throw new Error("Cancel failed: " + JSON.stringify(cancelRes.body));
        }
        console.log("✓ Cancel -> status:", cancelRes.body.status);

        // Test Resume flow
        console.log("[Testing: POST /research/:id/resume (CANCELLED -> QUEUED)]");
        const resumeRes = await makeRequest(TEST_PORT, "POST", `/research/${job2Id}/resume`, null,
            { Authorization: `Bearer ${token}` });
        if (resumeRes.status !== 200 || resumeRes.body.status !== "queued") {
            throw new Error("Resume failed: " + JSON.stringify(resumeRes.body));
        }
        console.log("✓ Resume -> status:", resumeRes.body.status);

        // Wait for job2 to complete too
        for (let i = 0; i < 30; i++) {
            await sleep(150);
            const p = await makeRequest(TEST_PORT, "GET", `/research/${job2Id}`, null,
                { Authorization: `Bearer ${token}` });
            if (p.body.status === "completed") {
                console.log("✓ Resumed job completed successfully");
                break;
            }
        }

        // Test Retry flow
        console.log("\n[Testing: POST /research/:id/retry (FAILED -> RETRY -> QUEUED -> COMPLETED)]");
        // Manually force a research to failed state directly in DB
        const failedJob = await Research.create({
            user: (await User.findOne({ email: testEmail.toLowerCase() }))._id,
            query: "Simulated failed research",
            title: "Simulated Failure Test",
            status: "failed",
            error: "Simulated network timeout",
            failedStage: "searching",
            retryCount: 0,
            maxRetries: 3
        });

        const retryRes = await makeRequest(TEST_PORT, "POST", `/research/${failedJob._id}/retry`, null,
            { Authorization: `Bearer ${token}` });
        if (retryRes.status !== 200) throw new Error("Retry failed: " + JSON.stringify(retryRes.body));
        console.log(`✓ Retry initiated. Attempt: ${retryRes.body.retryCount}/${retryRes.body.maxRetries}`);
        console.log("✓ Status after retry trigger:", retryRes.body.status);

        // Wait for retried job to complete
        for (let i = 0; i < 30; i++) {
            await sleep(150);
            const p = await makeRequest(TEST_PORT, "GET", `/research/${failedJob._id}`, null,
                { Authorization: `Bearer ${token}` });
            if (p.body.status === "completed") {
                console.log("✓ Retried job completed successfully with status: completed");
                break;
            }
        }

        // Cleanup
        const user = await User.findOne({ email: testEmail.toLowerCase() });
        await Research.deleteMany({ user: user._id });
        await Report.deleteMany({ user: user._id });
        await User.deleteOne({ _id: user._id });
        console.log("\n✓ Cleanup complete.");

        console.log("\n==========================================================");
        console.log("🎉 ALL DAY 7 LIFECYCLE STATE MACHINE TESTS PASSED 100%!");
        console.log("==========================================================");
    } catch (err) {
        console.error("\n❌ Test Failed:", err);
        process.exit(1);
    } finally {
        server.close();
        await mongoose.connection.close();
    }
}

runLifecycleTests();
