import React from "react";

export default function EmailCard({ email, isSelected, onClick, aiInsights }) {
  // Extract user-friendly sender name, stripping raw email addresses
  const getCleanSender = (fromStr) => {
    if (!fromStr) return "Unknown";
    const match = fromStr.match(/^"?(.*?)"?\s*<.*>$/);
    return match ? match[1] : fromStr;
  };

  // Human-readable relative or short date formatting
  const formatEmailDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
      }
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    } catch {
      return dateStr;
    }
  };

  // Obtain priority class. Unread prioritizations come from backend, read defaults to None
  const priority = aiInsights?.priority || email.final_priority;
  const isUnread = email.read_status === "unread";

  // AI flags
  const isMeeting =
    email.ai_analysis?.is_meeting_request || aiInsights?.is_meeting_request;
  const hasDeadline =
    email.ai_analysis?.has_deadline || aiInsights?.has_deadline;
  const deadlineDate =
    email.ai_analysis?.deadline_date || aiInsights?.deadline_date;

  return (
    <div
      onClick={onClick}
      className={`p-4 border-b border-slate-200 dark:border-slate-800/40 cursor-pointer transition-all duration-150 relative ${
        isSelected
          ? "bg-indigo-600/5 dark:bg-indigo-600/10 border-l-2 border-l-indigo-500"
          : "hover:bg-slate-100/50 dark:hover:bg-slate-800/30 border-l-2 border-l-transparent"
      } ${!isUnread ? "opacity-65" : ""}`}
    >
      {/* Unread indicator dot */}
      {isUnread && (
        <span className="absolute left-1 top-5 h-1.5 w-1.5 rounded-full bg-indigo-500 shadow-sm" />
      )}

      <div className="flex items-center justify-between mb-1">
        <span
          className={`text-xs font-bold truncate max-w-[150px] ${
            isSelected
              ? "text-indigo-600 dark:text-indigo-400"
              : isUnread
                ? "text-slate-800 dark:text-slate-200"
                : "text-slate-500 dark:text-slate-400"
          }`}
        >
          {getCleanSender(email.sender)}
        </span>
        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">
          {formatEmailDate(email.date)}
        </span>
      </div>

      <div
        className={`text-xs truncate mb-1 ${
          isUnread
            ? "font-bold text-slate-700 dark:text-slate-300"
            : "text-slate-500 dark:text-slate-400"
        }`}
      >
        {email.subject}
      </div>

      <p className="text-[11px] text-slate-500 dark:text-slate-500 line-clamp-2 leading-relaxed">
        {email.snippet || "(No description)"}
      </p>

      {/* Badges footer */}
      <div className="mt-2.5 flex items-center justify-between">
        {/* Source Account Badge */}
        {email.account_email ? (
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 max-w-[120px] truncate border border-slate-200/50 dark:border-slate-700/30">
            {email.account_email.split("@")[0]}
          </span>
        ) : (
          <span />
        )}

        <div className="flex items-center space-x-1.5">
          {/* Meeting Request Indicator */}
          {isMeeting && (
            <span
              className="inline-flex items-center px-1.5 py-0.5 rounded bg-blue-500/10 dark:bg-blue-500/10 border border-blue-500/20 text-[9px] font-bold text-blue-600 dark:text-blue-400 shadow-sm"
              title="Meeting Request"
            >
              📅 Call
            </span>
          )}

          {/* Deadline warning indicator */}
          {hasDeadline && (
            <span
              className="inline-flex items-center px-1.5 py-0.5 rounded bg-rose-500/10 dark:bg-rose-500/10 border border-rose-500/20 text-[9px] font-bold text-rose-600 dark:text-rose-400 shadow-sm"
              title={
                deadlineDate ? `Deadline: ${deadlineDate}` : "Deadline warning"
              }
            >
              ⏳ {deadlineDate ? deadlineDate : "Due"}
            </span>
          )}

          {/* Priority tag */}
          {priority && (
            <span
              className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold tracking-wide uppercase ${
                priority === "Critical"
                  ? "bg-rose-500 text-white dark:bg-rose-500/15 dark:text-rose-400 border border-rose-500/35"
                  : priority === "High"
                    ? "bg-red-500/10 text-red-500 dark:text-red-400 border border-red-500/20"
                    : priority === "Medium"
                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                      : "bg-slate-200 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-300 dark:border-slate-700/50"
              }`}
            >
              {priority}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
