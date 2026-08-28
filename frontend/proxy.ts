import { NextRequest, NextResponse } from "next/server";

// Per-request nonce lets us drop 'unsafe-inline' and 'unsafe-eval' from
// script-src. Next.js reads the nonce off this header and applies it to
// every script tag it injects (framework runtime, RSC payloads, etc.) --
// see https://nextjs.org/docs/app/guides/content-security-policy.
//
// style-src keeps 'unsafe-inline' deliberately: CSP has no nonce mechanism
// for the HTML style="" attribute (only for <style> elements), and this
// app relies on React inline style objects throughout. Dropping it would
// silently break rendering, not just tighten security.
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");

  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    // Skip static assets and image optimization so the nonce dance only
    // runs on page/document requests.
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
