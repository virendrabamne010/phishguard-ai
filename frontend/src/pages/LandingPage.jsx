import { ArrowRight, ShieldCheck, Cpu, Globe2, Lock } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function LandingPage({ onEnter }) {
  const highlights = [
    {
      title: "Live threat monitoring",
      description: "Monitor inbound emails, analyze risk instantly, and surface suspicious messages in a polished console.",
      icon: ShieldCheck,
    },
    {
      title: "Explainable AI insights",
      description: "Review model-driven risk reasons and analytics for each email with transparent indicators.",
      icon: Cpu,
    },
    {
      title: "Secure deployment ready",
      description: "Designed for internal deployment with health checks, authentication, and container-based setup.",
      icon: Lock,
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute left-[-10%] top-[-10%] h-72 w-72 rounded-full bg-indigo-600/20 blur-[120px]" />
        <div className="absolute bottom-[-8%] right-[-8%] h-80 w-80 rounded-full bg-emerald-500/10 blur-[120px]" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-10 lg:px-10">
        <header className="flex items-center justify-between rounded-full border border-slate-800/80 bg-slate-900/70 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600/20 text-indigo-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">PhishGuard AI</p>
              <p className="text-xs text-slate-400">Enterprise phishing defense platform</p>
            </div>
          </div>
          <button
            onClick={onEnter}
            className="rounded-full border border-indigo-500/30 bg-indigo-600/15 px-4 py-2 text-sm font-semibold text-indigo-300 transition hover:bg-indigo-600/25"
          >
            Open dashboard
          </button>
        </header>

        <main className="flex flex-1 flex-col justify-center py-16 lg:flex-row lg:items-center lg:gap-16">
          <section className="max-w-2xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-sm text-emerald-300">
              <Globe2 className="h-4 w-4" />
              Production-ready internal security workflow
            </div>
            <h1 className="text-4xl font-semibold leading-tight text-white sm:text-5xl">
              Detect phishing threats with speed, clarity, and confidence.
            </h1>
            <p className="mt-6 text-lg text-slate-400">
              PhishGuard AI combines a modern admin console, explainable ML scoring, and a streamlined inbox workflow into one polished experience.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                onClick={onEnter}
                className="glow-button inline-flex items-center gap-2 rounded-full bg-indigo-600 px-8 py-3.5 text-sm font-bold text-white transition-transform hover:-translate-y-0.5 shadow-lg shadow-indigo-600/30"
              >
                Initialize Defense System <ArrowRight className="h-4 w-4" />
              </button>
              <a
                href={`${API_BASE}/docs`}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-slate-700 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white"
              >
                View API docs
              </a>
            </div>
          </section>

          <section className="w-full max-w-xl rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/50 backdrop-blur">
            <div className="mb-6 flex items-center gap-3">
              <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-300">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Platform overview</h2>
                <p className="text-sm text-slate-400">Why this solution feels enterprise-ready</p>
              </div>
            </div>

            <div className="space-y-4">
              {highlights.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 rounded-xl bg-indigo-500/10 p-2 text-indigo-300">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-white">{item.title}</h3>
                        <p className="mt-1 text-sm text-slate-400">{item.description}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
