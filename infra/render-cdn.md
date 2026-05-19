Render + CDN (recommended) — Image CDN and caching guide

Goal
- Serve optimized images from an edge CDN (Cloudflare, Fastly, or your chosen CDN) with on-the-fly transforms or pre-generated variants.
- Ensure correct caching, negotiated formats (AVIF/WebP), and long TTLs for static assets.

High-level options
1) Edge transforms (recommended):
   - Deploy a Cloudflare Worker (or use CDN-native transforms) that accepts requests like:
     `https://cdn.example.com/images/path/to.jpg?w=720&fm=webp&q=80`
   - Worker fetches from origin (Supabase storage or static host) and returns transformed image with `Cache-Control: public, max-age=31536000, immutable` and `Vary: Accept`.
   - This minimizes storage duplication and lets the edge handle formats.

2) Pre-generate variants at build time:
   - Use `desktop-web/scripts/optimize_images.js` to generate `webp/avif/jpeg` variants and `manifest.json` per image.
   - Upload optimized files to CDN origin (Supabase Storage or a CDN bucket) and serve using `srcset` and `picture` elements.

Render-specific hints
- `render.yaml` now includes env vars:
  - `CDN_IMAGE_PROXY_URL` — point frontend to the CDN/Worker base URL.
  - `CDN_IMAGE_ORIGIN` — origin that stores original images.

Nginx / server headers
- Ensure images are served with these headers (example in `desktop-web/nginx.conf`):
  - `Vary: Accept`
  - `Cache-Control: public, max-age=31536000, immutable`
- For HTML/entry files, use `Cache-Control: no-cache, no-store, must-revalidate` to ensure clients fetch the latest shell.

Frontend integration
- Use responsive `picture` tags with `srcset` generated from optimized manifests, or call CDN proxy with parameters:
  - `https://cdn.example.com/images/path/to.jpg?w=320&fm=webp&q=80`
- Use `Vary: Accept` so CDNs can cache per-accept-header and return AVIF/WebP where supported.

Security and Deploy
- Keep `.well-known` files and App Links served over HTTPS and behind the same CDN domain to simplify verification.
- Do NOT commit secret keys or fingerprints to Git. Place SHA256 fingerprints and Team ID in CI secrets or Render dashboard variables.

CDN / Cloudflare Quick Steps
1. Deploy `infra/cloudflare/worker-image-proxy` and set `ORIGIN_HOST_PLACEHOLDER` to `CDN_IMAGE_ORIGIN`.
2. Point `CDN_IMAGE_PROXY_URL` to the Worker route.
3. Configure CDN caching rules: cache `/images/*` with long TTL and respect query params only for `w,fm,q` (use Cache Key settings).
4. Enable Brotli and HTTP/2, and Edge TTLs.

Notes
- Testing: run Lighthouse and verify `Largest Contentful Paint` improves and image format served is AVIF/WebP when supported.
- If you prefer another CDN (e.g., Fastly Image Optimizer, Cloudinary, Imgix) adapt the worker or use their native transforms.
