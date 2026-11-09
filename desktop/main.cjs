const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("node:child_process");
const net = require("node:net");
const path = require("node:path");
const fs = require("node:fs");

let apiProcess;
let workerProcess;
let mainWindow;
let stopping = false;

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function startBackend(role, port, dataDirectory, logFile) {
  const env = {
    ...process.env,
    DATABASE_PATH: path.join(dataDirectory, "invoice_engine.db"),
    INVOICE_ENGINE_DATA_DIR: dataDirectory,
    PORT: String(port),
    PYTHONUNBUFFERED: "1"
  };

  if (app.isPackaged) {
    const executable = path.join(process.resourcesPath, "backend", "invoice-engine-backend.exe");
    const child = spawn(executable, [role, String(port)], { cwd: dataDirectory, env, windowsHide: true });
    child.stdout?.on("data", (chunk) => fs.appendFileSync(logFile, `[${role}] ${chunk}`));
    child.stderr?.on("data", (chunk) => fs.appendFileSync(logFile, `[${role}:stderr] ${chunk}`));
    child.on("exit", (code, signal) => fs.appendFileSync(logFile, `[${role}] exited code=${code} signal=${signal}\\n`));
    child.on("error", (error) => fs.appendFileSync(logFile, `[${role}] spawn error: ${error.stack || error}\\n`));
    return child;
  }

  const python = process.env.INVOICE_ENGINE_PYTHON || "python";
  const args = role === "api"
    ? ["-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", String(port)]
    : ["worker.py"];
  return spawn(python, args, { cwd: app.getAppPath(), env, windowsHide: true });
}

async function waitForApi(port) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (apiProcess?.exitCode !== null && apiProcess?.exitCode !== undefined) {
      throw new Error(`The local API exited with code ${apiProcess.exitCode}.`);
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(1500) });
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error("The local Invoice Engine service did not start within 30 seconds.");
}

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 980,
    minHeight: 680,
    title: "Invoice Engine",
    backgroundColor: "#f7f8fa",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  mainWindow.webContents.setWindowOpenHandler(({ url: target }) => {
    if (target.startsWith("https://")) shell.openExternal(target);
    return { action: "deny" };
  });
  mainWindow.loadURL(url);
  mainWindow.on("closed", () => { mainWindow = null; });
}

function stopServices() {
  if (stopping) return;
  stopping = true;
  for (const child of [workerProcess, apiProcess]) {
    if (child && child.exitCode === null) child.kill();
  }
}

app.whenReady().then(async () => {
  const dataDirectory = path.join(app.getPath("userData"), "data");
  fs.mkdirSync(dataDirectory, { recursive: true });
  const logFile = path.join(dataDirectory, "startup.log");
  fs.writeFileSync(logFile, `Invoice Engine startup ${new Date().toISOString()}\\n`);

  // The API serves frontend files from a relative "frontend" directory.
  // Copy the packaged frontend into the writable runtime directory so the
  // backend can find it when its working directory is userData/data.
  const packagedFrontend = path.join(app.getAppPath(), "frontend");
  const runtimeFrontend = path.join(dataDirectory, "frontend");
  if (fs.existsSync(packagedFrontend)) {
    fs.cpSync(packagedFrontend, runtimeFrontend, { recursive: true, force: true });
  }

  const port = await getFreePort();
  fs.appendFileSync(logFile, `Starting API on port ${port}; packaged=${app.isPackaged}; cwd=${dataDirectory}\\n`);
  apiProcess = startBackend("api", port, dataDirectory, logFile);
  apiProcess.on("error", (error) => dialog.showErrorBox("Invoice Engine could not start", error.message));
  workerProcess = startBackend("worker", port, dataDirectory, logFile);
  workerProcess.on("error", (error) => dialog.showErrorBox("Invoice Engine worker could not start", error.message));
  try {
    await waitForApi(port);
    fs.appendFileSync(logFile, "API health check passed; opening window.\\n");
    createWindow(`http://127.0.0.1:${port}/frontend/auth.html`);
  } catch (error) {
    fs.appendFileSync(logFile, `STARTUP FAILURE: ${error.stack || error}\\n`);
    stopServices();
    dialog.showErrorBox("Invoice Engine could not start", `${error.message}\\n\\nDiagnostic log: ${logFile}`);
    app.quit();
  }
});

app.on("before-quit", stopServices);
app.on("window-all-closed", () => app.quit());
