#!/usr/bin/env python3
"""
Release Planner - Web UI
A Flask web application for browsing JIRA releases and tickets.
"""

import os
import sys
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
import pandas as pd
from jira_client import JiraClient
from utils import export_to_csv, export_to_excel, calculate_stats
from config_manager import config_manager, JiraConfig

# Fix Windows console encoding for Unicode characters (emojis)
if sys.platform == 'win32':
    try:
        # Set console to UTF-8 mode
        os.system('chcp 65001 >nul 2>&1')
        # Reconfigure stdout/stderr to use UTF-8
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr.encoding != 'utf-8':
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception as e:
        # Fallback: just continue, but print might fail for emojis
        print(f"Warning: Could not set UTF-8 encoding: {e}")

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global JIRA client
jira_client = None

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    try:
        if jira_client and jira_client.jira:
            # Quick JIRA connectivity check
            jira_client.jira.myself()
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'jira_connected': True
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'jira_connected': False,
                'error': 'JIRA client not initialized'
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'jira_connected': False,
            'error': str(e)
        }), 503

# Simple cache for frequently accessed data
cache = {
    'teams': {'data': None, 'timestamp': 0},
    'releases': {'data': None, 'timestamp': 0}
}
CACHE_DURATION = 300  # 5 minutes cache
TEAMS_CACHE_DURATION = 1800  # 30 minutes for teams (they change less frequently)

def get_cached_data(cache_key):
    """Get cached data if still valid"""
    if cache_key in cache:
        cache_data = cache[cache_key]
        # Use longer cache duration for teams
        duration = TEAMS_CACHE_DURATION if cache_key == 'teams' else CACHE_DURATION
        if time.time() - cache_data['timestamp'] < duration:
            return cache_data['data']
    return None

def set_cached_data(cache_key, data):
    """Set data in cache with current timestamp"""
    cache[cache_key] = {
        'data': data,
        'timestamp': time.time()
    }

def get_jira_client():
    """Get or create JIRA client instance using configuration manager."""
    global jira_client
    if jira_client is None:
        try:
            # Use configuration manager to get JIRA client
            jira_client = config_manager.get_jira_client()
            if jira_client:
                # Test connection
                jira_client.server_info()
                return jira_client
            else:
                return None
        except Exception as e:
            print(f"Error creating JIRA client: {e}")
            return None
    return jira_client

@app.before_request
def check_configuration():
    """Check if JIRA is configured before handling requests."""
    # Skip configuration check for config-related routes and static files
    skip_routes = ['/config', '/api/config/test', '/api/config/save', '/api/config/logout', '/api/config/user', '/api/connection-status', '/static']
    
    if any(request.path.startswith(route) for route in skip_routes):
        return None
    
    # Check if configuration is complete
    if not config_manager.is_configured():
        return redirect(url_for('config_page'))
    
    return None

@app.route('/config')
def config_page():
    """Configuration page for JIRA settings."""
    config = config_manager.get_config()
    return render_template('config.html', config=config)

