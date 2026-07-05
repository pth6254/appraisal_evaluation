import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "부동산 AI 시세추정",
  description: "LangGraph 기반 부동산 시세추정 · 추천 · 시뮬레이션",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="h-full">
      <body className="h-full">
        <AuthProvider>
          <Navbar />
          <main className="ml-[220px] min-h-screen p-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
