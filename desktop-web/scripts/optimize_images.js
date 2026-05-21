#!/usr/bin/env node
import fs from 'fs/promises';
import path from 'path';

let sharp;
try {
  ({ default: sharp } = await import('sharp'));
} catch (err) {
  console.warn('sharp not available, skipping image optimization:', err.message);
  process.exit(0);
}

const srcDir = process.argv[2] || 'public/images';
const outDir = process.argv[3] || 'public/images/optimized';
const sizes = [320, 480, 720, 1024, 1600, 2400];
const formats = ['webp', 'avif', 'jpeg'];

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

async function walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = [];
  for (const e of entries) {
    const res = path.resolve(dir, e.name);
    if (e.isDirectory()) files.push(...await walk(res));
    else files.push(res);
  }
  return files;
}

function isImage(file) {
  return /\.(jpe?g|png|tiff|webp)$/i.test(file);
}

async function processImage(file) {
  const rel = path.relative(srcDir, file);
  const base = path.join(outDir, path.dirname(rel));
  await ensureDir(base);

  const name = path.parse(file).name;
  const manifest = { src: rel.replace(/\\\\/g, '/'), variants: {} };

  for (const fmt of formats) {
    manifest.variants[fmt] = [];
    for (const w of sizes) {
      const outName = `${name}-w${w}.${fmt}`;
      const outPath = path.join(base, outName);
      const transformer = sharp(file).resize({ width: w }).toFormat(fmt, { quality: 80 });
      try {
        await transformer.toFile(outPath);
        manifest.variants[fmt].push(outPath.replace(/.*public\\/i, '').replace(/\\\\/g, '/'));
      } catch (err) {
        console.error('Failed to process', file, fmt, w, err.message);
      }
    }
  }

  // write manifest next to optimized directory
  const manifestPath = path.join(outDir, rel + '.json');
  await ensureDir(path.dirname(manifestPath));
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2));
}

(async () => {
  try {
    try {
      await fs.access(srcDir);
    } catch {
      console.log(`Source image directory not found, skipping optimization: ${srcDir}`);
      process.exit(0);
    }

    const all = await walk(srcDir);
    const images = all.filter(isImage);
    if (images.length === 0) {
      console.log(`No images found in ${srcDir}, skipping optimization.`);
      process.exit(0);
    }

    for (const img of images) {
      console.log('Optimizing', img);
      await processImage(img);
    }
    console.log('Optimization complete.');
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
})();
