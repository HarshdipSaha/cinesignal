import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./Layout.css";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <header className="shell-header">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-word">
            CINE<span className="brand-word-accent">SIGNAL</span>
          </span>
        </Link>
        <div className="shell-header-tag mono">agentic attention intelligence</div>
      </header>
      <main className="shell-main">{children}</main>
      <footer className="shell-footer mono">
        <span>CineSignal — screening-room analytics</span>
        <span className="shell-footer-dot" aria-hidden="true" />
        <span>evidence-backed playbooks</span>
      </footer>
    </div>
  );
}
