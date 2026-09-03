"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Brand } from "./brand";
import {
  StudioApiError,
  StudioBootstrap,
  StudioDevice,
  studioApi,
} from "../lib/studio-api";
import { StudioMcpSettings } from "./studio-mcp-settings";

function formatDate(value: string | null | undefined) {
  const date = new Date(value ?? "");
  if (Number.isNaN(date.getTime())) return "Current beta";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function deviceActivity(device: StudioDevice) {
  if (!device.last_seen_at) return "Waiting for its first conversation";
  return `Last active ${new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(device.last_seen_at))}`;
}

export function StudioSettings() {
  const router = useRouter();
  const [data, setData] = useState<StudioBootstrap | null>(null);
  const [loadError, setLoadError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [passwordPending, setPasswordPending] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [confirmingDevice, setConfirmingDevice] = useState<string | null>(null);
  const [devicePending, setDevicePending] = useState<string | null>(null);
  const [deviceError, setDeviceError] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    studioApi<StudioBootstrap>("bootstrap")
      .then(setData)
      .catch((requestError) => {
        if (requestError instanceof StudioApiError && requestError.status === 401) {
          router.replace("/studio/login");
          return;
        }
        setLoadError(requestError instanceof Error ? requestError.message : "Settings could not load");
      });
  }, [router]);

  async function signOut() {
    await studioApi("auth/signout", { method: "POST" }).catch(() => null);
    router.replace("/studio/login");
    router.refresh();
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordMessage("");
    setPasswordError("");
    if (newPassword !== confirmation) {
      setPasswordError("The new passwords do not match");
      return;
    }

    setPasswordPending(true);
    try {
      await studioApi("account/password", {
        method: "PUT",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setPasswordMessage("Password updated. Other Studio sessions were signed out.");
    } catch (requestError) {
      setPasswordError(requestError instanceof Error ? requestError.message : "Password could not be updated");
    } finally {
      setPasswordPending(false);
    }
  }

  async function revokeDevice(device: StudioDevice) {
    setDeviceError("");
    setDevicePending(device.id);
    try {
      const next = await studioApi<StudioBootstrap>(`devices/${device.id}`, {
        method: "DELETE",
      });
      setData(next);
      setConfirmingDevice(null);
    } catch (requestError) {
      setDeviceError(requestError instanceof Error ? requestError.message : "That Watch could not be removed");
    } finally {
      setDevicePending(null);
    }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDeleteError("");
    if (deleteConfirmation !== "DELETE") {
      setDeleteError("Type DELETE to confirm");
      return;
    }

    setDeletePending(true);
    try {
      await studioApi("account", {
        method: "DELETE",
        body: JSON.stringify({ current_password: deletePassword }),
      });
      router.replace("/studio/signup");
      router.refresh();
    } catch (requestError) {
      setDeleteError(requestError instanceof Error ? requestError.message : "Your account could not be deleted");
      setDeletePending(false);
    }
  }

  if (!data) {
    return (
      <main className="studio-loading">
        <Image src="/kumavoice-mark.svg" alt="Kuma" width={72} height={42} priority />
        <p>{loadError || "Opening settings…"}</p>
      </main>
    );
  }

  return (
    <main className="studio-page studio-settings-page">
      <header className="studio-header">
        <Brand short />
        <div className="studio-header-status">
          <span className="studio-live-dot" />
          Account controls
        </div>
        <div className="studio-account">
          <span className="studio-account-email">{data.user.email}</span>
          <Link href="/studio">Studio</Link>
          <button type="button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      <div className="studio-settings-shell">
        <section className="studio-settings-hero">
          <div>
            <p className="studio-mono-label studio-mono-label-dark">Kuma controls</p>
            <h1>Your agent.<br />Your access.</h1>
            <p>Manage who can reach Kuma without putting credentials or account controls on the Watch.</p>
          </div>
          <div className="studio-settings-signal" aria-hidden="true">
            <span className="studio-settings-orbit" />
            <span className="studio-settings-watch">
              <Image src="/kumavoice-mark.svg" alt="" width={76} height={44} />
              <i />
            </span>
            <span className="studio-settings-signal-copy">
              <small>Private line</small>
              <strong>{data.devices.length || "No"} active {data.devices.length === 1 ? "Watch" : "Watches"}</strong>
            </span>
          </div>
        </section>

        <section className="studio-settings-workspace">
          <header className="studio-settings-heading">
            <div>
              <p className="studio-step-label">Settings</p>
              <h2>Keep Kuma under your control.</h2>
              <p>Review active devices, connect MCP servers, update your password, or remove your account and its data.</p>
            </div>
            <Link className="studio-back-button" href="/studio"><span aria-hidden="true">←</span> Back to Studio</Link>
          </header>

          <div className="studio-settings-grid">
            <section className="studio-settings-card studio-settings-devices" aria-labelledby="devices-heading">
              <div className="studio-settings-card-heading">
                <div>
                  <span className="studio-settings-icon" aria-hidden="true">⌁</span>
                  <div>
                    <p>Paired devices</p>
                    <h3 id="devices-heading">Watches with access</h3>
                  </div>
                </div>
                <span className="studio-settings-count">{data.devices.length}</span>
              </div>

              {deviceError && <p className="studio-form-error" role="alert">{deviceError}</p>}
              {data.devices.length ? (
                <div className="studio-device-list">
                  {data.devices.map((device) => (
                    <article className="studio-settings-device" key={device.id}>
                      <div className="studio-settings-device-face" aria-hidden="true">
                        <Image src="/kumavoice-mark.svg" alt="" width={58} height={34} />
                        <span />
                      </div>
                      <div className="studio-settings-device-copy">
                        <span className="studio-device-status"><i /> Active</span>
                        <h4>{device.name}</h4>
                        <p>{deviceActivity(device)}</p>
                        <small>Paired {formatDate(device.created_at)}</small>
                      </div>
                      <div className="studio-settings-device-actions">
                        {confirmingDevice === device.id ? (
                          <div className="studio-inline-confirm">
                            <p>This Watch will need a new pairing code.</p>
                            <div>
                              <button type="button" onClick={() => setConfirmingDevice(null)} disabled={devicePending === device.id}>Cancel</button>
                              <button className="is-danger" type="button" onClick={() => revokeDevice(device)} disabled={devicePending === device.id}>
                                {devicePending === device.id ? "Removing…" : "Remove access"}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button type="button" onClick={() => setConfirmingDevice(device.id)}>Remove</button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="studio-settings-empty">
                  <span aria-hidden="true">○</span>
                  <div>
                    <strong>No Watch is paired</strong>
                    <p>Open Kuma on Apple Watch for a new code, then return to Studio to connect it.</p>
                  </div>
                  <Link href="/studio">Pair a Watch <span aria-hidden="true">→</span></Link>
                </div>
              )}
            </section>

            <StudioMcpSettings />

            <section className="studio-settings-card studio-settings-account" aria-labelledby="account-heading">
              <div className="studio-settings-card-heading">
                <div>
                  <span className="studio-settings-icon" aria-hidden="true">@</span>
                  <div>
                    <p>Account</p>
                    <h3 id="account-heading">Studio identity</h3>
                  </div>
                </div>
              </div>
              <dl className="studio-account-details">
                <div>
                  <dt>Email</dt>
                  <dd>{data.user.email}</dd>
                </div>
                <div>
                  <dt>Member since</dt>
                  <dd>{formatDate(data.user.created_at)}</dd>
                </div>
              </dl>
              <p className="studio-settings-note">Email changes will arrive with verified email delivery.</p>
            </section>

            <section className="studio-settings-card studio-settings-password" aria-labelledby="password-heading">
              <div className="studio-settings-card-heading">
                <div>
                  <span className="studio-settings-icon" aria-hidden="true">◇</span>
                  <div>
                    <p>Security</p>
                    <h3 id="password-heading">Change password</h3>
                  </div>
                </div>
              </div>
              <p className="studio-settings-note">Email recovery is not enabled yet, so you’ll need your current password.</p>
              <form className="studio-settings-form" onSubmit={changePassword} aria-busy={passwordPending}>
                <label className="studio-field">
                  <span>Current password</span>
                  <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" minLength={8} required />
                </label>
                <div className="studio-settings-password-row">
                  <label className="studio-field">
                    <span>New password</span>
                    <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={8} required />
                  </label>
                  <label className="studio-field">
                    <span>Confirm new password</span>
                    <input type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" minLength={8} required />
                  </label>
                </div>
                {passwordError && <p className="studio-form-error" role="alert">{passwordError}</p>}
                {passwordMessage && <p className="studio-form-success" role="status">{passwordMessage}</p>}
                <button className="studio-submit" disabled={passwordPending}>
                  {passwordPending ? "Updating…" : "Update password"} <span aria-hidden="true">→</span>
                </button>
              </form>
            </section>

            <section className={`studio-settings-card studio-settings-danger ${deleteOpen ? "is-open" : ""}`} aria-labelledby="delete-heading">
              <div className="studio-settings-danger-copy">
                <p className="studio-step-label">Danger zone</p>
                <h3 id="delete-heading">Delete your Kuma account</h3>
                <p>This permanently removes your profile, provider credentials, MCP connections, sessions, pairing records, and Watch access.</p>
              </div>
              {!deleteOpen ? (
                <button className="studio-danger-button" type="button" onClick={() => setDeleteOpen(true)}>Delete account</button>
              ) : (
                <form className="studio-delete-form" onSubmit={deleteAccount} aria-busy={deletePending}>
                  <label className="studio-field">
                    <span>Current password</span>
                    <input type="password" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} autoComplete="current-password" minLength={8} required />
                  </label>
                  <label className="studio-field">
                    <span>Type DELETE to confirm</span>
                    <input value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} autoComplete="off" pattern="DELETE" required />
                  </label>
                  {deleteError && <p className="studio-form-error" role="alert">{deleteError}</p>}
                  <div>
                    <button type="button" onClick={() => { setDeleteOpen(false); setDeleteError(""); }} disabled={deletePending}>Cancel</button>
                    <button className="studio-danger-button" disabled={deletePending || deleteConfirmation !== "DELETE"}>
                      {deletePending ? "Deleting…" : "Delete permanently"}
                    </button>
                  </div>
                </form>
              )}
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
