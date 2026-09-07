import { ArrowLeft, Search } from "lucide-react";
import { ButtonLink } from "@/components/ui";

export default function NotFound() {
  return (
    <section className="mx-auto max-w-xl py-16 sm:py-24">
      <p className="eyebrow text-signal">Page not found · 404</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight">
        This path ends here.
      </h1>
      <p className="mt-4 text-base leading-7 text-muted">
        The page may have moved, or the address may be incomplete. Return to
        your workspace or search the evidence to pick up your research.
      </p>
      <div className="mt-7 flex flex-wrap gap-3">
        <ButtonLink href="/">
          <ArrowLeft className="mr-2 h-4 w-4" aria-hidden />
          Back to workspace
        </ButtonLink>
        <ButtonLink href="/search">
          <Search className="mr-2 h-4 w-4" aria-hidden />
          Search evidence
        </ButtonLink>
      </div>
    </section>
  );
}
