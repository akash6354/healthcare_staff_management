// Copies brand assets from /media (read-only source of truth) into an app's public/brand folder.
import { cpSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const target = resolve(process.cwd(), process.argv[2] ?? 'public', 'brand');
mkdirSync(target, { recursive: true });
cpSync(resolve(import.meta.dirname, '..', 'media'), target, { recursive: true });
console.log(`brand assets -> ${target}`);
