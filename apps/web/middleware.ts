/**
 * Next.js middleware — route protection.
 *
 * Checks for the presence of the cs_session cookie before allowing access
 * to authenticated routes. Cookie presence is a fast heuristic only; the
 * actual JWT verification is done by FastAPI on every authenticated API call.
 *
 * Protected: /watchlists/*
 * Public:    everything else (search, company pages, sign-in, register)
 */

import { type NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/watchlists")) {
    const session = request.cookies.get("cs_session");
    if (!session) {
      const signInUrl = new URL("/sign-in", request.url);
      signInUrl.searchParams.set("next", pathname);
      return NextResponse.redirect(signInUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/watchlists/:path*"],
};
