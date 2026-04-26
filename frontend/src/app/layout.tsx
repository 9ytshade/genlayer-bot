import type { Metadata } from "next";
import { WalletProvider } from "@/context/WalletContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "GenLayer AI — Talk to the Blockchain",
  description:
    "An AI-powered chatbot that lets you execute on-chain transactions, check balances, and deploy Intelligent Contracts using plain English.",
  keywords: ["GenLayer", "AI", "blockchain", "chatbot", "Intelligent Contracts"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased" suppressHydrationWarning>
        <WalletProvider>
          {children}
        </WalletProvider>
      </body>
    </html>
  );
}
