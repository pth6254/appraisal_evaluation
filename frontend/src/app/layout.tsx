import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "부동산 AI 감정평가",
  description: "LangGraph 기반 부동산 가치 분석 · 추천 · 시뮬레이션",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="h-full">
      <body className="h-full">
        <Navbar />
        <main className="ml-[220px] min-h-screen p-6">{children}</main>
      </body>
    </html>
  );
}
