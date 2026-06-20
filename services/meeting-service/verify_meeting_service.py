import os
import sys
import unittest
import sqlite3
import asyncio
from datetime import datetime
from typing import List, Optional

# Adjust Python path to import from services/meeting-service
sys.path.append(r"c:\Users\ASUS\OneDrive\Desktop\Ai_Assistan_Email\services\meeting-service")

import main
from repository import MeetingRepository, Meeting, Participant

class SQLiteMeetingRepository(MeetingRepository):
    def __init__(self, db_path="test_meetings.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    source_email_id TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    meeting_platform TEXT NOT NULL,
                    meeting_url TEXT,
                    meeting_title TEXT NOT NULL,
                    description TEXT,
                    organizer TEXT,
                    start_datetime TEXT NOT NULL,
                    end_datetime TEXT NOT NULL,
                    prev_start_datetime TEXT,
                    prev_end_datetime TEXT,
                    status TEXT NOT NULL,
                    calendar_added_flag INTEGER DEFAULT 0,
                    reminder_1_day_sent INTEGER DEFAULT 0,
                    reminder_1_hour_sent INTEGER DEFAULT 0,
                    created_timestamp TEXT NOT NULL,
                    updated_timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meeting_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id INTEGER NOT NULL,
                    participant_email TEXT NOT NULL,
                    participant_name TEXT,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meeting_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    meeting_id INTEGER UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    reminder_time TEXT NOT NULL,
                    sent INTEGER DEFAULT 0,
                    acknowledged INTEGER DEFAULT 0,
                    acknowledged_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
        finally:
            conn.close()

    async def initialize_db(self) -> None:
        self._init_db()

    async def create_meeting(self, meeting: Meeting) -> Meeting:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO meetings (
                    user_id, source_email_id, source_platform, meeting_platform, meeting_url,
                    meeting_title, description, organizer, start_datetime, end_datetime,
                    prev_start_datetime, prev_end_datetime, status, calendar_added_flag,
                    reminder_1_day_sent, reminder_1_hour_sent, created_timestamp, updated_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meeting.user_id, meeting.source_email_id, meeting.source_platform, meeting.meeting_platform,
                meeting.meeting_url, meeting.meeting_title, meeting.description, meeting.organizer,
                meeting.start_datetime, meeting.end_datetime, meeting.prev_start_datetime, meeting.prev_end_datetime,
                meeting.status, meeting.calendar_added_flag, meeting.reminder_1_day_sent, meeting.reminder_1_hour_sent,
                meeting.created_timestamp, meeting.updated_timestamp
            ))
            meeting_id = cursor.lastrowid
            meeting.id = meeting_id
            
            # Save participants list in meeting_participants table (matches direct SQL checks in test)
            for p in meeting.participants:
                cursor.execute("""
                    INSERT INTO meeting_participants (meeting_id, participant_email, participant_name)
                    VALUES (?, ?, ?)
                """, (meeting_id, p.participant_email, p.participant_name))
                p.meeting_id = meeting_id
                
            conn.commit()
            return meeting
        finally:
            conn.close()

    def _row_to_meeting(self, row, conn) -> Meeting:
        m_dict = dict(row)
        meeting_id = m_dict["id"]
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM meeting_participants WHERE meeting_id = ?", (meeting_id,))
        p_rows = cursor.fetchall()
        participants = [
            Participant(
                id=pr["id"],
                meeting_id=pr["meeting_id"],
                participant_email=pr["participant_email"],
                participant_name=pr["participant_name"]
            )
            for pr in p_rows
        ]
        
        return Meeting(
            id=m_dict["id"],
            user_id=m_dict["user_id"],
            source_email_id=m_dict["source_email_id"],
            source_platform=m_dict["source_platform"],
            meeting_platform=m_dict["meeting_platform"],
            meeting_url=m_dict["meeting_url"],
            meeting_title=m_dict["meeting_title"],
            description=m_dict["description"],
            organizer=m_dict["organizer"],
            start_datetime=m_dict["start_datetime"],
            end_datetime=m_dict["end_datetime"],
            prev_start_datetime=m_dict["prev_start_datetime"],
            prev_end_datetime=m_dict["prev_end_datetime"],
            status=m_dict["status"],
            calendar_added_flag=m_dict["calendar_added_flag"],
            reminder_1_day_sent=m_dict["reminder_1_day_sent"],
            reminder_1_hour_sent=m_dict["reminder_1_hour_sent"],
            created_timestamp=m_dict["created_timestamp"],
            updated_timestamp=m_dict["updated_timestamp"],
            participants=participants
        )

    async def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_meeting(row, conn)
            return None
        finally:
            conn.close()

    async def get_meeting_by_source_email(self, user_id: str, source_email_id: str) -> Optional[Meeting]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meetings WHERE user_id = ? AND source_email_id = ?", (user_id, source_email_id))
            row = cursor.fetchone()
            if row:
                return self._row_to_meeting(row, conn)
            return None
        finally:
            conn.close()

    async def get_meeting_by_url(self, user_id: str, meeting_url: str) -> Optional[Meeting]:
        if not meeting_url:
            return None
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meetings WHERE user_id = ? AND meeting_url = ?", (user_id, meeting_url))
            row = cursor.fetchone()
            if row:
                return self._row_to_meeting(row, conn)
            return None
        finally:
            conn.close()

    async def get_meeting_by_title_and_organizer(self, user_id: str, title: str, organizer: str) -> Optional[Meeting]:
        if not title:
            return None
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if organizer:
                cursor.execute(
                    "SELECT * FROM meetings WHERE user_id = ? AND meeting_title = ? AND organizer = ?",
                    (user_id, title, organizer)
                )
            else:
                cursor.execute(
                    "SELECT * FROM meetings WHERE user_id = ? AND meeting_title = ? AND organizer IS NULL",
                    (user_id, title)
                )
            row = cursor.fetchone()
            if row:
                return self._row_to_meeting(row, conn)
            return None
        finally:
            conn.close()

    async def update_meeting(self, meeting: Meeting) -> Meeting:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE meetings SET
                    user_id = ?, source_email_id = ?, source_platform = ?, meeting_platform = ?, meeting_url = ?,
                    meeting_title = ?, description = ?, organizer = ?, start_datetime = ?, end_datetime = ?,
                    prev_start_datetime = ?, prev_end_datetime = ?, status = ?, calendar_added_flag = ?,
                    reminder_1_day_sent = ?, reminder_1_hour_sent = ?, created_timestamp = ?, updated_timestamp = ?
                WHERE id = ?
            """, (
                meeting.user_id, meeting.source_email_id, meeting.source_platform, meeting.meeting_platform,
                meeting.meeting_url, meeting.meeting_title, meeting.description, meeting.organizer,
                meeting.start_datetime, meeting.end_datetime, meeting.prev_start_datetime, meeting.prev_end_datetime,
                meeting.status, meeting.calendar_added_flag, meeting.reminder_1_day_sent, meeting.reminder_1_hour_sent,
                meeting.created_timestamp, meeting.updated_timestamp, meeting.id
            ))
            
            cursor.execute("DELETE FROM meeting_participants WHERE meeting_id = ?", (meeting.id,))
            for p in meeting.participants:
                cursor.execute("""
                    INSERT INTO meeting_participants (meeting_id, participant_email, participant_name)
                    VALUES (?, ?, ?)
                """, (meeting.id, p.participant_email, p.participant_name))
                p.meeting_id = meeting.id
                
            conn.commit()
            return meeting
        finally:
            conn.close()

    async def delete_meeting(self, meeting_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def list_meetings(self, user_id: str, calendar_added_only: bool = False) -> List[Meeting]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            if calendar_added_only:
                cursor.execute(
                    "SELECT * FROM meetings WHERE user_id = ? AND calendar_added_flag = 1 ORDER BY start_datetime ASC",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM meetings WHERE user_id = ? ORDER BY start_datetime ASC",
                    (user_id,)
                )
            rows = cursor.fetchall()
            return [self._row_to_meeting(row, conn) for row in rows]
        finally:
            conn.close()

    async def list_pending_meetings(self, user_id: str) -> List[Meeting]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM meetings WHERE user_id = ? AND calendar_added_flag = 0 AND status != 'Dismissed' ORDER BY start_datetime ASC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [self._row_to_meeting(row, conn) for row in rows]
        finally:
            conn.close()

    async def list_upcoming_meetings(self, user_id: str) -> List[Meeting]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now_str = datetime.utcnow().isoformat()
            cursor.execute(
                "SELECT * FROM meetings WHERE user_id = ? AND calendar_added_flag = 1 AND start_datetime >= ? ORDER BY start_datetime ASC",
                (user_id, now_str)
            )
            rows = cursor.fetchall()
            return [self._row_to_meeting(row, conn) for row in rows]
        finally:
            conn.close()

    async def create_or_update_reminder(self, user_id: str, meeting_id: int, title: str, start_time: datetime, reminder_time: datetime) -> None:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            # SQLite ON CONFLICT replacement
            cursor.execute("""
                INSERT OR REPLACE INTO meeting_reminders (
                    user_id, meeting_id, title, start_time, reminder_time, sent, acknowledged
                ) VALUES (?, ?, ?, ?, ?, 0, 0)
            """, (user_id, meeting_id, title, start_time.isoformat(), reminder_time.isoformat()))
            conn.commit()
        finally:
            conn.close()

    async def trigger_reminder(self, meeting_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE meeting_reminders SET sent = 1 WHERE meeting_id = ?", (meeting_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def get_pending_reminders(self, user_id: str) -> List[dict]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, m.meeting_url, m.meeting_platform, m.description
                FROM meeting_reminders r
                JOIN meetings m ON r.meeting_id = m.id
                WHERE r.user_id = ? AND r.sent = 1 AND r.acknowledged = 0
                ORDER BY r.start_time ASC
            """, (user_id,))
            rows = cursor.fetchall()
            reminders = []
            for row in rows:
                r_dict = dict(row)
                r_dict["sent"] = bool(r_dict["sent"])
                r_dict["acknowledged"] = bool(r_dict["acknowledged"])
                reminders.append(r_dict)
            return reminders
        finally:
            conn.close()

    async def acknowledge_reminder(self, meeting_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            now_str = datetime.utcnow().isoformat()
            cursor.execute("UPDATE meeting_reminders SET acknowledged = 1, acknowledged_at = ? WHERE meeting_id = ?", (now_str, meeting_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def close(self) -> None:
        pass


class TestMeetingServiceLogic(unittest.TestCase):
    def setUp(self):
        # Initialize test database
        if os.path.exists("test_meetings.db"):
            try:
                os.remove("test_meetings.db")
            except Exception:
                pass
        self.repo = SQLiteMeetingRepository("test_meetings.db")
        main.repo = self.repo

    def tearDown(self):
        # Clear main module repo so references are dropped
        main.repo = None
        self.repo = None
        if os.path.exists("test_meetings.db"):
            try:
                os.remove("test_meetings.db")
            except Exception:
                pass

    def test_regex_url_matching(self):
        meet_body = "Hi, join our Google Meet at https://meet.google.com/abc-defg-hij"
        zoom_body = "Please connect via Zoom: https://zoom.us/j/123456789?pwd=test"
        teams_body = "Teams link: https://teams.microsoft.com/l/meetup-join/19%3ameeting_xyz%40thread.v2/0?context=%7b%22Tid%22%3a%22abc%22%7d"
        no_meet_body = "Hello! See you tomorrow at the office."

        url, plat = main.extract_meeting_url(meet_body)
        self.assertEqual(plat, "Google Meet")
        self.assertEqual(url, "https://meet.google.com/abc-defg-hij")

        url, plat = main.extract_meeting_url(zoom_body)
        self.assertEqual(plat, "Zoom")
        self.assertEqual(url, "https://zoom.us/j/123456789?pwd=test")

        url, plat = main.extract_meeting_url(teams_body)
        self.assertEqual(plat, "Microsoft Teams")
        self.assertTrue("meetup-join" in url)

        url, plat = main.extract_meeting_url(no_meet_body)
        self.assertIsNone(url)
        self.assertIsNone(plat)

    def test_ics_parsing(self):
        ics_text = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:test-uid-123
DTSTART:20260610T150000Z
DTEND:20260610T160000Z
SUMMARY:Sprint Review Planning
DESCRIPTION:Discuss sprint planning
ORGANIZER;CN=Aakash:mailto:aakash@example.com
ATTENDEE;CN=User;ROLE=REQ-PARTICIPANT:mailto:user@example.com
LOCATION:https://meet.google.com/abc-defg-hij
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""
        ics_data = main.parse_ics_content(ics_text)
        self.assertIsNotNone(ics_data)
        data, participants = ics_data
        
        self.assertEqual(data["title"], "Sprint Review Planning")
        self.assertEqual(data["organizer"], "aakash@example.com")
        self.assertEqual(main.convert_ics_datetime(data["dtstart"]), "2026-06-10T15:00:00Z")
        self.assertEqual(main.convert_ics_datetime(data["dtend"]), "2026-06-10T16:00:00Z")
        self.assertEqual(data["location"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual(participants[0]["email"], "user@example.com")

    def test_keyword_filtering(self):
        self.assertTrue(main.has_meeting_keywords("Let's schedule a call tomorrow."))
        self.assertTrue(main.has_meeting_keywords("Invite you to a webinar."))
        self.assertFalse(main.has_meeting_keywords("Here is the monthly receipt for your subscription."))

    def test_repository_crud_and_uniqueness(self):
        # Create a meeting
        meet = Meeting(
            user_id="executive@example.com",
            source_email_id="msg-1",
            source_platform="gmail",
            meeting_platform="Zoom",
            meeting_url="https://zoom.us/j/99999",
            meeting_title="Initial Sync",
            description="Sync description",
            organizer="sender@example.com",
            start_datetime="2026-06-10T10:00:00",
            end_datetime="2026-06-10T11:00:00",
            status="Pending",
            calendar_added_flag=0,
            created_timestamp="2026-06-05T00:00:00",
            updated_timestamp="2026-06-05T00:00:00",
            participants=[
                Participant(participant_email="p1@example.com", participant_name="P1")
            ]
        )
        saved = asyncio.run(self.repo.create_meeting(meet))
        self.assertIsNotNone(saved.id)
        
        # Verify normalization of participants
        conn = sqlite3.connect("test_meetings.db")
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM meeting_participants WHERE meeting_id = ?", (saved.id,)).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["participant_email"], "p1@example.com")
        finally:
            conn.close()

        # Test retrieval by URL
        found = asyncio.run(self.repo.get_meeting_by_url("executive@example.com", "https://zoom.us/j/99999"))
        self.assertIsNotNone(found)
        self.assertEqual(found.meeting_title, "Initial Sync")

        # Test duplicate skip
        # Same URL, same dates
        main.repo = self.repo
        
        asyncio.run(main.save_or_update_meeting(
            user_id="executive@example.com",
            source_email_id="msg-2",
            source_platform="gmail",
            meeting_platform="Zoom",
            meeting_url="https://zoom.us/j/99999",
            meeting_title="Initial Sync",
            description="Sync description duplicate",
            organizer="sender@example.com",
            start_datetime="2026-06-10T10:00:00",
            end_datetime="2026-06-10T11:00:00",
            status="Pending",
            participants=[]
        ))
        
        # Verify no duplicate is created (still 1 meeting in DB)
        all_meetings = asyncio.run(self.repo.list_meetings("executive@example.com"))
        self.assertEqual(len(all_meetings), 1)

        # Test Reschedule Update
        # Same URL, new dates
        asyncio.run(main.save_or_update_meeting(
            user_id="executive@example.com",
            source_email_id="msg-3",
            source_platform="gmail",
            meeting_platform="Zoom",
            meeting_url="https://zoom.us/j/99999",
            meeting_title="Initial Sync",
            description="Rescheduled description",
            organizer="sender@example.com",
            start_datetime="2026-06-10T12:00:00",
            end_datetime="2026-06-10T13:00:00",
            status="Pending",
            participants=[
                Participant(participant_email="p2@example.com", participant_name="P2")
            ]
        ))
        
        # Verify updated fields
        updated = asyncio.run(self.repo.get_meeting(saved.id))
        self.assertEqual(updated.status, "Updated")
        self.assertEqual(updated.start_datetime, "2026-06-10T12:00:00")
        self.assertEqual(updated.prev_start_datetime, "2026-06-10T10:00:00")
        self.assertEqual(len(updated.participants), 2)  # Merged participants

        # Test cancellation
        asyncio.run(main.save_or_update_meeting(
            user_id="executive@example.com",
            source_email_id="msg-4",
            source_platform="gmail",
            meeting_platform="Zoom",
            meeting_url="https://zoom.us/j/99999",
            meeting_title="Initial Sync",
            description="Cancelled description",
            organizer="sender@example.com",
            start_datetime="2026-06-10T12:00:00",
            end_datetime="2026-06-10T13:00:00",
            status="Cancelled",
            participants=[]
        ))
        
        cancelled = asyncio.run(self.repo.get_meeting(saved.id))
        self.assertEqual(cancelled.status, "Cancelled")

if __name__ == "__main__":
    unittest.main()
