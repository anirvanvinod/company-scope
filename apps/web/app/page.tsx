// Phase 0 placeholder — the real search-first home page is implemented in Phase 7.
// See docs/07-frontend-wireframes.md §1 Home page for the target wireframe.
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          CompanyScope
        </h1>
        <p className="mt-3 text-lg text-gray-500">
          Explainable UK company intelligence — coming soon
        </p>
        <p className="mt-2 text-sm text-gray-400">
          Public-data analysis from Companies House. Not investment advice.
        </p>
      </div>
    </main>
  );
}
