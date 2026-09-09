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

async function runAuthorizationTests() {
    console.log("==================================================");
    console.log("     DAY 4: AUTHORIZATION & PERMISSIONS TESTS     ");
    console.log("==================================================");

    const TEST_PORT = 5088;
    const server = http.createServer(app);
    await new Promise((resolve) => server.listen(TEST_PORT, resolve));

    if (mongoose.connection.readyState === 0) {
        await mongoose.connect(process.env.MONGODB_URI);
    }

    const timestamp = Date.now();
    const userA_Email = `user_a_${timestamp}@example.com`;
    const userB_Email = `user_b_${timestamp}@example.com`;
    const adminEmail = `admin_${timestamp}@example.com`;
    const password = "SecurePassword123!";

    try {
        // Step 1: Register User A, User B, and Admin
        console.log("\n[1] Registering User A, User B, and Admin...");
        const regA = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "User A",
            email: userA_Email,
            password: password
        });
        const tokenA = regA.body.accessToken;

        const regB = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "User B",
            email: userB_Email,
            password: password
        });
        const tokenB = regB.body.accessToken;

        const regAdmin = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "Admin User",
            email: adminEmail,
            password: password,
            role: "admin"
        });
        const tokenAdmin = regAdmin.body.accessToken;

        console.log("✓ User A registered (role: user)");
        console.log("✓ User B registered (role: user)");
        console.log("✓ Admin registered (role: admin)");

        // Step 2: User A creates Research A and Research B
        console.log("\n[2] User A creates Research A and Research B...");
        const resA1 = await makeRequest(TEST_PORT, "POST", "/research", {
            title: "Research A: Indian EV Market Trends",
            query: "Analyze Indian electric vehicle adoption in 2026"
        }, { Authorization: `Bearer ${tokenA}` });

        const resA2 = await makeRequest(TEST_PORT, "POST", "/research", {
            title: "Research B: Solid State Battery Advances",
            query: "Latest developments in solid state battery tech"
        }, { Authorization: `Bearer ${tokenA}` });

        const researchA_Id = resA1.body.data._id;
        const researchB_Id = resA2.body.data._id;
        console.log("✓ Research A created by User A (ID:", researchA_Id, ")");
        console.log("✓ Research B created by User A (ID:", researchB_Id, ")");

        // Step 3: User B creates Research C
        console.log("\n[3] User B creates Research C...");
        const resB1 = await makeRequest(TEST_PORT, "POST", "/research", {
            title: "Research C: AI Chip Architectures",
            query: "Compare next-gen NPU and GPU efficiency"
        }, { Authorization: `Bearer ${tokenB}` });

        const researchC_Id = resB1.body.data._id;
        console.log("✓ Research C created by User B (ID:", researchC_Id, ")");

        // Step 4: Scoped List Validation
        console.log("\n[4] Validating Scoped Research Lists...");
        const listA = await makeRequest(TEST_PORT, "GET", "/research", null, {
            Authorization: `Bearer ${tokenA}`
        });
        console.log("User A sees count:", listA.body.count);
        const titlesA = listA.body.data.map(r => r.title);
        if (listA.body.count !== 2 || titlesA.includes("Research C: AI Chip Architectures")) {
            throw new Error("FAIL: User A saw User B's research in list!");
        }
        console.log("✓ User A only sees their own research (A and B).");

        const listB = await makeRequest(TEST_PORT, "GET", "/research", null, {
            Authorization: `Bearer ${tokenB}`
        });
        console.log("User B sees count:", listB.body.count);
        const titlesB = listB.body.data.map(r => r.title);
        if (listB.body.count !== 1 || !titlesB.includes("Research C: AI Chip Architectures")) {
            throw new Error("FAIL: User B list scoping broken!");
        }
        console.log("✓ User B only sees their own research (C).");

        // Step 5: Resource-Level Authorization (CRITICAL TEST)
        console.log("\n[5] Resource-Level Authorization (User A attempting to access User B's Research C)...");
        
        // GET /research/B's-research
        const getCross = await makeRequest(TEST_PORT, "GET", `/research/${researchC_Id}`, null, {
            Authorization: `Bearer ${tokenA}`
        });
        console.log("User A GET Research C -> Status:", getCross.status, "(Expected: 403 Forbidden)");
        if (getCross.status !== 403) {
            throw new Error("FAIL: User A was able to GET User B's research! Status: " + getCross.status);
        }
        console.log("✓ User A is forbidden (403) from GET /research/B's-research");

        // PUT /research/B's-research
        const putCross = await makeRequest(TEST_PORT, "PUT", `/research/${researchC_Id}`, {
            title: "Hacked by User A"
        }, { Authorization: `Bearer ${tokenA}` });
        console.log("User A PUT Research C -> Status:", putCross.status, "(Expected: 403 Forbidden)");
        if (putCross.status !== 403) {
            throw new Error("FAIL: User A was able to PUT User B's research!");
        }
        console.log("✓ User A is forbidden (403) from PUT /research/B's-research");

        // DELETE /research/B's-research
        const delCross = await makeRequest(TEST_PORT, "DELETE", `/research/${researchC_Id}`, null, {
            Authorization: `Bearer ${tokenA}`
        });
        console.log("User A DELETE Research C -> Status:", delCross.status, "(Expected: 403 Forbidden)");
        if (delCross.status !== 403) {
            throw new Error("FAIL: User A was able to DELETE User B's research!");
        }
        console.log("✓ User A is forbidden (403) from DELETE /research/B's-research");

        // Step 6: Reports Authorization
        console.log("\n[6] Reports Ownership & Authorization...");
        // User A creates report for Research A (Success)
        const reportA = await makeRequest(TEST_PORT, "POST", "/reports", {
            researchId: researchA_Id,
            title: "Executive Summary: EV Market",
            content: "Detailed findings on EV market growth..."
        }, { Authorization: `Bearer ${tokenA}` });
        console.log("User A creates Report for Research A -> Status:", reportA.status, "(Expected 201)");
        if (reportA.status !== 201) {
            throw new Error("FAIL: User A failed to create Report for owned research");
        }
        const reportA_Id = reportA.body.data._id;

        // User A tries to create report for Research C (owned by User B) -> 403
        const reportCross = await makeRequest(TEST_PORT, "POST", "/reports", {
            researchId: researchC_Id,
            title: "Unauthorized Report",
            content: "Trying to attach report to another user's research"
        }, { Authorization: `Bearer ${tokenA}` });
        console.log("User A creates Report on Research C -> Status:", reportCross.status, "(Expected 403)");
        if (reportCross.status !== 403) {
            throw new Error("FAIL: User A was allowed to attach report to User B's research!");
        }
        console.log("✓ Cross-user report creation blocked (403)");

        // User B tries to GET User A's Report -> 403
        const getReportCross = await makeRequest(TEST_PORT, "GET", `/reports/${reportA_Id}`, null, {
            Authorization: `Bearer ${tokenB}`
        });
        console.log("User B GET Report A -> Status:", getReportCross.status, "(Expected 403)");
        if (getReportCross.status !== 403) {
            throw new Error("FAIL: User B was able to view User A's report!");
        }
        console.log("✓ Cross-user report viewing blocked (403)");

        // Step 7: Admin Permissions & Override
        console.log("\n[7] Admin Permissions & Superuser Access...");
        // Admin can access User A's research
        const adminGetA = await makeRequest(TEST_PORT, "GET", `/research/${researchA_Id}`, null, {
            Authorization: `Bearer ${tokenAdmin}`
        });
        if (adminGetA.status !== 200) {
            throw new Error("FAIL: Admin cannot access User A's research");
        }
        console.log("✓ Admin successfully accessed User A's research (200 OK)");

        // Admin can access User B's research
        const adminGetC = await makeRequest(TEST_PORT, "GET", `/research/${researchC_Id}`, null, {
            Authorization: `Bearer ${tokenAdmin}`
        });
        if (adminGetC.status !== 200) {
            throw new Error("FAIL: Admin cannot access User B's research");
        }
        console.log("✓ Admin successfully accessed User B's research (200 OK)");

        // Admin views all research across the system
        const adminList = await makeRequest(TEST_PORT, "GET", "/research", null, {
            Authorization: `Bearer ${tokenAdmin}`
        });
        // Count must include at least the 3 created in this test run
        if (adminList.body.count < 3) {
            throw new Error(`FAIL: Admin should see at least 3 research items (got ${adminList.body.count})`);
        }
        // Verify our 3 specific test items are present
        const ids = adminList.body.data.map(r => r._id);
        if (!ids.includes(researchA_Id) || !ids.includes(researchB_Id) || !ids.includes(researchC_Id)) {
            throw new Error("FAIL: Admin list is missing one of the 3 test research items");
        }
        console.log(`✓ Admin sees all research items including the 3 created in this test run (Total: ${adminList.body.count})`);

        // Step 8: Role-Based Access Control (RBAC) on Admin Routes
        console.log("\n[8] Role-Based Access Control on Admin Routes (/admin)...");
        // User A tries to access /admin/users -> 403 Forbidden
        const rbacUser = await makeRequest(TEST_PORT, "GET", "/admin/users", null, {
            Authorization: `Bearer ${tokenA}`
        });
        console.log("User A (role: user) GET /admin/users -> Status:", rbacUser.status, "(Expected 403)");
        if (rbacUser.status !== 403) {
            throw new Error("FAIL: Non-admin was allowed into /admin/users!");
        }
        console.log("✓ Non-admin access to admin routes blocked (403 Forbidden)");

        // Admin accesses /admin/users -> 200 OK
        const rbacAdmin = await makeRequest(TEST_PORT, "GET", "/admin/users", null, {
            Authorization: `Bearer ${tokenAdmin}`
        });
        console.log("Admin GET /admin/users -> Status:", rbacAdmin.status, "(Expected 200)");
        if (rbacAdmin.status !== 200 || rbacAdmin.body.count < 3) {
            throw new Error("FAIL: Admin could not access /admin/users");
        }
        console.log("✓ Admin successfully accessed /admin/users");

        // Admin checks system stats
        const stats = await makeRequest(TEST_PORT, "GET", "/admin/stats", null, {
            Authorization: `Bearer ${tokenAdmin}`
        });
        console.log("Admin GET /admin/stats -> Stats:", stats.body.stats);
        if (stats.status !== 200) {
            throw new Error("FAIL: Admin could not access /admin/stats");
        }
        console.log("✓ Admin successfully fetched system statistics");

        // Cleanup test data
        console.log("\n[9] Cleaning up test data...");
        await User.deleteMany({ email: { $in: [userA_Email, userB_Email, adminEmail] } });
        await Research.deleteMany({ _id: { $in: [researchA_Id, researchB_Id, researchC_Id] } });
        await Report.deleteMany({ _id: reportA_Id });
        console.log("✓ Test data cleaned up.");

        console.log("\n==================================================");
        console.log("🎉 ALL AUTHORIZATION & RBAC TESTS PASSED 100%!");
        console.log("==================================================");
    } catch (err) {
        console.error("\n❌ Test Failed:", err);
        process.exit(1);
    } finally {
        server.close();
        await mongoose.connection.close();
    }
}

runAuthorizationTests();
