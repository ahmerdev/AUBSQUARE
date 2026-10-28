// Exports the original hard-coded React content (src/data/*.ts) to backend/seed/frontend_content.json
// so it can be imported into the database with:  python manage.py import_frontend_content
// Run from the project root:  node backend/tools/export_frontend_data.mjs
import { build } from 'esbuild';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..');
const tmp = mkdtempSync(join(tmpdir(), 'aub-export-'));
const entry = join(tmp, 'entry.ts');
writeFileSync(entry, `
import { servicesData } from '${join(root, 'src/data/services.ts').replace(/\\/g, '/')}';
import { projectsData } from '${join(root, 'src/data/projects.ts').replace(/\\/g, '/')}';
import { caseStudiesData } from '${join(root, 'src/data/caseStudies.ts').replace(/\\/g, '/')}';
import { articlesData } from '${join(root, 'src/data/articles.ts').replace(/\\/g, '/')}';
import { testimonialsData } from '${join(root, 'src/data/testimonials.ts').replace(/\\/g, '/')}';
import { faqsData } from '${join(root, 'src/data/faqs.ts').replace(/\\/g, '/')}';
export default { services: servicesData, projects: projectsData, caseStudies: caseStudiesData, articles: articlesData, testimonials: testimonialsData, faqs: faqsData };
`);
const out = join(tmp, 'out.mjs');
await build({ entryPoints: [entry], bundle: true, format: 'esm', outfile: out, platform: 'node', logLevel: 'error' });
const mod = await import(pathToFileURL(out).href);
writeFileSync(join(root, 'backend', 'seed', 'frontend_content.json'), JSON.stringify(mod.default, null, 2));
console.log('Exported', Object.fromEntries(Object.entries(mod.default).map(([k, v]) => [k, v.length])));
