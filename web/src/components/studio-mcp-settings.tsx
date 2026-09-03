"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  MCPConnection,
  StudioApiError,
  studioApi,
} from "../lib/studio-api";

type AuthType = MCPConnection["auth_type"];

function statusLabel(connection: MCPConnection) {
  switch (connection.status) {
    case "connected":
      return "Connected";
    case "authorization_required":
      return "Needs authorization";
    case "pending":
      return "Ready to discover";
    case "error":
      return connection.last_error || "Connection failed";
    default:
      return connection.status;
  }
}

function hostLabel(url: string) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function authLabel(authType: AuthType) {
  if (authType === "bearer") return "Bearer";
  if (authType === "oauth") return "OAuth";
  return "No auth";
}

function toolLabel(tool: MCPConnection["tools"][number]) {
  return tool.title || tool.remote_name;
}

export function StudioMcpSettings() {
  const [connections, setConnections] = useState<MCPConnection[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [serverUrl, setServerUrl] = useState("");
  const [authType, setAuthType] = useState<AuthType>("none");
  const [bearerToken, setBearerToken] = useState("");
  const [oauthClientId, setOauthClientId] = useState("");
  const [oauthClientSecret, setOauthClientSecret] = useState("");

  async function refresh() {
    const payload = await studioApi<{ connections: MCPConnection[] }>("mcp/connections");
    setConnections(payload.connections);
    return payload.connections;
  }

  useEffect(() => {
    const connected = new URLSearchParams(window.location.search).get("mcp") === "connected";
    refresh()
      .then(async (next) => {
        if (connected) {
          setMessage("Authorized. Enable the tools Kuma may use from the Watch.");
        }
        const waiting = next.filter((connection) => connection.status === "pending");
        if (!waiting.length) return;
        setPending("discover");
        try {
          for (const connection of waiting) {
            await studioApi(`mcp/connections/${connection.id}/discover`, {
              method: "POST",
            });
          }
          await refresh();
        } catch (requestError) {
          setError(requestError instanceof Error ? requestError.message : "Catalog refresh failed");
        } finally {
          setPending(null);
        }
      })
      .catch((requestError) => {
        if (requestError instanceof StudioApiError && requestError.status === 401) {
          return;
        }
        setLoadError(requestError instanceof Error ? requestError.message : "MCP settings could not load");
      });
  }, []);

  async function addConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setPending("create");
    try {
      const created = await studioApi<MCPConnection>("mcp/connections", {
        method: "POST",
        body: JSON.stringify({
          name,
          server_url: serverUrl,
          auth_type: authType,
          bearer_token: authType === "bearer" ? bearerToken : undefined,
          oauth_client_id: authType === "oauth" && oauthClientId ? oauthClientId : undefined,
          oauth_client_secret: authType === "oauth" && oauthClientSecret ? oauthClientSecret : undefined,
          oauth_token_endpoint_auth_method:
            authType === "oauth" && oauthClientSecret ? "client_secret_post" : "none",
        }),
      });
      setName("");
      setServerUrl("");
      setBearerToken("");
      setOauthClientId("");
      setOauthClientSecret("");
      if (created.auth_type === "oauth") {
        const started = await studioApi<{ authorization_url: string }>(
          `mcp/connections/${created.id}/oauth/start`,
          { method: "POST" },
        );
        window.location.assign(started.authorization_url);
        return;
      }
      await studioApi(`mcp/connections/${created.id}/discover`, { method: "POST" });
      await refresh();
      setMessage("Server added. Enable each tool before Kuma can use it.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That MCP server could not be added");
    } finally {
      setPending(null);
    }
  }

  async function authorize(connection: MCPConnection) {
    setError("");
    setPending(connection.id);
    try {
      const started = await studioApi<{ authorization_url: string }>(
        `mcp/connections/${connection.id}/oauth/start`,
        { method: "POST" },
      );
      window.location.assign(started.authorization_url);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Authorization could not start");
      setPending(null);
    }
  }

  async function discover(connection: MCPConnection) {
    setError("");
    setPending(connection.id);
    try {
      const next = await studioApi<MCPConnection>(
        `mcp/connections/${connection.id}/discover`,
        { method: "POST" },
      );
      setConnections((current) =>
        (current ?? []).map((item) => (item.id === next.id ? next : item)),
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Catalog refresh failed");
    } finally {
      setPending(null);
    }
  }

  async function removeConnection(connection: MCPConnection) {
    setError("");
    setPending(connection.id);
    try {
      await studioApi(`mcp/connections/${connection.id}`, { method: "DELETE" });
      setConnections((current) => (current ?? []).filter((item) => item.id !== connection.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That server could not be removed");
    } finally {
      setPending(null);
    }
  }

  async function toggleTool(connection: MCPConnection, toolId: string, enabled: boolean) {
    setError("");
    try {
      const tool = await studioApi<MCPConnection["tools"][number]>(
        `mcp/connections/${connection.id}/tools/${toolId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ enabled, risk: "read" }),
        },
      );
      setConnections((current) =>
        (current ?? []).map((item) =>
          item.id === connection.id
            ? { ...item, tools: item.tools.map((entry) => (entry.id === tool.id ? tool : entry)) }
            : item,
        ),
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That tool could not be updated");
    }
  }

  const enabledCount = (connections ?? []).reduce(
    (count, connection) => count + connection.tools.filter((tool) => tool.enabled).length,
    0,
  );

  return (
    <section className="studio-settings-card studio-settings-mcp" aria-labelledby="mcp-heading">
      <div className="studio-settings-card-heading">
        <div>
          <span className="studio-settings-icon" aria-hidden="true">⌘</span>
          <div>
            <p>Connectors</p>
            <h3 id="mcp-heading">MCP servers</h3>
          </div>
        </div>
        <span className="studio-settings-count">{enabledCount}</span>
      </div>
      <p className="studio-settings-note">Enable the tools Kuma may use from the Watch.</p>

      {loadError && <p className="studio-form-error" role="alert">{loadError}</p>}
      {error && <p className="studio-form-error" role="alert">{error}</p>}
      {message && <p className="studio-form-success" role="status">{message}</p>}

      {connections?.length ? (
        <div className="studio-mcp-list">
          {connections.map((connection) => {
            const enabledTools = connection.tools.filter((tool) => tool.enabled).length;
            return (
            <article className="studio-mcp-connection" key={connection.id}>
              <div className="studio-mcp-connection-copy">
                <span className="studio-device-status"><i /> {statusLabel(connection)}</span>
                <h4>{connection.name}</h4>
                <p>
                  {hostLabel(connection.server_url)}
                  <span aria-hidden="true"> · </span>
                  {authLabel(connection.auth_type)}
                  {connection.tools.length ? (
                    <>
                      <span aria-hidden="true"> · </span>
                      {enabledTools} of {connection.tools.length} on
                    </>
                  ) : null}
                </p>
              </div>
              <div className="studio-mcp-connection-actions">
                {connection.auth_type === "oauth" && connection.status === "authorization_required" ? (
                  <button type="button" onClick={() => authorize(connection)} disabled={pending === connection.id}>
                    {pending === connection.id ? "Opening…" : "Authorize"}
                  </button>
                ) : (
                  <button type="button" onClick={() => discover(connection)} disabled={pending === connection.id}>
                    {pending === connection.id ? "Refreshing…" : "Refresh"}
                  </button>
                )}
                <button type="button" onClick={() => removeConnection(connection)} disabled={pending === connection.id}>
                  Remove
                </button>
              </div>
              {connection.tools.length ? (
                <ul className="studio-mcp-tools">
                  {connection.tools.map((tool) => (
                    <li key={tool.id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={tool.enabled}
                          onChange={(event) => toggleTool(connection, tool.id, event.target.checked)}
                        />
                        <span>{toolLabel(tool)}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="studio-settings-note">No tools discovered yet.</p>
              )}
            </article>
            );
          })}
        </div>
      ) : connections ? (
        <div className="studio-settings-empty">
          <span aria-hidden="true">○</span>
          <div>
            <strong>No MCP server yet</strong>
            <p>Add a remote Streamable HTTP URL. Local stdio servers are not supported.</p>
          </div>
        </div>
      ) : (
        <p className="studio-settings-note">{pending ? "Refreshing tools…" : "Loading connectors…"}</p>
      )}

      <form className="studio-settings-form studio-mcp-form" onSubmit={addConnection} aria-busy={pending === "create"}>
        <label className="studio-field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={80} required />
        </label>
        <label className="studio-field">
          <span>Server URL</span>
          <input
            value={serverUrl}
            onChange={(event) => setServerUrl(event.target.value)}
            placeholder="https://example.com/mcp"
            minLength={8}
            required
          />
        </label>
        <label className="studio-field">
          <span>Authentication</span>
          <select value={authType} onChange={(event) => setAuthType(event.target.value as AuthType)}>
            <option value="none">None</option>
            <option value="bearer">Bearer token</option>
            <option value="oauth">OAuth 2.1</option>
          </select>
        </label>
        {authType === "bearer" && (
          <label className="studio-field">
            <span>Bearer token</span>
            <input
              type="password"
              value={bearerToken}
              onChange={(event) => setBearerToken(event.target.value)}
              autoComplete="off"
              required
            />
          </label>
        )}
        {authType === "oauth" && (
          <details className="studio-mcp-advanced">
            <summary>Pre-registered client (optional)</summary>
            <p className="studio-settings-note">
              Leave this blank. Kuma will open the provider’s sign-in page and come back here.
              Use these fields only if that server requires a client you already created.
            </p>
            <div className="studio-settings-password-row">
              <label className="studio-field">
                <span>Client ID</span>
                <input value={oauthClientId} onChange={(event) => setOauthClientId(event.target.value)} autoComplete="off" />
              </label>
              <label className="studio-field">
                <span>Client secret</span>
                <input
                  type="password"
                  value={oauthClientSecret}
                  onChange={(event) => setOauthClientSecret(event.target.value)}
                  autoComplete="off"
                />
              </label>
            </div>
          </details>
        )}
        <button className="studio-submit" disabled={pending === "create"}>
          {pending === "create" ? "Adding…" : authType === "oauth" ? "Add and authorize" : "Add server"} <span aria-hidden="true">→</span>
        </button>
      </form>
    </section>
  );
}
