const http = require('node:http');
const https = require('node:https');
const dns = require('node:dns').promises;
const net = require('node:net');

function isPublicAddress(address) {
    if (net.isIP(address) === 4) {
        const [a, b] = address.split('.').map(Number);
        return !(a === 0 || a === 10 || a === 127 || a >= 224 ||
            (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) ||
            (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127) ||
            (a === 198 && (b === 18 || b === 19)));
    }
    // Only globally routed IPv6; mapped IPv4 and link-local addresses are excluded.
    return net.isIP(address) === 6 && /^[23][0-9a-f]{3}:/i.test(address);
}

async function request(url, { signal, method = 'GET', headers = {}, body, timeoutMs = 10000, maxBytes = 2_000_000 } = {}, redirects = 0) {
    signal?.throwIfAborted();
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password ||
        (parsed.port && !['80', '443'].includes(parsed.port))) throw new Error('Unsupported source URL');
    const hostname = parsed.hostname.replace(/^\[|\]$/g, '');
    const addresses = await Promise.race([
        dns.lookup(hostname, { all: true }),
        new Promise((_, reject) => {
            const timer = setTimeout(() => reject(new Error('DNS lookup timed out')), timeoutMs);
            timer.unref();
        })
    ]);
    signal?.throwIfAborted();
    if (!addresses.length || addresses.some(({ address }) => !isPublicAddress(address))) throw new Error('Source URL is not public');
    const address = addresses[0];
    const response = await new Promise((resolve, reject) => {
        let timer;
        const req = (parsed.protocol === 'https:' ? https : http).request(parsed, {
            method, signal,
            headers: { 'User-Agent': 'DeepResearchAI/2.0', 'Accept-Encoding': 'identity', ...headers },
            // Pin the validated DNS answer for this connection, including redirects.
            lookup: (_host, options, callback) => options.all
                ? callback(null, [address]) : callback(null, address.address, address.family)
        }, (res) => {
            const chunks = [];
            let size = 0;
            res.on('data', (chunk) => {
                size += chunk.length;
                if (size > maxBytes) req.destroy(new Error('Source exceeds download limit'));
                else chunks.push(chunk);
            });
            res.on('error', reject);
            res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, text: Buffer.concat(chunks).toString('utf8') }));
        });
        timer = setTimeout(() => req.destroy(new Error('Source request timed out')), timeoutMs);
        req.on('close', () => clearTimeout(timer));
        req.on('error', reject);
        if (body) req.write(body);
        req.end();
    });
    if (response.status >= 300 && response.status < 400 && response.headers.location) {
        if (redirects >= 4 || method !== 'GET') throw new Error('Source redirect limit exceeded');
        return request(new URL(response.headers.location, parsed).href, { signal, timeoutMs, maxBytes }, redirects + 1);
    }
    if (response.status < 200 || response.status >= 300) throw new Error(`Source returned HTTP ${response.status}`);
    return response;
}

async function mapConcurrent(items, limit, fn, signal) {
    const results = new Array(items.length);
    let cursor = 0;
    await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => {
        while (cursor < items.length) {
            signal?.throwIfAborted();
            const index = cursor++;
            results[index] = await fn(items[index], index);
        }
    }));
    return results;
}

module.exports = { request, mapConcurrent, isPublicAddress };
