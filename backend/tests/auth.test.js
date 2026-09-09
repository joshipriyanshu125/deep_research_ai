require("dotenv").config();
const http = require("http");
const mongoose = require("mongoose");
const crypto = require("crypto");
const app = require("../src/server");
const User = require("../src/models/User");
const {
    generateAccessToken,
    generateRefreshToken,
    verifyAccessToken,
    verifyRefreshToken
} = require("../src/utils/token");

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

async function runTestSuite() {
    console.log("=========================================");
    console.log("   DAY 3: AUTHENTICATION TEST SUITE      ");
    console.log("=========================================");

    const TEST_PORT = 5099;
    const server = http.createServer(app);
    await new Promise((resolve) => server.listen(TEST_PORT, resolve));

    // Connect to MongoDB if not already connected
    if (mongoose.connection.readyState === 0) {
        await mongoose.connect(process.env.MONGODB_URI);
    }

    const testEmail = `authtest_${Date.now()}@example.com`;
    const initialPassword = "Password123!";
    const newPassword = "NewSecretPassword456!";

    try {
        // --- 1. UNIT TESTS: MODEL & TOKENS ---
        console.log("\n--- [Phase 1] Unit Tests: Model & JWT ---");
        const userObj = new User({
            name: "Test User",
            email: `unit_${Date.now()}@example.com`,
            password: initialPassword
        });
        await userObj.save();

        const rawUser = await User.findById(userObj._id).select("+password");
        if (rawUser.password === initialPassword || !rawUser.password.startsWith("$2")) {
            throw new Error("FAIL: Password hashing failed");
        }
        console.log("✓ Passwords securely hashed with bcrypt");

        const isMatch = await rawUser.comparePassword(initialPassword);
        const isWrongMatch = await rawUser.comparePassword("WrongPassword");
        if (!isMatch || isWrongMatch) {
            throw new Error("FAIL: Password comparison failed");
        }
        console.log("✓ Password comparison works correctly");

        const accessTok = generateAccessToken(userObj);
        const refreshTok = generateRefreshToken(userObj);
        const decAccess = verifyAccessToken(accessTok);
        const decRefresh = verifyRefreshToken(refreshTok);
        if (!decAccess || !decRefresh) {
            throw new Error("FAIL: JWT token signing or verification failed");
        }
        console.log("✓ JWT access & refresh tokens generated & verified");

        await User.findByIdAndDelete(userObj._id);

        // --- 2. E2E TESTS: ALL 7 ENDPOINTS ---
        console.log("\n--- [Phase 2] End-to-End API Endpoint Tests ---");

        // 1. POST /auth/register
        console.log("[1] POST /auth/register");
        const regRes = await makeRequest(TEST_PORT, "POST", "/auth/register", {
            name: "Auth Test User",
            email: testEmail,
            password: initialPassword
        });
        if (regRes.status !== 201 || !regRes.body.accessToken || !regRes.body.refreshToken) {
            throw new Error("POST /auth/register failed: " + JSON.stringify(regRes.body));
        }
        let accessToken = regRes.body.accessToken;
        let refreshToken = regRes.body.refreshToken;
        console.log("✓ Status 201 - Registered successfully with tokens");

        // 2. POST /auth/login
        console.log("[2] POST /auth/login");
        const loginRes = await makeRequest(TEST_PORT, "POST", "/auth/login", {
            email: testEmail,
            password: initialPassword
        });
        if (loginRes.status !== 200 || !loginRes.body.accessToken) {
            throw new Error("POST /auth/login failed: " + JSON.stringify(loginRes.body));
        }
        accessToken = loginRes.body.accessToken;
        refreshToken = loginRes.body.refreshToken;
        console.log("✓ Status 200 - Logged in successfully");

        // 3. GET /auth/me (Protected Route)
        console.log("[3] GET /auth/me (Protected)");
        const meRes = await makeRequest(TEST_PORT, "GET", "/auth/me", null, {
            Authorization: `Bearer ${accessToken}`
        });
        if (meRes.status !== 200 || meRes.body.user.email !== testEmail.toLowerCase()) {
            throw new Error("GET /auth/me failed: " + JSON.stringify(meRes.body));
        }
        console.log("✓ Status 200 - Accessed protected profile with Bearer token");

        // 3b. Unauthorized test
        const unauthRes = await makeRequest(TEST_PORT, "GET", "/auth/me");
        if (unauthRes.status !== 401) {
            throw new Error("Expected 401 for unauthenticated request");
        }
        console.log("✓ Status 401 - Unauthenticated access correctly blocked");

        // 4. POST /auth/refresh
        console.log("[4] POST /auth/refresh");
        const refreshRes = await makeRequest(TEST_PORT, "POST", "/auth/refresh", {
            refreshToken: refreshToken
        });
        if (refreshRes.status !== 200 || !refreshRes.body.accessToken) {
            throw new Error("POST /auth/refresh failed: " + JSON.stringify(refreshRes.body));
        }
        accessToken = refreshRes.body.accessToken;
        refreshToken = refreshRes.body.refreshToken;
        console.log("✓ Status 200 - Access token refreshed");

        // 5. POST /auth/forgot-password
        console.log("[5] POST /auth/forgot-password");
        const forgotRes = await makeRequest(TEST_PORT, "POST", "/auth/forgot-password", {
            email: testEmail
        });
        if (forgotRes.status !== 200 || !forgotRes.body.resetToken) {
            throw new Error("POST /auth/forgot-password failed: " + JSON.stringify(forgotRes.body));
        }
        const resetToken = forgotRes.body.resetToken;
        console.log("✓ Status 200 - Reset token generated:", resetToken);

        // 6. POST /auth/reset-password
        console.log("[6] POST /auth/reset-password");
        const resetRes = await makeRequest(TEST_PORT, "POST", "/auth/reset-password", {
            resetToken: resetToken,
            newPassword: newPassword
        });
        if (resetRes.status !== 200) {
            throw new Error("POST /auth/reset-password failed: " + JSON.stringify(resetRes.body));
        }
        console.log("✓ Status 200 - Password reset successfully");

        // Verify login with updated password
        const newLoginRes = await makeRequest(TEST_PORT, "POST", "/auth/login", {
            email: testEmail,
            password: newPassword
        });
        if (newLoginRes.status !== 200) {
            throw new Error("Login with new password failed!");
        }
        console.log("✓ Status 200 - Successfully authenticated with new password");

        // 7. POST /auth/logout
        console.log("[7] POST /auth/logout");
        const logoutRes = await makeRequest(TEST_PORT, "POST", "/auth/logout", {
            refreshToken: newLoginRes.body.refreshToken
        });
        if (logoutRes.status !== 200) {
            throw new Error("POST /auth/logout failed: " + JSON.stringify(logoutRes.body));
        }
        console.log("✓ Status 200 - Logged out successfully");

        // Clean up test record
        await User.findOneAndDelete({ email: testEmail.toLowerCase() });
        console.log("\n✓ Cleanup complete.");

        console.log("=========================================");
        console.log("🎉 ALL TESTS COMPLETED SUCCESSFULLY!");
        console.log("=========================================\n");
    } catch (err) {
        console.error("Test Suite Failed:", err);
        process.exit(1);
    } finally {
        server.close();
        await mongoose.connection.close();
    }
}

runTestSuite();
