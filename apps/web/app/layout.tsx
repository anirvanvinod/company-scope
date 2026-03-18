import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import { TopNav } from "@/components/layout/TopNav";
import { Footer } from "@/components/layout/Footer";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "CompanyScope",
    template: "%s — CompanyScope",
  },
  description:
    "Explainable UK company intelligence built on Companies House public data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="flex min-h-screen flex-col bg-stone-50 font-sans text-stone-900 antialiased">
        <TopNav />
        <div className="flex flex-1 flex-col">{children}</div>
        <Footer />
      </body>
    </html>
  );
}
