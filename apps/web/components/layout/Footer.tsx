export function Footer() {
  return (
    <footer className="border-t border-stone-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-xs leading-relaxed text-stone-400">
          CompanyScope uses public data from{" "}
          <a
            href="https://find-and-update.company-information.service.gov.uk"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-stone-600"
          >
            Companies House
          </a>
          .{" "}
          <span className="font-medium text-stone-500">
            This is not investment advice, legal advice, or a regulated credit
            score.
          </span>{" "}
          Data may be incomplete or out of date. Always verify with primary
          sources before making any decision.
        </p>
      </div>
    </footer>
  );
}
