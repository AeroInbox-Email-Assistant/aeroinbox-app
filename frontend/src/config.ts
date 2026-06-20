/**
 * Centralized Application Configuration
 * Resolves settings from environment variables and exports constants for API access.
 */

// Resolves base API URL, defaulting to relative routing for dev proxy / production single domain
export const API_BASE_URL: string = import.meta.env.VITE_API_URL || "";

// Centralized endpoints
export const AUTH_LOGIN_URL = `${API_BASE_URL}/auth/login`;
export const AUTH_CALLBACK_URL = `${API_BASE_URL}/auth/callback`;
export const AUTH_REFRESH_URL = `${API_BASE_URL}/auth/refresh`;
export const EMAILS_UNREAD_URL = `${API_BASE_URL}/emails/unread`;
export const MEETINGS_URL = `${API_BASE_URL}/meetings`;
