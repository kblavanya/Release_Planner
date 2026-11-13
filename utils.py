"""
Utility functions for data processing and display
"""
import csv
import pandas as pd
from typing import List, Dict, Any
from tabulate import tabulate
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from models import JiraTicket, JiraRelease, ReleaseSummary
import os
from datetime import datetime


def display_releases(releases: List[JiraRelease]):
    """Display releases in a formatted table"""
    if not releases:
        print("No releases found.")
        return
    
    headers = ["Name", "Status", "Release Date", "Description"]
    rows = []
    
    for release in releases:
        status = "Released" if release.released else "Unreleased"
        if release.archived:
            status = "Archived"
        
        release_date = release.release_date.strftime('%Y-%m-%d') if release.release_date else "Not set"
        description = (release.description or "")[:50] + "..." if release.description and len(release.description) > 50 else (release.description or "")
        
        rows.append([release.name, status, release_date, description])
    
    print("\n📋 Available Releases:")
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def display_tickets(tickets: List[JiraTicket], max_description_length: int = 50):
    """Display tickets in a formatted table"""
    if not tickets:
        print("No tickets found.")
        return
    
    headers = ["Key", "Summary", "Status", "Assignee", "Priority", "Type", "Story Points"]
    rows = []
    
    for ticket in tickets:
        summary = ticket.summary[:50] + "..." if len(ticket.summary) > 50 else ticket.summary
        assignee = ticket.assignee or "Unassigned"
        story_points = ticket.story_points or "-"
        
        rows.append([
            ticket.key,
            summary,
            ticket.status,
            assignee,
            ticket.priority,
            ticket.issue_type,
            story_points
        ])
    
    print(f"\n🎫 Tickets ({len(tickets)} total):")
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def display_release_summary(summary: ReleaseSummary):
    """Display release summary statistics"""
    print(f"\n📊 Release Summary: {summary.release_name}")
    print("=" * 50)
    print(f"Total Tickets: {summary.total_tickets}")
    print(f"Completion: {summary.completion_percentage:.1f}%")
    
    if summary.total_story_points:
        print(f"Total Story Points: {summary.total_story_points}")
    
    print("\n📈 Tickets by Status:")
    for status, count in summary.tickets_by_status.items():
        percentage = (count / summary.total_tickets) * 100
        print(f"  {status}: {count} ({percentage:.1f}%)")
    
    print("\n🎯 Tickets by Priority:")
    for priority, count in summary.tickets_by_priority.items():
        percentage = (count / summary.total_tickets) * 100
        print(f"  {priority}: {count} ({percentage:.1f}%)")
    
    print("\n👥 Tickets by Assignee:")
    for assignee, count in summary.tickets_by_assignee.items():
        percentage = (count / summary.total_tickets) * 100
        print(f"  {assignee}: {count} ({percentage:.1f}%)")


def export_tickets_to_csv(tickets: List[JiraTicket], filename: str):
    """Export tickets to CSV file"""
    if not tickets:
        print("No tickets to export.")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'Key', 'Summary', 'Status', 'Assignee', 'Priority', 'Type',
            'Created', 'Updated', 'Story Points', 'Fix Version', 'Labels',
            'Components', 'Description'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for ticket in tickets:
            writer.writerow({
                'Key': ticket.key,
                'Summary': ticket.summary,
                'Status': ticket.status,
                'Assignee': ticket.assignee or '',
                'Priority': ticket.priority,
                'Type': ticket.issue_type,
                'Created': ticket.created.isoformat(),
                'Updated': ticket.updated.isoformat(),
                'Story Points': ticket.story_points or '',
                'Fix Version': ticket.fix_version or '',
                'Labels': ', '.join(ticket.labels),
                'Components': ', '.join(ticket.components),
                'Description': ticket.description or ''
            })
    
    print(f"✅ Exported {len(tickets)} tickets to {filename}")


