import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AUTH_CALLBACK_URL } from "@/config";

export default function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const accessToken = searchParams.get("access_token");
    const email = searchParams.get("email");
    const error = searchParams.get("error");
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (error) {
      navigate(`/?error=${encodeURIComponent(error)}`);
      return;
    }

    if (code) {
      // Redirect to backend callback to exchange code for session token
      window.location.href = `${AUTH_CALLBACK_URL}?code=${code}&state=${state || "new"}`;
      return;
    }

    if (accessToken) {
      // 1. Manage active session (masking session_id inside google_access_token for backward compatibility)
      localStorage.setItem("aeroinbox_session_id", accessToken);
      localStorage.setItem("google_access_token", accessToken);

      if (email) {
        localStorage.setItem("user_email", email);
      }

      // 2. Manage multiple connected accounts list - ONLY emails, no raw credentials in browser
      let accounts;
      try {
        const stored = localStorage.getItem("aeroinbox_accounts");
        accounts = stored ? JSON.parse(stored) : [];
      } catch {
        accounts = [];
      }
      if (!Array.isArray(accounts)) {
        accounts = [];
      }

      const existingIdx = accounts.findIndex((a) => a.email === email);
      const newAccountObj = {
        email: email || "unknown@gmail.com",
      };

      if (existingIdx > -1) {
        accounts[existingIdx] = newAccountObj;
      } else {
        accounts.push(newAccountObj);
      }
      localStorage.setItem("aeroinbox_accounts", JSON.stringify(accounts));

      navigate("/dashboard");
    } else {
      navigate("/?error=No%20credentials%20received%20from%20Google");
    }
  }, [searchParams, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#0f172a] via-[#090d16] to-[#0f172a] text-white">
      <div className="text-center space-y-4">
        <div className="relative inline-flex h-10 w-10">
          <div className="absolute inset-0 rounded-full border-4 border-indigo-500/20"></div>
          <div className="absolute inset-0 rounded-full border-4 border-indigo-500 border-t-transparent animate-spin"></div>
        </div>
        <p className="text-sm text-slate-400 font-medium">
          Securing your session and configuring assistant...
        </p>
      </div>
    </div>
  );
}
