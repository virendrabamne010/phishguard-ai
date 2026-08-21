import { useState, useEffect } from "react";
import { Database, AlertCircle, RefreshCw, Download } from "lucide-react";
import { getDatabaseDump } from "../api/client";

export default function DatabaseView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDatabase = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDatabaseDump();
      setData(data);
    } catch (err) {
      console.error("Failed to fetch database dump:", err);
      setError("Failed to connect to the database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatabase();
  }, []);

  const handleExportCSV = () => {
    if (!data?.emails || data.emails.length === 0) {
      alert("No data to export.");
      return;
    }
    const headers = ["ID", "Subject", "Sender", "Risk Score", "Label", "Reported"];
    const rows = data.emails.map(email => [
      email.id,
      `"${email.subject.replace(/"/g, '""')}"`,
      `"${email.sender.replace(/"/g, '""')}"`,
      email.risk_score,
      email.label,
      email.reported
    ]);
    const csvContent = [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", "phishguard_emails.csv");
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Database className="w-8 h-8 text-indigo-500" />
            Raw Database
          </h1>
          <p className="text-slate-400 mt-2">
            Admin view of the internal SQLite tables.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 rounded-lg transition-colors border border-indigo-500/30"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
          <button
            onClick={fetchDatabase}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors border border-slate-700"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 flex items-center gap-3 text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* System Settings Table */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur-sm">
        <div className="p-5 border-b border-slate-800 bg-slate-800/20">
          <h2 className="text-lg font-semibold text-white">System Settings Table</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 text-slate-400 text-xs uppercase font-semibold">
              <tr>
                <th className="px-6 py-4">ID</th>
                <th className="px-6 py-4">Mode</th>
                <th className="px-6 py-4">Global Scanned</th>
                <th className="px-6 py-4">Global Phishing</th>
                <th className="px-6 py-4">Global Suspicious</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data?.settings?.map((setting) => (
                <tr key={setting.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4 font-mono text-indigo-400">{setting.id}</td>
                  <td className="px-6 py-4">
                    <span className="px-2.5 py-1 rounded-full bg-slate-800 text-xs font-medium">
                      {setting.mode}
                    </span>
                  </td>
                  <td className="px-6 py-4">{setting.global_scanned}</td>
                  <td className="px-6 py-4 text-red-400">{setting.global_phishing}</td>
                  <td className="px-6 py-4 text-orange-400">{setting.global_suspicious}</td>
                </tr>
              ))}
              {(!data?.settings || data.settings.length === 0) && !loading && (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-slate-500">
                    No settings found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Emails Table */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur-sm">
        <div className="p-5 border-b border-slate-800 bg-slate-800/20">
          <h2 className="text-lg font-semibold text-white">Email Records Table <span className="text-sm font-normal text-slate-500 ml-2">({data?.emails?.length || 0} rows)</span></h2>
        </div>
        <div className="overflow-x-auto max-h-[600px]">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 text-slate-400 text-xs uppercase font-semibold sticky top-0 z-10 shadow-md">
              <tr>
                <th className="px-6 py-4">ID</th>
                <th className="px-6 py-4 min-w-[200px]">Subject</th>
                <th className="px-6 py-4 min-w-[200px]">Sender</th>
                <th className="px-6 py-4">Risk Score</th>
                <th className="px-6 py-4">Label</th>
                <th className="px-6 py-4">Reported</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data?.emails?.map((email) => (
                <tr key={email.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-indigo-400 truncate max-w-[100px]" title={email.id}>{email.id}</td>
                  <td className="px-6 py-4 truncate max-w-[250px]" title={email.subject}>{email.subject}</td>
                  <td className="px-6 py-4 truncate max-w-[200px]" title={email.sender}>{email.sender}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                      email.risk_score >= 70 ? 'bg-red-500/10 text-red-400' :
                      email.risk_score >= 30 ? 'bg-orange-500/10 text-orange-400' :
                      'bg-emerald-500/10 text-emerald-400'
                    }`}>
                      {email.risk_score}
                    </span>
                  </td>
                  <td className="px-6 py-4 capitalize">{email.label}</td>
                  <td className="px-6 py-4">
                    {email.reported ? (
                      <span className="text-amber-500 font-medium">True</span>
                    ) : (
                      <span className="text-slate-500">False</span>
                    )}
                  </td>
                </tr>
              ))}
              {(!data?.emails || data.emails.length === 0) && !loading && (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-slate-500">
                    No emails in database.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
