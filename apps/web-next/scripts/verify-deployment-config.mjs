import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const appDirectory = path.resolve(scriptDirectory, "..");
const errors = [];

function readJson(filePath, label) {
  try {
    return JSON.parse(readFileSync(filePath, "utf8"));
  } catch (error) {
    errors.push(`${label} is missing or invalid JSON: ${error.message}`);
    return {};
  }
}

function findRepositoryRoot(startDirectory) {
  let currentDirectory = startDirectory;

  while (true) {
    const isRepositoryRoot =
      existsSync(path.join(currentDirectory, ".git")) ||
      (
        existsSync(path.join(currentDirectory, "docker-compose.yml")) &&
        existsSync(path.join(currentDirectory, "apps", "web-next"))
      );
    if (isRepositoryRoot) return currentDirectory;

    const parentDirectory = path.dirname(currentDirectory);
    if (parentDirectory === currentDirectory) return startDirectory;
    currentDirectory = parentDirectory;
  }
}

function findViteConfigs(rootDirectory) {
  const ignoredDirectories = new Set([
    ".git",
    ".next",
    ".vercel",
    ".venv",
    "node_modules",
    "venv",
  ]);
  const viteConfigPattern = /^vite\.config\.(?:cjs|cts|js|jsx|mjs|mts|ts|tsx)$/i;
  const matches = [];

  function visit(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        if (!ignoredDirectories.has(entry.name)) visit(entryPath);
      } else if (entry.isFile() && viteConfigPattern.test(entry.name)) {
        matches.push(entryPath);
      }
    }
  }

  visit(rootDirectory);
  return matches;
}

const vercelConfig = readJson(
  path.join(appDirectory, "vercel.json"),
  "vercel.json",
);
const packageConfig = readJson(
  path.join(appDirectory, "package.json"),
  "package.json",
);
const packageLock = readJson(
  path.join(appDirectory, "package-lock.json"),
  "package-lock.json",
);

if (vercelConfig.framework !== "nextjs") {
  errors.push('vercel.json must set "framework" to "nextjs"');
}
if (vercelConfig.buildCommand !== "npm run build") {
  errors.push('vercel.json must set "buildCommand" to "npm run build"');
}
if (vercelConfig.installCommand !== "npm ci") {
  errors.push('vercel.json must set "installCommand" to "npm ci"');
}

if (
  packageConfig.scripts?.["verify:deployment"] !==
  "node scripts/verify-deployment-config.mjs"
) {
  errors.push(
    'package.json "verify:deployment" must run the deployment verifier',
  );
}
if (packageConfig.scripts?.prebuild !== "npm run verify:deployment") {
  errors.push(
    'package.json "prebuild" must run "npm run verify:deployment"',
  );
}
if (!/^next\s+build(?:\s|$)/.test(packageConfig.scripts?.build ?? "")) {
  errors.push('package.json "build" script must use "next build"');
}
if (!/^next\s+start(?:\s|$)/.test(packageConfig.scripts?.start ?? "")) {
  errors.push('package.json "start" script must use "next start"');
}
if (!packageConfig.dependencies?.next) {
  errors.push('package.json must declare "next" as a runtime dependency');
}

const dependencySections = [
  "dependencies",
  "devDependencies",
  "optionalDependencies",
  "peerDependencies",
];
for (const section of dependencySections) {
  for (const dependencyName of Object.keys(packageConfig[section] ?? {})) {
    if (dependencyName === "vite" || dependencyName.startsWith("@vitejs/")) {
      errors.push(`package.json ${section} must not include "${dependencyName}"`);
    }
  }
}

for (const packagePath of Object.keys(packageLock.packages ?? {})) {
  const normalizedPackagePath = packagePath.replaceAll("\\", "/");
  if (
    /(?:^|\/)node_modules\/vite(?:\/|$)/.test(normalizedPackagePath) ||
    /(?:^|\/)node_modules\/@vitejs(?:\/|$)/.test(normalizedPackagePath)
  ) {
    errors.push(`package-lock.json must not include "${packagePath}"`);
  }
}

const repositoryRoot = findRepositoryRoot(appDirectory);
for (const configPath of findViteConfigs(repositoryRoot)) {
  errors.push(
    `Vite config is not allowed: ${path.relative(repositoryRoot, configPath)}`,
  );
}

if (errors.length > 0) {
  console.error("Deployment configuration verification failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exitCode = 1;
} else {
  console.log(
    "Deployment configuration verified: apps/web-next uses Next.js without Vite.",
  );
}
