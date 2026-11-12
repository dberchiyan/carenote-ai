import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex max-w-xl flex-1 flex-col items-start gap-4 px-6 py-24">
      <p className="text-brand-text text-sm font-semibold">404</p>
      <h1 className="text-4xl font-semibold tracking-[-0.03em]">Page not found</h1>
      <p className="text-ink-2">The page you are looking for does not exist.</p>
      <Link href="/" className="text-brand-text font-medium underline">
        Back to CareNote AI
      </Link>
    </main>
  );
}
