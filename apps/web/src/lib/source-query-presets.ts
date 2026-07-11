export type SourceQueryPreset = {
  value: string;
  label: string;
  defaultQuery: string;
  credential: string;
  examples: string[];
  guidance: string;
  privacy: string;
};

export const sourceQueryPresets: SourceQueryPreset[] = [
  {
    value: "hackernews",
    label: "Hacker News",
    defaultQuery: "ask",
    credential: "No credentials required.",
    examples: ["ask", "show", "job", "manual workflow"],
    guidance:
      "Use ask, new, top, best, show, or job; other text filters Ask HN client-side.",
    privacy: "Stores source URLs and normalized public story fields.",
  },
  {
    value: "fixture",
    label: "Fixture files",
    defaultQuery: "",
    credential: "No credentials required.",
    examples: ["", "fixture demo"],
    guidance: "Use for deterministic local regression checks.",
    privacy: "Uses sanitized repository fixture records only.",
  },
  {
    value: "discourse",
    label: "Discourse forum",
    defaultQuery: "manual workflow",
    credential:
      "Operator-gated; an exact public HTTPS forum must be authorized first.",
    examples: ["manual workflow", "pain point", "workaround"],
    guidance:
      "Create and authorize one public forum in Sources, then bind that exact source to this project.",
    privacy:
      "Stores public topic fields and source URLs; cookies, credentials, private categories, and raw author identities are excluded.",
  },
  {
    value: "github",
    label: "GitHub Issues",
    defaultQuery: 'is:issue is:open "manual workflow"',
    credential: "Operator-gated in browser runs; GITHUB_TOKEN is optional for quota.",
    examples: [
      'is:issue is:open "manual workflow"',
      '"github actions" "error"',
      'label:bug "export csv"',
    ],
    guidance:
      "Use issue-search terms that describe repeated work, failures, or workaround pain.",
    privacy: "Use public-only tokens and do not store private issue data in demos.",
  },
  {
    value: "reddit",
    label: "Reddit",
    defaultQuery: "manual workflow automation",
    credential: "Operator-gated; Reddit OAuth credentials are required.",
    examples: [
      "manual workflow automation",
      "spreadsheet report",
      "onboarding analytics",
    ],
    guidance:
      "Use narrow, pain-oriented phrases and keep limits modest for source terms.",
    privacy: "Stores normalized public post fields and omits raw author identity.",
  },
  {
    value: "stackexchange",
    label: "Stack Exchange",
    defaultQuery: "automation manual workflow",
    credential: "Operator-gated in browser runs; STACK_EXCHANGE_KEY is optional.",
    examples: [
      "automation manual workflow",
      "github actions log analyzer",
      "export csv report",
    ],
    guidance:
      "Use practical problem phrases that match public Q&A wording.",
    privacy: "Stores normalized public question fields and source URLs.",
  },
];

export const sourceQueryPresetByType = Object.fromEntries(
  sourceQueryPresets.map((preset) => [preset.value, preset]),
) as Record<string, SourceQueryPreset>;

export const browserSafeScanSourceOrder = ["hackernews"];

export function queryExamplesLabel(sourceType: string) {
  const examples = sourceQueryPresetByType[sourceType]?.examples ?? [];
  return examples.filter(Boolean).join(", ");
}
