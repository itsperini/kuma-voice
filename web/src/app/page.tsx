"use client";

import Image from "next/image";
import Link from "next/link";
import { MotionConfig, motion } from "motion/react";
import { Brand } from "../components/brand";

const easeOut = [0.22, 1, 0.36, 1] as const;
const studioOrigin = process.env.NEXT_PUBLIC_STUDIO_ORIGIN?.replace(/\/$/, "");
const studioSignupHref = studioOrigin ? `${studioOrigin}/signup` : "/studio/signup";

const agentTools = [
  "notify",
  "ask",
  "request_confirmation",
  "deliver_result",
];

const privacyPrinciples = [
  {
    title: "Audio passes through",
    copy: "Voice is designed to be processed for the request, not kept as an archive.",
  },
  {
    title: "Memory stays legible",
    copy: "Persistent memories are explicit, reviewable, and yours to remove.",
  },
  {
    title: "Access stays reversible",
    copy: "Devices, agents, and connectors can be disconnected from one place.",
  },
];

export default function Home() {
  return (
    <MotionConfig reducedMotion="user">
      <div className="site-shell">
      <motion.header
        className="site-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, ease: easeOut }}
      >
        <Brand short />
        <nav className="desktop-nav" aria-label="Primary navigation">
          <a href="#loop">How it works</a>
          <a href="#mcp">For agents</a>
          <a href="#privacy">Privacy</a>
        </nav>
        <Link className="nav-cta" href={studioSignupHref}>
          Private beta <span aria-hidden="true">↗</span>
        </Link>
      </motion.header>

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <motion.p
              className="eyebrow"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, delay: 0.12, ease: easeOut }}
            >
              <span className="status-dot" aria-hidden="true" />
              A direct line to your agents
            </motion.p>
            <h1 id="hero-title">
              <motion.span
                className="hero-line hero-line-primary"
                initial={{ opacity: 0, y: 42 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.78, delay: 0.18, ease: easeOut }}
              >
                Your agents,
              </motion.span>
              <motion.span
                className="hero-line hero-line-accent"
                initial={{ opacity: 0, y: 52 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.82, delay: 0.28, ease: easeOut }}
              >
                on your wrist.
              </motion.span>
            </h1>
            <motion.p
              className="hero-description"
              initial={{ opacity: 0, y: 22 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.66, delay: 0.42, ease: easeOut }}
            >
              Speak from Apple Watch. Let your agents reach back with results,
              questions, and approvals—without a companion iPhone app.
            </motion.p>
            <motion.div
              className="hero-actions"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.52, ease: easeOut }}
            >
              <Link className="button button-primary" href={studioSignupHref}>
                Join the private beta <span aria-hidden="true">↗</span>
              </Link>
              <a className="text-link" href="#loop">
                See the loop <span aria-hidden="true">↓</span>
              </a>
            </motion.div>
            <motion.ul
              className="hero-notes"
              aria-label="Product qualities"
              initial="hidden"
              animate="visible"
              variants={{
                hidden: {},
                visible: { transition: { delayChildren: 0.62, staggerChildren: 0.08 } },
              }}
            >
              {["Watch-only", "Built for MCP", "Human in the loop"].map((note) => (
                <motion.li
                  key={note}
                  variants={{
                    hidden: { opacity: 0, y: 10 },
                    visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: easeOut } },
                  }}
                >
                  {note}
                </motion.li>
              ))}
            </motion.ul>
            <motion.div
              className="watch-native-proof"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.52, delay: 0.78, ease: easeOut }}
            >
              <Image
                src="/applewatch-screenshot.PNG"
                alt="Kuma in the watchOS app grid"
                width={374}
                height={446}
                sizes="62px"
              />
              <span>
                <strong>Installed right on your Watch</strong>
                <small>No companion iPhone app.</small>
              </span>
            </motion.div>
          </div>

          <motion.div
            className="hero-stage"
            aria-label="Kuma Voice on Apple Watch"
            initial={{ opacity: 0, y: 54, scale: 0.975 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            whileHover={{ y: -5, scale: 1.003 }}
            transition={{ duration: 0.82, delay: 0.5, ease: easeOut }}
          >
            <div className="stage-label">
              <span className="stage-channel">
                Live agent line
                <span className="voice-meter" aria-hidden="true">
                  {[0, 1, 2, 3].map((bar) => (
                    <motion.span
                      key={bar}
                      animate={{ scaleY: [0.35, 1, 0.5, 0.82, 0.35] }}
                      transition={{
                        duration: 1.35,
                        delay: bar * 0.1,
                        repeat: Number.POSITIVE_INFINITY,
                        ease: "easeInOut",
                      }}
                    />
                  ))}
                </span>
              </span>
              <span className="stage-status">Available</span>
            </div>
            <motion.div
              className="stage-orbit"
              aria-hidden="true"
              animate={{ rotate: 360 }}
              transition={{ duration: 28, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
            >
              <span />
            </motion.div>
            <motion.div
              className="agent-cursor"
              aria-hidden="true"
              animate={{ x: [0, -10, 5, 0], y: [0, 8, -4, 0] }}
              transition={{ duration: 7, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
            >
              <span className="cursor-tip" />
              <span>Kuma agent</span>
            </motion.div>
            <Image
              className="watch-banner"
              src="/watchos-header-banner-v3.png"
              alt="Kuma Voice listening and responding on Apple Watch"
              width={1774}
              height={887}
              priority
              sizes="(max-width: 900px) 94vw, 50vw"
            />
            <motion.div
              className="agent-ping"
              animate={{ y: [0, -4, 0] }}
              transition={{ duration: 4.8, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
            >
              <span className="ping-icon" aria-hidden="true">
                <Image src="/kumavoice-mark.svg" alt="" width={32} height={21} />
              </span>
              <span>
                <small>Kuma agent</small>
                Deployment is ready
              </span>
              <span className="ping-action">Approve</span>
            </motion.div>
          </motion.div>
        </section>

        <motion.section
          className="loop-section"
          id="loop"
          aria-labelledby="loop-title"
          initial={{ opacity: 0, y: 42 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.16 }}
          transition={{ duration: 0.76, ease: easeOut }}
        >
          <div className="section-heading">
            <p className="section-kicker">A two-way interface</p>
            <h2 id="loop-title">You call your agent. Your agent can call back.</h2>
          </div>

          <div className="signal-board">
            <motion.div
              className="signal-step signal-human"
              initial={{ opacity: 0, x: -26 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.45 }}
              transition={{ duration: 0.64, delay: 0.12, ease: easeOut }}
            >
              <div className="step-meta">
                <span className="step-time">09:41</span>
                <span className="step-owner">You</span>
              </div>
              <p>“Check the release and tell me when it’s ready.”</p>
              <span className="signal-label">Voice from Watch</span>
            </motion.div>

            <div className="signal-line" aria-hidden="true">
              <span className="signal-node" />
              <span className="signal-pulse" />
              <span className="signal-node" />
            </div>

            <motion.div
              className="signal-step signal-agent"
              initial={{ opacity: 0, x: 26 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.45 }}
              transition={{ duration: 0.64, delay: 0.2, ease: easeOut }}
            >
              <div className="step-meta">
                <span className="step-time">09:44</span>
                <span className="step-owner">Agent</span>
              </div>
              <p>“All checks passed. Deploy to production?”</p>
              <div className="approval-row" aria-label="Example response actions">
                <span>Hold</span>
                <span className="approve">Approve</span>
              </div>
            </motion.div>
          </div>
        </motion.section>

        <motion.section
          className="mcp-section"
          id="mcp"
          aria-labelledby="mcp-title"
          initial={{ opacity: 0, y: 42 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.16 }}
          transition={{ duration: 0.76, ease: easeOut }}
        >
          <motion.div
            className="mcp-copy"
            initial={{ opacity: 0, x: -24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.66, delay: 0.12, ease: easeOut }}
          >
            <p className="section-kicker section-kicker-dark">For any agent</p>
            <h2 id="mcp-title">A Watch your agent can call.</h2>
            <p>
              Kuma binds your Apple Watch to a secure remote MCP endpoint. Your
              agent gets a small, permissioned set of tools for reaching you at
              exactly the right moment.
            </p>
          </motion.div>

          <motion.div
            className="tool-console"
            aria-label="Example Kuma MCP tools"
            initial={{ opacity: 0, x: 30, rotate: 1.5 }}
            whileInView={{ opacity: 1, x: 0, rotate: -0.8 }}
            viewport={{ once: true, amount: 0.36 }}
            transition={{ duration: 0.72, delay: 0.18, ease: easeOut }}
          >
            <div className="console-topline">
              <span>kuma.watch</span>
              <span className="console-online">connected</span>
            </div>
            <div className="tool-list">
              {agentTools.map((tool, index) => (
                <motion.div
                  className="tool-row"
                  key={tool}
                  initial={{ opacity: 0, x: 16 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, amount: 0.7 }}
                  transition={{ duration: 0.42, delay: 0.3 + index * 0.07, ease: easeOut }}
                >
                  <code>kuma.{tool}</code>
                  <span aria-hidden="true">↗</span>
                </motion.div>
              ))}
            </div>
            <p className="console-note">
              The microphone always starts with you. Agents can never listen in.
            </p>
          </motion.div>
        </motion.section>

        <motion.section
          className="privacy-section"
          id="privacy"
          aria-labelledby="privacy-title"
          initial={{ opacity: 0, y: 42 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.14 }}
          transition={{ duration: 0.76, ease: easeOut }}
        >
          <div className="section-heading privacy-heading">
            <p className="section-kicker">Private by posture</p>
            <h2 id="privacy-title">Keep the useful context. Leave the archive behind.</h2>
            <p>
              Kuma is being designed around explicit memory and short-lived
              conversations, so personalization does not require keeping every word.
            </p>
          </div>
          <div className="privacy-grid">
            {privacyPrinciples.map((principle, index) => (
              <motion.article
                key={principle.title}
                initial={{ opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.45 }}
                transition={{ duration: 0.52, delay: 0.12 + index * 0.08, ease: easeOut }}
              >
                <span className="privacy-check" aria-hidden="true">✓</span>
                <h3>{principle.title}</h3>
                <p>{principle.copy}</p>
              </motion.article>
            ))}
          </div>
        </motion.section>

        <motion.section
          className="closing-section"
          aria-labelledby="closing-title"
          initial={{ opacity: 0, y: 38 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.22 }}
          transition={{ duration: 0.72, ease: easeOut }}
        >
          <div>
            <p className="section-kicker section-kicker-dark">Private beta</p>
            <h2 id="closing-title">Give your agents a direct line to your wrist.</h2>
          </div>
          <Link className="button button-light" href={studioSignupHref}>
            Request early access <span aria-hidden="true">↗</span>
          </Link>
        </motion.section>
      </main>

      <footer className="site-footer">
        <Brand short />
        <p>Independent Apple Watch software for human-agent collaboration.</p>
        <a href="https://x.com/kumavoice" target="_blank" rel="noreferrer">
          @kumavoice <span aria-hidden="true">↗</span>
        </a>
      </footer>
      </div>
    </MotionConfig>
  );
}
