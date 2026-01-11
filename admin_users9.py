# admin_users.py - Users Management Admin Panel with PDF Download
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from functools import wraps

# ✅ PDF Generation Imports
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='admin_templates', static_folder='admin_static')
app.secret_key = os.environ.get('ADMIN_SECRET_KEY', 'admin-secret-key-change-in-production')

# ✅ SAME LOCATION PARSING FUNCTION
def parse_location_data(location_string):
    """
    Parse location string in format: "Address | Latitude | Longitude | MapLink"
    Returns: Dictionary with all components
    """
    if not location_string:
        return {
            'address': '',
            'latitude': None,
            'longitude': None,
            'map_link': None,
            'is_auto_detected': False
        }
    
    if ' | ' in location_string:
        parts = location_string.split(' | ')
        if len(parts) >= 4:
            try:
                return {
                    'address': parts[0],
                    'latitude': float(parts[1]) if parts[1] else None,
                    'longitude': float(parts[2]) if parts[2] else None,
                    'map_link': parts[3],
                    'is_auto_detected': True,
                    'full_string': location_string
                }
            except ValueError:
                pass
    
    return {
        'address': location_string,
        'latitude': None,
        'longitude': None,
        'map_link': None,
        'is_auto_detected': False,
        'full_string': location_string
    }

