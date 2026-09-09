require("dotenv").config();
const http = require("http");
const mongoose = require("mongoose");
const app = require("../src/server");
const User = require("../src/models/User");
const Research = require("../src/models/Research");
const Report = require("../src/models/Report");
const researchQueue = require("../src/queue/researchQueue");
const researchWorker = require("../src/workers/researchWorker");
const researchEngine = require("../src/services/researchEngine");

function makeRequest(port, method, path, body = null, headers = {}) {
    return new Promise((resolve, reject) => {
        const payload = body ? JSON.stringify(body) : null;
        const requestHeaders = {
            "Content-Type": "application/json",
            ...headers
        };
        if (payload) {
            requestHeaders["Content-Length"] = Buffer.byteLength(payload);
        }

        const req = http.request(
            {
                hostname: "127.0.0.1",
                port: port,
                path: path,
                method: method,
                headers: requestHeaders
            },
            (res) => {
                let data = "";
                res.on("data", (chunk) => (data += chunk));
                res.on("end", () => {
                    try {
                        const parsed = JSON.parse(data);
                        resolve({ status: res.statusCode, body: parsed });
                    } catch (e) {
                        resolve({ status: res.statusCode, body: data });
                    }
                });
            }
        );

        req.on("error", reject);
        if (payload) req.write(payload);
        req.end();
    });
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runJobSystemTests() {
    console.log("==========================================================");
    console.log("       DAY 6: RESEARCH JOB SYSTEM (QUEUE, WORKER, ENGINE) ");
    console.log("==========================================================");

    const TEST_PORT = 5066;
    const server = http.createServer(app);
    await new Promise((resolve) => server.listen(TEST_PORT, resolve));

    if (mongoose.connection.readyState === 0) {
        await mongoose.connect(process.env.MONGODB_URI);
    }

    const testEmail = `job_user_${Date.now()}@example.com`;
    const password = "JobPassword123!";

    try {
        // Step 1: Authentication
        console.log("\n[1] Registering User for Job System Test...");
        const regRes = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "Job System Tester",
            email: testEmail,
            password: password
        });
        const token = regRes.body.accessToken;
        console.log("✓ User authenticated");

        // Step 2: Post Research (API -> Job -> Queue)
        console.log("\n[2] Testing API -> Research Job -> Queue Dispatch...");
        const queryText = "Analyze the Indian EV market and identify the best investment opportunities.";
        const createRes = await makeRequest(TEST_PORT, "POST", "/research", {
            query: queryText
        }, { Authorization: `Bearer ${token}` });

        if (createRes.status !== 201) {
            throw new Error("Failed to create research job: " + JSON.stringify(createRes.body));
        }

        const researchId = createRes.body.research_id;
        console.log("✓ Initial Status:", createRes.body.status, "(Expected: queued)");
        console.log("✓ Research ID:", researchId);

        // Step 3: Track Stage Transitions through Engine Lifecycle
        console.log("\n[3] Tracking Lifecycle Status Transitions (planning -> researching -> analyzing -> fact_checking -> writing -> completed)...");
        const observedStatuses = new Set([createRes.body.status]);

        let finalDoc = null;
        for (let i = 0; i < 25; i++) {
            await sleep(150);
            const statusRes = await makeRequest(TEST_PORT, "GET", `/research/${researchId}`, null, {
                Authorization: `Bearer ${token}`
            });

            const currentStatus = statusRes.body.status;
            observedStatuses.add(currentStatus);

            console.log(`- Polling [${i + 1}]: Status = ${currentStatus.padEnd(14)} | Progress = ${statusRes.body.progress}% | Step = ${statusRes.body.currentStep}`);

            if (currentStatus === "completed") {
                finalDoc = statusRes.body.data;
                break;
            }
        }

        if (!observedStatuses.has("completed")) {
            throw new Error("Research did not reach 'completed' status");
        }

        console.log("\n✓ Observed Status Transitions during execution:");
        console.log(Array.from(observedStatuses).map((s) => `  → ${s}`).join("\n"));

        // Step 4: Verify Research Output and Linked Report
        console.log("\n[4] Verifying Artifacts (Sources, Findings, Final Report)...");
        if (!finalDoc.sources || finalDoc.sources.length === 0) {
            throw new Error("No sources collected");
        }
        if (!finalDoc.findings || finalDoc.findings.length === 0) {
            throw new Error("No findings extracted");
        }
        console.log(`✓ Sources Collected: ${finalDoc.sources.length}`);
        console.log(`✓ Findings Extracted & Verified: ${finalDoc.findings.length}`);

        const report = await Report.findOne({ research: researchId });
        if (!report) {
            throw new Error("Linked Report was not automatically created by Research Engine");
        }
        console.log("✓ Linked Report Generated: ID =", report._id.toString());
        console.log("✓ Report Title:", report.title);

        // Step 5: Test Cancellation Status & Abort
        console.log("\n[5] Testing Job Cancellation Status Transition ('cancelled')...");
        const job2Res = await makeRequest(TEST_PORT, "POST", "/research", {
            query: "Quantum Computing Hardware Benchmarks 2026"
        }, { Authorization: `Bearer ${token}` });

        const job2Id = job2Res.body.research_id;
        const cancelRes = await makeRequest(TEST_PORT, "POST", `/research/${job2Id}/cancel`, null, {
            Authorization: `Bearer ${token}`
        });

        if (cancelRes.status !== 200 || cancelRes.body.status !== "cancelled") {
            throw new Error("Failed to cancel job: " + JSON.stringify(cancelRes.body));
        }
        console.log("✓ Cancelled Job Status:", cancelRes.body.status);

        // Cleanup
        await User.findOneAndDelete({ email: testEmail.toLowerCase() });
        await Research.deleteMany({ _id: { $in: [researchId, job2Id] } });
        await Report.deleteMany({ research: { $in: [researchId, job2Id] } });
        console.log("\n✓ Cleanup complete.");

        console.log("\n==========================================================");
        console.log("🎉 ALL DAY 6 RESEARCH JOB SYSTEM TESTS PASSED 100%!");
        console.log("==========================================================");
    } catch (err) {
        console.error("\n❌ Test Failed:", err);
        process.exit(1);
    } finally {
        server.close();
        await mongoose.connection.close();
    }
}

runJobSystemTests();
