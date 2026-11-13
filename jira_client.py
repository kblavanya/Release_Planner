"""
JIRA Client for connecting to JIRA and retrieving data
"""
import os
from typing import List, Optional
from datetime import datetime
from jira import JIRA
from dotenv import load_dotenv
from models import JiraTicket, JiraRelease, ReleaseSummary

load_dotenv()


class JiraClient:
    """Client for interacting with JIRA"""
    
    def __init__(self):
        self.server = os.getenv('JIRA_SERVER')
        self.username = os.getenv('JIRA_USERNAME')
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY')
        
        # Add alias for web UI compatibility
        self.project = self.project_key  
        
        # Cache for team data to avoid repeated API calls
        self._team_cache = {}
        self._org_id_cache = None
        
        if not all([self.server, self.username, self.api_token]):
            raise ValueError("Missing required JIRA configuration. Please check your .env file.")
        
        self.jira = JIRA(
            server=self.server,
            basic_auth=(self.username, self.api_token)
        )
    
    def test_connection(self):
        """Test the JIRA connection"""
        try:
            self.jira.myself()
            return True
        except Exception as e:
            print(f"JIRA connection failed: {e}")
            return False
    
    def get_jira_team_members(self, team_name: str, release_name: str = None) -> List[str]:
        """Get team members dynamically from JIRA tickets assigned to the team."""
        
        # Create cache key that includes release for better context
        cache_key = f"{team_name}_{release_name}" if release_name else team_name
        
        # Check cache first
        if cache_key in self._team_cache:
            print(f"📦 Using cached team members for '{team_name}' (release: {release_name}): {self._team_cache[cache_key]}")
            return self._team_cache[cache_key]
        
        try:
            # Always extract team members from actual JIRA tickets for dynamic, up-to-date team composition
            print(f"🎯 Getting team members for '{team_name}' from JIRA tickets (release: {release_name})")
            members = self._get_team_members_from_tickets(team_name, release_name=release_name)
            
            # Cache the result for performance
            self._team_cache[cache_key] = members
            print(f"✅ Found {len(members)} team members from tickets: {members}")
            return members
                
        except Exception as e:
            print(f"❌ Error getting team members for '{team_name}': {e}")
            return []
    
    def _find_team_id_by_name(self, team_name: str) -> Optional[str]:
        """Find team ID by name using JIRA's internal teams API with pagination."""
        
        try:
            # Use JIRA's internal teams API endpoint
            api_url = f"{self.jira._options['server']}/rest/teams/1.0/teams"
            
            print(f"🔍 Searching for team '{team_name}' using JIRA teams API: {api_url}")
            
            start_at = 0
            max_results = 50
            
            while True:
                # Make paginated API call
                response = self.jira._session.get(
                    api_url,
                    headers={'Accept': 'application/json'},
                    params={
                        'startAt': start_at,
                        'maxResults': max_results
                    }
                )
                
                print(f"📊 Teams API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"📋 Found {len(data.get('teams', []))} teams in this batch")
                    
                    # Search through teams in this batch
                    for team in data.get('teams', []):
                        team_display_name = team.get('displayName', '')
                        team_name_field = team.get('name', '')
                        
                        # Match team by name (case-insensitive)
                        if (team_display_name.lower() == team_name.lower() or 
                            team_name_field.lower() == team_name.lower()):
                            team_id = team.get('id')
                            print(f"✅ Found team '{team_name}' with ID: {team_id}")
                            print(f"🏢 Team details: displayName='{team_display_name}', name='{team_name_field}'")
                            return team_id
                    
                    # Check if we need to continue pagination
                    if data.get('isLast', True):
                        break
                    start_at += max_results
                    
                else:
                    print(f"❌ Teams API returned status {response.status_code}: {response.text[:500]}...")
                    break
            
            # If not found, show available teams for debugging
            print(f"❌ Team '{team_name}' not found in JIRA teams")
            print(f"🔄 Trying to list some available teams for reference...")
            self._list_available_teams_sample()
            
            # Fallback to hardcoded team IDs
            hardcoded_teams = {
                'TrailBlazers': 'adf74aef-bbeb-4a5b-999e-8eb744f2b74e-222'
            }
            
            if team_name in hardcoded_teams:
                team_id = hardcoded_teams[team_name]
                print(f"✅ Found team '{team_name}' via hardcoded mapping: {team_id}")
                return team_id
                
        except Exception as e:
            print(f"❌ Error searching for team '{team_name}': {e}")
        
        return None
    
    def _list_available_teams_sample(self):
        """List a sample of available teams for debugging."""
        try:
            api_url = f"{self.jira._options['server']}/rest/teams/1.0/teams"
            response = self.jira._session.get(
                api_url,
                headers={'Accept': 'application/json'},
                params={'startAt': 0, 'maxResults': 10}
            )
            
            if response.status_code == 200:
                data = response.json()
                teams = data.get('teams', [])
                if teams:
                    print(f"📋 Sample of available teams:")
                    for i, team in enumerate(teams, 1):
                        display_name = team.get('displayName', 'No display name')
                        name = team.get('name', 'No name')
                        team_id = team.get('id', 'No ID')
                        print(f"   {i}. '{display_name}' (name: '{name}', id: {team_id})")
                else:
                    print(f"📋 No teams found in API response")
            else:
                print(f"⚠️  Could not fetch team list for debugging: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️  Error fetching team list: {e}")
    
    def _get_team_members_by_id_direct(self, team_id: str, team_name: str) -> List[str]:
        """Get team members directly using team ID, trying multiple JIRA API endpoints."""
        
        print(f"🔍 Trying to get team members for '{team_name}' (ID: {team_id}) using direct JIRA APIs...")
        
        # List of API endpoints to try
        api_endpoints = [
            f"{self.jira._options['server']}/rest/teams/1.0/teams/{team_id}/members",
            f"{self.jira._options['server']}/rest/api/3/team/{team_id}/members", 
            f"{self.jira._options['server']}/rest/api/2/team/{team_id}/members",
            f"{self.jira._options['server']}/rest/teams/1.0/team/{team_id}/members"
        ]
        
        for api_url in api_endpoints:
            try:
                print(f"🔍 Trying API endpoint: {api_url}")
                
                response = self.jira._session.get(
                    api_url,
                    headers=self.jira._session.headers
                )
                
                print(f"📊 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    members_data = response.json()
                    print(f"📋 Response data: {members_data}")
                    
                    members = self._parse_team_members_response(members_data)
                    
                    if members:
                        print(f"✅ SUCCESS! Found {len(members)} team members: {members}")
                        return members
                    else:
                        print(f"⚠️  Endpoint returned data but no members extracted")
                        
                elif response.status_code == 404:
                    print(f"⚠️  Endpoint not found (404)")
                elif response.status_code == 403:
                    print(f"⚠️  Access forbidden (403)")
                else:
                    print(f"⚠️  Status {response.status_code}: {response.text[:200]}...")
                    
            except Exception as e:
                print(f"❌ Error with endpoint {api_url}: {e}")
                continue
        
        print(f"❌ All JIRA teams API endpoints failed for team '{team_name}'")
        return []
    
    def _parse_team_members_response(self, data) -> List[str]:
        """Parse team members from various JIRA API response formats."""
        
        members = []
        
        # Handle different response structures
        members_list = []
        if isinstance(data, list):
            members_list = data
        elif 'values' in data:
            members_list = data['values']
        elif 'members' in data:
            members_list = data['members']
        elif 'data' in data:
            members_list = data['data']
        elif 'results' in data:
            members_list = data['results']
        
        for member in members_list:
            member_name = None
            
            # Try different ways to extract member name
            if isinstance(member, str):
                member_name = member
            elif 'user' in member:
                user = member['user']
                member_name = (user.get('displayName') or 
                             user.get('name') or 
                             user.get('emailAddress'))
            elif 'displayName' in member:
                member_name = member['displayName']
            elif 'name' in member:
                member_name = member['name']
            elif 'emailAddress' in member:
                member_name = member['emailAddress']
            
            if member_name:
                members.append(member_name)
        
        return sorted(members) if members else []

    def _get_team_members_by_id(self, team_id: str, team_name: str) -> List[str]:
        """Get team members using team ID from JIRA's internal teams API."""
        
        try:
            # Use JIRA's internal team members API endpoint
            api_url = f"{self.jira._options['server']}/rest/teams/1.0/teams/{team_id}/members"
            
            print(f"🏢 Getting team members for '{team_name}' (ID: {team_id}) from JIRA teams API...")
            
            start_at = 0
            max_results = 50
            all_members = []
            
            while True:
                # Make paginated API call for team members
                response = self.jira._session.get(
                    api_url,
                    headers={'Accept': 'application/json'},
                    params={
                        'startAt': start_at,
                        'maxResults': max_results
                    }
                )
                
                print(f"📊 Team members API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    members_batch = data.get('members', [])
                    print(f"📋 Found {len(members_batch)} members in this batch")
                    
                    # Extract member names from this batch
                    for member in members_batch:
                        member_name = None
                        
                        # Try different ways to extract member name
                        if 'user' in member:
                            user = member['user']
                            member_name = (user.get('displayName') or 
                                         user.get('name') or 
                                         user.get('emailAddress'))
                        elif 'displayName' in member:
                            member_name = member['displayName']
                        elif 'name' in member:
                            member_name = member['name']
                        elif 'emailAddress' in member:
                            member_name = member['emailAddress']
                        elif isinstance(member, str):
                            member_name = member
                        
                        if member_name:
                            all_members.append(member_name)
                    
                    # Check if we need to continue pagination
                    if data.get('isLast', True) or len(members_batch) < max_results:
                        break
                    start_at += max_results
                    
                else:
                    print(f"❌ Team members API returned status {response.status_code}: {response.text[:500]}...")
                    
                    # Try alternative endpoint
                    alt_api_url = f"{self.jira._options['server']}/rest/api/3/team/{team_id}/members"
                    print(f"🔄 Trying alternative endpoint: {alt_api_url}")
                    
                    alt_response = self.jira._session.get(
                        alt_api_url,
                        headers={'Accept': 'application/json'}
                    )
                    
                    if alt_response.status_code == 200:
                        alt_data = alt_response.json()
                        print(f"✅ Alternative endpoint succeeded")
                        
                        # Handle alternative response format
                        alt_members = alt_data.get('values', alt_data.get('members', []))
                        for member in alt_members:
                            member_name = member.get('displayName', member.get('name', member.get('emailAddress')))
                            if member_name:
                                all_members.append(member_name)
                    
                    break
            
            if all_members:
                unique_members = sorted(list(set(all_members)))
                print(f"✅ Found {len(unique_members)} team members via JIRA teams API: {unique_members}")
                return unique_members
            else:
                print(f"⚠️  No members found via JIRA teams API, trying fallback...")
                return self._get_team_members_from_tickets(team_name)
                
        except Exception as e:
            print(f"❌ Error getting team members for team ID {team_id}: {e}")
            return self._get_team_members_from_tickets(team_name)
    
    def _get_organization_id(self) -> Optional[str]:
        """Get the organization ID from JIRA instance."""
        
        # Use the provided organization ID
        org_id = "681f9ce2-dce5-46cc-a81a-9b235845ce52"
        
        # Return cached org ID if available
        if self._org_id_cache:
            return self._org_id_cache
        
        print(f"✅ Using provided organization ID: {org_id}")
        self._org_id_cache = org_id  # Cache it
        return org_id
    
    def _get_auth_header(self) -> str:
        """Get the base64 encoded auth header for API calls."""
        import base64
        
        auth_string = f"{self.username}:{self.api_token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return encoded_auth
    
    def _get_team_members_from_tickets(self, team_name: str, release_name: str = None) -> List[str]:
        """Extract team members from all ticket roles: assignees, QA contacts, reporters, and team collaborators."""
        try:
            print(f"🔍 Comprehensive: Getting ALL team members for '{team_name}' from tickets...")
            
            team_members = set()
            projects = ['ESP', 'PSSR']
            
            # Strategy 1: Get people from current release (if specified)
            if release_name:
                print(f"🎯 Strategy 1: Current release '{release_name}' extraction")
                for project_key in projects:
                    try:
                        project_tickets = self.get_tickets_by_release(release_name, project_key=project_key, max_results=1000)
                        team_tickets = [t for t in project_tickets if t.team == team_name]
                        
                        if team_tickets:
                            print(f"🎯 Found {len(team_tickets)} tickets for {team_name} in {project_key}")
                            for ticket in team_tickets:
                                # Assignee
                                if ticket.assignee:
                                    team_members.add(ticket.assignee)
                                # Reporter 
                                if ticket.reporter:
                                    team_members.add(ticket.reporter)
                        
                    except Exception as e:
                        print(f"⚠️  Strategy 1: Could not get tickets from {project_key}: {e}")
                        continue
            
            # Strategy 2: Broader JQL search for team-related tickets (last 90 days)
            print(f"🔍 Strategy 2: Broader team search (last 90 days)")
            for project_key in projects:
                try:
                    # Search for tickets with team assignment - expanded timeframe and fields
                    jql = f'project = {project_key} AND cf[14895] ~ "{team_name}" AND updated >= -90d ORDER BY updated DESC'
                    
                    print(f"🔍 JQL search: {jql}")
                    
                    # Request more fields including QA contact and other potential team member fields
                    fields_to_check = [
                        'assignee', 'reporter', 'customfield_14895',  # Basic fields
                        'customfield_10026', 'customfield_10027',     # Potential QA contact fields
                        'customfield_10028', 'customfield_10029',     # More QA/tester fields
                        'customfield_11043', 'customfield_11044',     # Additional team fields
                        'customfield_14896', 'customfield_14897'      # Adjacent team fields
                    ]
                    
                    issues = self.jira.search_issues(
                        jql,
                        maxResults=300,  # Increased for better coverage
                        fields=fields_to_check
                    )
                    
                    print(f"📋 JQL found {len(issues)} issues for {team_name} in {project_key}")
                    
                    for issue in issues:
                        # Extract assignee
                        if hasattr(issue.fields, 'assignee') and issue.fields.assignee:
                            if hasattr(issue.fields.assignee, 'displayName'):
                                team_members.add(issue.fields.assignee.displayName)
                        
                        # Extract reporter
                        if hasattr(issue.fields, 'reporter') and issue.fields.reporter:
                            if hasattr(issue.fields.reporter, 'displayName'):
                                team_members.add(issue.fields.reporter.displayName)
                        
                        # Check all potential QA contact fields
                        for field_name in fields_to_check:
                            if hasattr(issue.fields, field_name):
                                field_value = getattr(issue.fields, field_name)
                                if field_value:
                                    # Handle different field formats
                                    if hasattr(field_value, 'displayName'):
                                        team_members.add(field_value.displayName)
                                    elif isinstance(field_value, list):
                                        for item in field_value:
                                            if hasattr(item, 'displayName'):
                                                team_members.add(item.displayName)
                                            elif isinstance(item, str):
                                                # Skip team names, only add person names
                                                if '@' in item or ' ' in item:
                                                    team_members.add(item)
                                    elif isinstance(field_value, str):
                                        # Skip team names, only add person names
                                        if '@' in field_value or ' ' in field_value:
                                            team_members.add(field_value)
                                            
                except Exception as project_error:
                    print(f"⚠️  Strategy 2: Error searching {project_key} for team {team_name}: {project_error}")
                    continue
            
            # Strategy 3: Search for tickets where team members are mentioned in comments/watchers
            print(f"🔍 Strategy 3: Historical collaboration search")
            for project_key in projects:
                try:
                    # Search for recent tickets where team members might have collaborated
                    jql = f'project = {project_key} AND (assignee was in membersOf("{team_name}") OR reporter was in membersOf("{team_name}")) AND updated >= -180d'
                    
                    issues = self.jira.search_issues(
                        jql,
                        maxResults=200,
                        fields=['assignee', 'reporter']
                    )
                    
                    print(f"📋 Historical search found {len(issues)} collaborative issues in {project_key}")
                    
                    for issue in issues:
                        if hasattr(issue.fields, 'assignee') and issue.fields.assignee:
                            if hasattr(issue.fields.assignee, 'displayName'):
                                team_members.add(issue.fields.assignee.displayName)
                        if hasattr(issue.fields, 'reporter') and issue.fields.reporter:
                            if hasattr(issue.fields.reporter, 'displayName'):
                                team_members.add(issue.fields.reporter.displayName)
                                
                except Exception as e:
                    print(f"🔍 Strategy 3: Skipping historical search for {project_key}: {e}")
                    continue
            
            # Clean up team members list - remove team names, system users, and invalid entries
            cleaned_members = set()
            team_name_variations = [team_name.lower(), team_name.replace('-', '').lower(), team_name.replace(' ', '').lower()]
            system_users = ['automation for jira', 'dev2 jira', 'jira system', 'system user', 'service account']
            
            for member in team_members:
                if member and isinstance(member, str):
                    member_lower = member.lower()
                    # Skip if it looks like a team name rather than a person
                    if not any(team_var in member_lower for team_var in team_name_variations):
                        # Skip system users
                        if not any(sys_user in member_lower for sys_user in system_users):
                            # Keep if it looks like a person name (has space or @ symbol)
                            if ' ' in member or '@' in member:
                                cleaned_members.add(member)
            
            members = sorted(list(cleaned_members))
            print(f"✅ Comprehensive extraction found {len(members)} total team members: {members}")
            return members
            
        except Exception as e:
            print(f"❌ Comprehensive team member extraction failed: {e}")
            return []
    
    def get_tickets_by_release(self, release_name: str, project_key: str = None, max_results: int = 5000, labels: List[str] = None) -> List[JiraTicket]:
        """
        Get all tickets for a specific release with proper pagination
        If labels are provided, uses OR logic: (release OR labels)
        """
        if not project_key:
            project_key = self.project_key
        
        if not project_key:
            raise ValueError("No project key provided")
        
        print(f"🔍 Searching for tickets in release: {release_name}, project: {project_key}, labels: {labels}, max_results: {max_results}")
        
        # Build JQL query
        jql_conditions = []
        
        # Project condition (always required)
        jql_conditions.append(f'project = {project_key}')
        
        # Build the release/labels condition with OR logic
        release_and_labels_conditions = []
        
        # Release/fixVersion condition
        release_and_labels_conditions.append(f'fixVersion = "{release_name}"')
        
        # Labels condition (if provided)
        if labels:
            # Create labels condition for each label with OR logic
            labels_conditions = []
            for label in labels:
                labels_conditions.append(f'labels = "{label}"')
            
            if labels_conditions:
                labels_or_condition = ' OR '.join(labels_conditions)
                release_and_labels_conditions.append(f'({labels_or_condition})')
        
        # Combine release and labels with OR logic
        if len(release_and_labels_conditions) > 1:
            release_or_labels = f'({" OR ".join(release_and_labels_conditions)})'
            jql_conditions.append(release_or_labels)
        else:
            # Only release condition
            jql_conditions.append(release_and_labels_conditions[0])
        
        jql = ' AND '.join(jql_conditions)
        print(f"🔍 Searching for tickets with JQL: {jql} (determined project: {project_key})")
        
        # Implement proper pagination to handle JIRA's 100-ticket limit
        all_issues = []
        start_at = 0
        batch_size = 100  # JIRA's actual limit
        batch_count = 0
        
        print(f"📄 Using pagination with batch_size={batch_size}")
        
        while True:
            batch_count += 1
            print(f"📄 Fetching batch {batch_count}: startAt={start_at}, maxResults={batch_size}")
            
            try:
                # Try multiple API methods for maximum compatibility
                batch_issues = None
                
                # Method 1: Try the enhanced search API first
                try:
                    if hasattr(self.jira, 'enhanced_search_issues'):
                        print(f"📡 Using enhanced_search_issues API")
                        batch_issues = self.jira.enhanced_search_issues(
                            jql,
                            startAt=start_at,
                            maxResults=batch_size
                        )
                except Exception as enhanced_error:
                    print(f"⚠️  enhanced_search_issues failed: {enhanced_error}")
                
                # Method 2: Fallback to regular search without expand
                if not batch_issues:
                    try:
                        print(f"📡 Using standard search_issues API (no expand)")
                        batch_issues = self.jira.search_issues(
                            jql,
                            startAt=start_at,
                            maxResults=batch_size
                        )
                    except Exception as search_error:
                        print(f"⚠️  search_issues failed: {search_error}")
                        
                        # Method 3: Last resort - try with a different approach
                        try:
                            print(f"📡 Using alternative JQL approach")
                            # Use the raw API call if the high-level methods fail
                            raw_result = self.jira._get_json(
                                f"search?jql={jql}&startAt={start_at}&maxResults={batch_size}"
                            )
                            # Convert raw result to issue objects manually if needed
                            batch_issues = raw_result.get('issues', [])
                        except Exception as raw_error:
                            print(f"❌ All search methods failed: {raw_error}")
                            break
                
                # Handle different response formats
                if batch_issues:
                    # If we got raw JSON, convert to issue objects
                    if isinstance(batch_issues, list) and batch_issues and not hasattr(batch_issues[0], 'key'):
                        print(f"📋 Batch {batch_count}: Converting {len(batch_issues)} raw issues to objects")
                        # Convert raw issues to proper issue objects
                        converted_issues = []
                        for raw_issue in batch_issues:
                            try:
                                # Create a mock issue object from raw data
                                issue = type('Issue', (), {})()
                                issue.key = raw_issue.get('key', '')
                                issue.fields = type('Fields', (), {})()
                                fields_data = raw_issue.get('fields', {})
                                for field, value in fields_data.items():
                                    setattr(issue.fields, field, value)
                                converted_issues.append(issue)
                            except Exception as convert_error:
                                print(f"⚠️  Error converting issue: {convert_error}")
                                continue
                        batch_issues = converted_issues
                    
                    print(f"📋 Batch {batch_count}: Retrieved {len(batch_issues)} issues")
                else:
                    print(f"📄 No issues in batch {batch_count} - pagination complete")
                    break
                
                if not batch_issues:
                    print(f"📄 No more issues found - pagination complete")
                    break
                
                all_issues.extend(batch_issues)
                
                # If we got fewer than batch_size, we've reached the end
                if len(batch_issues) < batch_size:
                    print(f"📄 Reached end: got {len(batch_issues)} < {batch_size}")
                    break
                
                # Move to next batch
                start_at += batch_size
                
                # Safety limit based on max_results parameter
                if len(all_issues) >= max_results:
                    print(f"📄 Reached requested limit of {max_results}")
                    all_issues = all_issues[:max_results]
                    break
                    
                # Absolute safety limit to prevent runaway queries
                if len(all_issues) > 10000:
                    print(f"📄 Absolute safety limit reached at {len(all_issues)}")
                    break
                    
            except Exception as e:
                print(f"❌ Error in batch {batch_count}: {e}")
                break
        
        issues = all_issues
        print(f"📋 PAGINATION COMPLETE: Found {len(issues)} total issues for release {release_name} in project {project_key}")
        
        tickets = []
        for issue in issues:
            try:
                # Calculate story points (could be in different fields)
                story_points = None
                # Try the correct field first (found through investigation - PSSR project uses this)
                if hasattr(issue.fields, 'customfield_10163') and issue.fields.customfield_10163:
                    story_points = float(issue.fields.customfield_10163)
                # Fallback to other common fields for other projects
                elif hasattr(issue.fields, 'customfield_10016') and issue.fields.customfield_10016:
                    story_points = float(issue.fields.customfield_10016)
                elif hasattr(issue.fields, 'story_points') and issue.fields.story_points:
                    story_points = float(issue.fields.story_points)
                elif hasattr(issue.fields, 'customfield_10004') and issue.fields.customfield_10004:
                    story_points = float(issue.fields.customfield_10004)
                
                # Get assignee (handle both object and dict formats)
                assignee = None
                if hasattr(issue.fields, 'assignee') and issue.fields.assignee:
                    if hasattr(issue.fields.assignee, 'displayName'):
                        assignee = issue.fields.assignee.displayName
                    elif isinstance(issue.fields.assignee, dict):
                        assignee = issue.fields.assignee.get('displayName') or issue.fields.assignee.get('name')
                    else:
                        assignee = str(issue.fields.assignee)
                
                # Get reporter (handle both object and dict formats)
                reporter = None
                if hasattr(issue.fields, 'reporter') and issue.fields.reporter:
                    if hasattr(issue.fields.reporter, 'displayName'):
                        reporter = issue.fields.reporter.displayName
                    elif isinstance(issue.fields.reporter, dict):
                        reporter = issue.fields.reporter.get('displayName') or issue.fields.reporter.get('name')
                    else:
                        reporter = str(issue.fields.reporter)
                
                # Get components (handle both object and dict formats)
                components = []
                if hasattr(issue.fields, 'components') and issue.fields.components:
                    for comp in issue.fields.components:
                        if hasattr(comp, 'name'):
                            components.append(comp.name)
                        elif isinstance(comp, dict):
                            components.append(comp.get('name', str(comp)))
                        else:
                            components.append(str(comp))
                
                # Get labels (handle both formats)
                labels = []
                if hasattr(issue.fields, 'labels') and issue.fields.labels:
                    labels = issue.fields.labels if isinstance(issue.fields.labels, list) else []
                
                # Get fix versions (handle both object and dict formats)
                fix_versions_list = []
                if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions:
                    for version in issue.fields.fixVersions:
                        if hasattr(version, 'name'):
                            fix_versions_list.append(version.name)
                        elif isinstance(version, dict):
                            fix_versions_list.append(version.get('name', str(version)))
                        else:
                            fix_versions_list.append(str(version))
                fix_version_string = ', '.join(fix_versions_list) if fix_versions_list else None
                
                # Extract team information from custom field (same logic as team discovery)
                team = None
                if hasattr(issue.fields, 'customfield_14895'):
                    team_field_value = getattr(issue.fields, 'customfield_14895')
                    if team_field_value:
                        if isinstance(team_field_value, list) and len(team_field_value) > 0:
                            team = team_field_value[0]  # Take first team if multiple
                        elif isinstance(team_field_value, str):
                            team = team_field_value
                
                # Fallback: check labels for team patterns
                if not team and labels:
                    for label in labels:
                        if 'team' in label.lower() and len(label) > 4:
                            team = label
                            break
                
                # Get QA Contact from custom fields (try multiple possible QA contact fields)
                qa_contact = None
                qa_contact_fields = ['customfield_10026', 'customfield_10027', 'customfield_10028', 'customfield_10029']
                for field_name in qa_contact_fields:
                    if hasattr(issue.fields, field_name):
                        field_value = getattr(issue.fields, field_name)
                        if field_value:
                            if hasattr(field_value, 'displayName'):
                                qa_contact = field_value.displayName
                                break
                            elif isinstance(field_value, dict):
                                qa_contact = field_value.get('displayName') or field_value.get('name')
                                if qa_contact:
                                    break
                            elif isinstance(field_value, str):
                                qa_contact = field_value
                                break
                
                ticket = JiraTicket(
                    key=issue.key,
                    summary=issue.fields.summary,
                    description=issue.fields.description or "",
                    issue_type=getattr(issue.fields.issuetype, 'name', issue.fields.issuetype.get('name', 'Unknown') if isinstance(issue.fields.issuetype, dict) else 'Unknown') if hasattr(issue.fields, 'issuetype') and issue.fields.issuetype else "Unknown",
                    status=getattr(issue.fields.status, 'name', issue.fields.status.get('name', 'Unknown') if isinstance(issue.fields.status, dict) else 'Unknown') if hasattr(issue.fields, 'status') and issue.fields.status else "Unknown",
                    priority=getattr(issue.fields.priority, 'name', issue.fields.priority.get('name', 'Unknown') if isinstance(issue.fields.priority, dict) else 'Unknown') if hasattr(issue.fields, 'priority') and issue.fields.priority else "Unknown",
                    assignee=assignee,
                    reporter=reporter,
                    created=issue.fields.created,
                    updated=issue.fields.updated,
                    story_points=story_points,
                    components=components,
                    labels=labels,
                    fix_version=fix_version_string,
                    team=team,
                    qa_contact=qa_contact,
                    release_name=release_name
                )
                tickets.append(ticket)
                
            except Exception as e:
                print(f"Error processing issue {issue.key}: {e}")
                continue
        
        print(f"✅ Processed {len(tickets)} tickets for release {release_name}")
        return tickets
    
    def get_releases(self) -> List[JiraRelease]:
        """Get all releases from the configured project"""
        return self.get_releases_for_project(self.project_key)
    
    def get_releases_for_project(self, project_key: str) -> List[JiraRelease]:
        """Get all releases for a specific project"""
        try:
            versions = self.jira.project_versions(project_key)
            releases = []
            
            for version in versions:
                # Safely access version attributes
                description = getattr(version, 'description', '') or ''
                start_date = getattr(version, 'startDate', None)
                release_date = getattr(version, 'releaseDate', None)
                
                # Parse dates if they are strings
                if start_date and isinstance(start_date, str):
                    try:
                        from datetime import datetime
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    except:
                        start_date = None
                        
                if release_date and isinstance(release_date, str):
                    try:
                        from datetime import datetime
                        release_date = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
                    except:
                        release_date = None
                
                release = JiraRelease(
                    name=version.name,
                    description=description,
                    start_date=start_date,
                    release_date=release_date,
                    released=getattr(version, 'released', False),
                    archived=getattr(version, 'archived', False),
                    project_key=project_key
                )
                releases.append(release)
            
            return releases
        except Exception as e:
            print(f"Error getting releases for project {project_key}: {e}")
            return []
    
    def get_project_releases(self) -> List[JiraRelease]:
        """Get releases for the configured project (alias for compatibility)"""
        return self.get_releases()
    
    def get_tickets_for_release(self, release_name: str, max_results: int = 5000) -> List[JiraTicket]:
        """Get tickets for a release (alias for compatibility)"""
        return self.get_tickets_by_release(release_name, self.project_key, max_results)
    
    def get_release_summary(self, release_name: str, project_key: str = None) -> ReleaseSummary:
        """Get summary statistics for a release"""
        if not project_key:
            project_key = self.project_key
            
        tickets = self.get_tickets_by_release(release_name, project_key)
        
        total_tickets = len(tickets)
        total_story_points = sum(ticket.story_points or 0 for ticket in tickets)
        
        # Count by status
        status_counts = {}
        for ticket in tickets:
            status = ticket.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by type
        type_counts = {}
        for ticket in tickets:
            issue_type = ticket.issue_type
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
        
        return ReleaseSummary(
            release_name=release_name,
            project_key=project_key,
            total_tickets=total_tickets,
            total_story_points=total_story_points,
            status_counts=status_counts,
            type_counts=type_counts
        )
    
    def get_teams(self, max_results: int = 5000) -> List[str]:
        """Get all unique teams by extracting team information from ticket labels"""
        print("🏢 Fetching teams from all projects...")
        
        try:
            # Get all tickets across projects to extract team information
            # We'll look for team patterns in labels or custom fields
            jql = 'order by created DESC'
            
            all_issues = []
            start_at = 0
            batch_size = 1000
            
            # Get a sample of recent tickets to extract team info
            while len(all_issues) < max_results:
                batch_issues = self.jira.search_issues(
                    jql,
                    startAt=start_at,
                    maxResults=min(batch_size, max_results - len(all_issues))
                )
                
                if not batch_issues:
                    break
                    
                all_issues.extend(batch_issues)
                start_at += len(batch_issues)
                
                if len(batch_issues) < batch_size:
                    break
            
            teams = set()
            
            # Extract teams from labels and custom fields
            for issue in all_issues:
                # Check labels for team patterns
                if hasattr(issue.fields, 'labels') and issue.fields.labels:
                    for label in issue.fields.labels:
                        # Look for team patterns in labels (e.g., "Team-Alpha", "TeamBeta", etc.)
                        if 'team' in label.lower() and len(label) > 4:
                            teams.add(label)
                
                # Check custom fields that might contain team info
                for field_name in ['customfield_14895']:  # Found in debug output
                    if hasattr(issue.fields, field_name):
                        field_value = getattr(issue.fields, field_name)
                        if field_value:
                            if isinstance(field_value, list):
                                teams.update(field_value)
                            elif isinstance(field_value, str):
                                teams.add(field_value)
            
            teams_list = sorted(list(teams))
            print(f"✅ Found {len(teams_list)} teams: {teams_list}")
            return teams_list
            
        except Exception as e:
            print(f"❌ Error fetching teams: {e}")
            # Return some default teams if extraction fails
            return ['Sunshiners', 'Alpha Team', 'Beta Team', 'Development Team']
    
    def get_teams_for_projects(self, project_keys: List[str], max_results: int = 5000) -> List[str]:
        """Get teams for specific projects"""
        print(f"🏢 Fetching teams for projects: {project_keys}")
        
        if not project_keys:
            return self.get_teams(max_results)
        
        try:
            teams = set()
            
            for project_key in project_keys:
                print(f"🔍 Getting teams for project: {project_key}")
                
                # Get recent tickets for this project
                jql = f'project = {project_key} order by created DESC'
                
                try:
                    issues = self.jira.search_issues(jql, maxResults=min(1000, max_results))
                    
                    for issue in issues:
                        # Check labels for team patterns
                        if hasattr(issue.fields, 'labels') and issue.fields.labels:
                            for label in issue.fields.labels:
                                if 'team' in label.lower() and len(label) > 4:
                                    teams.add(label)
                        
                        # Check custom field that contained team info (from debug output)
                        if hasattr(issue.fields, 'customfield_14895'):
                            field_value = getattr(issue.fields, 'customfield_14895')
                            if field_value:
                                if isinstance(field_value, list):
                                    teams.update(field_value)
                                elif isinstance(field_value, str):
                                    teams.add(field_value)
                    
                except Exception as e:
                    print(f"⚠️  Error getting teams for project {project_key}: {e}")
                    continue
            
            teams_list = sorted(list(teams))
            print(f"✅ Found {len(teams_list)} teams for projects {project_keys}: {teams_list}")
            
            # If no teams found, return some defaults
            if not teams_list:
                print("⚠️  No teams found, returning defaults")
                return ['Sunshiners', 'Development Team']
                
            return teams_list
            
        except Exception as e:
            print(f"❌ Error fetching teams for projects: {e}")
            return ['Sunshiners', 'Development Team']
    
    def get_team_assignee_workload(self, team_name: str, release_name: str = None) -> dict:
        """Get workload breakdown by assignee for a specific team"""
        print(f"👥 Getting assignee workload for team: {team_name}, release: {release_name}")
        
        try:
            workload = {}
            
            if release_name:
                # Get tickets for the specific release - we need to determine project
                # Since this method doesn't get project parameter, we'll try to get tickets for all projects
                # and filter by team
                tickets = []
                for project_key in ['PSSR', 'ESP']:  # Try both main projects
                    try:
                        project_tickets = self.get_tickets_by_release(release_name, project_key=project_key)
                        # Filter by team
                        team_tickets = [t for t in project_tickets if t.team == team_name]
                        tickets.extend(team_tickets)
                        if team_tickets:
                            print(f"🎯 Found {len(team_tickets)} tickets for {team_name} in {project_key}")
                    except Exception as e:
                        print(f"⚠️  Could not get tickets from {project_key}: {e}")
                        continue
            else:
                # Fallback: search recent tickets with team filter
                tickets = []
            
            # Calculate workload per assignee
            for ticket in tickets:
                if ticket.assignee:
                    if ticket.assignee not in workload:
                        workload[ticket.assignee] = {
                            'tickets': 0,
                            'story_points': 0.0
                        }
                    
                    workload[ticket.assignee]['tickets'] += 1
                    if ticket.story_points:
                        workload[ticket.assignee]['story_points'] += ticket.story_points
            
            print(f"✅ Calculated workload for {len(workload)} assignees in team {team_name}")
            return workload
            
        except Exception as e:
            print(f"❌ Error calculating team workload: {e}")
            return {}


def get_jira_client():
    """Factory function to create a JiraClient instance"""
    return JiraClient()
