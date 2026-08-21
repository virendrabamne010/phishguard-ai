import { lazy, Suspense, useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import ErrorBoundary from "./components/ErrorBoundary";
import { LayoutDashboard, Inbox, ShieldCheck, Database, LogOut, Settings as SettingsIcon } from "lucide-react";
import { clearTokens } from "./api/client";

const InboxView = lazy(() => import("./pages/InboxView"));
const EmailDetail = lazy(() => import("./pages/EmailDetail"));
const SystemAnalytics = lazy(() => import("./pages/SystemAnalytics"));
const DatabaseView = lazy(() => import("./pages/DatabaseView"));
const Login = lazy(() => import("./pages/Login"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const Settings = lazy(() => import("./pages/Settings"));

function ScreenLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-300">
      <div className="flex items-center gap-3 text-sm font-medium">
        <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
        Loading workspace...
      </div>
    </div>
  );
}

export default function App() {
  const [selectedEmailId, setSelectedEmailId] = useState(null);
  const [activeTab, setActiveTab] = useState("inbox");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showLanding, setShowLanding] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("phishguard_token");
    if (token) {
      setIsAuthenticated(true);
      setShowLanding(false); // Skip landing if already logged in
    }
  }, []);

  function handleLogout() {
    clearTokens(); // Clears both access + refresh tokens
    setIsAuthenticated(false);
    setShowLanding(true);
  }

  if (!isAuthenticated) {
    return (
      <Suspense fallback={<ScreenLoader />}>
        <Toaster position="top-right" toastOptions={{ style: { background: '#1e293b', color: '#fff', border: '1px solid #334155' } }} />
        {showLanding ? (
          <LandingPage onEnter={() => setShowLanding(false)} />
        ) : (
          <Login onLogin={() => setIsAuthenticated(true)} />
        )}
      </Suspense>
    );
  }

  if (selectedEmailId) {
    return (
      <Suspense fallback={<ScreenLoader />}>
        <EmailDetail
          emailId={selectedEmailId}
          onBack={() => setSelectedEmailId(null)}
        />
      </Suspense>
    );
  }

  return (
    <ErrorBoundary>
      <Toaster 
        position="top-right" 
        toastOptions={{
          style: { background: '#1e293b', color: '#fff', border: '1px solid #334155' }
        }} 
      />
      <div className="flex h-screen bg-slate-950 overflow-hidden">
        {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col flex-shrink-0 z-20 hidden md:flex">
        <div className="p-6 flex items-center gap-3 border-b border-slate-800/50">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
             <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <h1 className="font-bold text-white tracking-wide">PhishGuard</h1>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <button 
            onClick={() => setActiveTab("inbox")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === "inbox" ? "bg-indigo-600/10 text-indigo-400" : "text-slate-400 hover:bg-slate-800/50"}`}
          >
            <Inbox className="w-5 h-5" />
            <span className="font-medium text-sm">Threat Inbox</span>
          </button>

          <button 
            onClick={() => setActiveTab("analytics")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === "analytics" ? "bg-indigo-600/10 text-indigo-400" : "text-slate-400 hover:bg-slate-800/50"}`}
          >
            <LayoutDashboard className="w-5 h-5" />
            <span className="font-medium text-sm">System Analytics</span>
          </button>

          <button 
            onClick={() => setActiveTab("database")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === "database" ? "bg-indigo-600/10 text-indigo-400" : "text-slate-400 hover:bg-slate-800/50"}`}
          >
            <Database className="w-5 h-5" />
            <span className="font-medium text-sm">Raw Database</span>
          </button>
          
          <button 
            onClick={() => setActiveTab("settings")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === "settings" ? "bg-indigo-600/10 text-indigo-400" : "text-slate-400 hover:bg-slate-800/50"}`}
          >
            <SettingsIcon className="w-5 h-5" />
            <span className="font-medium text-sm">Settings</span>
          </button>
        </nav>
        
        {/* Logout Button at bottom of sidebar */}
        <div className="p-4 border-t border-slate-800/50">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 text-sm font-semibold rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <LogOut size={18} />
            Logout Securely
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto relative z-10 pb-16 md:pb-0">
        <Suspense fallback={<ScreenLoader />}>
          {activeTab === "inbox" ? (
            <InboxView onSelectEmail={setSelectedEmailId} />
          ) : activeTab === "analytics" ? (
            <SystemAnalytics />
          ) : activeTab === "settings" ? (
            <Settings />
          ) : (
            <DatabaseView />
          )}
        </Suspense>
      </main>

      {/* Mobile Bottom Navigation — visible only on small screens */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-slate-900/95 backdrop-blur-md border-t border-slate-800 flex items-center justify-around px-2 py-2">
        <button
          onClick={() => setActiveTab("inbox")}
          className={`flex flex-col items-center gap-1 px-4 py-2 rounded-xl transition-all ${
            activeTab === "inbox" ? "text-indigo-400" : "text-slate-500"
          }`}
        >
          <Inbox className="w-5 h-5" />
          <span className="text-[10px] font-semibold">Inbox</span>
        </button>
        <button
          onClick={() => setActiveTab("analytics")}
          className={`flex flex-col items-center gap-1 px-4 py-2 rounded-xl transition-all ${
            activeTab === "analytics" ? "text-indigo-400" : "text-slate-500"
          }`}
        >
          <LayoutDashboard className="w-5 h-5" />
          <span className="text-[10px] font-semibold">Analytics</span>
        </button>
        <button
          onClick={() => setActiveTab("database")}
          className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all ${
            activeTab === "database" ? "text-indigo-400" : "text-slate-500"
          }`}
        >
          <Database className="w-5 h-5" />
          <span className="text-[10px] font-semibold">Database</span>
        </button>
        <button
          onClick={() => setActiveTab("settings")}
          className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all ${
            activeTab === "settings" ? "text-indigo-400" : "text-slate-500"
          }`}
        >
          <SettingsIcon className="w-5 h-5" />
          <span className="text-[10px] font-semibold">Settings</span>
        </button>
        <button
          onClick={handleLogout}
          className="flex flex-col items-center gap-1 px-4 py-2 rounded-xl transition-all text-slate-500 hover:text-red-400"
        >
          <LogOut className="w-5 h-5" />
          <span className="text-[10px] font-semibold">Logout</span>
        </button>
      </nav>
      </div>
    </ErrorBoundary>
  );
}
