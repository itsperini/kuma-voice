"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { Brand } from "./brand";
import {
  StudioApiError,
  StudioBootstrap,
  studioApi,
} from "../lib/studio-api";

const steps = [
  { id: "profile", label: "You", detail: "Shape the replies" },
  { id: "watch", label: "Watch", detail: "Pair the device" },
  { id: "provider", label: "Voice", detail: "Connect OpenAI" },
] as const;

type OnboardingStep = (typeof steps)[number]["id"] | "complete";

const useCaseOptions = [
  {
    value: "personal-assistant",
    title: "Everyday assistant",
    detail: "Questions, errands, and quick help from your wrist.",
  },
  {
    value: "workflows-approvals",
    title: "Workflows & approvals",
    detail: "Review decisions and keep work moving while away.",
  },
  {
    value: "reminders-planning",
    title: "Reminders & planning",
    detail: "Stay on top of plans, lists, and your day.",
  },
  {
    value: "smart-home",
    title: "Home & automations",
    detail: "Trigger routines and control connected tools.",
  },
  {
    value: "hands-free-access",
    title: "Hands-free access",
    detail: "Use an assistant while your hands or phone are busy.",
  },
  {
    value: "fitness-outdoors",
    title: "Fitness & outdoors",
    detail: "Get help while walking, training, or exploring.",
  },
  {
    value: "voice-mcp",
    title: "Voice + MCP",
    detail: "Connect tools and experiment with custom agents.",
  },
  {
    value: "exploring",
    title: "Just exploring",
    detail: "See what an agent on your wrist can become.",
  },
] as const;

const roles = [
  { value: "Personal use", label: "Personal use" },
  { value: "Creator", label: "Creator" },
  { value: "Founder", label: "Founder" },
  { value: "Developer", label: "Developer" },
  { value: "Operator", label: "Product / operations" },
  { value: "Researcher", label: "Researcher" },
  { value: "Student", label: "Student / educator" },
  { value: "Freelancer", label: "Freelancer / consultant" },
  { value: "Other", label: "Other" },
] as const;

const comfortOptions = [
  { value: "everyday", title: "Keep it simple", detail: "I want it to work for me." },
  { value: "tinkerer", title: "Let me customize", detail: "I enjoy connecting tools." },
  { value: "developer", title: "I build with APIs", detail: "Code and MCP feel familiar." },
] as const;

const discoverySources = [
  { value: "", label: "Choose one" },
  { value: "tiktok", label: "TikTok" },
  { value: "instagram", label: "Instagram" },
  { value: "youtube", label: "YouTube" },
  { value: "x", label: "X / Twitter" },
  { value: "reddit", label: "Reddit" },
  { value: "hacker-news", label: "Hacker News" },
  { value: "github", label: "GitHub" },
  { value: "product-hunt", label: "Product Hunt" },
  { value: "friend", label: "A friend or colleague" },
  { value: "search", label: "Search" },
  { value: "other", label: "Somewhere else" },
] as const;

const railCopy = {
  profile: {
    label: "Start with you",
    title: "Make Kuma sound like yours.",
    copy: "A few choices tune the answers before the first conversation.",
  },
  watch: {
    label: "Connect your wrist",
    title: "Pair without an iPhone.",
    copy: "The short code creates a private connection between this Studio and your Watch.",
  },
  provider: {
    label: "Bring a voice",
    title: "Your key stays off the Watch.",
    copy: "Kuma encrypts it server-side and only shows the final four characters here.",
  },
  complete: {
    label: "Setup complete",
    title: "Your wrist line is live.",
    copy: "Open Kuma on Apple Watch and start your first conversation.",
  },
} as const;

