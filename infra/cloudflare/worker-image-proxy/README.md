Cloudflare Worker image proxy scaffold

Purpose
- Provide on-the-fly image transforms (resize, quality, format) at the edge using Cloudflare Images API via the Worker `cf.image` transform option.

Usage
1. Install Wrangler (Cloudflare CLI) and login:
   - `npm install -g wrangler`
   - `wrangler login`
2. Update `wrangler.toml` with your `account_id` and desired `route`.
3. Deploy:
   - `wrangler publish --name wallfruits-image-proxy`

Request format
- Example proxied URL:
  - `https://cdn.example.com/images/path/to/photo.jpg?w=720&fm=webp&q=80`
- Query params:
  - `w` — width in px
  - `fm` — format: `auto`, `webp`, `avif`, `jpeg`
  - `q` — quality (1-100)

Notes
- This scaffold uses Cloudflare's `cf.image` transform, which runs only on Cloudflare Workers.
- Ensure your origin allows the Worker to fetch images (CORS not required for direct image fetch but origin protections should allow worker requests).
- Add caching rules on Cloudflare for `/images/*` to leverage edge caches.
