/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*', // your FastAPI backend URL
      },
    ]
  },
}

module.exports = nextConfig;
