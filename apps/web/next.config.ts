import type { NextConfig } from "next";

/**
 * Architecture note (docs/01-system-architecture.md):
 *
 * - The browser NEVER calls Companies House directly.
 * - All Companies House integration lives in the API and worker services.
 * - Client-side code (TanStack Query, added in Phase 7) calls the CompanyScope
 *   FastAPI backend only, via NEXT_PUBLIC_API_URL.
 * - Server-side Next.js code (server components, route handlers) must use
 *   API_INTERNAL_URL (not public) so requests route correctly inside Docker.
 *   These are two different env vars for two different network paths:
 *
 *   NEXT_PUBLIC_API_URL  → http://localhost:8000  (browser → host port)
 *   API_INTERNAL_URL     → http://api:8000        (Next.js server → Docker network)
 */
const nextConfig: NextConfig = {
  // Rewrites, route handlers, and server-side data fetching are added in
  // later phases as the public API surface is built out.
};

export default nextConfig;
