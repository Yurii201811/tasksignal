import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchProjects } from "../src/features/research-projects";
import { api } from "../src/lib/api";
import type {
  LocalWorkspace,
  ResearchProject,
  Scan,
  Source,
} from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: {
    localWorkspace: vi.fn(),
    researchProjects: vi.fn(),
    sources: vi.fn(),
    scans: vi.fn(),
    createResearchProject: vi.fn(),
    runResearchProject: vi.fn(),
    runDueResearchProjects: vi.fn(),
  },
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

const unconfiguredWorkspace: LocalWorkspace = {
  id: 1,
  owner_name: "",
  workspace_goal: "",
  default_source_type: "hackernews",
  default_query: "ask",
  default_limit: 30,
  default_cadence: "manual",
  default_schedule_interval_hours: null,
  configured: false,
  created_at: "2026-09-01T09:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

function project(
  overrides: Partial<ResearchProject> & Pick<ResearchProject, "id" | "name">,
): ResearchProject {
  return {
    description: null,
    source_type: "hackernews",
    query: "ask",
    limit: 30,
    cadence: "manual",
    schedule_interval_hours: null,
    labels: [],
    enabled: true,
    last_scan_id: null,
    last_scan_status: null,
    last_run_at: null,
    next_run_at: null,
    run_count: 0,
    created_at: "2026-09-01T09:00:00Z",
    updated_at: "2026-09-01T09:00:00Z",
    ...overrides,
  };
}

const ciProject = project({
  id: "project-ci",
  name: "Track CI/CD pain",
  description: "Repeated pipeline complaints.",
  labels: ["ci", "developer-tools"],
  last_scan_id: "scan-ci",
  last_scan_status: "completed",
  last_run_at: "2026-09-10T10:00:00Z",
  run_count: 3,
});

const redditProject = project({
  id: "project-reddit",
  name: "Reddit onboarding gaps",
  source_type: "reddit",
  query: "onboarding analytics",
  last_scan_id: "scan-reddit",
  last_scan_status: "failed",
  last_run_at: "2026-09-11T10:00:00Z",
  run_count: 1,
});

const forumProject = project({
  id: "project-forum",
  name: "Forum workaround hunt",
  source_type: "discourse",
  query: "manual workflow",
});

const forumSource: Source = {
  id: "source-forum",
  name: "Example forum",
  type: "discourse",
  config_json: {},
  enabled: true,
  created_at: "2026-09-01T09:00:00Z",
};

const completedScan: Scan = {
  id: "scan-new",
  source_id: null,
  source_type: "reddit",
  source_name: "Reddit",
  status: "completed",
  query: "onboarding analytics",
  started_at: "2026-09-12T10:00:00Z",
  finished_at: "2026-09-12T10:00:30Z",
  error_message: null,
  items_found: 12,
  items_saved: 9,
  signals_detected: 4,
  clusters_created: 2,
  opportunities_created: 1,
  outcome_message: null,
};

function renderFeature() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <ResearchProjects />
      </QueryClientProvider>,
    ),
  };
}

function createDisclosure() {
  return screen
    .getByRole("heading", { name: "New project", level: 2 })
    .closest("details")!;
}

