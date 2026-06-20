import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AUTH_LOGIN_URL } from "@/config";

export default function Login() {
  const [searchParams] = useSearchParams();
  const [error, setError] = useState(null);

  useEffect(() => {
    const errorParam = searchParams.get("error");
    if (errorParam) {
      setError(decodeURIComponent(errorParam));
    }
  }, [searchParams]);

  const handleLogin = () => {
    window.location.href = AUTH_LOGIN_URL;
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#0f172a] via-[#090d16] to-[#0f172a] px-6 py-12 relative overflow-hidden">
      {/* Subtle ambient blur highlights */}
      <div className="absolute top-1/4 left-1/4 h-[300px] w-[300px] rounded-full bg-indigo-500/10 blur-[80px]" />
      <div className="absolute bottom-1/4 right-1/4 h-[350px] w-[350px] rounded-full bg-violet-500/10 blur-[100px]" />

      <div className="w-full max-w-md space-y-8 rounded-2xl border border-slate-800/60 bg-slate-900/40 p-8 backdrop-blur-xl shadow-2xl relative z-10">
        <div className="text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-400 mb-4 shadow-inner">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-6 h-6"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.59 14.37a6 6 0 0 1-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 0 0 6.16-12.12A14.98 14.98 0 0 0 9.631 8.41m5.96 5.96a14.956 14.956 0 0 1-12.067-.539m12.067.539-1.38-1.38m2.76 0-1.38 1.38M12.085 10.255V8.59m0 8.016v-1.666M8.59 12.085H6.924m8.016 0h-1.666"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            AeroInbox
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            AI-Powered Executive Assistant for Gmail
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400 text-center animate-pulse">
            <span className="font-semibold">Authentication Error:</span> {error}
          </div>
        )}

        <div className="mt-8 space-y-6">
          <p className="text-xs text-slate-500 text-center leading-relaxed">
            AeroInbox securely analyzes your unread emails to extract executive
            summaries, assign priority levels, and draft ready-to-send
            professional responses.
          </p>

          <button
            onClick={handleLogin}
            className="group relative flex w-full justify-center rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm font-medium text-white transition-all duration-200 hover:bg-slate-800 hover:border-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          >
            <span className="absolute inset-y-0 left-0 flex items-center pl-3">
              <svg
                className="h-5 w-5 text-slate-400 group-hover:text-indigo-400 transition-colors"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12.24 10.285V13.4h6.887C18.2 15.614 15.645 18 12.24 18c-3.86 0-7-3.14-7-7s3.14-7 7-7c1.7 0 3.25.61 4.47 1.625l2.437-2.437C17.312 1.596 14.93 1 12.24 1c-5.523 0-10 4.477-10 10s4.477 10 10 10c5.783 0 9.62-4.053 9.62-9.79 0-.66-.06-1.29-.18-1.925H12.24Z" />
              </svg>
            </span>
            Connect with Gmail
          </button>
        </div>

        <div className="pt-4 border-t border-slate-800/40 text-center">
          <span className="text-xs text-slate-600">
            Uses read-only Gmail access. Your data remains fully secure.
          </span>
        </div>
      </div>
    </div>
  );
}
