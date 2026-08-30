"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Brand } from "./brand";
import { StudioApiError, studioApi } from "../lib/studio-api";

type StudioAuthFormProps = {
  mode: "signup" | "signin";
};

export function StudioAuthForm({ mode }: StudioAuthFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const isSignup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (isSignup && password !== confirmation) {
      setError("The passwords do not match");
      return;
    }

    setPending(true);
    try {
      await studioApi(`auth/${isSignup ? "signup" : "signin"}`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push("/studio");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof StudioApiError
          ? requestError.message
          : "Kuma Studio could not complete that request",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="studio-auth-page">
      <section className="studio-auth-story" aria-label="Kuma Studio introduction">
        <Brand short className="studio-back-link" />
        <div className="studio-auth-copy">
          <p className="studio-mono-label">Kuma Studio / private beta</p>
          <h1>{isSignup ? "A direct line to your agents." : "Your wrist line is waiting."}</h1>
          <p>
            Set the voice, connect your Apple Watch, and keep your provider
            credentials safely off the device.
          </p>
        </div>
        <div className="studio-signal-card" aria-hidden="true">
          <span className="studio-signal-cat">
            <img src="/kumavoice-mark.svg" alt="" />
          </span>
          <span className="studio-signal-copy">
            <strong>Private voice line</strong>
            <small>Studio → Watch</small>
          </span>
          <span className="studio-signal-wave">
            <i />
            <i />
            <i />
            <i />
            <i />
          </span>
        </div>
      </section>

      <section className="studio-auth-panel">
        <div className="studio-form-wrap">
          <p className="studio-step-label">{isSignup ? "Create your line" : "Welcome back"}</p>
          <h2>{isSignup ? "Start with your account" : "Sign in to Studio"}</h2>
          <p className="studio-form-intro">
            {isSignup
              ? "Create your private Studio. Setup takes about two minutes."
              : "Continue setting up your Watch and agent."}
          </p>

          <form className="studio-form" onSubmit={submit} aria-busy={pending}>
            <label>
              <span>Email</span>
              <input
                type="email"
                name="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                placeholder="you@example.com"
                autoFocus
                required
              />
            </label>
            <label>
              <span>Password</span>
              <div className="studio-password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={isSignup ? "new-password" : "current-password"}
                  minLength={8}
                  placeholder="At least 8 characters"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>
            {isSignup && (
              <label>
                <span>Confirm password</span>
                <input
                  type={showPassword ? "text" : "password"}
                  name="confirmation"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
            )}

            {isSignup && <p className="studio-field-hint">Use 8 or more characters.</p>}
            {error && <p className="studio-form-error" role="alert" aria-live="polite">{error}</p>}
            <button className="studio-submit" type="submit" disabled={pending}>
              {pending ? "Opening Studio…" : isSignup ? "Create account" : "Sign in"}
              <span aria-hidden="true">↗</span>
            </button>
          </form>

          <div className="studio-auth-trust" aria-label="Kuma Studio benefits">
            <span><i /> No iPhone required</span>
            <span><i /> Keys stay server-side</span>
          </div>

          <p className="studio-auth-switch">
            {isSignup ? "Already have an account?" : "New to Kuma?"}{" "}
            <Link href={isSignup ? "/studio/login" : "/studio/signup"}>
              {isSignup ? "Sign in" : "Create one"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
