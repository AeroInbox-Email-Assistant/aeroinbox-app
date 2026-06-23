import React from "react";
import PropTypes from "prop-types";
import { useNavigate } from "react-router-dom";

export default function Sidebar({
  onOpenRules,
  activeSection,
  setActiveSection,
}) {
  const navigate = useNavigate();
  const email = localStorage.getItem("user_email") || "executive@gmail.com";

  const handleLogout = () => {
    localStorage.removeItem("google_access_token");
    localStorage.removeItem("google_refresh_token");
    localStorage.removeItem("user_email");
    localStorage.removeItem("aeroinbox_accounts");
    navigate("/");
  };

  return (
    <aside className="w-64 border-r border-slate-200 dark:border-slate-800/60 bg-slate-50 dark:bg-[#090d16]/80 backdrop-blur-xl flex flex-col justify-between p-6 transition-colors duration-150">
      <div className="space-y-8">
        {/* Brand/Logo */}
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-indigo-600/15 border border-indigo-500/30 flex items-center justify-center text-indigo-500 dark:text-indigo-400 shadow-inner">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.59 14.37a6 6 0 0 1-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 0 0 6.16-12.12A14.98 14.98 0 0 0 9.631 8.41m5.96 5.96a14.956 14.956 0 0 1-12.067-.539m12.067.539-1.38-1.38m2.76 0-1.38 1.38M12.085 10.255V8.59m0 8.016v-1.666M8.59 12.085H6.924m8.016 0h-1.666"
              />
            </svg>
          </div>
          <span className="text-lg font-bold tracking-tight text-slate-800 dark:text-white">
            AeroInbox
          </span>
        </div>

        {/* Sidebar Nav */}
        <nav className="space-y-1.5">
          <button
            onClick={() => setActiveSection("inbox")}
            className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg border text-left font-medium text-sm transition-all cursor-pointer ${
              activeSection === "inbox"
                ? "bg-indigo-600/10 border-indigo-500/20 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-800/30"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75"
              />
            </svg>
            <span>Executive Inbox</span>
          </button>

          <button
            onClick={() => setActiveSection("spam")}
            className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg border text-left font-medium text-sm transition-all cursor-pointer ${
              activeSection === "spam"
                ? "bg-indigo-600/10 border-indigo-500/20 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-800/30"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m0-10.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.57-.598-3.75h-.152c-3.196 0-6.1-1.249-8.25-3.286Zm0 13.036h.008v.008H12v-.008Z"
              />
            </svg>
            <span>Important Spam</span>
          </button>

          <button
            onClick={() => setActiveSection("meetings")}
            className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg border text-left font-medium text-sm transition-all cursor-pointer ${
              activeSection === "meetings"
                ? "bg-indigo-600/10 border-indigo-500/20 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-800/30"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
              />
            </svg>
            <span>Meetings Calendar</span>
          </button>

          <button
            onClick={() => setActiveSection("tasks")}
            className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg border text-left font-medium text-sm transition-all cursor-pointer ${
              activeSection === "tasks"
                ? "bg-indigo-600/10 border-indigo-500/20 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-600 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-800/30"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12h3.75M9 15h3.375M9 9h3.375m-.1 3.248a3.75 3.75 0 1 1 0-5.996m0 5.996a3.75 3.75 0 0 1 0-5.996M12 18.75a.75.75 0 1 1 0-1.5.75.75 0 0 1 0 1.5Z"
              />
            </svg>
            <span>Tasks Board</span>
          </button>

          <button
            onClick={onOpenRules}
            className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg border border-transparent text-left font-medium text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-800/30 transition-all cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.645-.869l.214-1.28Z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
            </svg>
            <span>Rules Settings</span>
          </button>
        </nav>
      </div>

      {/* Account Info and Logout */}
      <div className="border-t border-slate-200 dark:border-slate-800/60 pt-6 space-y-4">
        <div className="flex flex-col px-3">
          <span className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-wider">
            Active Mailbox
          </span>
          <span
            className="text-xs text-slate-700 dark:text-slate-300 truncate font-semibold mt-1"
            title={email}
          >
            {email}
          </span>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center space-x-2.5 px-3 py-2 text-sm text-slate-500 dark:text-slate-400 hover:text-red-500 rounded-lg hover:bg-red-500/5 hover:border hover:border-red-500/10 transition-all cursor-pointer font-medium"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="w-4 h-4"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75"
            />
          </svg>
          <span>Disconnect All</span>
        </button>
      </div>
    </aside>
  );
}

Sidebar.propTypes = {
  onOpenRules: PropTypes.func.isRequired,
  activeSection: PropTypes.string.isRequired,
  setActiveSection: PropTypes.func.isRequired,
};
