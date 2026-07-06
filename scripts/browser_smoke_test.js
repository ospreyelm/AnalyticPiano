const { spawn, execSync } = require("child_process");
const net = require("net");
const path = require("path");

const browsePath = path.join(process.env.HOME, ".claude/skills/gstack/browse/dist/browse");

function isPortInUse(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(1000);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true); // Connected successfully, so port is in use
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => {
      socket.destroy();
      resolve(false); // Refused or other error, port is free
    });
    socket.connect(port, "127.0.0.1");
  });
}

async function waitForServer(port, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const inUse = await isPortInUse(port);
    if (inUse) {
      return; // Server is up and listening
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Timeout waiting for server on port ${port}`);
}

function runBrowse(args) {
  try {
    const output = execSync(`"${browsePath}" ${args}`, { stdio: "pipe" });
    return { success: true, output: output.toString() };
  } catch (err) {
    return { success: false, error: err.message, output: err.stdout ? err.stdout.toString() : "", stderr: err.stderr ? err.stderr.toString() : "" };
  }
}

async function main() {
  let spawnedDjango = null;
  let spawnedVite = null;

  try {
    const djangoInUse = await isPortInUse(8765);
    const viteInUse = await isPortInUse(5173);

    if (!djangoInUse) {
      console.log("Starting Django server...");
      spawnedDjango = spawn("/Library/Frameworks/Python.framework/Versions/3.13/bin/python3", [
        "manage.py",
        "runserver",
        "0.0.0.0:8765",
        "--settings=harmony.settings.local"
      ], {
        env: {
          ...process.env,
          DATABASE_URL: "postgres://postgres@localhost:5432/analyticpiano"
        }
      });
      // Capture and discard output to prevent buffer overflow
      spawnedDjango.stdout.on("data", () => {});
      spawnedDjango.stderr.on("data", () => {});
      await waitForServer(8765);
      console.log("Django server is ready.");
    } else {
      console.log("Django server is already running.");
    }

    if (!viteInUse) {
      console.log("Starting Vite dev server...");
      spawnedVite = spawn("npx", ["vite"]);
      spawnedVite.stdout.on("data", () => {});
      spawnedVite.stderr.on("data", () => {});
      await waitForServer(5173);
      console.log("Vite server is ready.");
    } else {
      console.log("Vite server is already running.");
    }

    // Ensure browse server is started and healthy
    console.log("Initializing browser automation...");
    runBrowse("status");

    // Check if we are logged in
    console.log("Navigating to login page check...");
    runBrowse("goto http://localhost:8765/s/login/");
    runBrowse("wait --networkidle");

    const urlCheck = runBrowse("url");
    if (urlCheck.output.includes("/login")) {
      console.log("Not logged in. Performing student login...");
      runBrowse("fill \"#id_email\" \"student@local.test\"");
      runBrowse("fill \"#id_password\" \"password\"");
      const loginResult = runBrowse("click \"button[type='submit']\"");
      if (!loginResult.success) {
        throw new Error("Failed to click submit on login page.");
      }
      runBrowse("wait --networkidle");
      const postLoginUrl = runBrowse("url").output;
      console.log(`Login submitted. Currently at: ${postLoginUrl.trim()}`);
    } else {
      console.log("Already logged in.");
    }

    // List of URLs to smoke test
    const testUrls = [
      "http://localhost:8765/s/units/9/play/?playlist=PA03SM&exercise_num=3",
      "http://localhost:8765/s/units/9/play/?playlist=PA03UO&exercise_num=1"
    ];

    let hasErrors = false;

    for (const url of testUrls) {
      console.log(`Testing URL: ${url}`);
      runBrowse(`goto "${url}"`);
      runBrowse("wait --networkidle");

      // Check console for errors, ignoring warnings/info messages
      const consoleLog = runBrowse("console --errors");
      const logLines = (consoleLog.output || "").split("\n");
      const errorLines = logLines.filter(line => {
        const lower = line.toLowerCase();
        if (
          lower.includes("[warning]") ||
          lower.includes("[info]") ||
          lower.includes("(no console errors)") ||
          lower.includes("--- begin untrusted external content") ||
          lower.includes("--- end untrusted external content") ||
          line.trim() === ""
        ) {
          return false;
        }
        return true;
      });

      if (errorLines.length > 0) {
        console.error(`❌ Console errors detected for URL: ${url}`);
        console.error(errorLines.join("\n"));
        hasErrors = true;
      } else {
        console.log(`✅ Passed: ${url}`);
      }
    }

    if (hasErrors) {
      throw new Error("One or more URLs failed the smoke test due to console errors.");
    }

    console.log("🎉 All browser smoke tests completed successfully with zero console errors!");
  } catch (error) {
    console.error("❌ Smoke test failed:", error.message);
    process.exitCode = 1;
  } finally {
    // Stop the browse server session gracefully
    console.log("Stopping browser session...");
    runBrowse("stop");

    if (spawnedDjango) {
      console.log("Stopping spawned Django server...");
      spawnedDjango.kill();
    }
    if (spawnedVite) {
      console.log("Stopping spawned Vite server...");
      spawnedVite.kill();
    }
  }
}

main();
