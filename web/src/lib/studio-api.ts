export type StudioUser = {
  id: string;
  email: string;
  created_at: string;
};

export type StudioProfile = {
  full_name: string;
  role: string;
  primary_goal: string | null;
  use_cases: string[];
  technical_comfort: "everyday" | "tinkerer" | "developer";
  discovery_source: string;
  response_style: "brief" | "balanced" | "detailed";
};

export type StudioDevice = {
  id: string;
  name: string;
  created_at: string;
  last_seen_at: string | null;
};

export type StudioBootstrap = {
  user: StudioUser;
  profile: StudioProfile | null;
  profile_complete: boolean;
  devices: StudioDevice[];
  openai: {
    configured: boolean;
    last_four: string | null;
  };
  next_step: "profile" | "watch" | "provider" | "complete";
};

export type MCPTool = {
  id: string;
  remote_name: string;
  name: string;
  title: string | null;
  description: string | null;
  enabled: boolean;
  risk: "read" | "write";
};

export type MCPConnection = {
  id: string;
  name: string;
  server_url: string;
  auth_type: "none" | "bearer" | "oauth";
  enabled: boolean;
  status: string;
  last_error: string | null;
  catalog_expires_at: string | null;
  tools: MCPTool[];
};

export class StudioApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function studioApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(`/api/studio/${path.replace(/^\//, "")}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : "Kuma Studio could not complete that request";
    throw new StudioApiError(response.status, message);
  }
  return payload as T;
}
