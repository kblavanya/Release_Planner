"""
Data models for the Release Planner application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class JiraTicket:
    """Represents a JIRA ticket/issue"""
    key: str
    summary: str
    status: str
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    priority: str = "Unknown"
    issue_type: str = "Task"
    description: str = ""
    story_points: Optional[float] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    resolved: Optional[datetime] = None
    release_name: Optional[str] = None
    team: Optional[str] = None
    url: Optional[str] = None
    fix_version: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    qa_contact: Optional[str] = None


@dataclass  
class JiraRelease:
    """Represents a JIRA release/version"""
    name: str
    id: str = ""
    description: str = ""
    start_date: Optional[datetime] = None
    release_date: Optional[datetime] = None
    released: bool = False
    archived: bool = False
    project_key: str = ""
    project_name: str = ""
    project_id: str = ""


@dataclass
class TeamMember:
    """Represents a JIRA team member"""
    account_id: str
    display_name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    active: bool = True
    time_zone: Optional[str] = None


@dataclass
class JiraTeam:
    """Represents a JIRA team"""
    id: str
    title: str
    description: Optional[str] = None
    members: List[TeamMember] = field(default_factory=list)
    type: str = "OPEN"  # OPEN, CLOSED, etc.
    site_url: Optional[str] = None


@dataclass
class ReleaseSummary:
    """Summary statistics for a release"""
    release_name: str
    total_tickets: int = 0
    total_story_points: float = 0.0
    status_breakdown: Dict[str, int] = field(default_factory=dict)
    assignee_breakdown: Dict[str, int] = field(default_factory=dict)
    priority_breakdown: Dict[str, int] = field(default_factory=dict)
    team_breakdown: Dict[str, int] = field(default_factory=dict)
    type_breakdown: Dict[str, int] = field(default_factory=dict)
    completion_percentage: float = 0.0
    working_days_remaining: int = 0
