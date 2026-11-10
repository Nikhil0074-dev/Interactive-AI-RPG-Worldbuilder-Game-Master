import "./globals.css";
import type { Metadata } from "next";
import { MotionInit } from "@/components/MotionInit";

export const metadata: Metadata = {
  title: "Interactive AI RPG Worldbuilder & Game Master",
  description: "An AI-narrated fantasy RPG where the world remembers what you do.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><MotionInit />{children}</body>
    </html>
  );
}
