"""
Configuration management for the Release Planner application.
Handles JIRA connection settings and validation.
"""

import json
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from jira import JIRA


@dataclass
class JiraConfig:
    """JIRA configuration data class"""
    jira_url: str = ""
    jira_email: str = ""
    jira_token: str = ""
    project_key: Optional[str] = None
    user_display_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JiraConfig':
        """Create from dictionary"""
        return cls(**data)
    
    def is_complete(self) -> bool:
        """Check if all required fields are filled"""
        return bool(self.jira_url and self.jira_email and self.jira_token)


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self._config: Optional[JiraConfig] = None
        self.load_config()
    
    def load_config(self) -> JiraConfig:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self._config = JiraConfig.from_dict(data)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Warning: Error loading config file: {e}")
                self._config = JiraConfig()
        else:
            self._config = JiraConfig()
        
        return self._config
    
    def save_config(self, config: JiraConfig) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            self._config = config
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_config(self) -> JiraConfig:
        """Get current configuration"""
        if self._config is None:
            self.load_config()
        return self._config
    
    def is_configured(self) -> bool:
        """Check if JIRA is properly configured"""
        config = self.get_config()
        return config.is_complete()
    
    def clear_config(self) -> bool:
        """Clear all configuration data"""
        try:
            # Create empty configuration
            empty_config = JiraConfig(
                jira_url="",
                jira_email="",
                jira_token="",
                project_key=None,
                user_display_name=None
            )
            
            # Save empty configuration to file
            if self.save_config(empty_config):
                self._config = empty_config
                return True
            return False
        except Exception as e:
            print(f"Error clearing config: {e}")
            return False
    
    def test_connection(self, config: JiraConfig) -> Dict[str, Any]:
        """Test JIRA connection with given configuration"""
        print(f"DEBUG: Testing connection to {config.jira_url} with user {config.jira_email}")
        
        try:
            # Create JIRA client
            print("DEBUG: Creating JIRA client...")
            jira = JIRA(
                server=config.jira_url,
                basic_auth=(config.jira_email, config.jira_token),
                options={'verify': True}
            )
            
            print("DEBUG: Getting server info...")
            # Test connection by getting server info
            server_info = jira.server_info()
            print(f"DEBUG: Server info received: {server_info}")
            
            print("DEBUG: Getting current user...")
            current_user = jira.current_user()
            print(f"DEBUG: Current user: {current_user}")
            
            # Get user display name - prioritize jira.myself() over current_user
            user_display_name = config.jira_email  # Fallback to email
            
            # Try to get detailed user info from myself() first
            try:
                print("DEBUG: Getting detailed user info from myself()...")
                myself = jira.myself()
                print(f"DEBUG: Myself response: {myself}")
                print(f"DEBUG: Myself type: {type(myself)}")
                print(f"DEBUG: Myself attributes: {dir(myself) if hasattr(myself, '__dict__') else 'No attributes'}")
                
                # Try different ways to extract display name
                if hasattr(myself, 'displayName') and myself.displayName:
                    user_display_name = myself.displayName
                    print(f"DEBUG: Found displayName: {user_display_name}")
                elif hasattr(myself, 'name') and myself.name:
                    user_display_name = myself.name  
                    print(f"DEBUG: Found name: {user_display_name}")
                elif hasattr(myself, 'emailAddress') and myself.emailAddress:
                    user_display_name = myself.emailAddress
                    print(f"DEBUG: Found emailAddress: {user_display_name}")
                elif isinstance(myself, dict):
                    # Handle if myself returns a dictionary
                    user_display_name = myself.get('displayName') or myself.get('name') or myself.get('emailAddress') or config.jira_email
                    print(f"DEBUG: Extracted from dict: {user_display_name}")
                else:
                    print(f"DEBUG: No suitable display name found, using email as fallback")
                    
            except Exception as user_error:
                print(f"WARNING: Could not get detailed user info: {user_error}")
                # Use current_user as backup if it's not just an ID
                if isinstance(current_user, str) and '@' in current_user:
                    user_display_name = current_user
                else:
                    user_display_name = config.jira_email
            
            print(f"DEBUG: Final user display name: {user_display_name}")
            
            # Get available projects
            projects = []
            try:
                print("DEBUG: Loading projects...")
                jira_projects = jira.projects()
                projects = [
                    {"key": p.key, "name": p.name, "id": p.id}
                    for p in jira_projects[:50]  # Limit to first 50 projects
                ]
                print(f"DEBUG: Found {len(projects)} projects")
            except Exception as e:
                print(f"WARNING: Could not load projects: {e}")
            
            result = {
                "success": True,
                "server_info": {
                    "baseUrl": server_info.get('baseUrl', config.jira_url),
                    "version": server_info.get('version', 'Unknown'),
                    "serverTitle": server_info.get('serverTitle', 'JIRA')
                },
                "current_user": current_user,
                "user_display_name": user_display_name,
                "projects": projects
            }
            print(f"DEBUG: Returning success result: {result}")
            return result
            
        except Exception as e:
            print(f"ERROR: JIRA connection failed: {str(e)}")
            error_message = str(e)
            
            # Provide more helpful error messages for common issues
            if "401" in error_message or "AUTHENTICATED_FAILED" in error_message:
                error_message = "Authentication failed. Please check your API token:\n\n" + \
                              "• Make sure your API token is valid and not expired\n" + \
                              "• Generate a new API token from JIRA Settings → Security → API tokens\n" + \
                              "• Ensure your email address is correct\n" + \
                              "• Verify you have access to this JIRA instance"
            elif "403" in error_message:
                error_message = "Access denied. Your account may not have sufficient permissions to access this JIRA instance."
            elif "404" in error_message:
                error_message = "JIRA server not found. Please check your JIRA URL is correct."
            elif "timeout" in error_message.lower():
                error_message = "Connection timeout. Please check your network connection and JIRA URL."
            
            return {
                "success": False,
                "error": error_message
            }
    
    def get_jira_client(self):
        """Get configured JIRA client that's compatible with existing JiraClient interface"""
        config = self.get_config()
        if not config.is_complete():
            return None
        
        try:
            # Import the actual JiraClient class
            from jira_client import JiraClient
            
            # Create a custom JiraClient that uses the configuration
            class ConfiguredJiraClient(JiraClient):
                def __init__(self, config):
                    # Override the initialization to use config instead of environment variables
                    self.server = config.jira_url
                    self.username = config.jira_email
                    self.api_token = config.jira_token
                    
                    # Handle None or empty project_key by using a reasonable default
                    if config.project_key and config.project_key.strip():
                        self.project_key = config.project_key
                    else:
                        # Default to a common project key, or you could fetch and use the first available project
                        self.project_key = "PLATFORM"  # Based on the available projects from the test
                        print(f"⚠️  No project key configured, using default: {self.project_key}")
                    
                    # Add alias for web UI compatibility
                    self.jira_server = self.server
                    
                    # Add cache attributes for team data to avoid repeated API calls
                    self._team_cache = {}
                    self._org_id_cache = None
                    
                    self.jira = None
                    self._connect()
                
                def _connect(self):
                    """Establish connection to JIRA"""
                    try:
                        from jira import JIRA
                        self.jira = JIRA(
                            server=self.server,
                            basic_auth=(self.username, self.api_token)
                        )
                        print(f"✅ Connected to JIRA via config: {self.server}")
                    except Exception as e:
                        raise ConnectionError(f"Failed to connect to JIRA: {str(e)}")
                
                def get_server_info(self) -> dict:
                    """Get JIRA server information"""
                    try:
                        info = self.jira.server_info()
                        return info
                    except Exception as e:
                        raise ConnectionError(f"Failed to get server info: {str(e)}")
                
                def get_current_user(self) -> str:
                    """Get current authenticated user display name"""
                    try:
                        user = self.jira.current_user()
                        # Try to get the user's display name
                        user_info = self.jira.user(user)
                        return user_info.displayName if hasattr(user_info, 'displayName') else user
                    except Exception as e:
                        print(f"Warning: Could not get user display name: {e}")
                        return self.username
                        
                # Add server_info method as an alias for compatibility
                def server_info(self):
                    """Alias for get_server_info for direct JIRA API compatibility"""
                    return self.jira.server_info()
                
                # Add current_user method as an alias for compatibility  
                def current_user(self):
                    """Alias for get_current_user for direct JIRA API compatibility"""
                    return self.jira.current_user()
            
            return ConfiguredJiraClient(config)
            
        except Exception as e:
            print(f"Error creating JIRA client: {e}")
            return None


# Global configuration manager instance
config_manager = ConfigManager()