@app.route('/api/config/test', methods=['POST'])
def test_config():
    """Test JIRA configuration."""
    try:
        data = request.get_json()
        print(f"DEBUG: Testing config with data: {data}")
        
        config = JiraConfig(
            jira_url=data.get('jira_url', ''),
            jira_email=data.get('jira_email', ''),
            jira_token=data.get('jira_token', '')
        )
        
        print(f"DEBUG: Created config object: {config.jira_url}, {config.jira_email}")
        
        result = config_manager.test_connection(config)
        print(f"DEBUG: Test result: {result}")
        
        return jsonify(result)
    
    except Exception as e:
        print(f"ERROR: Exception in test_config: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """Save JIRA configuration."""
    try:
        data = request.get_json()
        config = JiraConfig(
            jira_url=data.get('jira_url', ''),
            jira_email=data.get('jira_email', ''),
            jira_token=data.get('jira_token', '')
        )
        
        if not config.is_complete():
            return jsonify({
                'success': False,
                'error': 'All required fields must be filled'
            }), 400
        
        # Test connection before saving
        test_result = config_manager.test_connection(config)
        if not test_result.get('success'):
            return jsonify({
                'success': False,
                'error': f"Connection test failed: {test_result.get('error')}"
            }), 400
        
        # Add user display name from test result
        if 'user_display_name' in test_result:
            config.user_display_name = test_result['user_display_name']
        
        # Save configuration
        if config_manager.save_config(config):
            # Reset global JIRA client to use new config
            global jira_client
            jira_client = None
            
            return jsonify({
                'success': True,
                'message': 'Configuration saved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/config/logout', methods=['POST'])
def logout():
    """Clear all configuration data (logout)."""
    try:
        # Clear configuration
        if config_manager.clear_config():
            # Reset global JIRA client
            global jira_client
            jira_client = None
            
            return jsonify({
                'success': True,
                'message': 'Configuration cleared successfully. You have been logged out.'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clear configuration'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/config/user')
def get_current_user():
    """Get current user info."""
    try:
        config = config_manager.get_config()
        if not config.is_complete():
            return jsonify({
                'success': False,
                'logged_in': False,
                'user': None
            })
        
        return jsonify({
            'success': True,
            'logged_in': True,
            'user': {
                'email': config.jira_email,
                'display_name': config.user_display_name or config.jira_email
            }
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'logged_in': False,
            'error': str(e)
        }), 500

@app.route('/')
def index():
    """Main dashboard page - redirects to releases."""
    return redirect(url_for('releases_page'))

@app.route('/api/connection-status')
def connection_status():
    """Check JIRA connection status."""
    if not config_manager.is_configured():
        return jsonify({
            'connected': False,
            'error': 'JIRA not configured'
        })
    
    client = get_jira_client()
    if client:
        try:
            info = client.server_info()
            user = client.current_user()
            return jsonify({
                'connected': True,
                'server': info.get('baseUrl', 'Unknown'),
                'version': info.get('version', 'Unknown'),
                'user': user
            })
        except Exception as e:
            return jsonify({
                'connected': False,
                'error': str(e)
            })
    else:
        return jsonify({
            'connected': False,
            'error': 'Failed to initialize JIRA client'
        })

@app.route('/api/releases')
def get_releases():
    """Get list of all releases from January 2025 onwards."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    team_filter = request.args.get('team', '')
    project_filter = request.args.get('project', '')  # Add project filter
    
    # Check cache for basic releases data (without filters)
    cache_key = f"releases_{project_filter}_{team_filter}" if project_filter or team_filter else 'releases'
    if not team_filter and not project_filter:
        cached_releases = get_cached_data('releases')
        if cached_releases is not None:
            return jsonify(cached_releases)
    
    try:
        # Get releases, optionally filtered by project
        all_releases = []
        if project_filter:
            # Handle multiple projects (comma-separated)
            project_keys = [p.strip() for p in project_filter.split(',') if p.strip()]
            for project_key in project_keys:
                try:
                    project_releases = client.get_releases_for_project(project_key)
                    all_releases.extend(project_releases)
                except Exception as e:
                    print(f"Error getting releases for project {project_key}: {e}")
                    continue
        else:
            all_releases = client.get_releases()
        
        # Convert releases to JSON-serializable format
        releases_data = []
        cutoff_date = datetime(2025, 1, 1)  # January 1, 2025
        
        for release in all_releases:
            # Skip archived releases
            if getattr(release, 'archived', False):
                continue  # Skip archived releases
            
            # Filter releases from January 2025 onwards
            release_date = getattr(release, 'release_date', None)
            if release_date and release_date < cutoff_date:
                continue  # Skip releases before January 2025
            
            # If team filter is specified, check if this release has tickets from that team
            if team_filter:
                try:
                    tickets = client.get_tickets_by_release(release.name, max_results=2000)
                    has_team_tickets = any(
                        ticket.team and team_filter.lower() in ticket.team.lower() 
                        for ticket in tickets
                    )
                    if not has_team_tickets:
                        continue  # Skip releases without tickets from the specified team
                except Exception as e:
                    # If we can't check tickets, include the release to be safe
                    pass
                
            # Also include unreleased/future releases without dates
            release_data = {
                'name': release.name,
                'id': release.id,
                'description': getattr(release, 'description', '') or '',
                'releaseDate': release_date.isoformat() if release_date else None,
                'released': getattr(release, 'released', False),
                'archived': getattr(release, 'archived', False)
            }
            releases_data.append(release_data)
        
        # Sort by release date (most recent first), then by name
        releases_data.sort(key=lambda x: (
            x['releaseDate'] or '9999-12-31',
            x['name']
        ), reverse=True)
        
        # Cache the result if no team filter
        if not team_filter:
            set_cached_data('releases', releases_data)
        
        return jsonify(releases_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/releases')
def releases_page():
    """Releases listing page."""
    return render_template('releases.html')

@app.route('/releases/<release_name>')
def release_detail(release_name):
    """Release detail page showing tickets."""
    # Get labels from URL parameters
    labels_param = request.args.get('labels', '')
    labels = [label.strip() for label in labels_param.split(',') if label.strip()] if labels_param else []
    
    return render_template('release_detail.html', release_name=release_name, labels=labels)

@app.route('/releases/multiple')
def multiple_releases_detail():
    """Multiple releases detail page showing combined tickets."""
    release_names = request.args.get('releases', '').split(',')
    release_names = [name.strip() for name in release_names if name.strip()]
    
    # Get labels from URL parameters
    labels_param = request.args.get('labels', '')
    labels = [label.strip() for label in labels_param.split(',') if label.strip()] if labels_param else []
    
    # Pass the release names and labels to the template
    return render_template('release_detail.html', release_name='multiple', release_names=release_names, labels=labels)

@app.route('/releases/<release_name>/report')
def release_report(release_name):
    """Release performance report page."""
    return render_template('release_report.html', release_name=release_name)

@app.route('/api/releases/<release_name>/tickets')
def get_release_tickets(release_name):
    """Get tickets for a specific release."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    # Get optional filters
    team_filter = request.args.get('team', '')
    labels_param = request.args.get('labels', '')
    project_filter = request.args.get('project', '')  # Project filter is required
    
    # Parse labels from comma-separated string
    labels = []
    if labels_param:
        labels = [label.strip() for label in labels_param.split(',') if label.strip()]
    
    try:
        # Clean up release name - remove UI suffixes like "(Unreleased)"
        clean_release_name = release_name
        if '(Unreleased)' in release_name:
            clean_release_name = release_name.replace(' (Unreleased)', '').strip()
        
        # Use the project parameter from the UI - no automatic inference
        project_key = project_filter
        if not project_key:
            return jsonify({'error': 'Project parameter is required. Please select a project in the UI.'}), 400
        
        # Get tickets from the specified project and release (with OR logic for labels)
        tickets = client.get_tickets_by_release(clean_release_name, project_key, max_results=5000, labels=labels if labels else None)
        
        # Filter by team if specified
        if team_filter:
            tickets = [ticket for ticket in tickets if ticket.team and team_filter.lower() in ticket.team.lower()]
        
        # Filter out tickets with completed/closed statuses that shouldn't be displayed
        excluded_statuses = ['ready for release', 'closed', 'done', 'ready to accept']
        tickets = [ticket for ticket in tickets if ticket.status.lower() not in excluded_statuses]
        
        # Convert tickets to JSON-serializable format
        tickets_data = []
        for ticket in tickets:
            tickets_data.append({
                'key': ticket.key,
                'summary': ticket.summary,
                'status': ticket.status,
                'assignee': ticket.assignee,
                'priority': ticket.priority,
                'issue_type': ticket.issue_type,
                'story_points': ticket.story_points,
                'fix_version': ticket.fix_version,
                'labels': ticket.labels or [],
                'url': f"{client.jira_server}/browse/{ticket.key}",
                'description': getattr(ticket, 'description', '') or '',
                'created': getattr(ticket, 'created', None),
                'updated': getattr(ticket, 'updated', None),
                'team': ticket.team,
                'qa_contact': getattr(ticket, 'qa_contact', None)
            })
        
        # Calculate statistics
        stats = calculate_stats(tickets)
        
        return jsonify({
            'tickets': tickets_data,
            'stats': stats,
            'total': len(tickets_data),
            'filters': {
                'release': release_name,
                'labels': labels,
                'team': team_filter
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/multiple/tickets')
def get_multiple_releases_tickets():
    """Get tickets for multiple releases."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    # Get release names from query parameter
    release_names = request.args.get('releases', '').split(',')
    release_names = [name.strip() for name in release_names if name.strip()]
    
    # Get optional filters
    team_filter = request.args.get('team', '')
    labels_param = request.args.get('labels', '')
    project_filter = request.args.get('project', '')
    
    # Parse labels from comma-separated string
    labels = []
    if labels_param:
        labels = [label.strip() for label in labels_param.split(',') if label.strip()]
    
    try:
        all_tickets = []
        
        # Check if we have either releases or labels
        if not release_names and not labels:
            return jsonify({'error': 'Either release names or labels must be provided'}), 400
        
        # Case 1: Specific releases provided
        if release_names:
            # Fetch tickets for each release
            for release_name in release_names:
                # Try with project parameter if provided, otherwise try without for backward compatibility
                if project_filter:
                    tickets = client.get_tickets_by_release(release_name, project_key=project_filter, max_results=5000, labels=labels if labels else None)
                else:
                    # For backward compatibility, try to infer project from release name
                    inferred_project = None
                    if any(keyword in release_name.lower() for keyword in ['esp', 'august', 'september', 'october', 'november', 'december', 'january', 'february', 'march', 'april', 'may', 'june', 'july']):
                        inferred_project = 'ESP'
                    elif any(keyword in release_name.lower() for keyword in ['sr_', 'pssr']):
                        inferred_project = 'PSSR'
                    
                    if inferred_project:
                        tickets = client.get_tickets_by_release(release_name, project_key=inferred_project, max_results=5000, labels=labels if labels else None)
                    else:
                        # Try both projects and combine results
                        tickets = []
                        for proj in ['ESP', 'PSSR']:
                            try:
                                proj_tickets = client.get_tickets_by_release(release_name, project_key=proj, max_results=5000, labels=labels if labels else None)
                                tickets.extend(proj_tickets)
                            except:
                                continue
                
                # Filter by team if specified
                if team_filter:
                    tickets = [ticket for ticket in tickets if ticket.team and team_filter.lower() in ticket.team.lower()]
                
                # Add release name to each ticket for identification
                for ticket in tickets:
                    ticket.release_name = release_name
                
                all_tickets.extend(tickets)
        
        # Case 2: Only labels provided (no specific releases) - search all tickets with these labels
        elif labels:
            # Use project filter if provided, otherwise search both projects
            projects_to_search = [project_filter] if project_filter else ['ESP', 'PSSR']
            
            for proj in projects_to_search:
                try:
                    # Use a dummy release name and rely on labels OR logic to find all matching tickets
                    # This will find tickets that have either the fixVersion OR the labels
                    tickets = client.get_tickets_by_release('__LABEL_SEARCH__', project_key=proj, max_results=5000, labels=labels)
                    
                    # Filter by team if specified
                    if team_filter:
                        tickets = [ticket for ticket in tickets if ticket.team and team_filter.lower() in ticket.team.lower()]
                    
                    # Add project info to each ticket for identification
                    for ticket in tickets:
                        ticket.release_name = f"Label: {', '.join(labels)}"
                        ticket.project_name = proj
                    
                    all_tickets.extend(tickets)
                except Exception as e:
                    print(f"⚠️ Error searching {proj} for labels {labels}: {e}")
                    continue
        
        # Deduplicate tickets by key (same ticket can appear in multiple releases)
        unique_tickets = {}
        for ticket in all_tickets:
            ticket_key = ticket.key
            if ticket_key not in unique_tickets:
                unique_tickets[ticket_key] = ticket
            else:
                # If ticket already exists, merge release names to show all releases it belongs to
                existing_ticket = unique_tickets[ticket_key]
                existing_release = getattr(existing_ticket, 'release_name', '')
                current_release = getattr(ticket, 'release_name', '')
                
                # Combine release names if different
                if existing_release and current_release and existing_release != current_release:
                    combined_releases = f"{existing_release}, {current_release}"
                    existing_ticket.release_name = combined_releases
        
        # Convert unique tickets to list
        all_tickets = list(unique_tickets.values())
        print(f"🔍 Deduplicated {len(all_tickets)} unique tickets from multiple releases")
        
        # Filter out tickets with completed/closed statuses that shouldn't be displayed
        excluded_statuses = ['ready for release', 'closed', 'done', 'ready to accept']
        all_tickets = [ticket for ticket in all_tickets if ticket.status.lower() not in excluded_statuses]
        print(f"🔍 After filtering out completed/closed statuses: {len(all_tickets)} tickets remaining")
        
        # Convert tickets to JSON-serializable format
        tickets_data = []
        for ticket in all_tickets:
            tickets_data.append({
                'key': ticket.key,
                'summary': ticket.summary,
                'status': ticket.status,
                'assignee': ticket.assignee,
                'priority': ticket.priority,
                'issue_type': ticket.issue_type,
                'story_points': ticket.story_points,
                'fix_version': ticket.fix_version,
                'labels': ticket.labels or [],
                'url': f"{client.jira_server}/browse/{ticket.key}",
                'description': getattr(ticket, 'description', '') or '',
                'created': getattr(ticket, 'created', None),
                'updated': getattr(ticket, 'updated', None),
                'team': ticket.team,
                'qa_contact': getattr(ticket, 'qa_contact', None),
                'release_name': getattr(ticket, 'release_name', '')
            })
        
        # Calculate statistics
        stats = calculate_stats(all_tickets)
        
        return jsonify({
            'tickets': tickets_data,
            'stats': stats,
            'total': len(tickets_data),
            'release_names': release_names
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/<release_name>/stats')
def get_release_stats(release_name):
    """Get ticket statistics for a specific release."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    # Get filters (same as tickets endpoint)
    project_filter = request.args.get('project', '')
    team_filter = request.args.get('team', '')
    labels_param = request.args.get('labels', '')
    
    # Parse labels from comma-separated string
    labels = []
    if labels_param:
        labels = [label.strip() for label in labels_param.split(',') if label.strip()]
    
    try:
        # Clean up release name - remove UI suffixes like "(Unreleased)"
        clean_release_name = release_name
        if '(Unreleased)' in release_name:
            clean_release_name = release_name.replace(' (Unreleased)', '').strip()
        
        # Use the project parameter from the UI - no automatic inference
        project_key = project_filter
        if not project_key:
            return jsonify({'error': 'Project parameter is required. Please select a project in the UI.'}), 400
        
        # Get tickets from the specified project and release (with OR logic for labels)
        tickets = client.get_tickets_by_release(clean_release_name, project_key, max_results=5000, labels=labels if labels else None)
        
        # Filter by team if specified (same logic as tickets endpoint)
        if team_filter:
            tickets = [ticket for ticket in tickets if ticket.team and team_filter.lower() in ticket.team.lower()]
        
        ticket_count = len(tickets)
        total_story_points = sum(
            getattr(ticket, 'story_points', 0) or 0 
            for ticket in tickets
        )
        
        response = jsonify({
            'releaseName': release_name,
            'ticketCount': ticket_count,
            'totalStoryPoints': total_story_points
        })
        
        # Add cache-control headers to prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<ticket_key>/update', methods=['POST'])
def update_ticket(ticket_key):
    """Update a specific ticket."""
    app.logger.info(f"DEBUG: Updating ticket {ticket_key}")
    
    client = get_jira_client()
    if not client:
        app.logger.error("DEBUG: JIRA client not available")
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        # Get the update data from request
        update_data = request.get_json()
        app.logger.info(f"DEBUG: Update data: {update_data}")
        
        if not update_data:
            app.logger.error("DEBUG: No update data provided")
            return jsonify({'error': 'No update data provided'}), 400
        
        # Update the ticket in JIRA
        app.logger.info(f"DEBUG: Calling client.update_ticket...")
        success = client.update_ticket(ticket_key, update_data)
        app.logger.info(f"DEBUG: Update result: {success}")
        
        if success:
            return jsonify({'message': 'Ticket updated successfully'})
        else:
            return jsonify({'error': 'Failed to update ticket'}), 500
            
    except Exception as e:
        app.logger.error(f"DEBUG: Exception occurred: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams')
def get_teams():
    """Get list of all teams."""
    print("[TEAMS] Teams API endpoint called")
    
    client = get_jira_client()
    if not client:
        print("[ERROR] JIRA client not available for teams")
        return jsonify({'error': 'JIRA client not available'}), 500
    
    # Get project filter from query parameters
    project_filter = request.args.get('project', '')
    print(f"[FILTER] Project filter for teams: {project_filter}")
    
    # Create cache key based on project filter
    cache_key = f"teams_{project_filter}" if project_filter else 'teams'
    
    # Check cache first
    cached_teams = get_cached_data(cache_key)
    if cached_teams is not None:
        print(f"[CACHE] Returning cached teams for {project_filter or 'all projects'}: {cached_teams}")
        return jsonify(cached_teams)
    
    try:
        print("[INFO] Fetching fresh teams data...")
        if project_filter:
            # Handle multiple projects (comma-separated)
            project_keys = [p.strip() for p in project_filter.split(',') if p.strip()]
            teams = client.get_teams_for_projects(project_keys)
        else:
            teams = client.get_teams()
        
        print(f"[SUCCESS] Retrieved {len(teams)} teams: {teams}")
        
        # Cache the result
        set_cached_data(cache_key, teams)
        
        return jsonify(teams)
    except Exception as e:
        print(f"[ERROR] Error getting teams: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects')
def get_projects():
    """Get list of all JIRA projects."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        # Get projects directly from JIRA
        jira_projects = client.jira.projects()
        projects = [
            {
                "key": p.key, 
                "name": p.name, 
                "id": p.id,
                "description": getattr(p, 'description', '') or ''
            }
            for p in jira_projects
        ]
        
        # Sort by key for better user experience
        projects.sort(key=lambda x: x['key'])
        
        return jsonify(projects)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/project/versions')
def get_project_versions():
    """Get list of all project versions/releases for dropdown editing."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        releases = client.get_releases()
        # Convert to simple list of release names for dropdown
        version_names = [release.name for release in releases if release.name]
        version_names.sort()  # Sort alphabetically
        
        return jsonify(version_names)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams/<team_name>/members')
def get_team_members(team_name):
    """Get members of a specific team from JIRA team API."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        # Get release parameter for better fallback team member extraction
        release_name = request.args.get('release')
        
        print(f"[TEAM] API: Getting team members for '{team_name}' using JIRA team API (release: {release_name})...")
        
        # Use the new JIRA team API method with release context
        members = client.get_jira_team_members(team_name, release_name=release_name)
        
        print(f"[SUCCESS] API: Returning {len(members)} team members for '{team_name}': {members}")
        return jsonify(members)
        
    except Exception as e:
        print(f"[ERROR] API: Error getting team members for '{team_name}': {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams/<team_name>/assignee-workload')
def get_team_assignee_workload(team_name):
    """Get workload breakdown by assignee for a team."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    release_name = request.args.get('release', '')
    project_filter = request.args.get('project', '')
    
    try:
        # For now, pass project info via the workload method (we could enhance this later)
        workload = client.get_team_assignee_workload(team_name, release_name if release_name else None)
        return jsonify(workload)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams/<team_name>/tickets-count')
def get_team_tickets_count(team_name):
    """Get ticket count and statistics for a team."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    release_name = request.args.get('release', '')
    
    try:
        stats = client.get_team_tickets_count(team_name, release_name if release_name else None)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# In-memory storage for team availability (in production, use a database)
team_availability_data = {}

@app.route('/api/teams/<team_name>/filtered-members')
def get_filtered_team_members(team_name):
    """Get team members who are actually working on the currently filtered tickets."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        # Get filter parameters (same as ticket filtering)
        release_name = request.args.get('release')
        project_key = request.args.get('project', 'PSSR')
        labels = request.args.getlist('labels')
        status_filter = request.args.get('status')
        assignee_filter = request.args.get('assignee')
        
        print(f"[FILTER] Getting filtered team members for '{team_name}' with filters: release={release_name}, project={project_key}, labels={labels}")
        
        # Get tickets based on current filters
        tickets = client.get_tickets_by_release(
            release_name or 'Sep2025', 
            project_key=project_key, 
            labels=labels if labels else None,
            max_results=1000
        )
        
        # Filter tickets by team
        team_tickets = [t for t in tickets if t.team == team_name]
        
        # Apply additional filters if specified
        if status_filter and status_filter != 'All Statuses':
            team_tickets = [t for t in team_tickets if t.status == status_filter]
        
        if assignee_filter and assignee_filter != 'All Assignees':
            team_tickets = [t for t in team_tickets if t.assignee == assignee_filter]
        
        print(f"[INFO] Found {len(team_tickets)} filtered tickets for team '{team_name}'")
        
        # Extract team members ONLY from the exact filtered tickets (no broader search)
        filtered_members = set()
        
        print(f"[INFO] Extracting team members from {len(team_tickets)} filtered tickets only")
        
        for ticket in team_tickets:
            # Add assignee if present
            if ticket.assignee and ticket.assignee.strip():
                filtered_members.add(ticket.assignee.strip())
                print(f"[ASSIGNEE] Added assignee: {ticket.assignee.strip()} from {ticket.key}")
            
            # Add QA contact if present (from ticket object, not separate search)
            if hasattr(ticket, 'qa_contact') and ticket.qa_contact and ticket.qa_contact.strip():
                filtered_members.add(ticket.qa_contact.strip())
                print(f"[QA] Added QA contact: {ticket.qa_contact.strip()} from {ticket.key}")
        
        members_list = sorted(list(filtered_members))
        print(f"[SUCCESS] Returning {len(members_list)} filtered team members: {members_list}")
        
        return jsonify(members_list)
        
    except Exception as e:
        print(f"[ERROR] Error getting filtered team members: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/teams/<team_name>/availability', methods=['GET', 'POST'])
def manage_team_availability(team_name):
    """Get or set team member availability."""
    if request.method == 'GET':
        # Return current availability data for the team
        team_data = team_availability_data.get(team_name, {})
        # Separate member availability from metadata
        availability_data = {k: v for k, v in team_data.items() if not k.startswith('_')}
        metadata = {k: v for k, v in team_data.items() if k.startswith('_')}
        
        return jsonify({
            'availability': availability_data,
            'metadata': metadata
        })
    
    elif request.method == 'POST':
        # Update availability data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if team_name not in team_availability_data:
            team_availability_data[team_name] = {}
        
        # Handle availability data (could be individual member data or bulk with metadata)
        if 'availability' in data and 'metadata' in data:
            # New format with metadata (dates)
            availability_data = data['availability']
            metadata = data['metadata']
            
            # Update member availability
            for member_name, availability in availability_data.items():
                try:
                    team_availability_data[team_name][member_name] = float(availability)
                except (ValueError, TypeError):
                    return jsonify({'error': f'Invalid availability value for {member_name}'}), 400
            
            # Store metadata (start_date, end_date, etc.)
            for key, value in metadata.items():
                if key.startswith('_'):
                    team_availability_data[team_name][key] = value
        else:
            # Legacy format - just member availability data
            for member_name, availability in data.items():
                try:
                    team_availability_data[team_name][member_name] = float(availability)
                except (ValueError, TypeError):
                    return jsonify({'error': f'Invalid availability value for {member_name}'}), 400
        
        # Calculate total availability (exclude metadata keys)
        availability_values = [v for k, v in team_availability_data[team_name].items() if not k.startswith('_')]
        total_availability = sum(availability_values)
        
        return jsonify({
            'success': True,
            'total_availability': total_availability,
            'team_data': team_availability_data[team_name]
        })

@app.route('/api/releases/batch-stats', methods=['POST'])
def get_batch_release_stats():
    """Get ticket statistics for multiple releases in a single request."""
    print("[STATS] Batch stats endpoint called")
    
    client = get_jira_client()
    if not client:
        print("[ERROR] JIRA client not available")
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        data = request.get_json()
        print(f"[REQUEST] Request data: {data}")
        
        if not data or 'releaseNames' not in data:
            print("[ERROR] No release names provided")
            return jsonify({'error': 'No release names provided'}), 400
        
        release_names = data['releaseNames']
        team_filter = data.get('team', '')
        max_results = min(int(data.get('maxResults', 1000)), 5000)  # Cap at 5000 for performance
        
        print(f"[PROCESSING] Processing {len(release_names)} releases: {release_names}")
        
        if not isinstance(release_names, list):
            return jsonify({'error': 'releaseNames must be an array'}), 400
        
        if len(release_names) > 20:  # Limit batch size
            return jsonify({'error': 'Too many releases requested (max 20)'}), 400
        
        batch_stats = {}
        
        for release_name in release_names:
            print(f"[RELEASE] Processing release: {release_name}")
            try:
                tickets = client.get_tickets_by_release(release_name, max_results=5000)
                print(f"[TICKETS] Found {len(tickets)} tickets for {release_name}")
                
                # Filter by team if specified
                if team_filter:
                    tickets = [
                        ticket for ticket in tickets 
                        if ticket.team and team_filter.lower() in ticket.team.lower()
                    ]
                    print(f"🎯 After team filter: {len(tickets)} tickets")
                
                ticket_count = len(tickets)
                total_story_points = sum(
                    getattr(ticket, 'story_points', 0) or 0 
                    for ticket in tickets
                )
                
                # Debug story points calculation
                if tickets:
                    story_points_list = [getattr(ticket, 'story_points', 0) or 0 for ticket in tickets]
                    print(f"📊 Story points breakdown for {release_name}: {story_points_list}")
                    print(f"📊 Individual story points: {[sp for sp in story_points_list if sp > 0]}")
                
                print(f"📊 Stats for {release_name}: {ticket_count} tickets, {total_story_points} story points")
                
                batch_stats[release_name] = {
                    'releaseName': release_name,
                    'ticketCount': ticket_count,
                    'totalStoryPoints': total_story_points
                }
                
            except Exception as e:
                print(f"❌ Error processing {release_name}: {str(e)}")
                batch_stats[release_name] = {
                    'releaseName': release_name,
                    'ticketCount': 0,
                    'totalStoryPoints': 0,
                    'error': str(e)
                }
        
        print(f"✅ Batch processing complete. Returning stats for {len(batch_stats)} releases")
        return jsonify({
            'stats': batch_stats,
            'totalReleases': len(release_names),
            'successfulReleases': len([s for s in batch_stats.values() if 'error' not in s])
        })
        
    except Exception as e:
        print(f"❌ Batch stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Export endpoints
@app.route('/api/releases/<release_name>/export')
def export_release_tickets(release_name):
    """Export tickets for a release to CSV."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        tickets = client.get_tickets_by_release(release_name, max_results=5000)
        filename = export_to_csv(tickets, release_name)
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"{release_name.replace(' ', '_')}_tickets.csv",
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/<release_name>/export-csv')
def export_release_tickets_csv(release_name):
    """Export tickets for a release to CSV."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        tickets = client.get_tickets_by_release(release_name, max_results=5000)
        filename = export_to_csv(tickets, release_name)
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"{release_name.replace(' ', '_')}_tickets.csv",
            mimetype='text/csv'
        )
    except Exception as e:
        app.logger.error(f"Error exporting to CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/<release_name>/export-excel')
def export_release_tickets_excel(release_name):
    """Export tickets for a release to Excel."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        tickets = client.get_tickets_by_release(release_name, max_results=5000)
        
        from utils import export_to_excel
        filename = export_to_excel(tickets, release_name)
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"{release_name.replace(' ', '_')}_tickets.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        app.logger.error(f"Error exporting to Excel: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/<release_name>/export-page', methods=['POST'])
def export_page_as_excel(release_name):
    """Export the current page state as an Excel file with multiple sheets."""
    print(f"DEBUG Backend: Export page request received for release: {release_name}")
    
    try:
        # Get page data from request
        page_data = request.get_json()
        print(f"DEBUG Backend: Raw request data received")
        
        if not page_data:
            print("DEBUG Backend: No page data provided")
            return jsonify({'error': 'No page data provided'}), 400
        
        # Debug logging with more detail
        print(f"DEBUG Backend: page_data type: {type(page_data)}")
        print(f"DEBUG Backend: page_data keys: {list(page_data.keys()) if isinstance(page_data, dict) else 'Not a dict'}")
        
        if 'current_tickets' in page_data:
            tickets_data = page_data['current_tickets']
            print(f"DEBUG Backend: current_tickets type: {type(tickets_data)}")
            print(f"DEBUG Backend: current_tickets length: {len(tickets_data) if isinstance(tickets_data, list) else 'Not a list'}")
            
            if isinstance(tickets_data, list):
                print(f"DEBUG Backend: Checking first few tickets...")
                for i, ticket in enumerate(tickets_data[:5]):  # Check more tickets
                    print(f"DEBUG Backend: Ticket {i} type: {type(ticket)}")
                    if isinstance(ticket, str):
                        print(f"DEBUG Backend: ERROR - Ticket {i} is a string: {ticket}")
                        # Return early with detailed error
                        return jsonify({'error': f'Ticket {i} is a string instead of object: {ticket}'}), 400
                    elif isinstance(ticket, dict):
                        print(f"DEBUG Backend: Ticket {i} keys: {list(ticket.keys())}")
                        if 'key' in ticket:
                            print(f"DEBUG Backend: Ticket {i} key: {ticket['key']}")
                    else:
                        print(f"DEBUG Backend: ERROR - Ticket {i} is neither string nor dict: {type(ticket)}")
                        return jsonify({'error': f'Ticket {i} has invalid type: {type(ticket)}'}), 400
        
        # Before calling export function, let's check if JIRA client is needed
        client = get_jira_client()
        if not client:
            print("DEBUG Backend: JIRA client not available")
            return jsonify({'error': 'JIRA client not available'}), 500
        
        print("DEBUG Backend: About to call export_page_to_excel...")
        from utils import export_page_to_excel
        filename = export_page_to_excel(page_data, release_name)
        print(f"DEBUG Backend: Export completed successfully, filename: {filename}")
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"{release_name.replace(' ', '_')}_page_export.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        print(f"DEBUG Backend: Exception occurred: {str(e)}")
        print(f"DEBUG Backend: Exception type: {type(e)}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"DEBUG Backend: Full traceback:\n{traceback_str}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/export-multiple')
def export_multiple_releases():
    """Export tickets from multiple releases to CSV."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    release_names = request.args.get('releases', '').split(',')
    release_names = [name.strip() for name in release_names if name.strip()]
    
    if not release_names:
        return jsonify({'error': 'No releases specified'}), 400
    
    try:
        all_tickets = []
        
        # Collect tickets from all specified releases
        for release_name in release_names:
            tickets = client.get_tickets_by_release(release_name, max_results=5000)
            # Add release name to each ticket for identification
            for ticket in tickets:
                ticket.release_name = release_name
            all_tickets.extend(tickets)
        
        if not all_tickets:
            return jsonify({'error': 'No tickets found in the specified releases'}), 404
        
        # Create CSV with release information
        filename = export_to_csv(all_tickets, f"Multiple_Releases_{len(release_names)}")
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"Multiple_Releases_{len(release_names)}_tickets.csv",
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Report endpoints
@app.route('/api/releases/<release_name>/report')
def get_release_report(release_name):
    """Get comprehensive report data for a specific release."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    # Get project parameter (required)
    project_key = request.args.get('project')
    if not project_key:
        return jsonify({'error': 'Project parameter is required. Please select a project in the UI.'}), 400
    
    try:
        tickets = client.get_tickets_by_release(release_name, project_key=project_key, max_results=5000)
        
        # Initialize counters
        assignee_stats = {}
        total_completed = 0
        total_in_progress = 0
        total_story_points_done = 0
        total_tickets = len(tickets)
        
        # Process each ticket
        for ticket in tickets:
            assignee = getattr(ticket, 'assignee', 'Unassigned') or 'Unassigned'
            status = getattr(ticket, 'status', 'Unknown') or 'Unknown'
            issue_type = getattr(ticket, 'issue_type', 'Unknown') or 'Unknown'
            story_points = getattr(ticket, 'story_points', 0) or 0
            
            # Initialize assignee stats if not exists
            if assignee not in assignee_stats:
                assignee_stats[assignee] = {
                    'assignee': assignee,
                    'completed_tickets': 0,
                    'in_progress_tickets': 0,
                    'total_tickets': 0,
                    'story_points_done': 0,
                    'ticket_types': {
                        'story': 0,
                        'bug': 0,
                        'spike': 0,
                        'other': 0
                    }
                }
            
            # Update assignee stats
            assignee_stats[assignee]['total_tickets'] += 1
            
            # Count by status
            if status.lower() in ['done', 'closed', 'resolved', 'completed', 'ready to accept']:
                assignee_stats[assignee]['completed_tickets'] += 1
                assignee_stats[assignee]['story_points_done'] += story_points
                total_completed += 1
                total_story_points_done += story_points
            elif status.lower() in ['in progress', 'in development', 'in review', 'dev in progress', 'ready for story review']:
                assignee_stats[assignee]['in_progress_tickets'] += 1
                total_in_progress += 1
            
            # Count by issue type
            issue_type_lower = issue_type.lower()
            if 'story' in issue_type_lower:
                assignee_stats[assignee]['ticket_types']['story'] += 1
            elif 'bug' in issue_type_lower:
                assignee_stats[assignee]['ticket_types']['bug'] += 1
            elif 'spike' in issue_type_lower:
                assignee_stats[assignee]['ticket_types']['spike'] += 1
            else:
                assignee_stats[assignee]['ticket_types']['other'] += 1
        
        # Convert to list, add completion rates, and sort by completed tickets (descending)
        assignee_list = list(assignee_stats.values())
        
        # Calculate completion rate for each assignee
        for assignee in assignee_list:
            if assignee['total_tickets'] > 0:
                assignee['completion_rate'] = (assignee['completed_tickets'] / assignee['total_tickets']) * 100
            else:
                assignee['completion_rate'] = 0.0
        
        assignee_list.sort(key=lambda x: x['completed_tickets'], reverse=True)
        
        return jsonify({
            'release_name': release_name,
            'summary': {
                'total_tickets': total_tickets,
                'total_completed': total_completed,
                'total_in_progress': total_in_progress,
                'total_story_points_done': total_story_points_done
            },
            'assignee_stats': assignee_list
        })
        
    except Exception as e:
        app.logger.error(f"Error generating report for {release_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/releases/<release_name>/report/export')
def export_release_report(release_name):
    """Export release report to Excel."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    # Get project parameter (required)
    project_key = request.args.get('project')
    if not project_key:
        return jsonify({'error': 'Project parameter is required. Please select a project in the UI.'}), 400
    
    try:
        # Get report data first
        tickets = client.get_tickets_by_release(release_name, project_key=project_key, max_results=5000)
        
        # Calculate the same stats as the report endpoint
        assignee_stats = {}
        total_completed = 0
        total_in_progress = 0
        total_story_points_done = 0
        total_tickets = len(tickets)
        
        # Process each ticket
        for ticket in tickets:
            assignee = getattr(ticket, 'assignee', 'Unassigned') or 'Unassigned'
            status = getattr(ticket, 'status', 'Unknown') or 'Unknown'
            issue_type = getattr(ticket, 'issue_type', 'Unknown') or 'Unknown'
            story_points = getattr(ticket, 'story_points', 0) or 0
            
            # Initialize assignee stats if not exists
            if assignee not in assignee_stats:
                assignee_stats[assignee] = {
                    'assignee': assignee,
                    'completed_tickets': 0,
                    'in_progress_tickets': 0,
                    'total_tickets': 0,
                    'story_points_done': 0,
                    'ticket_types': {
                        'story': 0,
                        'bug': 0,
                        'spike': 0,
                        'other': 0
                    }
                }
            
            # Update assignee stats
            assignee_stats[assignee]['total_tickets'] += 1
            
            # Count by status
            if status.lower() in ['done', 'closed', 'resolved', 'completed', 'ready to accept']:
                assignee_stats[assignee]['completed_tickets'] += 1
                assignee_stats[assignee]['story_points_done'] += story_points
                total_completed += 1
                total_story_points_done += story_points
            elif status.lower() in ['in progress', 'in development', 'in review', 'dev in progress', 'ready for story review']:
                assignee_stats[assignee]['in_progress_tickets'] += 1
                total_in_progress += 1
            
            # Count by issue type
            issue_type_lower = issue_type.lower()
            if 'story' in issue_type_lower:
                assignee_stats[assignee]['ticket_types']['story'] += 1
            elif 'bug' in issue_type_lower:
                assignee_stats[assignee]['ticket_types']['bug'] += 1
            elif 'spike' in issue_type_lower:
                assignee_stats[assignee]['ticket_types']['spike'] += 1
            else:
                assignee_stats[assignee]['ticket_types']['other'] += 1
        
        # Convert to list, add completion rates, and sort by completed tickets (descending)
        assignee_list = list(assignee_stats.values())
        
        # Calculate completion rate for each assignee
        for assignee in assignee_list:
            if assignee['total_tickets'] > 0:
                assignee['completion_rate'] = (assignee['completed_tickets'] / assignee['total_tickets']) * 100
            else:
                assignee['completion_rate'] = 0.0
        
        assignee_list.sort(key=lambda x: x['completed_tickets'], reverse=True)
        
        # Prepare summary stats
        summary_stats = {
            'total_tickets': total_tickets,
            'total_completed': total_completed,
            'total_in_progress': total_in_progress,
            'total_story_points_done': total_story_points_done
        }
        
        # Export to Excel using the utils function
        from utils import export_report_to_excel
        filename = export_report_to_excel(release_name, assignee_list, summary_stats, tickets)
        
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"{release_name.replace(' ', '_')}_report.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        app.logger.error(f"Error exporting report for {release_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear server-side cache."""
    global cache
    cache = {
        'teams': {'data': None, 'timestamp': 0},
        'releases': {'data': None, 'timestamp': 0}
    }
    return jsonify({'message': 'Cache cleared successfully'})

@app.route('/api/tickets/<ticket_key>/transitions')
def get_ticket_transitions(ticket_key):
    """Get available transitions for a ticket."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        issue = client.jira.issue(ticket_key)
        transitions = client.jira.transitions(issue)
        
        # Format transitions for frontend
        formatted_transitions = []
        for transition in transitions:
            formatted_transitions.append({
                'id': transition['id'],
                'name': transition['to']['name'],
                'to_status': transition['to']['name']
            })
        
        return jsonify({'transitions': formatted_transitions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<ticket_key>/statuses')
def get_ticket_statuses(ticket_key):
    """Get available statuses for a ticket."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        statuses = client.get_available_statuses(ticket_key)
        return jsonify(statuses)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/project/users')
def get_assignable_users():
    """Get users that can be assigned to issues in the project."""
    client = get_jira_client()
    if not client:
        return jsonify({'error': 'JIRA client not available'}), 500
    
    try:
        users = client.get_assignable_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error="Internal server error"), 500

if __name__ == '__main__':
    print(">> Starting Release Planner Web UI...")
    print(">> Testing JIRA connection...")
    
    client = get_jira_client()
    if client:
        try:
            info = client.get_server_info()
            print(f"[OK] Connected to JIRA: {info.get('baseUrl', 'Unknown')}")
            print(f"[INFO] Server Version: {info.get('version', 'Unknown')}")
            print(f"[USER] Current User: {client.get_current_user()}")
        except Exception as e:
            print(f"[ERROR] JIRA connection test failed: {e}")
    else:
        print("[ERROR] Failed to initialize JIRA client")
    
    print("\n>> Starting web server...")
    print(">> Open your browser to: http://localhost:5001")
    print(">> Press Ctrl+C to stop the server")
    print()
    print("=" * 60)
    print("*** APPLICATION IS READY! ***")
    print(">> Go to: http://localhost:5001")
    print(">> The JIRA Release Planner is now running!")
    print("=" * 60)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
