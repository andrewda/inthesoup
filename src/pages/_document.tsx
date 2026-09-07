import { Html, Head, Main, NextScript } from 'next/document'

export default function Document() {
  return (
    <Html lang="en" className="h-full">
      <Head>
        {/* Run before the body is painted, without waiting for React hydration. */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function () {
            var mode = 'system';
            try {
              var saved = localStorage.getItem('darkMode');
              if (saved === 'light' || saved === 'dark') mode = saved;
            } catch (_) {}
            var dark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
            document.documentElement.classList.toggle('dark', dark);
            document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
          })();
        ` }} />
      </Head>
      <body className="h-full">
        <Main />
        <NextScript />
      </body>
    </Html>
  )
}
