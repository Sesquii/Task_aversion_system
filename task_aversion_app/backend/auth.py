# backend/auth.py
"""
OAuth authentication module for Google OAuth.
Handles session management, user creation, and authentication flow.
"""
import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from dotenv import load_dotenv
from nicegui import app, ui
from fastapi import Request
from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx

from backend.database import get_session, User, UserPreferences, init_db
from backend.user_state import UserStateManager

# Load environment variables from .env file
load_dotenv()

# Initialize database
init_db()

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI', 'http://localhost:8080/auth/callback')
SESSION_EXPIRY_DAYS = int(os.getenv('SESSION_EXPIRY_DAYS', '30'))

# Google OAuth endpoints
GOOGLE_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'

# UserStateManager for migrating anonymous data
user_state_manager = UserStateManager()


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return str(uuid.uuid4())


def create_session(user_id: int, email: str) -> str:
    """
    Create a new session for the user.
    
    Args:
        user_id: Integer user ID from database
        email: User email address
        
    Returns:
        Session token string
    """
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS)
    
    # Store session token in browser storage (shared across tabs)
    app.storage.browser['session_token'] = token
    
    # Store session data server-side (keyed by token)
    app.storage.general[f'session:{token}'] = {
        'user_id': user_id,
        'email': email,
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': expires_at.isoformat()
    }
    
    return token


def get_current_user() -> Optional[int]:
    """
    Get the current authenticated user ID from session.
    Performs lazy cleanup of expired sessions.
    
    Returns:
        Integer user_id if authenticated, None otherwise
    """
    try:
        # Get session token from browser storage
        session_token = app.storage.browser.get('session_token')
    except RuntimeError:
        # Storage not initialized yet (happens during page registration before ui.run())
        return None
    
    if not session_token:
        return None
    
    # Get session data from server-side storage
    session_key = f'session:{session_token}'
    session_data = app.storage.general.get(session_key)
    
    if not session_data:
        # Session not found, clear browser token
        app.storage.browser.pop('session_token', None)
        return None
    
    # Check expiration
    expires_at_str = session_data.get('expires_at')
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.utcnow() >= expires_at:
                # Session expired, clean up
                app.storage.browser.pop('session_token', None)
                app.storage.general.pop(session_key, None)
                return None
        except (ValueError, TypeError):
            # Invalid expiration date, treat as expired
            app.storage.browser.pop('session_token', None)
            app.storage.general.pop(session_key, None)
            return None
    
    # Lazy cleanup: Remove expired sessions (check a few random keys)
    # This is a lightweight cleanup that doesn't scan all sessions
    cleanup_expired_sessions_lazy()
    
    return session_data.get('user_id')


def cleanup_expired_oauth_states():
    """
    Clean up expired OAuth state tokens from storage.
    Called lazily during OAuth flow.
    """
    current_time = datetime.utcnow()
    keys_to_remove = []
    
    # Check all oauth_state keys
    for key in list(app.storage.general.keys()):
        if key.startswith('oauth_state:'):
            state_data = app.storage.general.get(key)
            if state_data:
                expires_at_str = state_data.get('expires_at')
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if current_time >= expires_at:
                            keys_to_remove.append(key)
                    except (ValueError, TypeError):
                        keys_to_remove.append(key)  # Invalid expiration, remove it
    
    # Remove expired states
    for key in keys_to_remove:
        app.storage.general.pop(key, None)
    
    if keys_to_remove:
        print(f"[Auth] Cleaned up {len(keys_to_remove)} expired OAuth states.")


def cleanup_expired_sessions_lazy():
    """
    Lazy cleanup of expired sessions.
    Only checks a small sample to avoid performance issues.
    """
    current_time = datetime.utcnow()
    keys_to_remove = []
    
    # Check up to 10 random session keys (to avoid scanning all)
    session_keys = [k for k in app.storage.general.keys() if k.startswith('session:')]
    if len(session_keys) > 10:
        # If many sessions, only check a sample
        import random
        session_keys = random.sample(session_keys, 10)
    
    for key in session_keys:
        session = app.storage.general.get(key)
        if session:
            expires_at_str = session.get('expires_at')
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if current_time >= expires_at:
                        keys_to_remove.append(key)
                except (ValueError, TypeError):
                    keys_to_remove.append(key)
    
    # Remove expired sessions
    for key in keys_to_remove:
        app.storage.general.pop(key, None)


