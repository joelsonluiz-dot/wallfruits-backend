addEventListener('fetch', event => {
  event.respondWith(handle(event.request))
})

async function handle(request) {
  try {
    const url = new URL(request.url)
    // Expected path: /image/<path-to-image>
    // Query params: w (width), q (quality), fm (format: webp,avif,jpeg)
    const pathParts = url.pathname.split('/').filter(Boolean)
    if (pathParts[0] !== 'image' || pathParts.length < 2) {
      return new Response('Not found', { status: 404 })
    }

    const imgPath = pathParts.slice(1).join('/')
    const originHost = ORIGIN_HOST_PLACEHOLDER || 'https://static.wallfruits.com'
    const originUrl = `${originHost}/images/${imgPath}`

    const width = parseInt(url.searchParams.get('w')) || undefined
    const quality = parseInt(url.searchParams.get('q')) || 80
    const fm = url.searchParams.get('fm') || 'auto' // auto, webp, avif, jpeg

    // Build CF image options; Cloudflare transforms when passing cf.image
    const cfOptions = {
      image: {
        quality,
        // only set width when provided
        ...(width ? { width } : {}),
        // automatic format selection if fm=auto
        ...(fm && fm !== 'auto' ? { format: fm } : {}),
      }
    }

    const fetchResponse = await fetch(originUrl, { cf: cfOptions })

    if (!fetchResponse.ok) {
      return new Response('Origin fetch failed', { status: 502 })
    }

    // Copy headers and add caching
    const headers = new Headers(fetchResponse.headers)
    headers.set('Cache-Control', 'public, max-age=31536000, immutable')
    headers.set('Vary', 'Accept')

    return new Response(fetchResponse.body, { status: fetchResponse.status, headers })
  } catch (err) {
    return new Response('Worker error: ' + err.message, { status: 500 })
  }
}
