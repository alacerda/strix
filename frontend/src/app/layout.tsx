import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Strix - Web GUI',
  description: 'Open-source AI Hackers for your apps',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