def create_tickets_dataframe(tickets: List[JiraTicket]) -> pd.DataFrame:
    """Convert tickets to pandas DataFrame for analysis"""
    if not tickets:
        return pd.DataFrame()
    
    data = []
    for ticket in tickets:
        data.append({
            'key': ticket.key,
            'summary': ticket.summary,
            'status': ticket.status,
            'assignee': ticket.assignee,
            'priority': ticket.priority,
            'issue_type': ticket.issue_type,
            'created': ticket.created,
            'updated': ticket.updated,
            'story_points': ticket.story_points,
            'fix_version': ticket.fix_version,
            'labels': ', '.join(ticket.labels),
            'components': ', '.join(ticket.components)
        })
    
    return pd.DataFrame(data)


def filter_tickets_by_status(tickets: List[JiraTicket], statuses: List[str]) -> List[JiraTicket]:
    """Filter tickets by status"""
    return [ticket for ticket in tickets if ticket.status in statuses]


def filter_tickets_by_assignee(tickets: List[JiraTicket], assignees: List[str]) -> List[JiraTicket]:
    """Filter tickets by assignee"""
    return [ticket for ticket in tickets if ticket.assignee in assignees]


def filter_tickets_by_priority(tickets: List[JiraTicket], priorities: List[str]) -> List[JiraTicket]:
    """Filter tickets by priority"""
    return [ticket for ticket in tickets if ticket.priority in priorities]


def export_to_csv(tickets: List[JiraTicket], release_name: str = None) -> str:
    """
    Export tickets to CSV format and return filename
    """
    # Generate filename with full path
    safe_name = "tickets"
    if release_name:
        safe_name = release_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(os.getcwd(), f"{safe_name}_{len(tickets)}_tickets_{timestamp}.csv")
    
    # Prepare data for CSV
    data = []
    for ticket in tickets:
        # Handle labels - convert list to comma-separated string
        labels_str = ''
        if hasattr(ticket, 'labels') and ticket.labels:
            labels_str = ', '.join(ticket.labels)
        
        row_data = {
            'Key': ticket.key,
            'Summary': ticket.summary,
            'Status': ticket.status,
            'Assignee': ticket.assignee or 'Unassigned',
            'Priority': ticket.priority,
            'Issue Type': ticket.issue_type,
            'Story Points': ticket.story_points or '',
            'Labels': labels_str,
            'Description': ticket.description or '',
            'Created': ticket.created or '',
            'Updated': ticket.updated or ''
        }
        
        # Add release name if available (for multi-release exports)
        if hasattr(ticket, 'release_name') and ticket.release_name:
            row_data['Release'] = ticket.release_name
        elif release_name and not release_name.startswith('Multiple_Releases'):
            row_data['Release'] = release_name
            
        data.append(row_data)
    
    # Write to CSV
    if data:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    return filename


def calculate_stats(tickets: List[JiraTicket]) -> Dict[str, Any]:
    """
    Calculate statistics for a list of tickets
    """
    if not tickets:
        return {
            'total': 0,
            'completion': 0.0,
            'story_points': 0,
            'statuses': {},
            'priorities': {},
            'assignees': {},
            'types': {}
        }
    
    total = len(tickets)
    
    # Count by various categories
    statuses = {}
    priorities = {}
    assignees = {}
    types = {}
    
    completed_count = 0
    total_story_points = 0
    
    for ticket in tickets:
        # Status counting and completion
        status = ticket.status or 'Unknown'
        statuses[status] = statuses.get(status, 0) + 1
        
        # Check if ticket is completed (you may need to adjust this logic)
        if status.lower() in ['done', 'closed', 'resolved', 'complete']:
            completed_count += 1
        
        # Priority counting
        priority = ticket.priority or 'Unknown'
        priorities[priority] = priorities.get(priority, 0) + 1
        
        # Assignee counting
        assignee = ticket.assignee or 'Unassigned'
        assignees[assignee] = assignees.get(assignee, 0) + 1
        
        # Type counting
        issue_type = ticket.issue_type or 'Unknown'
        types[issue_type] = types.get(issue_type, 0) + 1
        
        # Story points
        if ticket.story_points:
            try:
                total_story_points += float(ticket.story_points)
            except (ValueError, TypeError):
                pass
    
    completion = (completed_count / total * 100) if total > 0 else 0.0
    
    return {
        'total': total,
        'completion': completion,
        'story_points': total_story_points if total_story_points > 0 else None,
        'statuses': statuses,
        'priorities': priorities,
        'assignees': assignees,
        'types': types
    }