describe("ResearchProjects", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(api.localWorkspace).mockResolvedValue(unconfiguredWorkspace);
    vi.mocked(api.sources).mockResolvedValue([]);
    vi.mocked(api.scans).mockResolvedValue([]);
    vi.mocked(api.researchProjects).mockResolvedValue([]);
  });

  it("lists saved projects ahead of a collapsed New project disclosure that the header action opens and focuses", async () => {
    vi.mocked(api.researchProjects).mockResolvedValue([
      ciProject,
      redditProject,
    ]);

    renderFeature();

    expect(
      await screen.findByRole("heading", {
        name: "Track CI/CD pain",
        level: 3,
      }),
    ).toBeInTheDocument();
    const savedHeading = screen.getByRole("heading", {
      name: "Saved projects",
      level: 2,
    });
    const createHeading = screen.getByRole("heading", {
      name: "New project",
      level: 2,
    });
    expect(
      savedHeading.compareDocumentPosition(createHeading) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByText("2 saved")).toBeInTheDocument();

    const disclosure = createDisclosure();
    expect(disclosure).not.toHaveAttribute("open");
    expect(
      screen.queryByText("No saved research projects yet"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "New project" }));

    await waitFor(() => expect(disclosure).toHaveAttribute("open"));
    expect(screen.getByLabelText("Project name")).toHaveFocus();
  });

  it("keeps the empty state hidden while loading and expands creation only for a truly empty list", async () => {
    const request = deferred<ResearchProject[]>();
    vi.mocked(api.researchProjects).mockReturnValue(request.promise);

    renderFeature();

    expect(screen.getByText("Loading projects")).toBeInTheDocument();
    expect(
      screen.queryByText("No saved research projects yet"),
    ).not.toBeInTheDocument();
    expect(createDisclosure()).not.toHaveAttribute("open");
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();

    request.resolve([]);

    expect(
      await screen.findByText("No saved research projects yet"),
    ).toBeInTheDocument();
    await waitFor(() => expect(createDisclosure()).toHaveAttribute("open"));
    expect(screen.queryByText("Loading projects")).not.toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No projects match these filters"),
    ).not.toBeInTheDocument();
  });

  it("filters saved projects by search and run status with a distinct no-match state", async () => {
    vi.mocked(api.researchProjects).mockResolvedValue([
      ciProject,
      redditProject,
      forumProject,
    ]);

    renderFeature();

    expect(
      await screen.findByRole("heading", {
        name: "Forum workaround hunt",
        level: 3,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(
      screen.getByText("Showing 3 of 3 saved projects"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not run 1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search projects" }),
      {
        target: { value: "onboarding" },
      },
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(
      screen.getByRole("heading", { name: "Reddit onboarding gaps", level: 3 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Showing 1 of 3 saved projects matching “onboarding”/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Completed 1" }));

    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(
      screen.getByText("No projects match these filters"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("No saved research projects yet"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Completed 1" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(createDisclosure()).not.toHaveAttribute("open");

    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(
      screen.getByRole("searchbox", { name: "Search projects" }),
    ).toHaveValue("");
    expect(screen.getByRole("button", { name: "All 3" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      screen.queryByText("No projects match these filters"),
    ).not.toBeInTheDocument();
  });

  it("offers Retry on a failed load without claiming the list is empty", async () => {
    vi.mocked(api.researchProjects)
      .mockRejectedValueOnce(
        new Error(JSON.stringify({ detail: "Project store unavailable" })),
      )
      .mockResolvedValue([ciProject]);

    renderFeature();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load projects");
    expect(alert).toHaveTextContent("Project store unavailable");
    expect(
      screen.queryByText("No saved research projects yet"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Loading projects")).not.toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
    expect(createDisclosure()).not.toHaveAttribute("open");

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", {
        name: "Track CI/CD pain",
        level: 3,
      }),
    ).toBeInTheDocument();
    expect(api.researchProjects).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("1 saved")).toBeInTheDocument();
  });

  it("runs a project with the locally saved operator token and refreshes related caches", async () => {
    vi.mocked(api.researchProjects).mockResolvedValue([redditProject]);
    vi.mocked(api.runResearchProject).mockResolvedValue(completedScan);
    vi.mocked(api.runDueResearchProjects).mockResolvedValue({
      ran: 1,
      skipped: 0,
      scans: [completedScan],
    });
    const { client } = renderFeature();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    expect(
      await screen.findByRole("heading", {
        name: "Reddit onboarding gaps",
        level: 3,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Not set")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Local operator token"), {
      target: { value: "local-secret" },
    });
    expect(window.localStorage.getItem("tasksignal.operatorToken")).toBe(
      "local-secret",
    );
    expect(screen.getByText("Saved locally")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Run Reddit onboarding gaps" }),
    );

    await waitFor(() =>
      expect(api.runResearchProject).toHaveBeenCalledWith(
        "project-reddit",
        "local-secret",
      ),
    );
    expect(await screen.findByText("Project run finished")).toBeInTheDocument();
    expect(screen.getByText(/9 saved from 12 found/)).toBeInTheDocument();
    await waitFor(() => {
      for (const queryKey of [
        ["research-projects"],
        ["scans"],
        ["stats"],
        ["opportunities"],
        ["opportunity-threads"],
        ["readiness"],
        ["evaluation"],
        ["research-project", "project-reddit"],
        ["research-project-runs", "project-reddit"],
        ["research-project-run-delta", "project-reddit"],
      ]) {
        expect(invalidate).toHaveBeenCalledWith({ queryKey });
      }
    });

    fireEvent.click(screen.getByRole("button", { name: "Run due" }));

    await waitFor(() =>
      expect(api.runDueResearchProjects).toHaveBeenCalledWith("local-secret"),
    );
    expect(
      await screen.findByText("Due projects processed"),
    ).toBeInTheDocument();
    await waitFor(() => {
      for (const queryKey of [
        ["research-project"],
        ["research-project-runs"],
        ["research-project-run-delta"],
      ]) {
        expect(invalidate).toHaveBeenCalledWith({ queryKey });
      }
    });
  });

  it("saves a project with the existing payload contract and refreshes the list", async () => {
    vi.mocked(api.createResearchProject).mockResolvedValue(
      project({ id: "project-new", name: "Track CI/CD pain" }),
    );
    const { client } = renderFeature();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    expect(
      await screen.findByText("No saved research projects yet"),
    ).toBeInTheDocument();
    await waitFor(() => expect(createDisclosure()).toHaveAttribute("open"));

    fireEvent.click(screen.getByRole("button", { name: "Save project" }));

    // react-query passes a mutation context as the second argument, so the
    // API contract check pins the payload argument only.
    await waitFor(() =>
      expect(api.createResearchProject).toHaveBeenCalledTimes(1),
    );
    expect(vi.mocked(api.createResearchProject).mock.calls[0][0]).toEqual({
      name: "Track CI/CD pain",
      description:
        "Find repeated complaints that could become a focused developer-tool MVP.",
      source_type: "hackernews",
      source_id: null,
      query: "ask",
      limit: 30,
      cadence: "manual",
      schedule_interval_hours: null,
      labels: ["ci", "developer-tools"],
      enabled: true,
    });
    expect(
      await screen.findByText("Research project saved"),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ["research-projects"],
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["readiness"] });
    });
    expect(createDisclosure()).toHaveAttribute("open");
  });

  it("distinguishes pending and failed forum loads from a truly empty Discourse source list", async () => {
    const sourcesRequest = deferred<Source[]>();
    vi.mocked(api.sources)
      .mockReturnValueOnce(sourcesRequest.promise)
      .mockResolvedValue([forumSource]);

    renderFeature();

    expect(
      await screen.findByText("No saved research projects yet"),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Source" }), {
      target: { value: "discourse" },
    });

    const forumSelect = screen.getByRole("combobox", {
      name: "Configured forum source",
    });
    expect(forumSelect).toHaveAttribute("aria-busy", "true");
    expect(forumSelect).toHaveAccessibleDescription(
      "Loading configured forums from the Sources page.",
    );
    expect(screen.queryByText(/Add a public forum/)).not.toBeInTheDocument();

    sourcesRequest.reject(
      new Error(JSON.stringify({ detail: "Sources unavailable" })),
    );

    expect(
      await screen.findByText(/Could not load configured forums/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Sources unavailable/)).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Configured forums unavailable" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Add a public forum/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Loading configured forums/),
    ).not.toBeInTheDocument();
    expect(forumSelect).not.toHaveAttribute("aria-busy");

    fireEvent.click(
      screen.getByRole("button", { name: "Retry loading configured forums" }),
    );

    expect(
      await screen.findByRole("option", { name: "Example forum" }),
    ).toBeInTheDocument();
    expect(api.sources).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByText(/Could not load configured forums/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Add a public forum/)).not.toBeInTheDocument();
    expect(forumSelect).not.toHaveAttribute("aria-describedby");
  });

  it("asks for a forum only after the source list loads successfully empty", async () => {
    renderFeature();

    expect(
      await screen.findByText("No saved research projects yet"),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Source" }), {
      target: { value: "discourse" },
    });

    expect(
      await screen.findByText(/Add a public forum on the Sources page first/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Sources/ })).toHaveAttribute(
      "href",
      "/sources",
    );
    expect(
      screen.queryByText(/Loading configured forums/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Could not load configured forums/),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Configured forum source" }),
    ).toHaveAccessibleDescription(/Add a public forum/);
  });
});
