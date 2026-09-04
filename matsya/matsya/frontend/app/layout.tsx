import type { Metadata } from 'next'
import '../src/index.css'

export const metadata: Metadata = {
  title: 'MATSYA — Urban Flood Digital Twin | Greater Chennai Corporation',
  description: 'Defense-grade real-time urban flood simulation, hydrologic network routing, and infrastructure impact intelligence.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-[#070A0F] text-slate-100 antialiased selection:bg-cyan-500 selection:text-black min-h-screen">
        {children}
      </body>
    </html>
  )
}
