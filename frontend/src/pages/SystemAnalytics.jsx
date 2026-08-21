import { useEffect, useState } from "react";
import { Activity, ShieldCheck, AlertTriangle, ShieldAlert, Cpu, Download, FileText, Database, Shield, Loader2 } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { getSystemAnalytics, getAuditLog, downloadExport } from "../api/client";
import toast from "react-hot-toast";

export default function SystemAnalytics() {
  const [stats, setStats] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null); // 'csv' | 'json' | null

  useEffect(() => {
    Promise.all([
      getSystemAnalytics().catch(err => {
        console.error("Failed to load analytics:", err);
        return null;
      }),
      getAuditLog(50).catch(err => {
        console.error("Failed to load audit logs:", err);
        return { entries: [] };
      })
    ]).then(([statsData, auditData]) => {
      setStats(statsData);
      setAuditLogs(auditData.entries || []);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="p-8 max-w-5xl mx-auto space-y-8 w-full animate-pulse">
        <div className="h-8 bg-slate-800 rounded w-48 mb-8"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-card h-32 bg-slate-800/50"></div>
          <div className="glass-card h-32 bg-slate-800/50"></div>
          <div className="glass-card h-32 bg-slate-800/50"></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
          <div className="glass-card h-80 bg-slate-800/50"></div>
          <div className="glass-card h-80 bg-slate-800/50"></div>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="p-8 text-center text-slate-400">
        Analytics service unavailable.
      </div>
    );
  }

  const { model_metrics } = stats;

  return (
    <div className="p-8 fade-in space-y-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <Activity className="w-6 h-6 text-indigo-400" />
          Global Telemetry
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card p-6 flex flex-col gap-2 relative overflow-hidden">
          <div className="absolute -top-4 -right-4 p-4 opacity-10">
            <ShieldCheck className="w-24 h-24 text-emerald-500" />
          </div>
          <span className="text-slate-400 text-sm font-semibold uppercase tracking-wider relative z-10">Total Scanned</span>
          <span className="text-5xl font-bold text-white relative z-10">{stats.global_scanned}</span>
        </div>
        
        <div className="glass-card p-6 flex flex-col gap-2 relative overflow-hidden">
          <div className="absolute -top-4 -right-4 p-4 opacity-10">
            <ShieldAlert className="w-24 h-24 text-red-500" />
          </div>
          <span className="text-slate-400 text-sm font-semibold uppercase tracking-wider relative z-10">Threats Blocked</span>
          <span className="text-5xl font-bold text-red-400 relative z-10">{stats.global_phishing}</span>
        </div>

        <div className="glass-card p-6 flex flex-col gap-2 relative overflow-hidden">
          <div className="absolute -top-4 -right-4 p-4 opacity-10">
            <AlertTriangle className="w-24 h-24 text-amber-500" />
          </div>
          <span className="text-slate-400 text-sm font-semibold uppercase tracking-wider relative z-10">Suspicious</span>
          <span className="text-5xl font-bold text-amber-400 relative z-10">{stats.global_suspicious}</span>
        </div>
      </div>

      {/* Visuals */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        <div className="glass-card p-6">
          <h3 className="text-lg font-semibold text-slate-300 mb-6">Threat Distribution</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={[
                    { name: 'Legitimate', value: Math.max(0, stats.global_scanned - stats.global_phishing - stats.global_suspicious), color: '#10b981' },
                    { name: 'Phishing', value: stats.global_phishing, color: '#ef4444' },
                    { name: 'Suspicious', value: stats.global_suspicious, color: '#f59e0b' },
                  ]}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {[
                    { name: 'Legitimate', value: Math.max(0, stats.global_scanned - stats.global_phishing - stats.global_suspicious), color: '#10b981' },
                    { name: 'Phishing', value: stats.global_phishing, color: '#ef4444' },
                    { name: 'Suspicious', value: stats.global_suspicious, color: '#f59e0b' },
                  ].map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="glass-card p-6">
          <h3 className="text-lg font-semibold text-slate-300 mb-6">Volume Overview</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[
                { name: 'Total Scanned', value: stats.global_scanned, fill: '#6366f1' },
                { name: 'Flagged', value: stats.global_phishing + stats.global_suspicious, fill: '#ef4444' }
              ]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" tick={{ fill: '#94a3b8' }} />
                <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8' }} />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f8fafc' }}
                  cursor={{ fill: '#334155', opacity: 0.4 }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <h2 className="text-2xl font-bold text-white flex items-center gap-3 pt-4">
        <Cpu className="w-6 h-6 text-indigo-400" />
        AI Model Performance
      </h2>

      {model_metrics && Object.keys(model_metrics).length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass-card p-6">
             <h3 className="text-lg font-semibold text-slate-300 mb-6">Cross-Validated Metrics</h3>
             <div className="space-y-5">
               {[
                 { label: "Accuracy", value: model_metrics.accuracy },
                 { label: "F1 Score", value: model_metrics.f1_score },
                 { label: "Precision", value: model_metrics.precision },
                 { label: "Recall", value: model_metrics.recall },
                 { label: "ROC-AUC", value: model_metrics.roc_auc },
               ].map((metric) => metric.value && (
                 <div key={metric.label}>
                   <div className="flex justify-between text-sm mb-1">
                     <span className="text-slate-400 font-medium">{metric.label}</span>
                     <span className="text-white font-mono">{(metric.value * 100).toFixed(2)}%</span>
                   </div>
                   <div className="w-full bg-slate-800/50 rounded-full h-2.5 shadow-inner">
                     <div className="bg-gradient-to-r from-indigo-500 to-cyan-400 h-2.5 rounded-full shadow-lg shadow-indigo-500/20" style={{ width: `${metric.value * 100}%` }} />
                   </div>
                 </div>
               ))}
             </div>
          </div>
          
          <div className="glass-card p-6">
             <h3 className="text-lg font-semibold text-slate-300 mb-6">Top Phishing Indicators (TF-IDF Weights)</h3>
             <div className="flex flex-wrap gap-2">
                {model_metrics.top_phishing_indicators && Object.entries(model_metrics.top_phishing_indicators).map(([word, weight]) => (
                  <div key={word} className="px-3 py-1.5 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 hover:bg-red-500/20 transition-colors">
                    <span className="text-red-300 font-mono text-sm">{word}</span>
                    <span className="text-slate-500 text-xs">{(weight).toFixed(2)}</span>
                  </div>
                ))}
             </div>
          </div>
        </div>
      ) : (
        <div className="glass-card p-8 text-center text-slate-400">
          Model metrics not available. Ensure train_model.py has been run and model artifacts exist.
        </div>
      )}

      {/* Export Section */}
      <div className="pt-6">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3 mb-6">
          <Database className="w-6 h-6 text-indigo-400" />
          Data Export & Compliance
        </h2>
        <div className="glass-card p-6 flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-300">Export Scan Results</h3>
            <p className="text-sm text-slate-500 mt-1">Download a full report of all analyzed emails for offline auditing.</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={async () => {
                setExporting("csv");
                try { await downloadExport("csv"); toast.success("CSV exported!"); }
                catch (err) { toast.error(err.message || "Export failed"); }
                finally { setExporting(null); }
              }}
              disabled={exporting === "csv"}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {exporting === "csv" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} CSV Export
            </button>
            <button
              onClick={async () => {
                setExporting("json");
                try { await downloadExport("json"); toast.success("JSON exported!"); }
                catch (err) { toast.error(err.message || "Export failed"); }
                finally { setExporting(null); }
              }}
              disabled={exporting === "json"}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {exporting === "json" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />} JSON Export
            </button>
          </div>
        </div>
      </div>

      {/* Audit Log Section */}
      <div className="pt-6">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3 mb-6">
          <Shield className="w-6 h-6 text-indigo-400" />
          Security Audit Log
        </h2>
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900/50 text-xs uppercase text-slate-400 font-semibold border-b border-slate-700/50">
                <tr>
                  <th className="px-6 py-4">Timestamp (UTC)</th>
                  <th className="px-6 py-4">Admin</th>
                  <th className="px-6 py-4">Action</th>
                  <th className="px-6 py-4">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {auditLogs.length > 0 ? (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap font-mono text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                      <td className="px-6 py-4">{log.admin_username}</td>
                      <td className="px-6 py-4 font-mono text-indigo-300">{log.action}</td>
                      <td className="px-6 py-4 font-mono text-slate-500">{log.ip_address || 'unknown'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="4" className="px-6 py-8 text-center text-slate-500">No audit logs found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
