import { useState } from "react";
import PropTypes from "prop-types";
import { getGmailSetupStatus } from "../api/client";
import { ExternalLink, X, CheckCircle, ChevronRight, ShieldCheck } from "lucide-react";

// Step-by-step Google Cloud Console guide
const SETUP_STEPS = [
  {
    title: "Create a Google Cloud Project",
    description: "Go to Google Cloud Console and create a new project (or select an existing one).",
    link: "https://console.cloud.google.com/projectcreate",
    linkLabel: "Open Google Cloud Console →",
  },
  {
    title: "Enable the Gmail API",
    description: 'In your project, go to "APIs & Services" → "Library", search for "Gmail API", and click Enable.',
    link: "https://console.cloud.google.com/apis/library/gmail.googleapis.com",
    linkLabel: "Enable Gmail API →",
  },
  {
    title: "Configure OAuth Consent Screen",
    description: 'Go to "APIs & Services" → "OAuth consent screen". Set type to "External", fill in App Name and your email. Save.',
    link: "https://console.cloud.google.com/apis/credentials/consent",
    linkLabel: "Configure Consent Screen →",
  },
  {
    title: "Add Yourself as Test User",
    description: 'Still on the OAuth consent screen, scroll to "Test users" and add your Gmail address. This lets you use the app before it is published.',
  },
  {
    title: "Create OAuth Credentials",
    description: 'Go to "APIs & Services" → "Credentials" → "+ Create Credentials" → "OAuth 2.0 Client ID". Choose "Web application".',
    link: "https://console.cloud.google.com/apis/credentials",
    linkLabel: "Open Credentials →",
  },
  {
    title: "Add Redirect URI",
    description: 'Under "Authorized redirect URIs", add exactly: http://localhost:8000/inbox/oauth/callback — then click Create.',
    code: "http://localhost:8000/inbox/oauth/callback",
  },
  {
    title: "Download credentials.json",
    description: 'After creating, click the download icon (⬇) on your new client ID. Rename the file to credentials.json and place it inside:',
    code: "backend/credentials.json",
  },
  {
    title: "Restart the backend",
    description: "Stop and restart the backend server. Then click 'Connect Gmail Account' again — the OAuth flow will open.",
  },
];