def logout():
    """Clear the current user session."""
    session_token = app.storage.browser.pop('session_token', None)
    if session_token:
        app.storage.general.pop(f'session:{session_token}', None)


def require_auth(original_url: Optional[str] = None):
    """
    Decorator/middleware to require authentication.
    Redirects to login if not authenticated.
    
    Args:
        original_url: URL to redirect to after login (defaults to current page)
    """
    def decorator(page_func):
        def wrapper():
            user_id = get_current_user()
            if user_id is None:
                # Store original URL for post-login redirect
                if original_url:
                    app.storage.browser['login_redirect'] = original_url
                else:
                    # Try to get current URL from request
                    try:
                        from nicegui import request
                        current_url = request.url.path
                        if current_url and current_url != '/login':
                            app.storage.browser['login_redirect'] = current_url
                    except Exception:
                        pass
                
                ui.navigate.to('/login')
                return
            
            # User is authenticated, call the page function
            return page_func()
        
        return wrapper
    return decorator


def get_or_create_user_from_oauth(google_id: str, email: str, name: Optional[str] = None) -> int:
    """
    Get or create a User record from OAuth data.
    
    Args:
        google_id: Google OAuth user ID
        email: User email address
        name: Optional user name
        
    Returns:
        Integer user_id from database
    """
    with get_session() as session:
        # Check if user exists by google_id
        user = session.query(User).filter(User.google_id == google_id).first()
        
        if user:
            # Update last login time
            user.last_login = datetime.utcnow()
            session.commit()
            return user.user_id
        
        # Check if user exists by email (in case google_id changed)
        user = session.query(User).filter(User.email == email).first()
        if user:
            # Update google_id and last login
            user.google_id = google_id
            user.last_login = datetime.utcnow()
            session.commit()
            return user.user_id
        
        # Create new user
        new_user = User(
            email=email,
            username=name,  # Optional username
            google_id=google_id,
            oauth_provider='google',
            email_verified=True,  # Google emails are pre-verified
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        return new_user.user_id


def migrate_user_preferences(old_string_user_id: str, new_integer_user_id: int) -> bool:
    """
    Migrate UserPreferences from CSV to database during OAuth login.
    
    Args:
        old_string_user_id: Old string user_id from localStorage/CSV
        new_integer_user_id: New integer user_id from database
        
    Returns:
        True if migration was successful, False otherwise
    """
    try:
        # Get preferences from CSV
        prefs = user_state_manager.get_user_preferences(old_string_user_id)
        if not prefs:
            return False  # No preferences to migrate
        
        # Check if UserPreferences already exists for this integer user_id
        with get_session() as session:
            # Note: UserPreferences uses String user_id currently, so we need to check
            # by converting integer to string for now (until migration script runs)
            existing = session.query(UserPreferences).filter(
                UserPreferences.user_id == str(new_integer_user_id)
            ).first()
            
            if existing:
                # Already migrated, update from CSV if needed
                # Merge CSV preferences into database
                for key, value in prefs.items():
                    if key == 'user_id':
                        continue  # Skip user_id
                    # Update database record with CSV values
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                session.commit()
                return True
            
            # Create new UserPreferences record in database
            # Note: We're using string user_id for now (migration script will convert later)
            new_prefs = UserPreferences(
                user_id=str(new_integer_user_id),  # Temporary: will be migrated to integer
                tutorial_completed=prefs.get('tutorial_completed', 'False').lower() == 'true',
                tutorial_choice=prefs.get('tutorial_choice', '') or '',
                tutorial_auto_show=prefs.get('tutorial_auto_show', 'True').lower() == 'true',
                tooltip_mode_enabled=prefs.get('tooltip_mode_enabled', 'True').lower() == 'true',
                survey_completed=prefs.get('survey_completed', 'False').lower() == 'true',
                created_at=datetime.fromisoformat(prefs.get('created_at', datetime.utcnow().isoformat())) if prefs.get('created_at') else datetime.utcnow(),
                last_active=datetime.fromisoformat(prefs.get('last_active', datetime.utcnow().isoformat())) if prefs.get('last_active') else datetime.utcnow(),
                gap_handling=prefs.get('gap_handling') or None
            )
            
            # Handle JSON fields
            json_fields = [
                'persistent_emotion_values',
                'productivity_history',
                'productivity_goal_settings',
                'monitored_metrics_config',
                'execution_score_chunk_state',
                'productivity_settings'
            ]
            
            for field in json_fields:
                value_str = prefs.get(field, '')
                if value_str:
                    try:
                        value_dict = json.loads(value_str)
                        setattr(new_prefs, field, value_dict)
                    except (json.JSONDecodeError, TypeError):
                        pass  # Skip invalid JSON
            
            session.add(new_prefs)
            session.commit()
            
            return True
    
    except Exception as e:
        print(f"[Auth] Error migrating user preferences: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_user_id_mapping(old_string_user_id: str, new_integer_user_id: int):
    """
    Store mapping between old string user_id and new integer user_id.
    This is used for migrating other tables (PopupTrigger, PopupResponse, SurveyResponse).
    
    Args:
        old_string_user_id: Old string user_id
        new_integer_user_id: New integer user_id
    """
    # Store mapping in server-side storage for later migration
    mapping_key = f'user_id_mapping:{old_string_user_id}'
    app.storage.general[mapping_key] = {
        'old_string_user_id': old_string_user_id,
        'new_integer_user_id': new_integer_user_id,
        'created_at': datetime.utcnow().isoformat()
    }


def login_with_google():
    """
    Initiate Google OAuth flow.
    Generates and stores state parameter for CSRF protection.
    """
    try:
        if not GOOGLE_CLIENT_ID:
            ui.notify("OAuth not configured. Please set GOOGLE_CLIENT_ID.", color='negative')
            print("[Auth] GOOGLE_CLIENT_ID not set")
            return
        
        print(f"[Auth] Initiating OAuth flow with client_id: {GOOGLE_CLIENT_ID[:20]}...")
        
        # Get client IP address for additional security
        try:
            from nicegui import request
            client_ip = request.client.host if hasattr(request, 'client') else None
        except Exception:
            client_ip = None
        
        # Generate state parameter for CSRF protection
        state_token = generate_session_token()
        # Store state server-side (app.storage.general works even after page is rendered)
        # Include IP address and expiration time for security
        state_key = f'oauth_state:{state_token}'
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # States expire after 10 minutes
        app.storage.general[state_key] = {
            'state': state_token,
            'client_ip': client_ip,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': expires_at.isoformat()
        }
        
        # Clean up expired states (lazy cleanup)
        cleanup_expired_oauth_states()
        
        # Build OAuth authorization URL
        params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': OAUTH_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state_token,
            'access_type': 'online',
            'prompt': 'select_account'
        }
        
        auth_url = f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"
        print(f"[Auth] Redirecting to: {GOOGLE_AUTHORIZATION_URL} (with params)")
        
        # Redirect to Google OAuth using JavaScript (ui.navigate.to doesn't work for external URLs)
        ui.run_javascript(f'window.location.href = "{auth_url}";')
    except Exception as e:
        print(f"[Auth] Error in login_with_google: {e}")
        import traceback
        traceback.print_exc()
        ui.notify(f"Error starting authentication: {str(e)}", color='negative')


async def oauth_callback(request: Request):
    """
    Handle OAuth callback from Google.
    Validates state parameter, exchanges code for token, creates/updates user, migrates data, creates session.
    
    Args:
        request: FastAPI Request object
    """
    try:
        # Get query parameters
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')
        
        # Handle OAuth errors
        if error:
            error_description = request.query_params.get('error_description', 'Unknown error')
            print(f"[Auth] OAuth error: {error} - {error_description}")
            ui.notify(f"Authentication failed: {error_description}", color='negative')
            ui.navigate.to('/login')
            return
        
        if not code or not state:
            ui.notify("Invalid OAuth callback. Missing code or state parameter.", color='negative')
            ui.navigate.to('/login')
            return
        
        # Validate state parameter (CSRF protection)
        # Read state from server-side storage (app.storage.general)
        state_key = f'oauth_state:{state}'
        stored_state_data = app.storage.general.get(state_key)
        
        if not stored_state_data:
            print(f"[Auth] CSRF: Invalid state parameter. State not found.")
            ui.notify("Security error: Invalid authentication state.", color='negative')
            ui.navigate.to('/login')
            return
        
        # Validate state value matches
        if stored_state_data.get('state') != state:
            print(f"[Auth] CSRF: State value mismatch.")
            ui.notify("Security error: Invalid authentication state.", color='negative')
            app.storage.general.pop(state_key, None)  # Clear invalid state
            ui.navigate.to('/login')
            return
        
        # Check expiration
        expires_at_str = stored_state_data.get('expires_at')
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.utcnow() >= expires_at:
                    print(f"[Auth] CSRF: State expired.")
                    ui.notify("Security error: Authentication state expired. Please try again.", color='negative')
                    app.storage.general.pop(state_key, None)
                    ui.navigate.to('/login')
                    return
            except (ValueError, TypeError):
                print(f"[Auth] Warning: Invalid expiration date in state data.")
        
        # Optional: Validate IP address (can be disabled if behind proxy/load balancer)
        # Note: IP validation may fail if user is behind a proxy or VPN
        stored_ip = stored_state_data.get('client_ip')
        if stored_ip:
            try:
                from nicegui import request
                current_ip = request.client.host if hasattr(request, 'client') else None
                # Only validate if we can get current IP (may be None behind proxy)
                if current_ip and current_ip != stored_ip:
                    print(f"[Auth] Warning: IP address mismatch. Stored: {stored_ip}, Current: {current_ip}")
                    # Don't fail - IP can change with proxies/VPNs, but log for security monitoring
            except Exception:
                pass  # IP validation is optional
        
        # Clear state immediately after validation (prevent reuse)
        app.storage.general.pop(state_key, None)
        
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    'client_id': GOOGLE_CLIENT_ID,
                    'client_secret': GOOGLE_CLIENT_SECRET,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': OAUTH_REDIRECT_URI
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json() if token_response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('error_description', f"HTTP {token_response.status_code}")
                print(f"[Auth] Token exchange failed: {error_msg}")
                ui.notify(f"Authentication failed: {error_msg}", color='negative')
                ui.navigate.to('/login')
                return
            
            token_data = token_response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                ui.notify("Authentication failed: No access token received.", color='negative')
                ui.navigate.to('/login')
                return
            
            # Get user info from Google API
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if userinfo_response.status_code != 200:
                error_msg = f"HTTP {userinfo_response.status_code}"
                print(f"[Auth] UserInfo fetch failed: {error_msg}")
                ui.notify(f"Authentication failed: Could not fetch user information.", color='negative')
                ui.navigate.to('/login')
                return
            
            userinfo = userinfo_response.json()
            google_id = userinfo.get('id')
            email = userinfo.get('email')
            name = userinfo.get('name')
            
            if not google_id or not email:
                ui.notify("Authentication failed: Missing user information.", color='negative')
                ui.navigate.to('/login')
                return
            
            # Create or update user in database
            user_id = get_or_create_user_from_oauth(google_id, email, name)
            
            # Migrate UserStateManager data (if user was previously anonymous)
            # Check for old string user_id in localStorage
            old_string_user_id = None
            try:
                # Try to get old user_id from browser storage
                old_string_user_id = app.storage.browser.get('tas_user_id')  # Default key from UserStateManager
                if not old_string_user_id:
                    # Try alternative key
                    old_string_user_id = app.storage.browser.get('user_id')
            except Exception:
                pass
            
            if old_string_user_id:
                # Migrate UserPreferences from CSV to database
                migrate_user_preferences(old_string_user_id, user_id)
                # Create mapping for other tables
                create_user_id_mapping(old_string_user_id, user_id)
            
            # Create session
            create_session(user_id, email)
            
            # Redirect to original URL or dashboard
            redirect_url = app.storage.browser.pop('login_redirect', '/')
            ui.navigate.to(redirect_url)
            
            ui.notify(f"Welcome, {name or email}!", color='positive')
    
    except Exception as e:
        print(f"[Auth] OAuth callback error: {e}")
        import traceback
        traceback.print_exc()
        ui.notify("An error occurred during authentication. Please try again.", color='negative')
        ui.navigate.to('/login')
