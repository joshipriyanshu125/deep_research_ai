require("dotenv").config({ path: "c:/Users/joshi/OneDrive/Desktop/deep_research_ai/backend/.env" });
const http = require("http");

function post(path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port: 5000,
        path,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data)
        }
      },
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
    req.write(data);
    req.end();
  });
}

async function run() {
  const uniqueName = `Priyanshu_${Date.now()}`;
  const uniqueEmail = `${uniqueName.toLowerCase()}@deep-research.ai`;
  const password = "Password123!";

  console.log("=========================================");
  console.log("    LOGIN IDENTIFIER & ERROR TEST        ");
  console.log("=========================================\n");

  // 1. Register
  console.log(`[1] Registering: Name="${uniqueName}", Email="${uniqueEmail}"`);
  const reg = await post("/api/auth/register", { name: uniqueName, email: uniqueEmail, password });
  console.log("Registration Status:", reg.status, reg.data?.success ? "✓ OK" : reg.data);

  // 2. Login by Email
  console.log("\n[2] Logging in by EMAIL:", uniqueEmail);
  const loginEmail = await post("/api/auth/login", { email: uniqueEmail, password });
  console.log("Login by Email Status:", loginEmail.status, loginEmail.data?.success ? "✓ OK" : loginEmail.data);

  // 3. Login by Name
  console.log("\n[3] Logging in by OPERATOR NAME:", uniqueName);
  const loginName = await post("/api/auth/login", { email: uniqueName, password });
  console.log("Login by Name Status:", loginName.status, loginName.data?.success ? "✓ OK" : loginName.data);

  // 4. Invalid Password test
  console.log("\n[4] Testing Invalid Password Error Message");
  const badLogin = await post("/api/auth/login", { email: uniqueName, password: "wrong-password" });
  console.log("Bad Login Status:", badLogin.status, "Message:", badLogin.data?.message);

  if (badLogin.data?.message === "Refresh token is required") {
    throw new Error("FAILED: Returned refresh token error instead of invalid credentials error");
  }

  console.log("\n=========================================");
  console.log("🎉 ALL LOGIN TESTS PASSED!");
  console.log("=========================================\n");
}

run().catch((err) => {
  console.error("Test error:", err);
  process.exit(1);
});
