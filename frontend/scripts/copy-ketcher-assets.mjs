import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendRoot = fileURLToPath(new URL("../", import.meta.url));
const source = path.join(frontendRoot, "node_modules", "ketcher-react", "dist");
const publicRoot = path.join(frontendRoot, "public");
const destination = path.join(publicRoot, "ketcher-assets");

if (!existsSync(source) || !readdirSync(source).length) {
  console.error(
    "Не найдены статические ресурсы Ketcher. Сначала выполните npm install в папке frontend."
  );
  process.exit(1);
}

mkdirSync(publicRoot, { recursive: true });
rmSync(destination, { recursive: true, force: true });
cpSync(source, destination, { recursive: true, force: true });

function countFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).reduce(
    (sum, entry) => sum + (entry.isDirectory() ? countFiles(path.join(dir, entry.name)) : 1),
    0
  );
}

const copied = countFiles(destination);
if (copied === 0) {
  console.error("Копирование ресурсов Ketcher не дало файлов.");
  process.exit(1);
}

console.log(`Ketcher static assets: copied ${copied} files to public/ketcher-assets`);