export function StudioOnboarding() {
  const router = useRouter();
  const [data, setData] = useState<StudioBootstrap | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("Personal use");
  const [goal, setGoal] = useState("");
  const [useCases, setUseCases] = useState<string[]>([]);
  const [technicalComfort, setTechnicalComfort] = useState<"everyday" | "tinkerer" | "developer">("everyday");
  const [discoverySource, setDiscoverySource] = useState("");
  const [responseStyle, setResponseStyle] = useState<"brief" | "balanced" | "detailed">("brief");
  const [pairingCode, setPairingCode] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [currentStep, setCurrentStep] = useState<OnboardingStep>("profile");
  const previousStep = useRef<string | null>(null);

  useEffect(() => {
    studioApi<StudioBootstrap>("bootstrap")
      .then((bootstrap) => {
        setData(bootstrap);
        setFullName(bootstrap.profile?.full_name ?? "");
        setRole(bootstrap.profile?.role ?? "Personal use");
        setGoal(bootstrap.profile?.primary_goal ?? "");
        setUseCases(bootstrap.profile?.use_cases ?? []);
        setTechnicalComfort(bootstrap.profile?.technical_comfort ?? "everyday");
        setDiscoverySource(bootstrap.profile?.discovery_source ?? "");
        setResponseStyle(bootstrap.profile?.response_style ?? "brief");
        setCurrentStep(bootstrap.next_step);
      })
      .catch((requestError) => {
        if (requestError instanceof StudioApiError && requestError.status === 401) {
          router.replace("/studio/login");
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Studio could not load");
      });
  }, [router]);

  const activeStep = currentStep;
  const activeIndex = activeStep === "complete" ? 3 : steps.findIndex((step) => step.id === activeStep);
  const furthestStepIndex = data?.next_step === "complete"
    ? 3
    : steps.findIndex((step) => step.id === data?.next_step);
  const firstName = data?.profile?.full_name.split(" ")[0];
  const currentRailCopy = railCopy[activeStep];
  const pairingDigits = useMemo(
    () => pairingCode.replace(/\D/g, "").slice(0, 6),
    [pairingCode],
  );

  useEffect(() => {
    if (!data) return;
    if (previousStep.current === null) {
      previousStep.current = activeStep;
      return;
    }
    if (previousStep.current === activeStep) return;
    previousStep.current = activeStep;
    document.querySelector(".studio-workspace")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [activeStep, data]);

  async function mutate(path: string, body: unknown) {
    setError("");
    setPending(true);
    try {
      const next = await studioApi<StudioBootstrap>(path, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setData(next);
      return next;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Studio could not save that");
      return null;
    } finally {
      setPending(false);
    }
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = await mutate("profile", {
      full_name: fullName,
      role,
      primary_goal: goal.trim() || null,
      use_cases: useCases,
      technical_comfort: technicalComfort,
      discovery_source: discoverySource,
      response_style: responseStyle,
    });
    if (next) setCurrentStep(next.next_step);
  }

  async function pairWatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      await studioApi("pairings/approve", {
        method: "POST",
        body: JSON.stringify({ user_code: pairingDigits }),
      });
      const next = await studioApi<StudioBootstrap>("bootstrap");
      setData(next);
      setCurrentStep(next.next_step);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "That code could not be paired");
    } finally {
      setPending(false);
    }
  }

  async function saveProvider(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = await mutate("providers/openai", { api_key: apiKey });
    if (next) {
      setApiKey("");
      setCurrentStep(next.next_step);
    }
  }

  function toggleUseCase(value: string) {
    setUseCases((selected) => {
      if (selected.includes(value)) {
        return selected.filter((item) => item !== value);
      }
      return selected.length < 3 ? [...selected, value] : selected;
    });
  }

  function navigateToStep(step: OnboardingStep, index: number) {
    if (!data || data.next_step === "complete" || index > furthestStepIndex) return;
    setError("");
    setCurrentStep(step);
  }

  async function signOut() {
    await studioApi("auth/signout", { method: "POST" }).catch(() => null);
    router.replace("/studio/login");
    router.refresh();
  }

  if (!data) {
    return (
      <main className="studio-loading">
        <Image src="/kumavoice-mark.svg" alt="Kuma" width={72} height={42} priority />
        <p>{error || "Opening your line…"}</p>
      </main>
    );
  }

  return (
    <main className="studio-page">
      <header className="studio-header">
        <Brand short />
        <div className="studio-header-status">
          <span className="studio-live-dot" />
          {activeStep === "complete" ? "Watch connected" : `Setup · ${activeIndex + 1} of 3`}
        </div>
        <div className="studio-account">
          <span className="studio-account-email">{data?.user.email}</span>
          <Link href="/studio/settings">Settings</Link>
          <button type="button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      <div className="studio-grid">
        <aside className="studio-rail">
          <div>
            <p className="studio-mono-label studio-mono-label-dark">{currentRailCopy.label}</p>
            <h1>{activeStep === "profile" && firstName ? `${firstName}, make Kuma yours.` : currentRailCopy.title}</h1>
            <p>{currentRailCopy.copy}</p>
          </div>

          <ol className="studio-progress">
            {steps.map((step, index) => (
              <li
                key={step.id}
                className={`${index === activeIndex ? "is-active" : ""} ${index < furthestStepIndex || data?.next_step === "complete" ? "is-done" : ""}`}
                aria-current={index === activeIndex ? "step" : undefined}
              >
                <button
                  type="button"
                  onClick={() => navigateToStep(step.id, index)}
                  disabled={data?.next_step === "complete" || index > furthestStepIndex}
                  aria-label={`${step.label}: ${step.detail}${index < furthestStepIndex ? ", completed" : ""}`}
                >
                  <span>{index < furthestStepIndex || data?.next_step === "complete" ? "✓" : index + 1}</span>
                  <span>
                    <strong>{step.label}</strong>
                    <small>{step.detail}</small>
                  </span>
                </button>
              </li>
            ))}
          </ol>

          <div className="studio-rail-foot">
            <span className="studio-live-dot" />
            Private connection
          </div>
        </aside>

        <section className="studio-workspace">
          {error && <p className="studio-banner-error" role="alert">{error}</p>}

          <MotionConfig reducedMotion="user">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={activeStep}
                className="studio-step-stage"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              >

          {activeStep === "profile" && (
            <form className="studio-work-card" onSubmit={saveProfile} aria-busy={pending}>
              <div className="studio-card-heading">
                <span className="studio-card-number">01</span>
                <div>
                  <p className="studio-step-label">Help us shape Kuma</p>
                  <h2>What should Kuma become for you?</h2>
                  <p>Your answers personalize the experience and help us decide what to build next.</p>
                </div>
              </div>

              <section className="studio-profile-block" aria-labelledby="about-you-heading">
                <div className="studio-question-heading">
                  <div>
                    <span>About you</span>
                    <h3 id="about-you-heading">Give Kuma a little context.</h3>
                  </div>
                  <small>1 minute</small>
                </div>

                <div className="studio-field-grid">
                  <label className="studio-field studio-field-wide">
                    <span>Your name</span>
                    <input value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="How should Kuma address you?" required />
                  </label>
                </div>

                <fieldset className="studio-role-picker">
                  <legend>Which best describes you?</legend>
                  <div>
                    {roles.map((option) => (
                      <label key={option.value} className={role === option.value ? "is-selected" : ""}>
                        <input
                          type="radio"
                          name="role"
                          value={option.value}
                          checked={role === option.value}
                          onChange={() => setRole(option.value)}
                        />
                        {option.label}
                      </label>
                    ))}
                  </div>
                </fieldset>

                <fieldset className="studio-comfort-picker">
                  <legend>How technical should Studio feel?</legend>
                  <div>
                    {comfortOptions.map((option) => (
                      <label key={option.value} className={technicalComfort === option.value ? "is-selected" : ""}>
                        <input
                          type="radio"
                          name="technical-comfort"
                          value={option.value}
                          checked={technicalComfort === option.value}
                          onChange={() => setTechnicalComfort(option.value)}
                        />
                        <strong>{option.title}</strong>
                        <small>{option.detail}</small>
                      </label>
                    ))}
                  </div>
                </fieldset>
              </section>

              <section className="studio-profile-block" aria-labelledby="why-kuma-heading">
                <div className="studio-question-heading">
                  <div>
                    <span>What brings you here</span>
                    <h3 id="why-kuma-heading">Tell us where Kuma could help.</h3>
                  </div>
                  <small>Choose up to 3</small>
                </div>

                <fieldset className="studio-goal-picker">
                  <legend className="studio-visually-hidden">What would you use Kuma for?</legend>
                  <div>
                    {useCaseOptions.map((option) => {
                      const selected = useCases.includes(option.value);
                      const unavailable = !selected && useCases.length >= 3;
                      return (
                        <label
                          key={option.value}
                          className={`${selected ? "is-selected" : ""} ${unavailable ? "is-unavailable" : ""}`}
                        >
                          <input
                            type="checkbox"
                            name="use-cases"
                            value={option.value}
                            checked={selected}
                            disabled={unavailable}
                            onChange={() => toggleUseCase(option.value)}
                          />
                          <span className="studio-choice-mark" aria-hidden="true">{selected ? "✓" : ""}</span>
                          <span>
                            <strong>{option.title}</strong>
                            <small>{option.detail}</small>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>

                <div className="studio-research-grid">
                  <label className="studio-field studio-goal-field">
                    <span className="studio-field-title">
                      What are you most excited to solve?
                      <small>Optional · {goal.length}/160</small>
                    </span>
                    <textarea
                      value={goal}
                      onChange={(event) => setGoal(event.target.value)}
                      placeholder="For example: staying organized without pulling out my phone, or approving work while I’m away from my desk."
                      maxLength={160}
                    />
                  </label>

                  <label className="studio-field">
                    <span>Where did you hear about Kuma?</span>
                    <select value={discoverySource} onChange={(event) => setDiscoverySource(event.target.value)} required>
                      {discoverySources.map((source) => (
                        <option key={source.value || "empty"} value={source.value} disabled={!source.value}>
                          {source.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </section>

              <section className="studio-profile-block studio-profile-block-last" aria-labelledby="reply-style-heading">
                <div className="studio-question-heading">
                  <div>
                    <span>Conversation</span>
                    <h3 id="reply-style-heading">How should answers feel?</h3>
                  </div>
                </div>
                <fieldset className="studio-style-picker">
                  <legend className="studio-visually-hidden">Answer length</legend>
                  {(["brief", "balanced", "detailed"] as const).map((style) => (
                    <label key={style} className={responseStyle === style ? "is-selected" : ""}>
                      <input type="radio" name="style" value={style} checked={responseStyle === style} onChange={() => setResponseStyle(style)} />
                      <strong>{style}</strong>
                      <small>{style === "brief" ? "Wrist-sized" : style === "balanced" ? "Enough context" : "More complete"}</small>
                    </label>
                  ))}
                </fieldset>
              </section>

              <div className="studio-card-actions">
                <small>We use these answers to personalize Kuma and prioritize the roadmap.</small>
                <button
                  className="studio-submit studio-submit-inline"
                  disabled={pending || useCases.length === 0 || !discoverySource}
                >
                  {pending ? "Saving…" : data?.devices.length ? "Save and continue" : "Continue to Watch"} <span aria-hidden="true">→</span>
                </button>
              </div>
            </form>
          )}

          {activeStep === "watch" && data.devices.length === 0 && (
            <form className="studio-work-card studio-pair-card" onSubmit={pairWatch} aria-busy={pending}>
              <div className="studio-card-heading">
                <span className="studio-card-number">02</span>
                <div>
                  <p className="studio-step-label">Pair your Watch</p>
                  <h2>Open Kuma on Apple Watch.</h2>
                  <p>It will show a six-digit code and point you back here.</p>
                </div>
              </div>

              <ol className="studio-pair-steps">
                <li><span>1</span><p><strong>Open Kuma</strong><small>Launch the app on your Apple Watch.</small></p></li>
                <li><span>2</span><p><strong>Find the code</strong><small>A six-digit code appears automatically.</small></p></li>
                <li><span>3</span><p><strong>Enter it here</strong><small>The code stays valid for 10 minutes.</small></p></li>
              </ol>

              <div className="studio-pair-visual">
                <div className="studio-watch-outline" aria-hidden="true">
                  <Image src="/kumavoice-mark.svg" alt="" width={68} height={40} />
                  <span>STUDIO.KUMAVOICE.COM</span>
                </div>
                <span className="studio-pair-beam" aria-hidden="true" />
                <div className="studio-code-entry">
                  <label htmlFor="pairing-code">Code from your Watch</label>
                  <div className="studio-code-field">
                    <input
                      id="pairing-code"
                      value={pairingCode}
                      onChange={(event) => setPairingCode(event.target.value)}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      pattern="[0-9 ]{6,7}"
                      aria-label="Six-digit Watch pairing code"
                      autoFocus
                      required
                    />
                    <div className="studio-code-cells" aria-hidden="true">
                      {Array.from({ length: 6 }, (_, index) => (
                        <span key={index}>{pairingDigits[index] ?? "·"}</span>
                      ))}
                    </div>
                  </div>
                  <button className="studio-submit" disabled={pending || pairingDigits.length !== 6}>
                    {pending ? "Pairing…" : "Pair this Watch"} <span aria-hidden="true">↗</span>
                  </button>
                  <small className="studio-code-hint">Keep the Watch app open while pairing.</small>
                </div>
              </div>

              <div className="studio-navigation-row">
                <button className="studio-back-button" type="button" onClick={() => navigateToStep("profile", 0)}>
                  <span aria-hidden="true">←</span> Back to You
                </button>
              </div>
            </form>
          )}

          {activeStep === "watch" && data.devices.length > 0 && (
            <div className="studio-work-card studio-watch-review">
              <div className="studio-card-heading">
                <span className="studio-card-number">02</span>
                <div>
                  <p className="studio-step-label">Watch connected</p>
                  <h2>Your wrist is already paired.</h2>
                  <p>Review the connection here, go back to update your answers, or continue to voice setup.</p>
                </div>
              </div>

              <div className="studio-device-review">
                <div className="studio-watch-outline studio-watch-outline-compact" aria-hidden="true">
                  <Image src="/kumavoice-mark.svg" alt="" width={68} height={40} />
                  <span>CONNECTED</span>
                </div>
                <div>
                  <span className="studio-device-status"><i /> Private connection active</span>
                  <small>Paired device</small>
                  <strong>{data.devices[0]?.name ?? "Apple Watch"}</strong>
                  <p>You won’t need another code unless you connect a different Watch later.</p>
                </div>
              </div>

              <div className="studio-step-actions">
                <button className="studio-back-button" type="button" onClick={() => navigateToStep("profile", 0)}>
                  <span aria-hidden="true">←</span> Back to You
                </button>
                <button className="studio-submit" type="button" onClick={() => navigateToStep("provider", 2)}>
                  Continue to Voice <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          )}

          {activeStep === "provider" && (
            <form className="studio-work-card" onSubmit={saveProvider} aria-busy={pending}>
              <div className="studio-card-heading">
                <span className="studio-card-number">03</span>
                <div>
                  <p className="studio-step-label">Voice provider</p>
                  <h2>Bring your OpenAI key.</h2>
                  <p>Kuma uses it server-side for realtime voice. It never enters the Watch bundle.</p>
                </div>
              </div>

              <div className="studio-secret-panel">
                <div className="studio-secret-status">
                  <span className="studio-lock" aria-hidden="true">◇</span>
                  <div>
                    <strong>Encrypted before storage</strong>
                    <small>The dashboard only keeps the last four characters visible.</small>
                  </div>
                </div>
                <label className="studio-field">
                  <span className="studio-field-title">
                    OpenAI API key
                    <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">Create a key ↗</a>
                  </span>
                  <div className="studio-password-field studio-key-field">
                    <input
                      type={showApiKey ? "text" : "password"}
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                      placeholder="sk-…"
                      autoComplete="off"
                      spellCheck={false}
                      minLength={20}
                      required
                    />
                    <button type="button" onClick={() => setShowApiKey((visible) => !visible)}>
                      {showApiKey ? "Hide" : "Show"}
                    </button>
                  </div>
                </label>
              </div>

              <div className="studio-step-actions">
                <button className="studio-back-button" type="button" onClick={() => navigateToStep("watch", 1)}>
                  <span aria-hidden="true">←</span> Back to Watch
                </button>
                <button className="studio-submit" disabled={pending}>
                  {pending ? "Encrypting…" : "Save key and finish"} <span aria-hidden="true">→</span>
                </button>
              </div>
            </form>
          )}

          {activeStep === "complete" && data && (
            <div className="studio-work-card studio-ready-card">
              <div className="studio-ready-mark">
                <Image src="/kumavoice-mark.svg" alt="Kuma" width={92} height={54} />
              </div>
              <p className="studio-step-label">Line connected</p>
              <h2>Kuma is ready on your wrist.</h2>
              <p>Open the Watch app and start a turn. Your personal OpenAI key stays on the server.</p>

              <div className="studio-ready-grid">
                <article>
                  <small>Device</small>
                  <strong>{data.devices[0]?.name ?? "Apple Watch"}</strong>
                  <span><i /> Paired</span>
                </article>
                <article>
                  <small>Voice</small>
                  <strong>OpenAI ••••{data.openai.last_four}</strong>
                  <span><i /> Encrypted</span>
                </article>
                <article>
                  <small>Reply style</small>
                  <strong>{data.profile?.response_style ?? "brief"}</strong>
                  <span><i /> Personalized</span>
                </article>
              </div>

              <div className="studio-first-turn">
                <span className="studio-first-turn-icon" aria-hidden="true">⌁</span>
                <div>
                  <strong>Try your first turn</strong>
                  <small>Open Kuma, then tap or Double Tap and ask: “What can you help me with?”</small>
                </div>
              </div>
            </div>
          )}
              </motion.div>
            </AnimatePresence>
          </MotionConfig>
        </section>
      </div>
    </main>
  );
}
