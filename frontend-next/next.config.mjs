/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow Next.js Image component to serve avatars from Supabase storage
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lgnaabrgdqomxuxfonqo.supabase.co",
        pathname: "/storage/v1/object/public/**",
      },
      // Google profile pictures served by Google OAuth
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
      },
    ],
  },
};

export default nextConfig;
