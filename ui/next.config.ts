import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  basePath: "/transformer",
  async redirects() {
    return [
      {
        source: "/",
        destination: "/transformer/schema",
        permanent: false,
        basePath: false,
      },
      {
        source: "/",
        destination: "/schema",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
