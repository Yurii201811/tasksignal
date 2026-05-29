import { AppShell } from "@/components/app-shell";
import { Badge, Card } from "@/components/ui";

const settings = [
  ["LLM provider", "none", "No paid LLM required. Default deterministic generation. Ollama/OpenAI are optional."],
  ["Embedding model", "all-MiniLM-L6-v2", "Falls back to deterministic local vectors when unavailable."],
  ["Fixture mode", "enabled", "Dashboard demo runs without credentials."],
  ["Privacy defaults", "author_hash", "Raw usernames are not stored by default."]
];

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Settings</h1>
          <p className="mt-2 text-slate-600">Runtime posture for local-first, privacy-conscious operation.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {settings.map(([label, value, description]) => (
            <Card key={label}>
              <div className="flex items-center justify-between gap-4">
                <h2 className="font-semibold text-ink">{label}</h2>
                <Badge tone={value === "enabled" ? "green" : "slate"}>{value}</Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
