/**
 * EmailDetail — Full email view with Explain Why section and Report button.
 */

import { useState, useEffect } from "react";
import RiskScoreBadge from "../components/RiskScoreBadge";
import { getEmailDetail, reportEmail, deleteEmail } from "../api/client";
import toast from "react-hot-toast";

import PropTypes from "prop-types";

export default function EmailDetail({ emailId, onBack }) {
  const [email, setEmail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reporting, setReporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    async function loadEmail() {
      setLoading(true);
      try {
        const data = await getEmailDetail(emailId);
        setEmail(data);
      } catch (err) {
        console.error("Failed to load email:", err);
      } finally {
        setLoading(false);
      }
    }
    loadEmail();
  }, [emailId]);

  async function handleReport() {
    setReporting(true);
    try {
      await reportEmail(emailId);
      setEmail((prev) => ({ ...prev, reported: true }));
    } catch (err) {
      console.error("Failed to report:", err);
    } finally {
      setReporting(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Are you sure you want to delete this email?")) return;
    
    setDeleting(true);
    try {
      await deleteEmail(emailId);
      toast.success("Email deleted successfully.");
      onBack(); // Go back to inbox after deletion
    } catch (err) {
      toast.error(err.message || "Failed to delete email.");
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!email) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-400">Email not found.</p>
      </div>
    );
  }

  const riskColor = email.label === "phishing" ? "red" : email.label === "suspicious" ? "amber" : "emerald";

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors text-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to Inbox
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-5 fade-in">
        {/* Risk Score Summary */}
        <div className={`glass-card p-5 border-l-4 ${
          riskColor === "red" ? "border-l-red-500" :
          riskColor === "amber" ? "border-l-amber-500" :
          "border-l-emerald-500"
        }`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <RiskScoreBadge score={email.risk_score} label={email.label} />
                {email.reported && (
                  <span className="text-xs px-2 py-1 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/20">
                    Reported
                  </span>
                )}
              </div>
              <h2 className="text-xl font-bold text-white">{email.subject}</h2>
              <p className="text-sm text-slate-400 mt-1">From: <span className="text-slate-300">{email.sender}</span></p>
            </div>

            {/* Risk meter */}
            <div className="flex-shrink-0 w-20 h-20 relative">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#1e293b"
                  strokeWidth="3"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={riskColor === "red" ? "#ef4444" : riskColor === "amber" ? "#f59e0b" : "#10b981"}
                  strokeWidth="3"
                  strokeDasharray={`${email.risk_score}, 100`}
                  strokeLinecap="round"
                  style={{ transition: "stroke-dasharray 1s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-lg font-bold ${
                  riskColor === "red" ? "text-red-400" :
                  riskColor === "amber" ? "text-amber-400" :
                  "text-emerald-400"
                }`}>{email.risk_score}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Explain Why */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5.002 5.002 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Explain Why
          </h3>

          <div className="space-y-2">
            {email.flagged_reasons.map((reason, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-800/40 hover:bg-slate-800/60 transition-colors">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                  riskColor === "red" ? "bg-red-500/20 text-red-400" :
                  riskColor === "amber" ? "bg-amber-500/20 text-amber-400" :
                  "bg-emerald-500/20 text-emerald-400"
                }`}>
                  <span className="text-xs font-bold">{i + 1}</span>
                </div>
                <p className="text-sm text-slate-300">{reason}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Email Body */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
            </svg>
            Full Email Body
          </h3>
          <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-700/30">
            <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
              {email.body}
            </pre>
          </div>
        </div>

        {/* Report & Delete Buttons */}
        <div className="flex justify-end gap-3">
          <button
            onClick={handleDelete}
            disabled={deleting}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 shadow-sm ${
              deleting
                ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                : "bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 active:scale-95"
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            {deleting ? "Deleting..." : "Delete Email"}
          </button>

          {email.reported ? (
            <div className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-orange-500/10 border border-orange-500/20 text-orange-400 text-sm font-semibold">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Reported
            </div>
          ) : (
            <button
              onClick={handleReport}
              disabled={reporting}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200
                         bg-orange-500/10 text-orange-400 border border-orange-500/20
                         hover:bg-orange-500/20 hover:border-orange-500/30
                         active:scale-95
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v1.5M3 21v-6m0 0l2.77-.693a9 9 0 016.208.682l.108.054a9 9 0 006.086.71l3.114-.732a48.524 48.524 0 01-.005-10.499l-3.11.732a9 9 0 01-6.085-.711l-.108-.054a9 9 0 00-6.208-.682L3 4.5M3 15V4.5" />
              </svg>
              {reporting ? "Reporting..." : "Report This Email"}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}

EmailDetail.propTypes = {
  emailId: PropTypes.string.isRequired,
  onBack: PropTypes.func.isRequired,
};
