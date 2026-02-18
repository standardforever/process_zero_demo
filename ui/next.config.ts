import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  basePath: "/transformer",
  async redirects() {
    return [
      {
        source: "/",
        destination: "/transformer/rules",
        permanent: false,
        basePath: false,
      },
      {
        source: "/",
        destination: "/rules",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
