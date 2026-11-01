// Имитация backend для тестов: поднимает /health на заданном порту.
const http = require("node:http");
const args = process.argv.slice(2);
const mode = process.env.FAKE_MODE || "ok";
const port = Number(args[args.indexOf("--port") + 1]);

if (mode === "crash") {
  console.error("boom: порт занят");
  process.exit(3);
}
if (mode === "silent") {
  setInterval(() => {}, 1000); // жив, но не отвечает
} else {
  http
    .createServer((req, res) => {
      if (req.url === "/health") {
        const app = mode === "foreign" ? "SomethingElse" : "ChemAnalyzer";
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ status: "healthy", application: app }));
      } else {
        res.statusCode = 404;
        res.end("{}");
      }
    })
    .listen(port, "127.0.0.1");
}