def get_db_connection():
    """Establish database connection"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise

# Admin credentials
ADMIN_CREDENTIALS = {
    'username': os.environ.get('ADMIN_USERNAME', 'admin'),
    'password': os.environ.get('ADMIN_PASSWORD', 'admin123')  # Simple password for demo
}

# Login required decorator
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please login to access admin panel', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ✅ PDF GENERATION FUNCTION
def generate_user_pdf(user_data, profile_image=None):
    """Generate PDF with user data"""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e293b')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#334155')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        textColor=colors.HexColor('#475569')
    )
    
    # Title
    story.append(Paragraph(f"USER PROFILE REPORT", title_style))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", 
                          styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Profile Section with Image
    if profile_image:
        try:
            # Download image from Cloudinary
            response = requests.get(profile_image, stream=True)
            if response.status_code == 200:
                img_buffer = io.BytesIO(response.content)
                img = Image(img_buffer, width=1.5*inch, height=1.5*inch)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Spacer(1, 10))
        except:
            pass
    
    # User Basic Info
    story.append(Paragraph("BASIC INFORMATION", heading_style))
    
    basic_data = [
        ["User ID", f"#{user_data['id']}"],
        ["Full Name", user_data['full_name']],
        ["Phone Number", user_data['phone']],
        ["Email Address", user_data['email']],
        ["Account Status", user_data.get('status', 'active').upper()],
        ["Registration Date", user_data['formatted_created']],
        ["Last Updated", user_data.get('formatted_updated', 'Never updated')]
    ]
    
    basic_table = Table(basic_data, colWidths=[2*inch, 4*inch])
    basic_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0'))
    ]))
    story.append(basic_table)
    
    # Location Information
    story.append(Paragraph("LOCATION INFORMATION", heading_style))
    
    location = user_data['parsed_location']
    location_data = [
        ["Address", location['address']],
        ["Location Type", "Auto-detected" if location['is_auto_detected'] else "Manual Entry"],
    ]
    
    if location['is_auto_detected']:
        location_data.extend([
            ["Latitude", str(location['latitude'])],
            ["Longitude", str(location['longitude'])],
            ["Google Maps Link", location['map_link'] or "Not available"]
        ])
    
    location_table = Table(location_data, colWidths=[2*inch, 4*inch])
    location_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0'))
    ]))
    story.append(location_table)
    
    # Raw Data Section
    story.append(Paragraph("RAW DATABASE DATA", heading_style))
    
    raw_data = [
        ["Database Column", "Value"],
        ["Full Location String", user_data['location'][:100] + "..." if len(user_data['location']) > 100 else user_data['location']],
        ["Profile Picture URL", user_data.get('profile_pic', 'Not available')[:80] + "..." if user_data.get('profile_pic') and len(user_data.get('profile_pic', '')) > 80 else user_data.get('profile_pic', 'Not available')],
        ["Created At (Raw)", str(user_data['created_at'])],
        ["User ID (Database)", str(user_data['id'])]
    ]
    
    raw_table = Table(raw_data, colWidths=[2*inch, 4*inch])
    raw_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#64748b')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0'))
    ]))
    story.append(raw_table)
    
    # Footer
    story.append(Spacer(1, 30))
    footer_text = f"Report generated by Bite Me Buddy Admin System | Confidential User Data"
    story.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#94a3b8'),
        alignment=TA_CENTER
    )))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/')
@admin_login_required
def admin_dashboard():
    """Admin dashboard - Users management"""
    return render_template('dashboard.html')

# API Endpoints for Users
@app.route('/admin/api/users/stats')
@admin_login_required
def get_users_stats():
    """Get users statistics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Total users
                cur.execute("SELECT COUNT(*) as total_users FROM users")
                total_users = cur.fetchone()['total_users']
                
                # Users with auto-detected location
                cur.execute("""
                    SELECT COUNT(*) as auto_users 
                    FROM users 
                    WHERE location LIKE '% | % | % | %'
                """)
                auto_users = cur.fetchone()['auto_users']
                
                # Today's registrations
                today = datetime.now().date()
                cur.execute("""
                    SELECT COUNT(*) as today_users 
                    FROM users 
                    WHERE DATE(created_at) = %s
                """, (today,))
                today_users = cur.fetchone()['today_users']
                
                # Last 7 days registrations
                week_ago = today - timedelta(days=7)
                cur.execute("""
                    SELECT COUNT(*) as week_users 
                    FROM users 
                    WHERE DATE(created_at) >= %s
                """, (week_ago,))
                week_users = cur.fetchone()['week_users']
                
                # Active vs Blocked users
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_users,
                        COUNT(CASE WHEN status = 'blocked' THEN 1 END) as blocked_users
                    FROM users
                """)
                status_data = cur.fetchone()
                active_users = status_data['active_users'] or 0
                blocked_users = status_data['blocked_users'] or 0
                
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'auto_users': auto_users,
                'today_users': today_users,
                'week_users': week_users,
                'active_users': active_users,
                'blocked_users': blocked_users
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users')
@admin_login_required
def get_users():
    """Get all users with filtering and pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '')
        location_filter = request.args.get('location_filter', 'all')
        status_filter = request.args.get('status_filter', 'all')
        date_filter = request.args.get('date_filter', 'all')
        
        offset = (page - 1) * per_page
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build WHERE clause
                conditions = []
                params = []
                
                if search:
                    conditions.append("""
                        (full_name ILIKE %s OR 
                         phone ILIKE %s OR 
                         email ILIKE %s OR 
                         location ILIKE %s)
                    """)
                    search_term = f"%{search}%"
                    params.extend([search_term, search_term, search_term, search_term])
                
                if location_filter == 'auto':
                    conditions.append("location LIKE '% | % | % | %'")
                elif location_filter == 'manual':
                    conditions.append("location NOT LIKE '% | % | % | %'")
                
                if status_filter != 'all':
                    conditions.append("status = %s")
                    params.append(status_filter)
                
                if date_filter != 'all':
                    now = datetime.now()
                    if date_filter == 'today':
                        conditions.append("DATE(created_at) = CURRENT_DATE")
                    elif date_filter == 'week':
                        conditions.append("created_at >= CURRENT_DATE - INTERVAL '7 days'")
                    elif date_filter == 'month':
                        conditions.append("created_at >= CURRENT_DATE - INTERVAL '30 days'")
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                # Get total count
                count_query = f"SELECT COUNT(*) as total FROM users WHERE {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()['total']
                
                # Get paginated data
                query = f"""
                    SELECT id, profile_pic, full_name, phone, email, location, 
                           status, created_at, 
                           COALESCE(updated_at, created_at) as last_updated
                    FROM users 
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([per_page, offset])
                cur.execute(query, params)
                users = cur.fetchall()
                
                # Parse location data and format dates
                for user in users:
                    parsed_loc = parse_location_data(user['location'])
                    user['parsed_location'] = parsed_loc
                    user['is_auto_detected'] = parsed_loc['is_auto_detected']
                    user['formatted_created'] = user['created_at'].strftime('%d %b %Y, %I:%M %p')
                    user['formatted_updated'] = user['last_updated'].strftime('%d %b %Y, %I:%M %p')
                
        return jsonify({
            'success': True,
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>', methods=['GET'])
@admin_login_required
def get_user_details(user_id):
    """Get single user details"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM users WHERE id = %s
                """, (user_id,))
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'error': 'User not found'})
                
                # Parse location
                parsed_loc = parse_location_data(user['location'])
                user['parsed_location'] = parsed_loc
                
                # Format dates
                user['formatted_created'] = user['created_at'].strftime('%d %b %Y, %I:%M %p')
                if user.get('updated_at'):
                    user['formatted_updated'] = user['updated_at'].strftime('%d %b %Y, %I:%M %p')
                
        return jsonify({'success': True, 'user': user})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>', methods=['PUT'])
@admin_login_required
def update_user(user_id):
    """Update user details"""
    try:
        data = request.get_json()
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    return jsonify({'success': False, 'error': 'User not found'})
                
                # Check if email already exists (for other users)
                if 'email' in data:
                    cur.execute("""
                        SELECT id FROM users WHERE email = %s AND id != %s
                    """, (data['email'], user_id))
                    if cur.fetchone():
                        return jsonify({'success': False, 'error': 'Email already registered to another user'})
                
                # Check if phone already exists (for other users)
                if 'phone' in data:
                    cur.execute("""
                        SELECT id FROM users WHERE phone = %s AND id != %s
                    """, (data['phone'], user_id))
                    if cur.fetchone():
                        return jsonify({'success': False, 'error': 'Phone number already registered to another user'})
                
                # Build update query
                update_fields = []
                update_values = []
                
                if 'full_name' in data:
                    update_fields.append("full_name = %s")
                    update_values.append(data['full_name'])
                
                if 'email' in data:
                    update_fields.append("email = %s")
                    update_values.append(data['email'])
                
                if 'phone' in data:
                    update_fields.append("phone = %s")
                    update_values.append(data['phone'])
                
                if 'location' in data:
                    update_fields.append("location = %s")
                    update_values.append(data['location'])
                
                if 'status' in data:
                    update_fields.append("status = %s")
                    update_values.append(data['status'])
                
                if 'password' in data and data['password']:
                    hashed_password = generate_password_hash(data['password'])
                    update_fields.append("password = %s")
                    update_values.append(hashed_password)
                
                # Always update timestamp
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                
                if update_fields:
                    update_query = f"""
                        UPDATE users 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                    """
                    update_values.append(user_id)
                    
                    cur.execute(update_query, update_values)
                    conn.commit()
                    
                    return jsonify({
                        'success': True, 
                        'message': 'User updated successfully'
                    })
                else:
                    return jsonify({
                        'success': False, 
                        'error': 'No fields to update'
                    })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>/status', methods=['PUT'])
@admin_login_required
def update_user_status(user_id):
    """Update user status (active/blocked)"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['active', 'blocked']:
            return jsonify({'success': False, 'error': 'Invalid status'})
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """, (new_status, user_id))
                
                if cur.rowcount == 0:
                    return jsonify({'success': False, 'error': 'User not found'})
                
                conn.commit()
                
                status_text = 'activated' if new_status == 'active' else 'blocked'
                return jsonify({
                    'success': True, 
                    'message': f'User {status_text} successfully'
                })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>', methods=['DELETE'])
@admin_login_required
def delete_user(user_id):
    """Delete user"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get user details before deleting (for logging)
                cur.execute("SELECT full_name, email FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'error': 'User not found'})
                
                # Delete user
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                
                return jsonify({
                    'success': True, 
                    'message': f'User {user["full_name"]} deleted successfully'
                })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/export')
@admin_login_required
def export_users():
    """Export users data to CSV"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, full_name, phone, email, location, status, created_at
                    FROM users 
                    ORDER BY created_at DESC
                """)
                users = cur.fetchall()
                
                # Create CSV content
                csv_data = "ID,Full Name,Phone,Email,Address,Latitude,Longitude,Map Link,Status,Registration Date\n"
                
                for user in users:
                    parsed_loc = parse_location_data(user['location'])
                    
                    # Escape commas in fields
                    address = parsed_loc['address'].replace(',', ';')
                    email = user['email'].replace(',', ';')
                    
                    csv_data += f'{user["id"]},"{user["full_name"]}","{user["phone"]}","{email}","{address}",'
                    csv_data += f'"{parsed_loc["latitude"]}","{parsed_loc["longitude"]}","{parsed_loc["map_link"]}",'
                    csv_data += f'"{user["status"]}","{user["created_at"]}"\n'
                
                return jsonify({
                    'success': True,
                    'csv_data': csv_data,
                    'filename': f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ✅ PHOTO DOWNLOAD ENDPOINTS
@app.route('/admin/api/users/<int:user_id>/download-photo')
@admin_login_required
def download_user_photo(user_id):
    """Download user profile photo from Cloudinary"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT profile_pic, full_name FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'error': 'User not found'})
                
                profile_pic_url = user['profile_pic']
                full_name = user['full_name']
                
                if not profile_pic_url or 'cloudinary' not in profile_pic_url.lower():
                    return jsonify({
                        'success': False, 
                        'error': 'No Cloudinary profile photo found for this user'
                    })
                
                # Return photo info for frontend to download
                return jsonify({
                    'success': True,
                    'photo_url': profile_pic_url,
                    'user_name': full_name,
                    'file_name': f"{full_name.replace(' ', '_')}_profile.jpg",
                    'message': 'Photo download ready'
                })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>/photo')
@admin_login_required
def get_user_photo(user_id):
    """Direct photo download (redirects to Cloudinary)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT profile_pic FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cur.fetchone()
                
                if not user or not user['profile_pic']:
                    return jsonify({'success': False, 'error': 'No photo available'})
                
                # Return Cloudinary URL
                return jsonify({
                    'success': True,
                    'photo_url': user['profile_pic']
                })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ✅ PDF DOWNLOAD ENDPOINTS
@app.route('/admin/api/users/<int:user_id>/download-pdf')
@admin_login_required
def download_user_pdf(user_id):
    """Generate and download user data as PDF"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get complete user data
                cur.execute("""
                    SELECT id, profile_pic, full_name, phone, email, location, 
                           status, created_at, 
                           COALESCE(updated_at, created_at) as last_updated
                    FROM users 
                    WHERE id = %s
                """, (user_id,))
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'error': 'User not found'}), 404
                
                # Parse location data
                parsed_loc = parse_location_data(user['location'])
                user['parsed_location'] = parsed_loc
                user['formatted_created'] = user['created_at'].strftime('%d %b %Y, %I:%M %p')
                user['formatted_updated'] = user['last_updated'].strftime('%d %b %Y, %I:%M %p')
                
                # Generate PDF
                pdf_buffer = generate_user_pdf(user, user.get('profile_pic'))
                
                # Create response
                filename = f"User_{user['full_name'].replace(' ', '_')}_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                return send_file(
                    pdf_buffer,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/pdf'
                )
                
    except Exception as e:
        print(f"PDF Generation Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/api/users/<int:user_id>/pdf-info')
@admin_login_required
def get_user_pdf_info(user_id):
    """Get user info for PDF generation"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT full_name FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'success': False, 'error': 'User not found'})
                
                filename = f"User_{user['full_name'].replace(' ', '_')}_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                return jsonify({
                    'success': True,
                    'download_url': f'/admin/api/users/{user_id}/download-pdf',
                    'filename': filename,
                    'user_name': user['full_name']
                })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Health check
@app.route('/admin/health')
def admin_health():
    """Health check endpoint"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as user_count FROM users")
                count = cur.fetchone()['user_count']
                
        return jsonify({
            'status': 'healthy', 
            'service': 'Users Admin Panel',
            'users_count': count
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)