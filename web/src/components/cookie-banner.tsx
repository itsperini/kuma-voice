"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "kuma-cookie-choice-v2";

type CookieChoice = "all" | "essential";

export function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      setVisible(!window.localStorage.getItem(STORAGE_KEY));
    } catch {
      setVisible(true);
    }
  }, []);

  function choose(choice: CookieChoice) {
    try {
      window.localStorage.setItem(STORAGE_KEY, choice);
    } catch {
      // Storage may be unavailable in a private browsing context.
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <aside className="cookie-banner" role="dialog" aria-labelledby="cookie-title" aria-describedby="cookie-copy">
      <div className="cookie-mark" aria-hidden="true">◖</div>
      <div className="cookie-copy">
        <strong id="cookie-title">Cookies, minus the crumbs.</strong>
        <p id="cookie-copy">
          Kuma only uses essential browser storage today. You can still choose
          whether to allow future analytics, and we will remember this choice on this device.
        </p>
      </div>
      <div className="cookie-actions">
        <button type="button" className="cookie-essential" onClick={() => choose("essential")}>Essential only</button>
        <button type="button" className="cookie-accept" onClick={() => choose("all")}>Accept all</button>
      </div>
    </aside>
  );
}
