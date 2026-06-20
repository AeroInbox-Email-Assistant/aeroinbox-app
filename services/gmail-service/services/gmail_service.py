import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi import HTTPException

def get_gmail_service(access_token: str):
    """
    Builds and returns the Gmail service client using the provided access token.
    """
    try:
        creds = Credentials(token=access_token)
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Failed to initialize Gmail client with provided access token: {str(e)}"
        )

def extract_body(payload):
    """
    Recursively decodes the body of a Gmail message, supporting plain text and HTML fallback.
    """
    if not payload:
        return ""
    
    # 1. Simple structure with body data
    body_data = payload.get("body", {}).get("data")
    if body_data:
        try:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
        except Exception:
            pass
            
    # 2. Multipart structure
    parts = payload.get("parts", [])
    plain_text = ""
    html_text = ""
    
    for part in parts:
        mime_type = part.get("mimeType", "")
        part_body = part.get("body", {})
        part_data = part_body.get("data")
        
        # Handle nested multipart parts
        if "parts" in part:
            nested = extract_body(part)
            if nested:
                return nested
                
        if part_data:
            try:
                decoded = base64.urlsafe_b64decode(part_data).decode("utf-8", errors="ignore")
                if mime_type == "text/plain":
                    plain_text += decoded
                elif mime_type == "text/html":
                    html_text += decoded
            except Exception:
                pass
                
    return plain_text if plain_text else html_text

async def fetch_emails(access_token: str, include_read: bool = False, max_results: int = 15):
    """
    Fetches emails from the authenticated user's Gmail inbox and spam folders.
    """
    service = get_gmail_service(access_token)
    try:
        # Build query (unread only or all)
        q = 'is:unread' if not include_read else ''

        # Call Gmail API list messages
        result = service.users().messages().list(
            userId='me',
            q=q,
            includeSpamTrash=True,
            maxResults=max_results
        ).execute()
        
        messages = result.get('messages', [])
        email_list = []
        
        for msg in messages:
            msg_id = msg['id']
            # Fetch the complete message object
            detail = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            label_ids = detail.get('labelIds', [])
            thread_id = detail.get('threadId', '')
            
            # Skip if message is in Trash or not in Inbox/Spam folders
            if 'TRASH' in label_ids:
                continue
            if 'INBOX' not in label_ids and 'SPAM' not in label_ids:
                continue
                
            payload = detail.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((h.get('value') for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
            sender = next((h.get('value') for h in headers if h.get('name', '').lower() == 'from'), 'Unknown Sender')
            date = next((h.get('value') for h in headers if h.get('name', '').lower() == 'date'), 'Unknown Date')
            
            body = extract_body(payload)
            snippet = detail.get('snippet', '')
            internal_date = int(detail.get('internalDate', 0))
            
            read_status = "read" if "UNREAD" not in label_ids else "unread"
            folder = "SPAM" if "SPAM" in label_ids else "INBOX"
            
            email_list.append({
                "id": msg_id,
                "sender": sender,
                "subject": subject,
                "date": date,
                "snippet": snippet,
                "body": body,
                "read_status": read_status,
                "folder": folder,
                "timestamp": internal_date,
                "thread_id": thread_id
            })
            
        return email_list
    except HttpError as error:
        try:
            import json
            error_details = json.loads(error.content.decode('utf-8'))
            message = error_details.get('error', {}).get('message', error.reason)
        except Exception:
            message = error.reason

        if error.resp.status == 401:
            raise HTTPException(
                status_code=401,
                detail="Gmail access token is invalid or expired."
            )
        elif error.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail=f"Gmail API access forbidden: {message}. Please ensure the Gmail API is enabled in your GCP project and that you granted the necessary permissions during login."
            )
        raise HTTPException(
            status_code=error.resp.status,
            detail=f"Gmail API error: {message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails: {str(e)}"
        )

def modify_message_labels(access_token: str, msg_id: str, add_labels: list[str], remove_labels: list[str]):
    """
    Modifies message labels (adds and/or removes labels) for a specific email.
    """
    service = get_gmail_service(access_token)
    try:
        body = {}
        if add_labels:
            body['addLabelIds'] = add_labels
        if remove_labels:
            body['removeLabelIds'] = remove_labels
            
        result = service.users().messages().modify(
            userId='me',
            id=msg_id,
            body=body
        ).execute()
        return {"status": "success", "id": msg_id, "labelIds": result.get("labelIds", [])}
    except HttpError as error:
        raise HTTPException(
            status_code=error.resp.status,
            detail=f"Gmail API label modification failed: {error.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to modify message labels: {str(e)}"
        )

async def search_emails(access_token: str, q: str, max_results: int = 15):
    """
    Searches emails using the Gmail API query parameter `q`.
    """
    service = get_gmail_service(access_token)
    try:
        # Call Gmail API list messages with search query
        result = service.users().messages().list(
            userId='me',
            q=q,
            includeSpamTrash=True,
            maxResults=max_results
        ).execute()
        
        messages = result.get('messages', [])
        email_list = []
        
        for msg in messages:
            msg_id = msg['id']
            # Fetch the complete message object
            detail = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            label_ids = detail.get('labelIds', [])
            thread_id = detail.get('threadId', '')
            
            # Skip if message is in Trash
            if 'TRASH' in label_ids:
                continue
                
            payload = detail.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((h.get('value') for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
            sender = next((h.get('value') for h in headers if h.get('name', '').lower() == 'from'), 'Unknown Sender')
            date = next((h.get('value') for h in headers if h.get('name', '').lower() == 'date'), 'Unknown Date')
            
            body = extract_body(payload)
            snippet = detail.get('snippet', '')
            internal_date = int(detail.get('internalDate', 0))
            
            read_status = "read" if "UNREAD" not in label_ids else "unread"
            folder = "SPAM" if "SPAM" in label_ids else "INBOX"
            
            email_list.append({
                "id": msg_id,
                "sender": sender,
                "subject": subject,
                "date": date,
                "snippet": snippet,
                "body": body,
                "read_status": read_status,
                "folder": folder,
                "timestamp": internal_date,
                "thread_id": thread_id
            })
            
        return email_list
    except HttpError as error:
        try:
            import json
            error_details = json.loads(error.content.decode('utf-8'))
            message = error_details.get('error', {}).get('message', error.reason)
        except Exception:
            message = error.reason

        if error.resp.status == 401:
            raise HTTPException(
                status_code=401,
                detail="Gmail access token is invalid or expired."
            )
        elif error.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail=f"Gmail API access forbidden: {message}. Please ensure the Gmail API is enabled in your GCP project and that you granted the necessary permissions during login."
            )
        raise HTTPException(
            status_code=error.resp.status,
            detail=f"Gmail API error: {message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search emails: {str(e)}"
        )


async def check_thread_has_reply(access_token: str, thread_id: str) -> bool:
    """
    Checks if a thread has any reply sent by the user (meaning a message in the thread has the 'SENT' label).
    """
    service = get_gmail_service(access_token)
    try:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])
        for msg in messages:
            if 'SENT' in msg.get('labelIds', []):
                return True
        return False
    except Exception:
        # Fall back to False if thread cannot be fetched
        return False