def export_to_excel(tickets: List[JiraTicket], release_name: str = None, team_availability: Dict = None, team_workload: Dict = None) -> str:
    """
    Export tickets and team data to Excel format with multiple sheets
    """
    # Generate filename with full path
    safe_name = "tickets"
    if release_name:
        safe_name = release_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(os.getcwd(), f"{safe_name}_{len(tickets)}_tickets_{timestamp}.xlsx")
    
    # Create workbook
    wb = Workbook()
    
    # Remove default sheet
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])
    
    # Sheet 1: Tickets
    create_tickets_sheet(wb, tickets, release_name)
    
    # Sheet 2: Team Availability (if provided)
    if team_availability:
        create_team_availability_sheet(wb, team_availability, team_workload)
    
    # Sheet 3: Summary Statistics
    create_summary_sheet(wb, tickets, release_name)
    
    # Save workbook
    wb.save(filename)
    return filename

def create_tickets_sheet(wb: Workbook, tickets: List[JiraTicket], release_name: str = None):
    """Create tickets sheet with formatting"""
    ws = wb.create_sheet("Tickets")
    
    # Headers
    headers = ['Key', 'Summary', 'Status', 'Assignee', 'Priority', 'Issue Type', 
               'Story Points', 'Fix Version', 'Labels', 'Description', 'Created', 'Updated']
    
    if any(hasattr(ticket, 'release_name') for ticket in tickets) or release_name:
        headers.insert(0, 'Release')
    
    # Add headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Add data
    for row, ticket in enumerate(tickets, 2):
        col = 1
        
        # Add release name if needed
        if 'Release' in headers:
            release_value = getattr(ticket, 'release_name', release_name or '')
            ws.cell(row=row, column=col, value=release_value)
            col += 1
        
        # Add ticket data
        ws.cell(row=row, column=col, value=ticket.key)
        col += 1
        ws.cell(row=row, column=col, value=ticket.summary)
        col += 1
        ws.cell(row=row, column=col, value=ticket.status)
        col += 1
        ws.cell(row=row, column=col, value=ticket.assignee or 'Unassigned')
        col += 1
        ws.cell(row=row, column=col, value=ticket.priority)
        col += 1
        ws.cell(row=row, column=col, value=ticket.issue_type)
        col += 1
        ws.cell(row=row, column=col, value=ticket.story_points or '')
        col += 1
        
        # Fix Version
        ws.cell(row=row, column=col, value=ticket.fix_version or '')
        col += 1
        
        # Labels
        labels_str = ''
        if hasattr(ticket, 'labels') and ticket.labels:
            labels_str = ', '.join(ticket.labels)
        ws.cell(row=row, column=col, value=labels_str)
        col += 1
        
        ws.cell(row=row, column=col, value=ticket.description or '')
        col += 1
        ws.cell(row=row, column=col, value=ticket.created or '')
        col += 1
        ws.cell(row=row, column=col, value=ticket.updated or '')
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

def create_team_availability_sheet(wb: Workbook, team_availability: Dict, team_workload: Dict = None):
    """Create team availability sheet"""
    ws = wb.create_sheet("Team Availability")
    
    # Headers
    headers = ['Assignee', 'Availability (days)', 'Tickets', 'Story Points', 'Workload Ratio']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Add data
    row = 2
    for assignee, availability in team_availability.items():
        ws.cell(row=row, column=1, value=assignee)
        ws.cell(row=row, column=2, value=availability)
        
        # Add workload data if available
        if team_workload and assignee in team_workload:
            workload = team_workload[assignee]
            ws.cell(row=row, column=3, value=workload.get('tickets', 0))
            ws.cell(row=row, column=4, value=workload.get('story_points', 0))
            
            # Calculate workload ratio
            if availability > 0:
                ratio = workload.get('story_points', 0) / availability
                ws.cell(row=row, column=5, value=f"{ratio:.1f}")
            else:
                ws.cell(row=row, column=5, value="N/A")
        else:
            ws.cell(row=row, column=3, value=0)
            ws.cell(row=row, column=4, value=0)
            ws.cell(row=row, column=5, value="N/A")
        
        row += 1
    
    # Add totals row
    if team_availability:
        ws.cell(row=row + 1, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=row + 1, column=2, value=sum(team_availability.values())).font = Font(bold=True)
        
        if team_workload:
            total_tickets = sum(workload.get('tickets', 0) for workload in team_workload.values())
            total_sp = sum(workload.get('story_points', 0) for workload in team_workload.values())
            ws.cell(row=row + 1, column=3, value=total_tickets).font = Font(bold=True)
            ws.cell(row=row + 1, column=4, value=total_sp).font = Font(bold=True)
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 30)
        ws.column_dimensions[column_letter].width = adjusted_width

