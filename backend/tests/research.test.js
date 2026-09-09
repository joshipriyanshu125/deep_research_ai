require("dotenv").config();
const http = require("http");
const mongoose = require("mongoose");
const app = require("../src/server");
const User = require("../src/models/User");
const Research = require("../src/models/Research");
const Report = require("../src/models/Report");

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

async function runResearchApiTests() {
    console.log("==================================================");
    console.log("       DAY 5: RESEARCH API & BACKGROUND QUEUE     ");
    console.log("==================================================");

    const TEST_PORT = 5077;
    const server = http.createServer(app);
    await new Promise((resolve) => server.listen(TEST_PORT, resolve));

    if (mongoose.connection.readyState === 0) {
        await mongoose.connect(process.env.MONGODB_URI);
    }

    const testEmail = `research_user_${Date.now()}@example.com`;
    const password = "ResearchPassword123!";

    try {
        // 1. Register User
        console.log("\n[1] Registering Test User...");
        const regRes = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "Research Tester",
            email: testEmail,
            password: password
        });
        const token = regRes.body.accessToken;
        console.log("✓ User registered and authenticated");

        // 2. POST /research (Non-blocking Fast Response)
        console.log("\n[2] POST /research (Initiating Asynchronous Research Job)...");
        const queryText = "Analyze the Indian EV market and identify the best investment opportunities.";
        
        const startTime = Date.now();
        const postRes = await makeRequest(TEST_PORT, "POST", "/research", {
            query: queryText
        }, { Authorization: `Bearer ${token}` });
        const duration = Date.now() - startTime;

        console.log("Response time:", duration, "ms");
        console.log("Status:", postRes.status);
        console.log("Response Body:", postRes.body);

        if (postRes.status !== 201) {
            throw new Error("POST /research failed: " + JSON.stringify(postRes.body));
        }

        if (!postRes.body.research_id || postRes.body.status !== "queued") {
            throw new Error("Expected research_id and status: queued in response");
        }

        if (duration > 1500) {
            throw new Error("FAIL: POST /research took too long — HTTP request must not block during research!");
        }

        const researchId = postRes.body.research_id;
        console.log("✓ POST /research returned immediately with status: 'queued' and research_id:", researchId);

        // 3. GET /research
        console.log("\n[3] GET /research (Listing User's Research Jobs)...");
        const listRes = await makeRequest(TEST_PORT, "GET", "/research", null, {
            Authorization: `Bearer ${token}`
        });
        console.log("Status:", listRes.status);
        console.log("Research count:", listRes.body.count);
        if (listRes.status !== 200 || listRes.body.count < 1) {
            throw new Error("GET /research failed: " + JSON.stringify(listRes.body));
        }
        console.log("✓ GET /research succeeded");

        // 4. GET /research/:id (Checking Progress)
        console.log("\n[4] GET /research/:id (Polling Status)...");
        const getRes = await makeRequest(TEST_PORT, "GET", `/research/${researchId}`, null, {
            Authorization: `Bearer ${token}`
        });
        console.log("Status:", getRes.status);
        console.log("Current Step:", getRes.body.currentStep);
        console.log("Progress:", getRes.body.progress, "%");
        if (getRes.status !== 200 || !getRes.body.research_id) {
            throw new Error("GET /research/:id failed: " + JSON.stringify(getRes.body));
        }
        console.log("✓ GET /research/:id returned current job details");

        // 5. POST /research/:id/cancel
        console.log("\n[5] POST /research/:id/cancel (Cancelling Job)...");
        const cancelRes = await makeRequest(TEST_PORT, "POST", `/research/${researchId}/cancel`, null, {
            Authorization: `Bearer ${token}`
        });
        console.log("Cancel Status:", cancelRes.status);
        console.log("Updated Status:", cancelRes.body.status);
        if (cancelRes.status !== 200 || cancelRes.body.status !== "cancelled") {
            throw new Error("Cancel failed: " + JSON.stringify(cancelRes.body));
        }
        console.log("✓ Job successfully cancelled");

        // 6. POST /research/:id/resume
        console.log("\n[6] POST /research/:id/resume (Resuming Cancelled Job)...");
        const resumeRes = await makeRequest(TEST_PORT, "POST", `/research/${researchId}/resume`, null, {
            Authorization: `Bearer ${token}`
        });
        console.log("Resume Status:", resumeRes.status);
        console.log("Updated Status:", resumeRes.body.status);
        if (resumeRes.status !== 200 || resumeRes.body.status !== "queued") {
            throw new Error("Resume failed: " + JSON.stringify(resumeRes.body));
        }
        console.log("✓ Job successfully resumed and re-queued");

        // 7. Wait for Background Job Completion
        console.log("\n[7] Waiting for background worker to complete research execution...");
        let completed = false;
        for (let attempt = 1; attempt <= 80; attempt++) {
            await sleep(150);
            const pollRes = await makeRequest(TEST_PORT, "GET", `/research/${researchId}`, null, {
                Authorization: `Bearer ${token}`
            });
            if (attempt % 5 === 0 || pollRes.body.status === "completed") {
                console.log(`Poll [${attempt}]: Progress ${pollRes.body.progress}% | Status: ${pollRes.body.status} | Step: ${pollRes.body.currentStep}`);
            }
            if (pollRes.body.status === "completed") {
                completed = true;
                console.log("✓ Sources Gathered:", pollRes.body.data.sources.length);
                console.log("✓ Findings Extracted:", pollRes.body.data.findings.length);
                break;
            }
        }
        if (!completed) {
            throw new Error("Worker did not complete research within expected timeframe");
        }
        console.log("✓ Research completed asynchronously in background!");

        // 8. DELETE /research/:id
        console.log("\n[8] DELETE /research/:id...");
        const delRes = await makeRequest(TEST_PORT, "DELETE", `/research/${researchId}`, null, {
            Authorization: `Bearer ${token}`
        });
        console.log("Delete Status:", delRes.status);
        if (delRes.status !== 200) {
            throw new Error("DELETE /research/:id failed: " + JSON.stringify(delRes.body));
        }
        console.log("✓ Research and associated reports deleted successfully");

        // Cleanup
        await User.findOneAndDelete({ email: testEmail.toLowerCase() });
        console.log("\n✓ Cleanup complete.");

        console.log("\n==================================================");
        console.log("🎉 ALL DAY 5 RESEARCH API TESTS PASSED 100%!");
        console.log("==================================================");
    } catch (err) {
        console.error("\n❌ Test Failed:", err);
        process.exit(1);
    } finally {
        server.close();
        await mongoose.connection.close();
    }
}

runResearchApiTests();
