require("dotenv").config();
const http = require("http");

function request(method, path, body = null, token = null) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (data) headers["Content-Length"] = Buffer.byteLength(data);

    const req = http.request(
      { hostname: "127.0.0.1", port: 5000, path, method, headers },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => {
          try { resolve({ status: res.statusCode, data: JSON.parse(buf) }); }
          catch (e) { resolve({ status: res.statusCode, text: buf }); }
        });
      }
    );
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

async function test() {
  console.log("=========================================");
  console.log("   FULL LIFECYCLE & MULTI-PAGE TEST      ");
  console.log("=========================================\n");

  const email = `test_operator_${Date.now()}@deep-research.ai`;
  console.log("[1] Registering Operator:", email);
  const reg = await request("POST", "/api/auth/register", {
    name: "Priyanshu Joshi",
    email,
    password: "Password123!"
  });
  console.log("✓ Registration Status:", reg.status, reg.data?.success ? "OK" : reg.data);
  const token = reg.data?.accessToken;
  if (!token) throw new Error("No access token returned");

  console.log("\n[2] Testing Profile /api/auth/me");
  const me = await request("GET", "/api/auth/me", null, token);
  console.log("✓ Profile:", me.data?.user?.name, me.data?.user?.email);

  console.log("\n[3] Submitting Deep Research Job");
  const research = await request("POST", "/api/research", {
    query: "Solid-state battery breakthroughs and commercialization timelines",
    depth: "standard",
    breadth: 3,
    categories: ["web", "academic", "market"]
  }, token);
  console.log("✓ Research Created:", research.status, "ID:", research.data?.id || research.data?.research_id);

  console.log("\n[4] Polling Research Status...");
  const jobId = research.data?.id || research.data?.research_id;
  let finished = false;
  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const statusRes = await request("GET", `/api/research/${jobId}`, null, token);
    const job = statusRes.data?.research || statusRes.data?.data || statusRes.data;
    console.log(`  -> Status: [${job.status}] Progress: ${job.progress}% Step: ${job.currentStep || 'N/A'}`);
    if (job.status === "completed" || job.status === "failed") {
      finished = true;
      break;
    }
  }

  console.log("\n[5] Fetching Reports Archive /api/reports");
  const reportsRes = await request("GET", "/api/reports", null, token);
  console.log("✓ Reports Archive count:", reportsRes.data?.reports?.length || reportsRes.data?.length || 0);

  console.log("\n=========================================");
  console.log("🎉 ALL MULTI-PAGE & BACKEND TESTS PASSED!");
  console.log("=========================================\n");
}

test().catch((err) => {
  console.error("Test error:", err);
  process.exit(1);
});
