import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Mounted at /app behind nginx (which proxies /app/* to this process).
  basePath: "/app",
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // Avatars come from googleusercontent.
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
      { protocol: "https", hostname: "*.googleusercontent.com" },
    ],
  },
};

export default nextConfig;
