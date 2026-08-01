import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    const apiOrigin = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
    const connectSource = apiOrigin ? new URL(apiOrigin).origin : "'self'";
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "object-src 'none'",
      "img-src 'self' data: https:",
      "font-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      `connect-src 'self' ${connectSource}`,
      "script-src 'self' 'unsafe-inline'",
      "upgrade-insecure-requests",
    ].join("; ");
    return [{
      source: "/(.*)",
      headers: [
        { key: "Content-Security-Policy", value: csp },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
      ],
    }];
  },
};

export default nextConfig;
