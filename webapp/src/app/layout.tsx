import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "JYRY AI Dashboard",
  description: "JYRY AI Bewerbungs-Assistent — Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
