// Single source of truth for product branding. Everything else reads BRAND.*
// instead of literal "CurriculumCraft" so the rename can happen by editing
// one file or by setting VITE_BRAND_* at build time (useful for forks).
//
// localStorage keys derived from BRAND.slug get a migration shim in
// utils/apiConfig.js that copies any pre-rename `mathcraft.*` value to
// the new key on first read so existing users don't lose their backend URL.

const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}

export const BRAND = {
  name: env.VITE_BRAND_NAME || 'CurriculumCraft',
  nameAr: env.VITE_BRAND_NAME_AR || 'كرافت المنهج',
  slug: env.VITE_BRAND_SLUG || 'curriculumcraft',
  tagline: env.VITE_BRAND_TAGLINE || 'AI Curriculum Workbook Generator',
  taglineAr: env.VITE_BRAND_TAGLINE_AR || 'مولّد المناهج بالذكاء الاصطناعي',
  monogram: env.VITE_BRAND_MONOGRAM || 'C',
  repoUrl: env.VITE_REPO_URL || 'https://github.com/mdSHash/curriculumcraft',
  hostingDocsUrl:
    env.VITE_HOSTING_DOCS_URL ||
    'https://github.com/mdSHash/curriculumcraft/blob/main/HOSTING.md',
  spaceUrl:
    env.VITE_SPACE_URL || 'https://huggingface.co/spaces/ScriptMaker/curriculumcraft',
  // Legacy slug used to migrate localStorage keys from the pre-rename build.
  // Don't change this — it's strictly the old key name we copy from.
  legacySlug: 'mathcraft',
}

export default BRAND
