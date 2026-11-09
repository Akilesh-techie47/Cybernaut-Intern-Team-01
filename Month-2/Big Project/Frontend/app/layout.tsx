/** @type {import('next').Metadata} */
import "./tailwind.css";
import { TopNav, BottomNav } from "../components/navigation";

export const metadata = {
  title: "AeroDelay AI",
  description:
    "Premium Aviation Intelligence Platform - Delay Risk Prediction & Flight Analytics",
  icons: {
    favicon: "/favicon.ico",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1.0,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-navy-950 text-navy-50 font-body antialiased">
        {/* Web fonts (progressive enhancement - falls back to system fonts) */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap"
          rel="stylesheet"
        />

        <TopNav />

        {/* Content offset: fixed top bar on md+, bottom nav on mobile */}
        <main className="flex flex-col min-h-screen pt-0 md:pt-16 pb-24 md:pb-12">
          {children}
        </main>

        <BottomNav />
      </body>
    </html>
  );
}