export default function ConnectButton({ onDemo, onGmail, onImap, loading }) {
  const [showGuide, setShowGuide] = useState(false);
  const [checkingGmail, setCheckingGmail] = useState(false);
  const [activeStep, setActiveStep] = useState(0);

  async function handleGmailClick() {
    setCheckingGmail(true);
    try {
      const status = await getGmailSetupStatus();
      if (status.credentials_configured) {
        // credentials.json exists — proceed with OAuth
        onGmail();
      } else {
        // credentials.json missing — show setup guide instead of error toast
        setActiveStep(0);
        setShowGuide(true);
      }
    } catch {
      // Backend offline — just try anyway
      onGmail();
    } finally {
      setCheckingGmail(false);
    }
  }

  if (loading || checkingGmail) {
    return (
      <div className="flex flex-col items-center justify-center space-y-4">
        <div className="pulse-ring w-12 h-12 text-indigo-500 rounded-full" />
        <p className="text-sm font-medium text-slate-400">
          {checkingGmail ? "Checking Gmail configuration..." : "Loading secure environment..."}
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="text-center max-w-md mx-auto fade-in">
        <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-500/10">
          <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Awaiting Data Source</h2>
        <p className="text-slate-400 text-sm mb-8 leading-relaxed">
          Connect your inbox to initialize the zero-trust ML pipeline.
        </p>

        <div className="space-y-3">
          {/* Gmail OAuth button */}
          <button
            onClick={handleGmailClick}
            className="w-full flex items-center justify-center px-4 py-3.5 rounded-xl border border-indigo-500/50 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 hover:text-white transition-all font-semibold text-sm shadow-[0_0_15px_rgba(99,102,241,0.2)]"
          >
            {/* Gmail G icon */}
            <svg className="w-5 h-5 mr-2 flex-shrink-0" viewBox="0 0 24 24" fill="none">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Connect Gmail Account
          </button>

          {/* IMAP button */}
          <button
            onClick={onImap}
            className="w-full flex items-center justify-center px-4 py-3.5 rounded-xl border border-emerald-500/50 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 hover:text-white transition-all font-semibold text-sm shadow-[0_0_15px_rgba(16,185,129,0.2)]"
          >
            <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Connect via IMAP
            <span className="ml-2 text-xs opacity-70 font-normal">(Gmail · Outlook · Yahoo · Any)</span>
          </button>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-800/50">
          <button
            onClick={onDemo}
            className="text-xs text-slate-500 hover:text-slate-300 underline underline-offset-4 transition-colors"
          >
            Need to test the system? Load Sandbox Data.
          </button>
        </div>
      </div>

      {/* ── Gmail Setup Guide Modal ── */}
      {showGuide && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/90 backdrop-blur-sm p-4 fade-in">
          <div className="glass-card w-full max-w-2xl max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-700/50">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Gmail OAuth Setup Guide</h3>
                  <p className="text-xs text-slate-400 mt-0.5">One-time setup · Takes about 5 minutes</p>
                </div>
              </div>
              <button
                onClick={() => setShowGuide(false)}
                className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Why this is needed */}
            <div className="px-6 py-4 bg-amber-500/5 border-b border-amber-500/10">
              <p className="text-xs text-amber-300/80 leading-relaxed">
                <span className="font-semibold text-amber-300">Why this is needed: </span>
                Gmail requires a Google Cloud project with OAuth credentials to grant read-only access.
                This is a one-time setup — your credentials stay on your machine and are never shared.
                <br />
                <span className="text-slate-400 mt-1 block">
                  💡 Easier alternative: Use <button onClick={() => { setShowGuide(false); onImap(); }} className="underline text-emerald-400 hover:text-emerald-300">IMAP with an App Password</button> instead — no Cloud Console needed.
                </span>
              </p>
            </div>

            {/* Steps */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {SETUP_STEPS.map((step, idx) => {
                const done = idx < activeStep;
                const active = idx === activeStep;
                return (
                  <button
                    key={idx}
                    onClick={() => setActiveStep(idx)}
                    className={`w-full text-left p-4 rounded-xl border transition-all ${
                      active
                        ? "bg-indigo-600/10 border-indigo-500/40"
                        : done
                        ? "bg-emerald-500/5 border-emerald-500/20"
                        : "bg-slate-900/40 border-slate-700/30 hover:border-slate-600/50"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Step indicator */}
                      <div className="flex-shrink-0 mt-0.5">
                        {done ? (
                          <CheckCircle className="w-5 h-5 text-emerald-400" />
                        ) : active ? (
                          <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-white text-xs font-bold">
                            {idx + 1}
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-slate-500 text-xs font-medium">
                            {idx + 1}
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-semibold ${active ? "text-white" : done ? "text-emerald-300" : "text-slate-300"}`}>
                          {step.title}
                        </p>
                        {active && (
                          <div className="mt-2 space-y-2">
                            <p className="text-xs text-slate-400 leading-relaxed">{step.description}</p>
                            {step.code && (
                              <div className="flex items-center gap-2 mt-2 bg-slate-900 rounded-lg px-3 py-2 border border-slate-700/50">
                                <code className="text-xs text-emerald-400 font-mono flex-1 break-all">{step.code}</code>
                                <button
                                  onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(step.code); }}
                                  className="text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0 text-xs"
                                  title="Copy"
                                >
                                  Copy
                                </button>
                              </div>
                            )}
                            {step.link && (
                              <a
                                href={step.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 underline underline-offset-2 transition-colors mt-1"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                                {step.linkLabel}
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Footer navigation */}
            <div className="px-6 py-4 border-t border-slate-700/50 flex items-center justify-between">
              <button
                onClick={() => setActiveStep((s) => Math.max(0, s - 1))}
                disabled={activeStep === 0}
                className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-sm font-medium hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                ← Back
              </button>

              <span className="text-xs text-slate-500">
                Step {activeStep + 1} of {SETUP_STEPS.length}
              </span>

              {activeStep < SETUP_STEPS.length - 1 ? (
                <button
                  onClick={() => setActiveStep((s) => s + 1)}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 transition-all flex items-center gap-1.5"
                >
                  Next <ChevronRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={() => { setShowGuide(false); onGmail(); }}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-500 transition-all flex items-center gap-1.5"
                >
                  <CheckCircle className="w-4 h-4" />
                  Done — Connect Now
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

ConnectButton.propTypes = {
  onDemo: PropTypes.func.isRequired,
  onGmail: PropTypes.func.isRequired,
  onImap: PropTypes.func.isRequired,
  loading: PropTypes.bool.isRequired,
};
