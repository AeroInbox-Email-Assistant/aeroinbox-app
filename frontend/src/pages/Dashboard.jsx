import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import EmailCard from "../components/EmailCard";
import AIInsights from "../components/AIInsights";

export default function Dashboard() {
  const navigate = useNavigate();
  const [emails, setEmails] = useState([]);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [aiInsightsCache, setAiInsightsCache] = useState({});
  const [aiLoading, setAiLoading] = useState(false);
  const [activeSection, setActiveSection] = useState("inbox"); // 'inbox' or 'spam'
  
  // Search state
  const [isSearchActive, setIsSearchActive] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  // Reminders alert state
  const [activeReminder, setActiveReminder] = useState(null);

  // Accounts management
  const [accounts, setAccounts] = useState([]);
  const [activeEmailFilter, setActiveEmailFilter] = useState(null); // null means Unified (All)
  const [refreshedTokensCount, setRefreshedTokensCount] = useState(0);

  // Filters
  const [showAll, setShowAll] = useState(false); // false: show unread only, true: show all
  const [selectedPriorityFilter, setSelectedPriorityFilter] = useState("All"); // 'All', 'Critical', 'High', 'Medium', 'Low'

  // Notifications
  const [notifications, setNotifications] = useState([]);

  // Rules Settings Dialog state
  const [isRulesOpen, setIsRulesOpen] = useState(false);
  const [rulesConfig, setRulesConfig] = useState({
    vip_senders: [],
    domains: [],
    keywords: [],
    custom_senders: [],
    custom_keywords: [],
    preference_boosts: { inbox_boost: 0, spam_boost: 0 },
  });
  const [newCustomSender, setNewCustomSender] = useState("");
  const [newCustomKeyword, setNewCustomKeyword] = useState("");
  const [isSavingRules, setIsSavingRules] = useState(false);

  // Meetings Calendar state
  const [meetingsDashboard, setMeetingsDashboard] = useState({
    today: [],
    tomorrow: [],
    upcoming: [],
    missed: [],
  });
  const [pendingMeetings, setPendingMeetings] = useState([]);
  const [meetingsLoading, setMeetingsLoading] = useState(false);

  // Task Board state
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");
  const [reminderInterval, setReminderInterval] = useState(2);
  const [activeTaskReminder, setActiveTaskReminder] = useState(null);

  // 30-Second Reminders Polling Loop (Meetings & Tasks)
  useEffect(() => {
    const pollReminders = async () => {
      const userEmail = activeEmailFilter || localStorage.getItem("user_email") || "executive@gmail.com";
      
      // 1. Poll meetings
      try {
        const response = await API.get("/meetings/reminders/pending", {
          params: { user_id: userEmail }
        });
        const pendingReminders = response.data || [];
        if (pendingReminders.length > 0) {
          setActiveReminder(pendingReminders[0]);
        } else {
          setActiveReminder(null);
        }
      } catch (err) {
        console.error("Failed to poll pending reminders:", err);
      }

      // 2. Poll tasks
      try {
        const response = await API.get("/tasks/reminders/pending", {
          params: { user_id: userEmail }
        });
        const pendingTasks = response.data || [];
        if (pendingTasks.length > 0) {
          setActiveTaskReminder(pendingTasks);
        } else {
          setActiveTaskReminder(null);
        }
      } catch (err) {
        console.error("Failed to poll pending task reminders:", err);
      }
    };

    pollReminders();
    const interval = setInterval(pollReminders, 30000);
    return () => clearInterval(interval);
  }, [activeEmailFilter]);

  const handleAcknowledgeReminder = async (meetingId) => {
    try {
      await API.post(`/meetings/reminders/${meetingId}/acknowledge`);
      setActiveReminder(null);
      fetchMeetings();
    } catch (err) {
      console.error("Failed to acknowledge reminder:", err);
    }
  };

  const handleSearch = async (query) => {
    if (!query || !query.trim()) {
      handleClearSearch();
      return;
    }
    setIsSearching(true);
    setIsSearchActive(true);
    setError(null);
    try {
      const response = await API.get("/emails/search", {
        params: { q: query.trim() }
      });
      const results = response.data?.emails || [];
      setSearchResults(results);
      if (results.length > 0) {
        setSelectedEmail(results[0]);
      } else {
        setSelectedEmail(null);
      }
    } catch (err) {
      console.error("Search failed:", err);
      setError("Search failed to execute. Please check query syntax.");
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearSearch = () => {
    setIsSearchActive(false);
    setSearchResults([]);
    const defaultList = getFilteredEmails(emails);
    if (defaultList.length > 0) {
      setSelectedEmail(defaultList[0]);
    } else {
      setSelectedEmail(null);
    }
  };

  // Load connected accounts from local storage
  const loadAccounts = () => {
    let list = [];
    try {
      const stored = localStorage.getItem("aeroinbox_accounts");
      list = stored ? JSON.parse(stored) : [];
    } catch (e) {
      list = [];
    }

    // Backward compatibility check
    const legacyToken = localStorage.getItem("google_access_token");
    const legacyEmail = localStorage.getItem("user_email");
    const legacyRefresh = localStorage.getItem("google_refresh_token") || "";

    if (list.length === 0 && legacyToken && legacyEmail) {
      const defaultAcc = {
        email: legacyEmail,
        access_token: legacyToken,
        refresh_token: legacyRefresh,
      };
      list = [defaultAcc];
      localStorage.setItem("aeroinbox_accounts", JSON.stringify(list));
    }
    setAccounts(list);
    return list;
  };

  const fetchEmails = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const list = loadAccounts();
      if (list.length === 0) {
        navigate("/");
        return;
      }

      // API request to post accounts and retrieve prioritized emails
      const response = await API.post("/emails/unread", {
        accounts: list,
        include_read: showAll,
      });

      const fetchedEmails = response.data?.emails || [];
      setEmails(fetchedEmails);

      // Pre-populate the AI insights cache from the fetched emails' bulk analyses
      const prePopulatedCache = {};
      fetchedEmails.forEach((email) => {
        if (email.ai_analysis) {
          prePopulatedCache[email.id] = email.ai_analysis;
        }
      });
      setAiInsightsCache(prePopulatedCache);

      // Generate in-app notifications from unread emails
      const newNotifs = [];
      fetchedEmails.forEach((email) => {
        if (email.read_status === "unread") {
          if (email.final_priority === "Critical") {
            newNotifs.push({
              type: "Critical",
              subject: email.subject,
              sender: email.sender,
              email: email,
            });
          }
          if (
            email.folder === "SPAM" &&
            email.ai_analysis?.is_spam_false_positive
          ) {
            newNotifs.push({
              type: "Spam Alert",
              subject: email.subject,
              sender: email.sender,
              email: email,
            });
          } else if (email.ai_analysis?.is_meeting_request) {
            newNotifs.push({
              type: "Meeting",
              subject: email.subject,
              sender: email.sender,
              email: email,
            });
          }
        }
      });
      setNotifications(newNotifs);

      // Auto-select the first email from the filtered view
      const firstEmail = getFilteredEmails(fetchedEmails)[0];
      if (firstEmail) {
        setSelectedEmail(firstEmail);
      } else {
        setSelectedEmail(null);
      }
    } catch (err) {
      console.error("Error fetching emails:", err);
      const errMsg =
        err.response?.data?.detail || err.message || "Please try again.";
      setError(`Failed to retrieve emails: ${errMsg}`);
    } finally {
      setIsLoading(false);
      fetchMeetings();
    }
  };

  const fetchMeetings = async () => {
    const userEmail =
      activeEmailFilter ||
      localStorage.getItem("user_email") ||
      "executive@gmail.com";
    setMeetingsLoading(true);
    try {
      const [dashRes, pendRes] = await Promise.allSettled([
        API.get("/meetings/dashboard", { params: { user_id: userEmail } }),
        API.get("/meetings/pending", { params: { user_id: userEmail } }),
      ]);

      if (
        dashRes.status === "fulfilled" &&
        dashRes.value?.data &&
        typeof dashRes.value.data === "object" &&
        !dashRes.value.data.detail
      ) {
        setMeetingsDashboard(dashRes.value.data);
      } else {
        console.error(
          "Error or invalid data in meetings dashboard:",
          dashRes.status === "fulfilled" ? dashRes.value.data : dashRes.reason,
        );
        setMeetingsDashboard({
          today: [],
          tomorrow: [],
          upcoming: [],
          missed: [],
        });
      }

      if (
        pendRes.status === "fulfilled" &&
        Array.isArray(pendRes.value?.data)
      ) {
        setPendingMeetings(pendRes.value.data);
      } else {
        console.error(
          "Error or invalid data in pending meetings:",
          pendRes.status === "fulfilled" ? pendRes.value.data : pendRes.reason,
        );
        setPendingMeetings([]);
      }
    } catch (err) {
      console.error("Error fetching meetings:", err);
      setMeetingsDashboard({
        today: [],
        tomorrow: [],
        upcoming: [],
        missed: [],
      });
      setPendingMeetings([]);
    } finally {
      setMeetingsLoading(false);
    }
  };

  const handleConfirmMeeting = async (meetingId) => {
    try {
      await API.post(`/meetings/${meetingId}/confirm`);
      await fetchMeetings();
    } catch (err) {
      console.error("Failed to confirm meeting:", err);
    }
  };

  const handleDismissMeeting = async (meetingId) => {
    try {
      await API.post(`/meetings/${meetingId}/dismiss`);
      await fetchMeetings();
    } catch (err) {
      console.error("Failed to dismiss meeting:", err);
    }
  };

  const handleAcceptUpdate = async (meetingId) => {
    try {
      await API.post(`/meetings/${meetingId}/accept-update`);
      await fetchMeetings();
    } catch (err) {
      console.error("Failed to accept meeting update:", err);
    }
  };

  const handleRemoveMeeting = async (meetingId) => {
    try {
      await API.post(`/meetings/${meetingId}/remove`);
      await fetchMeetings();
    } catch (err) {
      console.error("Failed to remove meeting:", err);
    }
  };

  const loadRules = async () => {
    try {
      const response = await API.get("/emails/config/rules");
      if (response.data) {
        setRulesConfig({
          vip_senders: Array.isArray(response.data.vip_senders)
            ? response.data.vip_senders
            : [],
          domains: Array.isArray(response.data.domains)
            ? response.data.domains
            : [],
          keywords: Array.isArray(response.data.keywords)
            ? response.data.keywords
            : [],
          custom_senders: Array.isArray(response.data.custom_senders)
            ? response.data.custom_senders
            : [],
          custom_keywords: Array.isArray(response.data.custom_keywords)
            ? response.data.custom_keywords
            : [],
          preference_boosts: response.data.preference_boosts || {
            inbox_boost: 0,
            spam_boost: 0,
          },
        });
      }
    } catch (err) {
      console.error("Error loading rules configuration:", err);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("google_access_token");
    if (!token) {
      navigate("/");
    } else {
      fetchEmails();
      loadRules();
    }
  }, [navigate, showAll]);

  // Trigger AI processing for the selected email on selection (on-demand fallback)
  useEffect(() => {
    if (!selectedEmail) return;

    const emailId = selectedEmail.id;
    if (aiInsightsCache[emailId]) return;

    const processEmailWithAI = async () => {
      setAiLoading(true);
      try {
        const contentToProcess =
          selectedEmail.body || selectedEmail.snippet || selectedEmail.subject;
        const response = await API.post("/ai/process", {
          email_id: emailId,
          email_content: contentToProcess,
          user_id: selectedEmail.account_email,
        });

        setAiInsightsCache((prev) => ({
          ...prev,
          [emailId]: response.data,
        }));
      } catch (err) {
        console.error("Error processing email with AI:", err);
        setAiInsightsCache((prev) => ({
          ...prev,
          [emailId]: {
            summary: "AI could not process this email.",
            priority: "Low",
            reply: "Failed to generate suggested response.",
          },
        }));
      } finally {
        setAiLoading(false);
      }
    };

    processEmailWithAI();
  }, [selectedEmail, aiInsightsCache]);

  useEffect(() => {
    if (activeSection === "meetings") {
      fetchMeetings();
    } else if (activeSection === "tasks") {
      fetchTasks();
      fetchSettings();
    }
  }, [activeSection, activeEmailFilter]);

  // Swapping theme or filter updates account lists
  const handleSwitchAccount = (email) => {
    setActiveEmailFilter(email);
    // Auto-select first matching email
    const filtered = emails.filter((e) => {
      const matchAcc = !email || e.account_email === email;
      const matchFolder =
        activeSection === "inbox"
          ? e.folder === "INBOX"
          : e.folder === "SPAM" && e.ai_analysis?.is_spam_false_positive;
      return matchAcc && matchFolder;
    });
    setSelectedEmail(filtered[0] || null);
  };

  // Generic function to filter emails according to state
  function getFilteredEmails(emailsList = emails) {
    if (isSearchActive) {
      return searchResults;
    }
    return emailsList.filter((email) => {
      // 1. Account Filter
      if (activeEmailFilter && email.account_email !== activeEmailFilter) {
        return false;
      }
      // 2. Folder Section Filter
      if (activeSection === "inbox") {
        if (email.folder !== "INBOX") return false;
      } else if (activeSection === "spam") {
        // Only show spam false positives
        if (
          email.folder !== "SPAM" ||
          !email.ai_analysis?.is_spam_false_positive
        )
          return false;
      }
      // 3. Priority Filter
      if (selectedPriorityFilter !== "All") {
        if (email.final_priority !== selectedPriorityFilter) return false;
      }
      return true;
    });
  }

  const filteredEmailsList = getFilteredEmails();

  // Label Modification actions:
  const handleMarkRead = async (email, read = true) => {
    const acc = accounts.find((a) => a.email === email.account_email);
    const token = acc
      ? acc.access_token
      : localStorage.getItem("google_access_token");

    try {
      const endpoint = read
        ? `/emails/${email.id}/read`
        : `/emails/${email.id}/unread`;
      await API.post(
        endpoint,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      // Refresh local emails list
      setEmails((prev) =>
        prev.map((e) => {
          if (e.id === email.id) {
            return { ...e, read_status: read ? "read" : "unread" };
          }
          return e;
        }),
      );
      // Update selected email reference
      if (selectedEmail?.id === email.id) {
        setSelectedEmail((prev) => ({
          ...prev,
          read_status: read ? "read" : "unread",
        }));
      }
    } catch (err) {
      console.error("Failed to change read status:", err);
    }
  };

  const handleMoveToInbox = async (email) => {
    const acc = accounts.find((a) => a.email === email.account_email);
    const token = acc
      ? acc.access_token
      : localStorage.getItem("google_access_token");

    try {
      await API.post(
        `/emails/${email.id}/move-to-inbox`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      await fetchEmails();
    } catch (err) {
      console.error("Failed to move email to inbox:", err);
    }
  };

  const handleMarkSafe = async (email) => {
    const acc = accounts.find((a) => a.email === email.account_email);
    const token = acc
      ? acc.access_token
      : localStorage.getItem("google_access_token");

    // Strip name bracket to get raw sender email
    const fromStr = email.sender || "";
    const match = fromStr.match(/<([^>]+)>/);
    const senderEmailAddress = match ? match[1] : fromStr;

    try {
      await API.post(
        `/emails/${email.id}/mark-safe`,
        {
          sender_email: senderEmailAddress,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      // Refresh rules configuration and emails
      await loadRules();
      await fetchEmails();
    } catch (err) {
      console.error("Failed to mark sender as safe:", err);
    }
  };

  const handleSaveRules = async () => {
    setIsSavingRules(true);
    try {
      await API.post("/emails/config/rules", rulesConfig);
      setIsRulesOpen(false);
      await fetchEmails(); // Refetch to recalculate scores with updated rules
    } catch (err) {
      console.error("Failed to save rules:", err);
    } finally {
      setIsSavingRules(false);
    }
  };

  const handleAddCustomSender = () => {
    if (
      newCustomSender.trim() &&
      !rulesConfig.custom_senders.includes(newCustomSender)
    ) {
      setRulesConfig((prev) => ({
        ...prev,
        custom_senders: [
          ...prev.custom_senders,
          newCustomSender.trim().toLowerCase(),
        ],
      }));
      setNewCustomSender("");
    }
  };

  const handleRemoveCustomSender = (sender) => {
    setRulesConfig((prev) => ({
      ...prev,
      custom_senders: prev.custom_senders.filter((s) => s !== sender),
    }));
  };

  const handleAddCustomKeyword = () => {
    if (
      newCustomKeyword.trim() &&
      !rulesConfig.custom_keywords.includes(newCustomKeyword)
    ) {
      setRulesConfig((prev) => ({
        ...prev,
        custom_keywords: [
          ...prev.custom_keywords,
          newCustomKeyword.trim().toLowerCase(),
        ],
      }));
      setNewCustomKeyword("");
    }
  };

  const handleRemoveCustomKeyword = (kw) => {
    setRulesConfig((prev) => ({
      ...prev,
      custom_keywords: prev.custom_keywords.filter((k) => k !== kw),
    }));
  };

  const fetchTasks = async () => {
    const userEmail = activeEmailFilter || localStorage.getItem("user_email") || "executive@gmail.com";
    setTasksLoading(true);
    try {
      const response = await API.get("/tasks", { params: { user_id: userEmail } });
      setTasks(response.data || []);
    } catch (err) {
      console.error("Failed to fetch tasks:", err);
    } finally {
      setTasksLoading(false);
    }
  };

  const fetchSettings = async () => {
    const userEmail = activeEmailFilter || localStorage.getItem("user_email") || "executive@gmail.com";
    try {
      const response = await API.get("/tasks/settings", { params: { user_id: userEmail } });
      if (response.data) {
        setReminderInterval(response.data.reminder_interval_hours);
      }
    } catch (err) {
      console.error("Failed to fetch task settings:", err);
    }
  };

  const saveSettings = async (interval) => {
    const userEmail = activeEmailFilter || localStorage.getItem("user_email") || "executive@gmail.com";
    try {
      await API.post("/tasks/settings", {
        user_id: userEmail,
        reminder_interval_hours: parseInt(interval)
      });
      setReminderInterval(parseInt(interval));
    } catch (err) {
      console.error("Failed to save task settings:", err);
    }
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    const userEmail = activeEmailFilter || localStorage.getItem("user_email") || "executive@gmail.com";
    try {
      const response = await API.post("/tasks", {
        user_id: userEmail,
        title: newTaskTitle,
        description: newTaskDesc,
        due_date: newTaskDueDate ? new Date(newTaskDueDate).toISOString() : null
      });
      setTasks((prev) => [response.data, ...prev]);
      setNewTaskTitle("");
      setNewTaskDesc("");
      setNewTaskDueDate("");
    } catch (err) {
      console.error("Failed to create task:", err);
    }
  };

  const handleUpdateTaskStatus = async (taskId, newStatus) => {
    try {
      const response = await API.put(`/tasks/${taskId}`, { status: newStatus });
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? response.data : t))
      );
    } catch (err) {
      console.error("Failed to update task status:", err);
    }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await API.delete(`/tasks/${taskId}`);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  const renderTasksDashboard = () => {
    if (tasksLoading) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center space-y-3 bg-slate-50 dark:bg-[#090d16]/30">
          <div className="h-8 w-8 rounded-full border-4 border-indigo-500/10 border-t-indigo-505 animate-spin"></div>
          <span className="text-xs text-slate-500 font-semibold">
            Loading Tasks Board...
          </span>
        </div>
      );
    }

    const pending = tasks.filter((t) => t.status === "pending");
    const completed = tasks.filter((t) => t.status === "completed");
    const dismissed = tasks.filter((t) => t.status === "dismissed");

    const getSourceBadge = (source) => {
      switch (source) {
        case "email_action_item":
          return (
            <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 text-[9px] font-bold">
              ✉️ AI Action Item
            </span>
          );
        case "email_no_reply":
          return (
            <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 text-[9px] font-bold">
              ⏳ Unreplied Email
            </span>
          );
        default:
          return (
            <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700/50 text-[9px] font-bold">
              👤 Manual
            </span>
          );
      }
    };

    const handleOpenLinkedEmail = (emailId) => {
      const email = emails.find((e) => e.id === emailId);
      if (email) {
        setSelectedEmail(email);
        setActiveSection(email.folder === "SPAM" ? "spam" : "inbox");
      } else {
        alert("Associated email could not be located in this page view.");
      }
    };

    return (
      <div className="flex-1 flex flex-col bg-slate-50 dark:bg-[#090d16]/30 min-w-0 transition-colors duration-150 p-6 overflow-y-auto space-y-6">
        {/* Header and Reminder Settings */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between pb-4 border-b border-slate-200 dark:border-slate-800/60 space-y-4 md:space-y-0">
          <div>
            <h1 className="text-xl font-extrabold text-slate-800 dark:text-white">
              Personal Assistant Tasks Board
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-450 mt-1 font-medium">
              Organize manual tasks and AI task lists extracted from your emails.
            </p>
          </div>
          <div className="flex items-center space-x-3 bg-white dark:bg-[#0e1424]/40 border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-2 shadow-sm">
            <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Reminder Interval:
            </span>
            <select
              value={reminderInterval}
              onChange={(e) => saveSettings(e.target.value)}
              className="bg-transparent text-xs font-bold text-slate-700 dark:text-white outline-none border-none cursor-pointer"
            >
              <option value="1">Every 1 Hour</option>
              <option value="2">Every 2 Hours (Default)</option>
              <option value="4">Every 4 Hours</option>
              <option value="0">Disabled</option>
            </select>
          </div>
        </div>

        {/* Task Creator Form & Tasks List Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Add Task Creator Form */}
          <div className="lg:col-span-1 bg-white dark:bg-[#0d1322] border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 h-fit">
            <h3 className="text-xs font-extrabold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              Add New Task
            </h3>
            <form onSubmit={handleCreateTask} className="space-y-3">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 dark:text-slate-405 uppercase">
                  Task Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Task title"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 dark:text-slate-405 uppercase">
                  Description
                </label>
                <textarea
                  placeholder="Optional description"
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  rows={3}
                  className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-indigo-500 outline-none resize-none"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 dark:text-slate-405 uppercase">
                  Due Date
                </label>
                <input
                  type="datetime-local"
                  value={newTaskDueDate}
                  onChange={(e) => setNewTaskDueDate(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-505 text-xs font-bold text-white rounded-lg transition-all shadow-md shadow-indigo-600/10 cursor-pointer"
              >
                Create Task
              </button>
            </form>
          </div>

          {/* Columns Section */}
          <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Column: Pending */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-extrabold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider flex items-center space-x-2">
                  <span>📥 Pending</span>
                  <span className="px-1.5 py-0.5 rounded-full bg-indigo-600/10 text-xs font-bold text-indigo-600 dark:text-indigo-400">
                    {pending.length}
                  </span>
                </h3>
              </div>
              <div className="space-y-3 overflow-y-auto max-h-[600px] pr-1">
                {pending.length === 0 ? (
                  <div className="p-8 text-center border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl text-[10px] text-slate-400 dark:text-slate-600 font-medium">
                    No pending tasks.
                  </div>
                ) : (
                  pending.map((task) => (
                    <div
                      key={task.id}
                      className="bg-white dark:bg-[#0d1322] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-3 hover:border-slate-300 dark:hover:border-slate-700/80 transition-all group"
                    >
                      <div className="flex items-start justify-between">
                        {getSourceBadge(task.task_source)}
                        {task.due_date && (
                          <span className="text-[9px] font-bold text-rose-500">
                            ⏳ {new Date(task.due_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-800 dark:text-white leading-snug break-words">
                          {task.title}
                        </h4>
                        {task.description && (
                          <p className="text-[10px] text-slate-500 dark:text-slate-450 leading-relaxed break-words font-medium">
                            {task.description}
                          </p>
                        )}
                      </div>
                      
                      {task.email_id && (
                        <button
                          onClick={() => handleOpenLinkedEmail(task.email_id)}
                          className="inline-flex items-center space-x-1.5 text-[9px] font-bold text-indigo-500 dark:text-indigo-400 hover:underline cursor-pointer"
                        >
                          <span>Open Associated Email</span>
                          <span>→</span>
                        </button>
                      )}

                      <div className="flex space-x-2 pt-1.5 border-t border-slate-100 dark:border-slate-800/40">
                        <button
                          onClick={() => handleUpdateTaskStatus(task.id, "completed")}
                          className="flex-1 py-1 px-2 rounded bg-emerald-500/10 hover:bg-emerald-500/15 text-emerald-600 dark:text-emerald-450 text-[9px] font-bold border border-emerald-500/20 transition-colors cursor-pointer"
                        >
                          Complete
                        </button>
                        <button
                          onClick={() => handleUpdateTaskStatus(task.id, "dismissed")}
                          className="flex-1 py-1 px-2 rounded bg-slate-100 hover:bg-slate-200/50 dark:bg-slate-800 dark:hover:bg-slate-800/85 text-slate-500 dark:text-slate-400 text-[9px] font-bold border border-slate-200 dark:border-slate-700/50 transition-colors cursor-pointer"
                        >
                          Not Necessary
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Column: Completed */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-extrabold text-emerald-500 dark:text-emerald-400 uppercase tracking-wider flex items-center space-x-2">
                  <span>✅ Completed</span>
                  <span className="px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600 dark:text-emerald-450">
                    {completed.length}
                  </span>
                </h3>
              </div>
              <div className="space-y-3 overflow-y-auto max-h-[600px] pr-1">
                {completed.length === 0 ? (
                  <div className="p-8 text-center border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl text-[10px] text-slate-400 dark:text-slate-600 font-medium">
                    No completed tasks.
                  </div>
                ) : (
                  completed.map((task) => (
                    <div
                      key={task.id}
                      className="bg-white dark:bg-[#0d1322] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-3 opacity-65 group"
                    >
                      <div className="flex items-start justify-between">
                        {getSourceBadge(task.task_source)}
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-700 dark:text-slate-300 leading-snug line-through break-words">
                          {task.title}
                        </h4>
                      </div>
                      <div className="flex space-x-2 pt-1 border-t border-slate-100 dark:border-slate-800/40">
                        <button
                          onClick={() => handleUpdateTaskStatus(task.id, "pending")}
                          className="flex-1 py-1 px-2 rounded bg-indigo-500/10 hover:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 text-[9px] font-bold border border-indigo-500/20 transition-colors cursor-pointer"
                        >
                          Restore
                        </button>
                        <button
                          onClick={() => handleDeleteTask(task.id)}
                          className="flex-1 py-1 px-2 rounded bg-rose-500/10 hover:bg-rose-500/15 text-rose-500 dark:text-rose-455 text-[9px] font-bold border border-rose-500/20 transition-colors cursor-pointer"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Column: Dismissed */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center space-x-2">
                  <span>🗑️ Not Necessary</span>
                  <span className="px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-800 text-xs font-bold text-slate-600 dark:text-slate-400">
                    {dismissed.length}
                  </span>
                </h3>
              </div>
              <div className="space-y-3 overflow-y-auto max-h-[600px] pr-1">
                {dismissed.length === 0 ? (
                  <div className="p-8 text-center border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl text-[10px] text-slate-400 dark:text-slate-600 font-medium">
                    No dismissed tasks.
                  </div>
                ) : (
                  dismissed.map((task) => (
                    <div
                      key={task.id}
                      className="bg-white dark:bg-[#0d1322] border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm space-y-3 opacity-65 group"
                    >
                      <div className="flex items-start justify-between">
                        {getSourceBadge(task.task_source)}
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-700 dark:text-slate-300 leading-snug break-words">
                          {task.title}
                        </h4>
                      </div>
                      <div className="flex space-x-2 pt-1 border-t border-slate-100 dark:border-slate-800/40">
                        <button
                          onClick={() => handleUpdateTaskStatus(task.id, "pending")}
                          className="flex-1 py-1 px-2 rounded bg-indigo-500/10 hover:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 text-[9px] font-bold border border-indigo-500/20 transition-colors cursor-pointer"
                        >
                          Restore
                        </button>
                        <button
                          onClick={() => handleDeleteTask(task.id)}
                          className="flex-1 py-1 px-2 rounded bg-rose-500/10 hover:bg-rose-500/15 text-rose-500 dark:text-rose-455 text-[9px] font-bold border border-rose-500/20 transition-colors cursor-pointer"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderMeetingsDashboard = () => {
    if (meetingsLoading) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center space-y-3 bg-white dark:bg-[#080b11]">
          <div className="h-8 w-8 rounded-full border-2 border-indigo-500/20 border-t-indigo-505 animate-spin"></div>
          <span className="text-xs text-slate-500 dark:text-slate-400 font-semibold">
            Loading calendar dashboard...
          </span>
        </div>
      );
    }

    const columns = [
      {
        title: "Today's Meetings",
        key: "today",
        color:
          "border-emerald-500/40 text-emerald-600 dark:text-emerald-450 bg-emerald-500/5",
      },
      {
        title: "Tomorrow's Meetings",
        key: "tomorrow",
        color:
          "border-blue-500/40 text-blue-600 dark:text-blue-450 bg-blue-500/5",
      },
      {
        title: "Upcoming Meetings",
        key: "upcoming",
        color:
          "border-indigo-500/40 text-indigo-600 dark:text-indigo-450 bg-indigo-500/5",
      },
      {
        title: "Missed / Past Meetings",
        key: "missed",
        color:
          "border-rose-500/40 text-rose-600 dark:text-rose-450 bg-rose-500/5",
      },
    ];

    return (
      <div className="flex-1 flex flex-col p-6 overflow-hidden bg-slate-50 dark:bg-[#070a13] transition-colors duration-150">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white">
              Meetings Calendar Dashboard
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              View and join your scheduled executive calls
            </p>
          </div>
          <button
            onClick={fetchMeetings}
            className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-505 text-xs font-bold text-white transition-all cursor-pointer shadow-md shadow-indigo-605/10 flex items-center space-x-1.5"
          >
            <span>Refresh Calendar</span>
          </button>
        </div>

        <div className="flex-1 grid grid-cols-4 gap-4 overflow-y-auto min-h-0 pb-4">
          {columns.map((col) => {
            const safeMeetingsDashboard =
              meetingsDashboard && typeof meetingsDashboard === "object"
                ? meetingsDashboard
                : {};
            const colMeetings = Array.isArray(safeMeetingsDashboard[col.key])
              ? safeMeetingsDashboard[col.key]
              : [];
            return (
              <div
                key={col.key}
                className="flex flex-col h-full min-h-0 bg-white/70 dark:bg-[#0c1221]/50 backdrop-blur-md rounded-2xl border border-slate-200 dark:border-slate-800/60 p-4"
              >
                <div
                  className={`px-3 py-1.5 rounded-lg border font-bold text-xs flex justify-between items-center ${col.color} mb-4`}
                >
                  <span>{col.title}</span>
                  <span className="bg-white/90 dark:bg-black/20 px-2 py-0.5 rounded-full text-[10px]">
                    {colMeetings.length}
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-1">
                  {colMeetings.length === 0 ? (
                    <div className="text-center py-8 text-slate-400 dark:text-slate-650 flex flex-col items-center">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="w-6 h-6 mb-1 text-slate-350 dark:text-slate-750"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5m-9-6h.008v.008H12v-.008ZM12 15h.008v.008H12V15Zm0 2.25h.008v.008H12v-.008ZM9.75 15h.008v.008H9.75V15Zm0 2.25h.008v.008H9.75v-.008ZM7.5 15h.008v.008H7.5V15Zm0 2.25h.008v.008H7.5v-.008Zm6.75-4.5h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V15Zm0 2.25h.008v.008h-.008v-.008Zm2.25-4.5h.008v.008H16.5v-.008Zm0 2.25h.008v.008H16.5V15Z"
                        />
                      </svg>
                      <span className="text-[10px]">No meetings</span>
                    </div>
                  ) : (
                    colMeetings.map((meet) => {
                      const formattedTime = new Date(
                        meet.start_datetime,
                      ).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      });
                      const formattedDate = new Date(
                        meet.start_datetime,
                      ).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                      });
                      const platformColors = {
                        "Google Meet":
                          "bg-indigo-500/10 text-indigo-600 dark:text-indigo-450 border-indigo-500/20",
                        Zoom: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
                        "Microsoft Teams":
                          "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
                      };
                      const badgeClass =
                        platformColors[meet.meeting_platform] ||
                        "bg-slate-500/10 text-slate-650 dark:text-slate-400 border-slate-500/20";

                      return (
                        <div
                          key={meet.id}
                          className="p-3.5 bg-white dark:bg-[#111827]/65 rounded-xl border border-slate-200 dark:border-slate-800/80 shadow-sm space-y-3 hover:shadow-md transition-all duration-200 group text-left"
                        >
                          <div className="flex justify-between items-start">
                            <span
                              className={`px-2 py-0.5 rounded border text-[9px] font-bold ${badgeClass}`}
                            >
                              {meet.meeting_platform}
                            </span>
                            {meet.status === "Cancelled" && (
                              <span className="px-2 py-0.5 rounded border border-red-500/30 bg-red-500/10 text-[9px] font-bold text-red-500 animate-pulse">
                                Cancelled
                              </span>
                            )}
                            {meet.status === "Updated" && (
                              <span className="px-2 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-[9px] font-bold text-amber-500 animate-pulse">
                                Rescheduled
                              </span>
                            )}
                          </div>

                          <div>
                            <h4 className="font-bold text-xs text-slate-850 dark:text-slate-100 line-clamp-2 leading-snug group-hover:text-indigo-500 dark:group-hover:text-indigo-400 transition-colors">
                              {meet.meeting_title}
                            </h4>
                            <div className="flex items-center space-x-1.5 mt-1.5 text-[10px] text-slate-500 dark:text-slate-400 font-medium">
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
                                  d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                                />
                              </svg>
                              <span>
                                {formattedDate} at {formattedTime}
                              </span>
                            </div>
                            {meet.organizer && (
                              <div className="text-[9px] text-slate-400 dark:text-slate-500 truncate mt-1">
                                Organized by:{" "}
                                <span className="font-semibold">
                                  {meet.organizer}
                                </span>
                              </div>
                            )}
                            {meet.participants &&
                              meet.participants.length > 0 && (
                                <div className="text-[9px] text-slate-400 dark:text-slate-500 mt-0.5">
                                  Attendees:{" "}
                                  <span className="font-semibold">
                                    {meet.participants.length} invited
                                  </span>
                                </div>
                              )}
                          </div>

                          <div className="pt-2 border-t border-slate-100 dark:border-slate-800/40 flex space-x-1.5">
                            {meet.meeting_url &&
                              meet.status !== "Cancelled" && (
                                <a
                                  href={meet.meeting_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex-1 py-1.5 rounded bg-indigo-600 hover:bg-indigo-505 text-[10px] font-bold text-white text-center transition-colors cursor-pointer"
                                >
                                  Join Meeting
                                </a>
                              )}
                            {meet.status === "Updated" && (
                              <button
                                onClick={() => handleAcceptUpdate(meet.id)}
                                className="px-2 py-1.5 rounded bg-amber-500 hover:bg-amber-600 text-[10px] font-bold text-white transition-colors cursor-pointer"
                              >
                                Accept Update
                              </button>
                            )}
                            <button
                              onClick={() => handleRemoveMeeting(meet.id)}
                              className="px-2.5 py-1.5 rounded border border-slate-200 dark:border-slate-800 hover:bg-red-500/5 hover:text-red-500 hover:border-red-500/20 text-[10px] font-bold text-slate-500 dark:text-slate-400 transition-all cursor-pointer"
                              title="Remove from Calendar"
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-[#080b11] overflow-hidden text-slate-800 dark:text-slate-100 font-sans transition-colors duration-150">
      {/* Sidebar navigation */}
      <Sidebar
        onOpenRules={() => setIsRulesOpen(true)}
        activeSection={activeSection}
        setActiveSection={(sec) => {
          setActiveSection(sec);
          // Auto select first email in the folder section
          const filtered = emails.filter((e) => {
            const matchAcc =
              !activeEmailFilter || e.account_email === activeEmailFilter;
            const matchFolder =
              sec === "inbox"
                ? e.folder === "INBOX"
                : e.folder === "SPAM" && e.ai_analysis?.is_spam_false_positive;
            return matchAcc && matchFolder;
          });
          setSelectedEmail(filtered[0] || null);
        }}
      />

      {/* Main content frame */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header toolbar */}
        <Header
          onRefresh={fetchEmails}
          isLoading={isLoading}
          accounts={accounts}
          activeEmail={activeEmailFilter}
          onSwitchAccount={handleSwitchAccount}
          notifications={notifications}
          onSelectEmail={(email) => {
            setSelectedEmail(email);
            // Sync current folder selection to match clicked email
            if (email.folder === "SPAM") {
              setActiveSection("spam");
            } else {
              setActiveSection("inbox");
            }
          }}
          onSearch={handleSearch}
          onClearSearch={handleClearSearch}
        />

        {/* Dynamic content split panel */}
        <div className="flex-1 flex min-h-0">
          {activeSection === "meetings" ? (
            renderMeetingsDashboard()
          ) : activeSection === "tasks" ? (
            renderTasksDashboard()
          ) : (
            <>
              {/* LEFT PANEL: Email List Column */}
              <div className="w-[380px] border-r border-slate-200 dark:border-slate-800/60 bg-white dark:bg-[#090d16]/30 flex flex-col min-h-0 transition-colors duration-150">
                {/* Filter Pill Controls bar */}
                <div className="p-3 border-b border-slate-200 dark:border-slate-800/40 flex justify-between items-center bg-slate-50/50 dark:bg-slate-900/10">
                  <div className="flex items-center space-x-1.5">
                    <button
                      onClick={() => setShowAll(false)}
                      className={`px-2.5 py-1 rounded-full text-[10px] font-bold transition-all cursor-pointer ${
                        !showAll
                          ? "bg-indigo-600 text-white shadow-sm"
                          : "bg-slate-200/65 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-350"
                      }`}
                    >
                      Unread
                    </button>
                    <button
                      onClick={() => setShowAll(true)}
                      className={`px-2.5 py-1 rounded-full text-[10px] font-bold transition-all cursor-pointer ${
                        showAll
                          ? "bg-indigo-600 text-white shadow-sm"
                          : "bg-slate-200/65 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-350"
                      }`}
                    >
                      All Mail
                    </button>
                  </div>

                  {/* Priority Select */}
                  <select
                    value={selectedPriorityFilter}
                    onChange={(e) => {
                      setSelectedPriorityFilter(e.target.value);
                      // Reset select
                      setSelectedEmail(null);
                    }}
                    className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded px-1.5 py-0.5 text-[10px] font-bold text-slate-600 dark:text-slate-300 outline-none"
                  >
                    <option value="All">All Priorities</option>
                    <option value="Critical">Critical</option>
                    <option value="High">High</option>
                    <option value="Medium">Medium</option>
                    <option value="Low">Low</option>
                  </select>
                </div>

                {/* List View Container */}
                {isLoading || isSearching ? (
                  <div className="flex-1 flex flex-col items-center justify-center space-y-3">
                    <div className="h-7 w-7 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin"></div>
                    <span className="text-xs text-slate-500 font-medium">
                      {isSearching ? "Searching mailbox..." : "Downloading mailboxes..."}
                    </span>
                  </div>
                ) : error ? (
                  <div className="p-6 text-center space-y-3">
                    <p className="text-xs text-red-500 dark:text-red-400 font-semibold">
                      {error}
                    </p>
                    <button
                      onClick={fetchEmails}
                      className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-bold text-white transition-all cursor-pointer"
                    >
                      Retry Connection
                    </button>
                  </div>
                ) : filteredEmailsList.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      className="w-8 h-8 text-slate-400 dark:text-slate-600"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z"
                      />
                    </svg>
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400">
                      All caught up!
                    </p>
                    <p className="text-[10px] text-slate-400 dark:text-slate-600">
                      No emails match the selected filters.
                    </p>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/20">
                    {filteredEmailsList.map((email) => (
                      <EmailCard
                        key={email.id}
                        email={email}
                        isSelected={selectedEmail?.id === email.id}
                        onClick={() => setSelectedEmail(email)}
                        aiInsights={
                          aiInsightsCache[email.id] || email.ai_analysis
                        }
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* RIGHT PANEL: Email Details & AI Insights Column */}
              <div className="flex-1 flex min-w-0 bg-white dark:bg-[#0b0f19]/25 transition-all">
                {selectedEmail ? (
                  <>
                    {/* Center Column: Email Details */}
                    <div className="flex-1 flex flex-col min-w-0 border-r border-slate-200 dark:border-slate-800/60 bg-white dark:bg-transparent">
                      {/* Action Toolbar */}
                      <div className="h-12 px-6 border-b border-slate-200 dark:border-slate-800/40 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/10">
                        <div className="flex items-center space-x-2">
                          {/* Mark Read/Unread Toggle */}
                          {selectedEmail.read_status === "unread" ? (
                            <button
                              onClick={() =>
                                handleMarkRead(selectedEmail, true)
                              }
                              className="px-3 py-1 rounded border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
                            >
                              Mark as Read
                            </button>
                          ) : (
                            <button
                              onClick={() =>
                                handleMarkRead(selectedEmail, false)
                              }
                              className="px-3 py-1 rounded border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
                            >
                              Mark as Unread
                            </button>
                          )}

                          {/* Spam Folder Intelligence Actions */}
                          {selectedEmail.folder === "SPAM" && (
                            <>
                              <button
                                onClick={() => handleMoveToInbox(selectedEmail)}
                                className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-[10px] font-bold text-white transition-colors cursor-pointer"
                              >
                                Move to Inbox
                              </button>
                              <button
                                onClick={() => handleMarkSafe(selectedEmail)}
                                className="px-3 py-1 rounded border border-emerald-500/30 hover:bg-emerald-500/10 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 transition-colors cursor-pointer"
                              >
                                Mark Safe Sender
                              </button>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Meeting notification alert banner */}
                      {(() => {
                        const safePendingMeetings = Array.isArray(
                          pendingMeetings,
                        )
                          ? pendingMeetings
                          : [];
                        const safeMeetingsDashboard =
                          meetingsDashboard &&
                          typeof meetingsDashboard === "object"
                            ? meetingsDashboard
                            : {};
                        const flatDashboardMeetings = Object.values(
                          safeMeetingsDashboard,
                        )
                          .flat()
                          .filter((m) => m && typeof m === "object");

                        const meetingForSelected =
                          safePendingMeetings.find(
                            (m) => m && m.source_email_id === selectedEmail.id,
                          ) ||
                          flatDashboardMeetings.find(
                            (m) => m && m.source_email_id === selectedEmail.id,
                          );
                        if (!meetingForSelected) return null;
                        return (
                          <div className="mx-6 mt-4 p-4 rounded-xl border border-indigo-500/20 bg-indigo-500/5 dark:bg-indigo-650/5 flex items-start justify-between space-x-4">
                            <div className="space-y-1">
                              <div className="flex items-center space-x-2">
                                <span className="h-2 w-2 rounded-full bg-indigo-500 animate-ping"></span>
                                <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                                  {meetingForSelected.status === "Cancelled"
                                    ? "Meeting Cancelled"
                                    : meetingForSelected.status === "Updated"
                                      ? "Meeting Rescheduled"
                                      : "Meeting Detected"}
                                </span>
                              </div>
                              <h3 className="text-xs font-bold text-slate-800 dark:text-white">
                                {meetingForSelected.meeting_title}
                              </h3>
                              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                                {new Date(
                                  meetingForSelected.start_datetime,
                                ).toLocaleDateString([], {
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                })}{" "}
                                at{" "}
                                {new Date(
                                  meetingForSelected.start_datetime,
                                ).toLocaleTimeString([], {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}{" "}
                                ({meetingForSelected.meeting_platform})
                              </p>
                              {meetingForSelected.status === "Updated" &&
                                meetingForSelected.prev_start_datetime && (
                                  <p className="text-[9px] text-amber-600 dark:text-amber-450 font-medium">
                                    Previous Time:{" "}
                                    {new Date(
                                      meetingForSelected.prev_start_datetime,
                                    ).toLocaleString([], {
                                      month: "short",
                                      day: "numeric",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })}
                                  </p>
                                )}
                            </div>
                            <div className="flex items-center space-x-2 self-center">
                              {meetingForSelected.status === "Cancelled" && (
                                <button
                                  onClick={() =>
                                    handleRemoveMeeting(meetingForSelected.id)
                                  }
                                  className="px-3 py-1.5 rounded bg-red-650 hover:bg-red-500 text-[10px] font-bold text-white transition-colors cursor-pointer"
                                >
                                  Remove From Calendar
                                </button>
                              )}
                              {meetingForSelected.status === "Updated" && (
                                <>
                                  <button
                                    onClick={() =>
                                      handleAcceptUpdate(meetingForSelected.id)
                                    }
                                    className="px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-600 text-[10px] font-bold text-white transition-colors cursor-pointer"
                                  >
                                    Accept Update
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleRemoveMeeting(meetingForSelected.id)
                                    }
                                    className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-[10px] font-bold text-slate-650 dark:text-slate-350 transition-colors cursor-pointer"
                                  >
                                    Dismiss
                                  </button>
                                </>
                              )}
                              {(meetingForSelected.status === "Pending" ||
                                (meetingForSelected.status === "Confirmed" &&
                                  meetingForSelected.calendar_added_flag ===
                                    0)) && (
                                <>
                                  <button
                                    onClick={() =>
                                      handleConfirmMeeting(
                                        meetingForSelected.id,
                                      )
                                    }
                                    className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-[10px] font-bold text-white transition-colors cursor-pointer"
                                  >
                                    Add to Calendar
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleDismissMeeting(
                                        meetingForSelected.id,
                                      )
                                    }
                                    className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-[10px] font-bold text-slate-650 dark:text-slate-350 transition-colors cursor-pointer"
                                  >
                                    Dismiss
                                  </button>
                                </>
                              )}
                            </div>
                          </div>
                        );
                      })()}

                      {/* Sender Details Header */}
                      <div className="p-6 border-b border-slate-200 dark:border-slate-800/60 space-y-3">
                        <div className="flex justify-between items-start">
                          <h1 className="text-sm font-bold text-slate-850 dark:text-white leading-snug">
                            {selectedEmail.subject}
                          </h1>
                          <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">
                            {new Date(selectedEmail.date).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs text-slate-405 dark:text-slate-550 font-bold">
                            From:
                          </span>
                          <span className="text-xs text-slate-700 dark:text-slate-300 truncate font-semibold">
                            {selectedEmail.sender}
                          </span>
                        </div>
                      </div>

                      {/* Scrollable Email Body */}
                      <div className="flex-1 p-6 overflow-y-auto bg-white dark:bg-transparent">
                        {selectedEmail.body ? (
                          <pre className="whitespace-pre-wrap font-sans text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
                            {selectedEmail.body}
                          </pre>
                        ) : (
                          <p className="text-xs text-slate-400 dark:text-slate-650 italic">
                            No email body content available.
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Right Column: AI Insights Pane */}
                    <div className="w-[380px] bg-slate-50 dark:bg-slate-900/10">
                      <AIInsights
                        insights={aiInsightsCache[selectedEmail.id]}
                        isLoading={aiLoading}
                        folder={selectedEmail.folder}
                      />
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-2">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1}
                      stroke="currentColor"
                      className="w-10 h-10 text-slate-300 dark:text-slate-700 animate-bounce"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M21.75 9v.906a2.25 2.25 0 0 1-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 0 0 1.183 1.981l6.478 3.488m8.839 2.51-4.66-2.51m0 0-1.023-.55a2.25 2.25 0 0 0-2.134 0l-1.022.55m0 0-4.661 2.51m16.5 1.615V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5a2.25 2.25 0 0 0 2.25 2.25h15a2.25 2.25 0 0 0 2.25-2.25Z"
                      />
                    </svg>
                    <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                      Select an email to read details
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-600">
                      Choose any item from the left column to display priority
                      analyses.
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Rules Customization Dialog Modal */}
      {isRulesOpen && (
        <div className="fixed inset-0 bg-slate-950/60 dark:bg-black/70 flex items-center justify-center p-6 z-50 backdrop-blur-sm">
          <div className="bg-white dark:bg-[#0c121e] rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-2xl shadow-2xl p-6 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-3.5 mb-4">
              <h3 className="text-base font-bold text-slate-800 dark:text-white">
                Configure Prioritization Rules
              </h3>
              <button
                onClick={() => setIsRulesOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-5 pr-1">
              {/* Custom sender VIPs list */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Custom VIP Senders
                </label>
                <div className="flex space-x-2">
                  <input
                    type="text"
                    placeholder="email@example.com or name snippet"
                    value={newCustomSender}
                    onChange={(e) => setNewCustomSender(e.target.value)}
                    className="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs outline-none focus:border-indigo-500"
                  />
                  <button
                    onClick={handleAddCustomSender}
                    className="px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white font-bold text-xs hover:bg-indigo-500 cursor-pointer"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {rulesConfig.custom_senders.length === 0 ? (
                    <span className="text-[10px] text-slate-400 italic">
                      No custom senders added yet.
                    </span>
                  ) : (
                    rulesConfig.custom_senders.map((sender, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700/50"
                      >
                        <span>{sender}</span>
                        <button
                          onClick={() => handleRemoveCustomSender(sender)}
                          className="hover:text-red-500 text-[9px] font-extrabold ml-1 cursor-pointer"
                        >
                          ✕
                        </button>
                      </span>
                    ))
                  )}
                </div>
              </div>

              {/* Custom keywords lists */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Custom Priority Keywords
                </label>
                <div className="flex space-x-2">
                  <input
                    type="text"
                    placeholder="urgent word or category tag"
                    value={newCustomKeyword}
                    onChange={(e) => setNewCustomKeyword(e.target.value)}
                    className="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs outline-none focus:border-indigo-500"
                  />
                  <button
                    onClick={handleAddCustomKeyword}
                    className="px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white font-bold text-xs hover:bg-indigo-500 cursor-pointer"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {rulesConfig.custom_keywords.length === 0 ? (
                    <span className="text-[10px] text-slate-400 italic">
                      No custom keywords added yet.
                    </span>
                  ) : (
                    rulesConfig.custom_keywords.map((kw, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700/50"
                      >
                        <span>{kw}</span>
                        <button
                          onClick={() => handleRemoveCustomKeyword(kw)}
                          className="hover:text-red-500 text-[9px] font-extrabold ml-1 cursor-pointer"
                        >
                          ✕
                        </button>
                      </span>
                    ))
                  )}
                </div>
              </div>

              {/* Folder Boost sliders */}
              <div className="space-y-4 pt-2">
                <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
                  Priority Preference Boosts
                </label>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-600 dark:text-slate-350">
                      Inbox Folder Boost score
                    </span>
                    <span className="text-indigo-600 dark:text-indigo-400 font-extrabold">
                      {rulesConfig.preference_boosts.inbox_boost} pts
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-30"
                    max="30"
                    value={rulesConfig.preference_boosts.inbox_boost}
                    onChange={(e) =>
                      setRulesConfig((prev) => ({
                        ...prev,
                        preference_boosts: {
                          ...prev.preference_boosts,
                          inbox_boost: parseInt(e.target.value),
                        },
                      }))
                    }
                    className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-slate-600 dark:text-slate-350">
                      Spam False-Positive Boost score
                    </span>
                    <span className="text-indigo-600 dark:text-indigo-400 font-extrabold">
                      {rulesConfig.preference_boosts.spam_boost} pts
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-30"
                    max="30"
                    value={rulesConfig.preference_boosts.spam_boost}
                    onChange={(e) =>
                      setRulesConfig((prev) => ({
                        ...prev,
                        preference_boosts: {
                          ...prev.preference_boosts,
                          spam_boost: parseInt(e.target.value),
                        },
                      }))
                    }
                    className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                  />
                </div>
              </div>

              {/* Standard active rules lists */}
              <div className="pt-2.5 border-t border-slate-100 dark:border-slate-800 space-y-3">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Standard Active Rules
                </span>
                <div className="grid grid-cols-2 gap-4 text-[10px] font-semibold text-slate-500 dark:text-slate-450">
                  <div>
                    <span className="font-bold text-slate-600 dark:text-slate-400 block mb-1">
                      Standard VIPs (+30 pts)
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {rulesConfig.vip_senders.map((v, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
                        >
                          {v}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="font-bold text-slate-600 dark:text-slate-400 block mb-1">
                      Target Domains (+20 pts)
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {rulesConfig.domains.map((d, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 rounded bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
                        >
                          @{d}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-2.5 border-t border-slate-100 dark:border-slate-800 pt-4 mt-4">
              <button
                onClick={() => setIsRulesOpen(false)}
                className="px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold text-slate-600 dark:text-slate-350 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRules}
                disabled={isSavingRules}
                className="px-4.5 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 text-xs font-bold transition-all disabled:opacity-50 cursor-pointer shadow-lg shadow-indigo-500/10"
              >
                {isSavingRules ? "Saving..." : "Apply Rules"}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* 30-Minute Meeting Alert Modal */}
      {activeReminder && (
        <div className="fixed inset-0 bg-slate-950/60 dark:bg-black/70 flex items-center justify-center p-6 z-50 backdrop-blur-md">
          <div className="bg-white dark:bg-[#0d1322] rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-md shadow-2xl p-6 overflow-hidden flex flex-col space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center space-x-3 text-indigo-600 dark:text-indigo-400 text-left">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
              </span>
              <h3 className="text-xs font-extrabold uppercase tracking-wider">
                Upcoming Meeting Alert
              </h3>
            </div>
            
            <div className="space-y-2 text-left">
              <h2 className="text-sm font-extrabold text-slate-800 dark:text-white leading-snug">
                {activeReminder.title}
              </h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold">
                Starts in 30 minutes!
              </p>
            </div>
            
            <div className="p-3.5 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2 text-left">
              <div className="flex items-center space-x-2 text-xs font-semibold text-slate-650 dark:text-slate-300">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 text-indigo-500">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                </svg>
                <span>
                  {new Date(activeReminder.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
              {activeReminder.meeting_platform && (
                <div className="text-[10px] text-slate-500 dark:text-slate-400 font-bold">
                  Platform: <span className="text-indigo-600 dark:text-indigo-400">{activeReminder.meeting_platform}</span>
                </div>
              )}
              {activeReminder.description && (
                <p className="text-[10px] text-slate-450 dark:text-slate-500 truncate italic">
                  "{activeReminder.description}"
                </p>
              )}
            </div>
            
            <div className="flex space-x-3 pt-2">
              {activeReminder.meeting_url && (
                <a
                  href={activeReminder.meeting_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-505 text-xs font-bold text-white text-center transition-all cursor-pointer shadow-lg shadow-indigo-500/10"
                >
                  Join Meeting
                </a>
              )}
              <button
                onClick={() => handleAcknowledgeReminder(activeReminder.meeting_id)}
                className="flex-1 py-2 rounded-lg border border-slate-250 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold text-slate-650 dark:text-slate-350 transition-colors cursor-pointer"
              >
                Acknowledge
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Personal Assistant Tasks Alert Modal */}
      {activeTaskReminder && activeTaskReminder.length > 0 && (
        <div className="fixed inset-0 bg-slate-950/60 dark:bg-black/70 flex items-center justify-center p-6 z-50 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#0d1322] rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-md shadow-2xl p-6 overflow-hidden flex flex-col space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center space-x-3 text-amber-500 dark:text-amber-400 text-left">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
              </span>
              <h3 className="text-xs font-extrabold uppercase tracking-wider">
                Personal Assistant Alert
              </h3>
            </div>
            
            <div className="space-y-2 text-left">
              <h2 className="text-sm font-extrabold text-slate-800 dark:text-white leading-snug">
                You have {activeTaskReminder.length} pending task{activeTaskReminder.length > 1 ? "s" : ""} requiring attention!
              </h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                Keep on top of your schedule and unreplied emails.
              </p>
            </div>
            
            <div className="max-h-48 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/40 p-1 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800 text-left">
              {activeTaskReminder.slice(0, 3).map((task) => (
                <div key={task.id} className="py-2.5 px-3 first:pt-1 last:pb-1">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">
                    {task.title}
                  </div>
                  {task.description && (
                    <div className="text-[10px] text-slate-500 dark:text-slate-455 truncate">
                      {task.description}
                    </div>
                  )}
                </div>
              ))}
              {activeTaskReminder.length > 3 && (
                <div className="py-2 px-3 text-[10px] text-slate-450 dark:text-slate-500 font-semibold italic text-center">
                  + {activeTaskReminder.length - 3} more tasks...
                </div>
              )}
            </div>
            
            <div className="flex space-x-3 pt-2">
              <button
                onClick={() => {
                  setActiveSection("tasks");
                  setActiveTaskReminder(null);
                }}
                className="flex-1 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-505 text-xs font-bold text-white text-center transition-all cursor-pointer shadow-lg shadow-indigo-500/10"
              >
                Go to Tasks Board
              </button>
              <button
                onClick={() => setActiveTaskReminder(null)}
                className="flex-1 py-2.5 rounded-lg border border-slate-250 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold text-slate-650 dark:text-slate-350 transition-colors cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
