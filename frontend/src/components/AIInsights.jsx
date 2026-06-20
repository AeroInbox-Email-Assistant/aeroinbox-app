import React, { useState, useEffect } from "react";

export default function AIInsights({ insights, isLoading, folder }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setCopied(false);
  }, [insights]);

  const handleCopy = () => {
    if (insights?.reply) {
      navigator.clipboard.writeText(insights.reply);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 space-y-4">
        {/* Elegant loading ring */}
        <div className="relative inline-flex h-10 w-10">
          <div className="absolute inset-0 rounded-full border-4 border-indigo-500/10"></div>
          <div className="absolute inset-0 rounded-full border-4 border-indigo-500 border-t-transparent animate-spin"></div>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
          AI is generating summaries & drafts...
        </p>
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-3">
        <div className="h-10 w-10 rounded-full bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-center text-slate-400 dark:text-slate-500 mb-1">
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
              d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
            />
          </svg>
        </div>
        <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
          Select an email to view AI Insights
        </p>
        <p className="text-[10px] text-slate-400 dark:text-slate-600 max-w-[200px] leading-relaxed">
          The assistant will automatically extract summary points, detect email
          priority, and suggest a professional draft reply.
        </p>
      </div>
    );
  }

  const {
    summary,
    priority,
    reply,
    is_spam_false_positive,
    spam_analysis_reason,
    is_meeting_request,
    has_deadline,
    deadline_date,
  } = insights;

  return (
    <div className="h-full flex flex-col p-6 space-y-5 overflow-y-auto border-l border-slate-200 dark:border-slate-800/60 bg-slate-50/50 dark:bg-[#090d16]/40 transition-all duration-150">
      {/* Title */}
      <div className="border-b border-slate-200 dark:border-slate-800/60 pb-3 flex items-center space-x-2">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className="w-4 h-4 text-indigo-500 dark:text-indigo-400"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
          />
        </svg>
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          AI Co-Pilot Insights
        </h3>
      </div>

      {/* False Positive Spam Indicator Alert */}
      {folder === "SPAM" && is_spam_false_positive && (
        <div className="p-3.5 rounded-lg border border-amber-500/25 bg-amber-500/5 text-xs text-amber-800 dark:text-amber-400 leading-relaxed font-semibold">
          <span className="text-base mr-1">⚠️</span>
          <strong>Spam False-Positive:</strong> Gemini has flagged this as an
          important legitimate message!
          {spam_analysis_reason && (
            <p className="mt-1 font-medium text-slate-600 dark:text-slate-300 text-[11px]">
              Reason: {spam_analysis_reason}
            </p>
          )}
        </div>
      )}

      {/* Meeting Request Badge */}
      {is_meeting_request && (
        <div className="p-3 rounded-lg border border-blue-500/20 bg-blue-500/5 text-xs text-blue-800 dark:text-blue-400 leading-relaxed font-semibold flex items-center space-x-2">
          <span>📅</span>
          <span>
            <strong>Meeting Invitation:</strong> Sender is requesting a call or
            schedule.
          </span>
        </div>
      )}

      {/* Action Deadline Warning Alert */}
      {has_deadline && (
        <div className="p-3 rounded-lg border border-rose-500/20 bg-rose-500/5 text-xs text-rose-800 dark:text-rose-400 leading-relaxed font-semibold flex items-center space-x-2">
          <span>⏳</span>
          <span>
            <strong>Deadline Alert:</strong> Action required{" "}
            {deadline_date ? `by: ${deadline_date}` : "promptly"}.
          </span>
        </div>
      )}

      {/* Priority */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
          Priority Level
        </span>
        <div>
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase ${
              priority === "Critical"
                ? "bg-rose-500 text-white dark:bg-rose-500/15 dark:text-rose-400 border border-rose-500/35"
                : priority === "High"
                  ? "bg-red-500/10 text-red-500 dark:text-red-400 border border-red-500/20"
                  : priority === "Medium"
                    ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                    : "bg-slate-200 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-350 dark:border-slate-700/50"
            }`}
          >
            {priority}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
          Executive Summary
        </span>
        <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950/30 text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
          {summary}
        </div>
      </div>

      {/* Reply suggestion */}
      <div className="space-y-3 flex-1 flex flex-col justify-between">
        <div className="space-y-1.5 flex-1 flex flex-col">
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            Suggested Reply
          </span>
          <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950/50 text-xs text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-line flex-1 min-h-[140px] font-sans">
            {reply}
          </div>
        </div>

        <button
          onClick={handleCopy}
          className={`w-full py-2.5 rounded-lg text-xs font-bold transition-all duration-200 flex items-center justify-center space-x-2 border cursor-pointer ${
            copied
              ? "bg-emerald-500/15 border-emerald-500/20 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20"
              : "bg-indigo-600 border-indigo-500/50 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-500/10"
          }`}
        >
          {copied ? (
            <>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
                className="w-3.5 h-3.5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m4.5 12.75 6 6 9-13.5"
                />
              </svg>
              <span>Copied!</span>
            </>
          ) : (
            <>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-3.5 h-3.5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H5.25m10.5 8.25V1.875C15.75 1.254 15.246.75 14.625.75h-9.75c-.621 0-1.125.504-1.125 1.125v15c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125Z"
                />
              </svg>
              <span>Copy Response</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
