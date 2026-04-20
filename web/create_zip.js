import fs from "fs";
import path from "path";
import archiver from "archiver";
import { fileURLToPath } from "url";
import { dirname } from "path";

// __dirname for ES Modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Project root (one folder up)
const rootDir = path.resolve(__dirname, "..");

// Target ZIP
const zipName = "python.zip";
const outPath = path.resolve(__dirname, "public", zipName);

// Delete previous ZIP if it exists
if (fs.existsSync(outPath)) {
  fs.unlinkSync(outPath);
  console.log(`[Info] Previous ${zipName} deleted`);
}

// Stream for new ZIP
const output = fs.createWriteStream(outPath);
const archive = archiver("zip", { zlib: { level: 9 } });

output.on("close", () => {
  console.log(`ZIP created: ${archive.pointer()} bytes → ${zipName}`);
});

archive.on("warning", (err) => {
  if (err.code === "ENOENT") console.warn(err);
  else throw err;
});

archive.on("error", (err) => {
  throw err;
});

archive.pipe(output);

// Add all files/folders from root, except "web" and "venv"
const items = fs.readdirSync(rootDir);

items.forEach((item) => {
  if (item === "web") return; // exclude
  if (item === "venv") return; // exclude
  if (item === ".git") return; // exclude
  const fullPath = path.join(rootDir, item);
  const stats = fs.statSync(fullPath);

  if (stats.isDirectory()) {
    archive.directory(fullPath, item); // add recursively
  } else {
    archive.file(fullPath, { name: item });
  }
});

// Finalize ZIP
archive.finalize();