def create_summary_sheet(wb: Workbook, tickets: List[JiraTicket], release_name: str = None):
    """Create summary statistics sheet"""
    ws = wb.create_sheet("Summary")
    
    # Title
    ws.cell(row=1, column=1, value=f"Summary Report - {release_name or 'Tickets'}").font = Font(size=16, bold=True)
    ws.cell(row=2, column=1, value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Basic statistics
    stats = calculate_stats(tickets)
    
    row = 4
    ws.cell(row=row, column=1, value="Basic Statistics").font = Font(size=14, bold=True)
    row += 1
    
    avg_story_points = stats['story_points'] / stats['total'] if stats['total'] > 0 and stats['story_points'] else 0
    
    basic_stats = [
        ("Total Tickets", stats['total']),
        ("Total Story Points", stats['story_points'] or 0),
        ("Average Story Points", f"{avg_story_points:.1f}"),
        ("Completion Rate", f"{stats['completion']:.1f}%")
    ]
    
    for label, value in basic_stats:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        row += 1
    
    # Status breakdown
    row += 1
    ws.cell(row=row, column=1, value="Status Breakdown").font = Font(size=14, bold=True)
    row += 1
    
    for status, count in stats['statuses'].items():
        ws.cell(row=row, column=1, value=status).font = Font(bold=True)
        ws.cell(row=row, column=2, value=count)
        row += 1
    
    # Priority breakdown
    row += 1
    ws.cell(row=row, column=1, value="Priority Breakdown").font = Font(size=14, bold=True)
    row += 1
    
    for priority, count in stats['priorities'].items():
        ws.cell(row=row, column=1, value=priority).font = Font(bold=True)
        ws.cell(row=row, column=2, value=count)
        row += 1
    
    # Assignee breakdown
    row += 1
    ws.cell(row=row, column=1, value="Assignee Breakdown").font = Font(size=14, bold=True)
    row += 1
    
    for assignee, count in stats['assignees'].items():
        ws.cell(row=row, column=1, value=assignee).font = Font(bold=True)
        ws.cell(row=row, column=2, value=count)
        row += 1
    
    # Auto-adjust column widths
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 15

def export_report_to_excel(release_name: str, assignee_stats: List[Dict], summary_stats: Dict, tickets: List[JiraTicket]) -> str:
    """Export comprehensive release report to Excel with multiple sheets."""
    wb = Workbook()
    
    # Remove default sheet
    wb.remove(wb.active)
    
    # Create summary sheet
    ws_summary = wb.create_sheet("Report Summary")
    
    # Title
    ws_summary.cell(row=1, column=1, value=f"{release_name} - Performance Report").font = Font(size=16, bold=True)
    ws_summary.cell(row=2, column=1, value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Summary stats
    row = 4
    ws_summary.cell(row=row, column=1, value="Overall Summary").font = Font(size=14, bold=True, color="FFFFFF")
    ws_summary.cell(row=row, column=1).fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    row += 1
    
    summary_items = [
        ("Total Tickets", summary_stats['total_tickets']),
        ("Completed Tickets", summary_stats['total_completed']),
        ("In Progress Tickets", summary_stats['total_in_progress']),
        ("Story Points Completed", summary_stats['total_story_points_done']),
        ("Completion Rate", f"{(summary_stats['total_completed'] / summary_stats['total_tickets'] * 100):.1f}%" if summary_stats['total_tickets'] > 0 else "0%"),
        ("Total Assignees", len(assignee_stats))
    ]
    
    for item_name, item_value in summary_items:
        ws_summary.cell(row=row, column=1, value=f"{item_name}:").font = Font(bold=True)
        ws_summary.cell(row=row, column=2, value=item_value)
        row += 1
    
    # Create assignee performance sheet
    ws_assignee = wb.create_sheet("Assignee Performance")
    
    # Headers
    headers = [
        "Assignee", "Total Tickets", "Completed", "In Progress", "Story Points Done",
        "User Stories", "Bugs", "Spikes", "Other", "Completion Rate"
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws_assignee.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row_idx, assignee in enumerate(assignee_stats, 2):
        completion_rate = (assignee['completed_tickets'] / assignee['total_tickets'] * 100) if assignee['total_tickets'] > 0 else 0
        
        row_data = [
            assignee['assignee'],
            assignee['total_tickets'],
            assignee['completed_tickets'],
            assignee['in_progress_tickets'],
            assignee['story_points_done'],
            assignee['ticket_types']['story'],
            assignee['ticket_types']['bug'],
            assignee['ticket_types']['spike'],
            assignee['ticket_types']['other'],
            f"{completion_rate:.1f}%"
        ]
        
        for col, value in enumerate(row_data, 1):
            ws_assignee.cell(row=row_idx, column=col, value=value)
    
    # Create ticket details sheet
    ws_tickets = wb.create_sheet("Ticket Details")
    
    # Convert tickets to DataFrame for easier handling
    ticket_data = []
    for ticket in tickets:
        ticket_data.append({
            'Key': ticket.key,
            'Summary': ticket.summary,
            'Status': ticket.status,
            'Assignee': ticket.assignee or 'Unassigned',
            'Issue Type': ticket.issue_type,
            'Priority': ticket.priority,
            'Story Points': ticket.story_points or 0,
            'Fix Version': ticket.fix_version or '',
            'Team': getattr(ticket, 'team', '') or '',
            'Created': ticket.created.strftime('%Y-%m-%d') if ticket.created else '',
            'Updated': ticket.updated.strftime('%Y-%m-%d') if ticket.updated else ''
        })
    
    if ticket_data:
        df = pd.DataFrame(ticket_data)
        
        # Headers
        for col, header in enumerate(df.columns, 1):
            cell = ws_tickets.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Data
        for row_idx, (_, row_data) in enumerate(df.iterrows(), 2):
            for col, value in enumerate(row_data, 1):
                ws.cell(row=row, column=col, value=value)
    
    # Auto-adjust column widths for all sheets
    for ws in wb.worksheets:
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
            ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save file
    filename = f"report_{release_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join('downloads', filename)
    
    # Ensure downloads directory exists
    os.makedirs('downloads', exist_ok=True)
    
    wb.save(filepath)
    return filepath

def export_page_to_excel(page_data: Dict, release_name: str) -> str:
    """
    Export the current page state as an Excel file with a single comprehensive sheet.
    This handles the 'Export page as Excel' functionality.
    """
    print(f"DEBUG: export_page_to_excel called with page_data type: {type(page_data)}")
    print(f"DEBUG: page_data keys: {list(page_data.keys()) if isinstance(page_data, dict) else 'Not a dict'}")
    
    # Create workbook
    wb = Workbook()
    
    # Use the default sheet and rename it
    ws = wb.active
    ws.title = "Release Export"
    
    # Add title and metadata - handle multiple releases
    if release_name == 'multiple' and 'release_names' in page_data and page_data['release_names']:
        release_names_list = page_data['release_names']
        if isinstance(release_names_list, list):
            title = f"Multiple Releases ({', '.join(release_names_list)}) - Page Export"
        else:
            title = f"{release_name} - Page Export"
    else:
        title = f"{release_name} - Page Export"
    
    # Merge cells for title and left-align it
    ws.merge_cells('A1:P1')
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(size=16, bold=True)
    title_cell.alignment = Alignment(horizontal="left")
    
    ws.cell(row=2, column=1, value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    row = 4
    
    # Add release statistics in a horizontal layout
    if 'release_stats' in page_data and page_data['release_stats']:
        print(f"DEBUG: release_stats type: {type(page_data['release_stats'])}")
        print(f"DEBUG: release_stats: {page_data['release_stats']}")
        
        # Create Release Statistics header
        ws.merge_cells(f'A{row}:D{row}')
        header_cell = ws.cell(row=row, column=1, value="Release Statistics")
        header_cell.font = Font(size=14, bold=True, color="FFFFFF")
        header_cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_cell.alignment = Alignment(horizontal="center")
        row += 1
        
        stats = page_data['release_stats']
        if isinstance(stats, dict):
            for key, value in stats.items():
                ws.cell(row=row, column=1, value=f"{key.replace('_', ' ').title()}:")
                ws.cell(row=row, column=1).font = Font(bold=True)
                ws.cell(row=row, column=2, value=str(value))
                row += 1
        row += 1
    
    # Applied filters section removed as per user request
    
    # Add comprehensive team data in a single layout
    if 'team_data' in page_data and page_data['team_data']:
        print(f"DEBUG: team_data type: {type(page_data['team_data'])}")
        print(f"DEBUG: team_data: {page_data['team_data']}")
        
        team_data = page_data['team_data']
        if isinstance(team_data, dict):
            # Debug logging for team_data structure
            print(f"DEBUG: Processing team_data with keys: {list(team_data.keys())}")
            if 'team_stats' in team_data:
                print(f"DEBUG: team_stats keys: {list(team_data['team_stats'].keys())}")
                print(f"DEBUG: team_stats content: {team_data['team_stats']}")
            
            # Team Information Header
            ws.merge_cells(f'A{row}:D{row}')
            header_cell = ws.cell(row=row, column=1, value="Team Information")
            header_cell.font = Font(size=14, bold=True, color="FFFFFF")
            header_cell.fill = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
            header_cell.alignment = Alignment(horizontal="center")
            row += 1
            
            if 'team_name' in team_data:
                ws.cell(row=row, column=1, value="Team Name:")
                ws.cell(row=row, column=1).font = Font(bold=True)
                ws.cell(row=row, column=2, value=team_data['team_name'])
                row += 1
            
            # Release Date Range in horizontal layout
            if 'release_date_range' in team_data and isinstance(team_data['release_date_range'], dict):
                ws.merge_cells(f'A{row}:D{row}')
                header_cell = ws.cell(row=row, column=1, value="Release Date Range")
                header_cell.font = Font(size=12, bold=True, color="FFFFFF")
                header_cell.fill = PatternFill(start_color="9B59B6", end_color="9B59B6", fill_type="solid")
                header_cell.alignment = Alignment(horizontal="center")
                row += 1
                
                date_range = team_data['release_date_range']
                date_range_items = [
                    ("Start Date", date_range.get('start_date', 'Not set')),
                    ("End Date", date_range.get('end_date', 'Not set')),
                    ("Working Days", date_range.get('working_days', '0 working days')),
                    ("Holidays", f"{date_range.get('holidays', '0')} days"),
                    ("Team Velocity", f"{date_range.get('team_velocity_sp_day_person', '1.0')} SP/day/person")
                ]
                
                for item_name, item_value in date_range_items:
                    ws.cell(row=row, column=1, value=f"{item_name}:")
                    ws.cell(row=row, column=1).font = Font(bold=True)
                    ws.cell(row=row, column=2, value=str(item_value))
                    row += 1
                row += 1
            
            # Team Statistics in horizontal layout
            if 'team_stats' in team_data and isinstance(team_data['team_stats'], dict):
                ws.merge_cells(f'A{row}:E{row}')
                header_cell = ws.cell(row=row, column=1, value="Team Statistics")
                header_cell.font = Font(size=12, bold=True, color="FFFFFF")
                header_cell.fill = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
                header_cell.alignment = Alignment(horizontal="center")
                row += 1
                
                # Create three-column layout: Team Statistics | Team Member Availability | Assignee Breakdown
                col_a_start = row
                for key, value in team_data['team_stats'].items():
                    display_name = key.replace('_', ' ').title()
                    if key == 'avg_sp_day':
                        display_name = "Average SP/Day"
                        value = f"{value}"
                    elif key == 'remaining_to_groom_sp':
                        # Check if this is overgroomed or remaining to groom
                        is_overgroomed = team_data['team_stats'].get('is_overgroomed', False)
                        if is_overgroomed:
                            display_name = "Overgroomed - Remove (SP)"
                        else:
                            display_name = "Remaining to Groom (SP)"
                        value = f"{value}"
                    elif key == 'is_overgroomed':
                        # Skip this key as it's just a flag
                        continue
                    
                    ws.cell(row=row, column=1, value=f"{display_name}:")
                    ws.cell(row=row, column=1).font = Font(bold=True)
                    ws.cell(row=row, column=2, value=str(value))
                    row += 1
                
                # Add Team Member Availability table (Column C-D)
                current_row = col_a_start
                if 'team_availability' in team_data and team_data['team_availability']:
                    ws.cell(row=current_row, column=4, value="Team Member").font = Font(bold=True, color="FFFFFF")
                    ws.cell(row=current_row, column=4).fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
                    ws.cell(row=current_row, column=5, value="Availability (Days)").font = Font(bold=True, color="FFFFFF")
                    ws.cell(row=current_row, column=5).fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
                    current_row += 1
                    
                    for member, availability in team_data['team_availability'].items():
                        ws.cell(row=current_row, column=4, value=member)
                        ws.cell(row=current_row, column=5, value=str(availability))
                        current_row += 1
                
                # Add Assignee Breakdown table (Column G-I)
                current_row = col_a_start
                if 'assignee_workload' in team_data and team_data['assignee_workload']:
                    ws.cell(row=current_row, column=7, value="Assignee").font = Font(bold=True, color="FFFFFF")
                    ws.cell(row=current_row, column=7).fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                    ws.cell(row=current_row, column=8, value="Total Tickets").font = Font(bold=True, color="FFFFFF")
                    ws.cell(row=current_row, column=8).fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                    ws.cell(row=current_row, column=9, value="Story Points").font = Font(bold=True, color="FFFFFF")
                    ws.cell(row=current_row, column=9).fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                    ws.cell(row=current_row, column=10, value="Status Breakdown").font = Font(bold=True, color="FFFFFF")
                    ws.cell(row=current_row, column=10).fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
                    current_row += 1
                    
                    for assignee, workload in team_data['assignee_workload'].items():
                        ws.cell(row=current_row, column=7, value=assignee)
                        ws.cell(row=current_row, column=8, value=str(workload.get('tickets', 0)))
                        ws.cell(row=current_row, column=9, value=str(workload.get('story_points', 0)))
                        ws.cell(row=current_row, column=10, value="")  # Status breakdown placeholder
                        current_row += 1
                
                # Move to next row after all tables
                row = max(row, current_row) + 2
    
    # Add Tickets section in the same sheet
    if 'current_tickets' in page_data and page_data['current_tickets']:
        tickets_data = page_data['current_tickets']
        print(f"DEBUG: current_tickets type: {type(tickets_data)}")
        print(f"DEBUG: tickets_data length: {len(tickets_data) if isinstance(tickets_data, list) else 'Not a list'}")
        
        if isinstance(tickets_data, list):
            # Filter out any problematic entries
            valid_tickets = []
            for i, ticket in enumerate(tickets_data):
                print(f"DEBUG: Processing ticket {i}, type: {type(ticket)}")
                
                # Check if this is a string instead of a dict/object
                if isinstance(ticket, str):
                    print(f"DEBUG: ERROR - Skipping string ticket at index {i}: {ticket}")
                    continue
                    
                # Check if this is None or not a dict
                if not isinstance(ticket, dict):
                    print(f"DEBUG: ERROR - Skipping non-dict ticket at index {i}: {type(ticket)}")
                    continue
                    
                # Check if it has the required fields
                if not ticket.get('key'):
                    print(f"DEBUG: WARNING - Ticket missing key at index {i}: {ticket}")
                    continue
                    
                valid_tickets.append(ticket)
            
            print(f"DEBUG: Valid tickets count: {len(valid_tickets)} out of {len(tickets_data)}")
            tickets_data = valid_tickets
        
        if len(tickets_data) > 0:
            # Add some spacing before tickets section
            row += 2
            
            # Create Tickets section header
            ws.merge_cells(f'A{row}:N{row}')
            header_cell = ws.cell(row=row, column=1, value="JIRA Tickets")
            header_cell.font = Font(size=14, bold=True, color="FFFFFF")
            header_cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_cell.alignment = Alignment(horizontal="center")
            row += 1
            
            # Headers
            headers = ['Key', 'Summary', 'Status', 'Assignee', 'Priority', 'Issue Type', 'Story Points', 'Fix Version', 'Labels', 'Exclude SP', 'Override SP', 'Description', 'Created', 'Updated']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")
            row += 1
            
            # Add ticket data
            for ticket in tickets_data:
                print(f"DEBUG: Adding ticket to Excel: {ticket.get('key', 'NO_KEY')}")
                
                try:
                    ws.cell(row=row, column=1, value=str(ticket.get('key', '')))
                    ws.cell(row=row, column=2, value=str(ticket.get('summary', '')))
                    ws.cell(row=row, column=3, value=str(ticket.get('status', '')))
                    ws.cell(row=row, column=4, value=str(ticket.get('assignee', '')))
                    ws.cell(row=row, column=5, value=str(ticket.get('priority', '')))
                    ws.cell(row=row, column=6, value=str(ticket.get('issue_type', '')))
                    ws.cell(row=row, column=7, value=str(ticket.get('story_points', '')))
                    
                    # Fix Version
                    ws.cell(row=row, column=8, value=str(ticket.get('fix_version', '')))
                    
                    # Handle labels (could be a list)
                    labels = ticket.get('labels', [])
                    if isinstance(labels, list):
                        labels_str = ', '.join(str(label) for label in labels) if labels else ''
                    else:
                        labels_str = str(labels) if labels else ''
                    ws.cell(row=row, column=9, value=labels_str)
                    
                    # Exclude SP (column 10)
                    exclude_sp = ticket.get('exclude_from_calculations', False)
                    ws.cell(row=row, column=10, value='Yes' if exclude_sp else 'No')
                    
                    # Override SP (column 11)
                    override_sp = ticket.get('override_story_points', '')
                    ws.cell(row=row, column=11, value=str(override_sp) if override_sp is not None and override_sp != '' else '')
                    
                    # Description and dates - convert to string to handle various data types (shifted columns)
                    ws.cell(row=row, column=12, value=str(ticket.get('description', '')))
                    
                    # Handle dates properly (shifted columns)
                    created = ticket.get('created', '')
                    updated = ticket.get('updated', '')
                    ws.cell(row=row, column=13, value=str(created) if created else '')
                    ws.cell(row=row, column=14, value=str(updated) if updated else '')
                    
                    row += 1
                except Exception as e:
                    print(f"DEBUG: Error processing ticket: {e}")
                    print(f"DEBUG: Ticket causing error: {ticket}")
                    # Continue processing other tickets instead of failing completely
                    continue
        
        # Auto-adjust column widths for the sheet (avoid MergedCell objects)
        from openpyxl.cell.cell import MergedCell
        
        # Use a different approach to set column widths to avoid MergedCell issues
        column_widths = {}
        
        # Iterate through all cells to calculate column widths
        for row in ws.iter_rows():
            for cell in row:
                if not isinstance(cell, MergedCell) and cell.value is not None:
                    column_letter = cell.column_letter
                    cell_length = len(str(cell.value))
                    
                    if column_letter not in column_widths:
                        column_widths[column_letter] = cell_length
                    else:
                        column_widths[column_letter] = max(column_widths[column_letter], cell_length)
        
        # Apply the calculated widths
        for column_letter, max_length in column_widths.items():
            # Set reasonable column widths
            if column_letter == 'B':  # Summary
                adjusted_width = min(max_length + 2, 50)
            elif column_letter == 'L':  # Description
                adjusted_width = min(max_length + 2, 40)
            else:
                adjusted_width = min(max_length + 2, 20)
            
            ws.column_dimensions[column_letter].width = adjusted_width

    
    # Generate filename
    safe_name = release_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(os.getcwd(), f"{safe_name}_page_export_{timestamp}.xlsx")
    
    # Save workbook
    wb.save(filename)
    return filename
