import React from "react";
import PropTypes from "prop-types";

function getPriorityClass(priority) {
  switch (priority) {
    case "Critical":
      return "bg-rose-500 text-white dark:bg-rose-500/15 dark:text-rose-400 border border-rose-500/35";
    case "High":
      return "bg-red-500/10 text-red-500 dark:text-red-400 border border-red-500/20";
    case "Medium":
      return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20";
    default:
      return "bg-slate-200 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-300 dark:border-slate-700/50";
  }
}

function getSenderClass(isSelected, isUnread) {
  if (isSelected) {
    return "text-indigo-600 dark:text-indigo-400";
  }
  if (isUnread) {
    return "text-slate-800 dark:text-slate-200";
  }
  return "text-slate-500 dark:text-slate-400";
}

export default function EmailCard({ email, isSelected, onClick, aiInsights }) {
  // Extract user-friendly sender name, stripping raw email addresses
  const getCleanSender = (fromStr) => {
    if (!fromStr) return "Unknown";
    const angleIdx = fromStr.indexOf("<");
    if (angleIdx !== -1) {
      const namePart = fromStr.substring(0, angleIdx).trim();
      return namePart.replace(/^"|"$/g, "").trim() || fromStr;
    }
    return fromStr;
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
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left p-4 border-b border-slate-200 dark:border-slate-800/40 cursor-pointer transition-all duration-150 relative ${
        isSelected
          ? "bg-indigo-600/5 dark:bg-indigo-600/10 border-l-2 border-l-indigo-500"
          : "hover:bg-slate-100/50 dark:hover:bg-slate-800/30 border-l-2 border-l-transparent"
      } ${isUnread ? "" : "opacity-65"}`}
    >
      {/* Unread indicator dot */}
      {isUnread && (
        <span className="absolute left-1 top-5 h-1.5 w-1.5 rounded-full bg-indigo-500 shadow-sm" />
      )}

      <div className="flex items-center justify-between mb-1">
        <span
          className={`text-xs font-bold truncate max-w-[150px] ${getSenderClass(isSelected, isUnread)}`}
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
              ⏳ {deadlineDate || "Due"}
            </span>
          )}

          {/* Priority tag */}
          {priority && (
            <span
              className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold tracking-wide uppercase ${getPriorityClass(priority)}`}
            >
              {priority}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

EmailCard.propTypes = {
  email: PropTypes.shape({
    id: PropTypes.string,
    sender: PropTypes.string,
    date: PropTypes.string,
    subject: PropTypes.string,
    snippet: PropTypes.string,
    account_email: PropTypes.string,
    read_status: PropTypes.string,
    final_priority: PropTypes.string,
    folder: PropTypes.string,
    ai_analysis: PropTypes.shape({
      is_meeting_request: PropTypes.bool,
      has_deadline: PropTypes.bool,
      deadline_date: PropTypes.string,
    }),
  }).isRequired,
  isSelected: PropTypes.bool,
  onClick: PropTypes.func.isRequired,
  aiInsights: PropTypes.shape({
    priority: PropTypes.string,
    is_meeting_request: PropTypes.bool,
    has_deadline: PropTypes.bool,
    deadline_date: PropTypes.string,
  }),
};
