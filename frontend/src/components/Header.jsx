import React, { useState } from "react";
import PropTypes from "prop-types";
import { AUTH_LOGIN_URL } from "@/config";

function getNotifTypeClass(type) {
  switch (type) {
    case "Critical":
      return "bg-red-500/10 text-red-500 dark:text-red-400";
    case "Spam Alert":
      return "bg-amber-500/10 text-amber-600 dark:text-amber-400";
    case "Meeting":
      return "bg-blue-500/10 text-blue-600 dark:text-blue-400";
    default:
      return "bg-indigo-500/10 text-indigo-500 dark:text-indigo-400";
  }
}

export default function Header({
  onRefresh,
  isLoading,
  accounts = [],
  activeEmail,
  onSwitchAccount,
  notifications = [],
  onSelectEmail,
  onSearch = () => {},
  onClearSearch = () => {},
}) {
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "dark");
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [notifMenuOpen, setNotifMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Toggle light/dark theme
  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  const handleAddAccount = () => {
    const sessionId =
      localStorage.getItem("aeroinbox_session_id") ||
      localStorage.getItem("google_access_token");
    if (sessionId) {
      globalThis.location.href = `${AUTH_LOGIN_URL}?session_id=${sessionId}`;
    } else {
      globalThis.location.href = AUTH_LOGIN_URL;
    }
  };

  return (
    <header className="h-16 border-b border-slate-200 dark:border-slate-800/60 bg-white dark:bg-[#090d16]/40 backdrop-blur-xl px-8 flex items-center justify-between z-20 transition-colors duration-150">
      <div className="flex items-center space-x-4">
        <h2 className="text-lg font-bold tracking-tight text-slate-800 dark:text-white">
          Executive Inbox
        </h2>
        <span className="flex items-center space-x-1.5 bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-0.5 rounded-full text-[10px] font-bold text-emerald-600 dark:text-emerald-400 shadow-sm">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
          </span>
          <span>AI Co-Pilot Active</span>
        </span>
      </div>

      {/* Interactive Search Bar */}
      <div className="flex-1 max-w-md mx-6">
        <div className="relative w-full">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            <svg
              className="w-4 h-4 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </span>
          <input
            type="text"
            placeholder="Search mailbox (press Enter)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                onSearch(searchQuery);
              }
            }}
            className="w-full pl-10 pr-8 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#0c1220]/50 text-slate-750 dark:text-slate-300 outline-none focus:border-indigo-500 transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery("");
                onClearSearch();
              }}
              className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600 dark:hover:text-white cursor-pointer"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Theme Switcher Button */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-white transition-all cursor-pointer"
          title={
            theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"
          }
        >
          {theme === "dark" ? (
            // Sun Icon
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 3v2.25m0 13.5V21M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M3 12h2.25m13.5 0H21M5.75 12a6.25 6.25 0 1 1 12.5 0 6.25 6.25 0 0 1-12.5 0Z"
              />
            </svg>
          ) : (
            // Moon Icon
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21.75 12.812c.002.032.003.064.003.096a8.807 8.807 0 0 1-8.807 8.807c-4.864 0-8.807-3.943-8.807-8.807 0-4.864 3.943-8.807 8.807-8.807.032 0 .064.001.096.003a9.979 9.979 0 0 0-.102 1.401c0 5.518 4.475 9.993 9.993 9.993 1.353 0 2.65-.268 3.829-.757a8.775 8.775 0 0 1-3.112 1.405Z"
              />
            </svg>
          )}
        </button>

        {/* Notifications Center */}
        <div className="relative">
          <button
            onClick={() => {
              setNotifMenuOpen(!notifMenuOpen);
              setAccountMenuOpen(false);
            }}
            className="relative p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-white transition-all cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
              />
            </svg>
            {notifications.length > 0 && (
              <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-red-500 text-[9px] font-bold text-white flex items-center justify-center animate-bounce shadow">
                {notifications.length}
              </span>
            )}
          </button>

          {notifMenuOpen && (
            <div className="absolute right-0 mt-2.5 w-80 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] shadow-2xl p-2 z-50">
              <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center mb-1">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  Alert Center
                </span>
                <span className="text-[10px] text-slate-400 font-medium">
                  {notifications.length} Active
                </span>
              </div>
              <div className="max-h-72 overflow-y-auto space-y-1">
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-xs text-slate-400 italic">
                    No urgent notifications.
                  </div>
                ) : (
                  notifications.map((n) => (
                    <button
                      type="button"
                      key={`notif-${n.type}-${n.subject}`}
                      onClick={() => {
                        onSelectEmail(n.email);
                        setNotifMenuOpen(false);
                      }}
                      className="w-full p-2.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/50 cursor-pointer text-left transition-colors"
                    >
                      <div className="flex justify-between items-start mb-0.5">
                        <span
                          className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded-full ${getNotifTypeClass(n.type)}`}
                        >
                          {n.type}
                        </span>
                        <span className="text-[9px] text-slate-400 font-medium">
                          Just now
                        </span>
                      </div>
                      <p className="text-[11px] font-bold text-slate-700 dark:text-slate-300 truncate">
                        {n.subject}
                      </p>
                      <p className="text-[10px] text-slate-400 truncate">
                        From: {n.sender}
                      </p>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Multi-Account Selector */}
        <div className="relative">
          <button
            onClick={() => {
              setAccountMenuOpen(!accountMenuOpen);
              setNotifMenuOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-slate-800/30 transition-all cursor-pointer"
          >
            <div className="h-4 w-4 rounded-full bg-indigo-500 text-white flex items-center justify-center text-[9px] font-bold shadow-inner">
              {activeEmail ? activeEmail.substring(0, 1).toUpperCase() : "U"}
            </div>
            <span className="max-w-[120px] truncate">
              {activeEmail || "All Accounts (Unified)"}
            </span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-3 h-3 text-slate-400"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m19.5 8.25-7.5 7.5-7.5-7.5"
              />
            </svg>
          </button>

          {accountMenuOpen && (
            <div className="absolute right-0 mt-2.5 w-64 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0c121e] shadow-2xl p-2 z-50 transition-all">
              <div className="px-3 py-1.5 text-[10px] text-slate-400 font-bold uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 mb-1">
                Connected Accounts
              </div>
              <div className="space-y-1">
                <button
                  onClick={() => {
                    onSwitchAccount(null);
                    setAccountMenuOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2.5 transition-colors cursor-pointer ${
                    activeEmail === null
                      ? "bg-indigo-600/10 text-indigo-600 dark:text-indigo-400"
                      : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/50"
                  }`}
                >
                  <div className="h-4 w-4 rounded-full bg-slate-400 text-white flex items-center justify-center text-[8px] font-bold">
                    ★
                  </div>
                  <span>Unified Inbox (All)</span>
                </button>

                {accounts.map((acc) => (
                  <button
                    key={acc.email}
                    onClick={() => {
                      onSwitchAccount(acc.email);
                      setAccountMenuOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold flex items-center space-x-2.5 transition-colors cursor-pointer ${
                      activeEmail === acc.email
                        ? "bg-indigo-600/10 text-indigo-600 dark:text-indigo-400"
                        : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/50"
                    }`}
                  >
                    <div className="h-4 w-4 rounded-full bg-indigo-500 text-white flex items-center justify-center text-[8px] font-bold">
                      {acc.email.substring(0, 1).toUpperCase()}
                    </div>
                    <span className="truncate flex-1">{acc.email}</span>
                  </button>
                ))}
              </div>
              <div className="border-t border-slate-100 dark:border-slate-800 mt-2 pt-2">
                <button
                  onClick={() => {
                    handleAddAccount();
                    setAccountMenuOpen(false);
                  }}
                  className="w-full flex items-center justify-center space-x-1.5 px-3 py-2 text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition-colors cursor-pointer"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                    className="w-3.5 h-3.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 4.5v15m7.5-7.5h-15"
                    />
                  </svg>
                  <span>Connect Account</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Sync Button */}
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-white disabled:opacity-40 transition-all cursor-pointer shadow-inner"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
            className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
            />
          </svg>
          <span>{isLoading ? "Syncing..." : "Sync Mail"}</span>
        </button>
      </div>
    </header>
  );
}

Header.propTypes = {
  onRefresh: PropTypes.func.isRequired,
  isLoading: PropTypes.bool,
  accounts: PropTypes.arrayOf(
    PropTypes.shape({
      email: PropTypes.string.isRequired,
      access_token: PropTypes.string,
      refresh_token: PropTypes.string,
    }),
  ),
  activeEmail: PropTypes.string,
  onSwitchAccount: PropTypes.func.isRequired,
  notifications: PropTypes.arrayOf(
    PropTypes.shape({
      type: PropTypes.string,
      subject: PropTypes.string,
      sender: PropTypes.string,
      email: PropTypes.object,
    }),
  ),
  onSelectEmail: PropTypes.func.isRequired,
  onSearch: PropTypes.func,
  onClearSearch: PropTypes.func,
};
