# admin_users.py - Users Management Admin Panel for Supabase
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv
from functools import wraps
import json

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='admin_templates', static_folder='admin_static')
app.secret_key = os.environ.get('ADMIN_SECRET_KEY', 'admin-secret-key-change-in-production')

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def get_supabase_client():
    """Get Supabase client instance"""
    return supabase

# Admin credentials
ADMIN_CREDENTIALS = {
    'username': os.environ.get('ADMIN_USERNAME', 'admin'),
    'password': os.environ.get('ADMIN_PASSWORD', 'admin123')
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

@app.route('/')
def root():
    """Root URL - Redirect to admin login page"""
    return redirect(url_for('admin_login'))

@app.route('/login')
def public_login():
    """Alternative login route"""
    return redirect(url_for('admin_login'))

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

@app.route('/admin/api/users/stats')
@admin_login_required
def get_users_stats():
    """Get users statistics"""
    try:
        client = get_supabase_client()
        
        # Get total users
        total_response = client.table('users').select('id').execute()
        total_users = len(total_response.data)
        
        # Get auto-detected location users
        auto_response = client.table('users').select('id').like('location', '% | % | % | %').execute()
        auto_users = len(auto_response.data)
        
        # Get today's users
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time()).isoformat()
        today_end = datetime.combine(today, datetime.max.time()).isoformat()
        today_response = client.table('users').select('id')\
            .gte('created_at', today_start)\
            .lte('created_at', today_end)\
            .execute()
        today_users = len(today_response.data)
        
        # Get last 7 days users
        week_ago = datetime.now() - timedelta(days=7)
        week_response = client.table('users').select('id')\
            .gte('created_at', week_ago.isoformat())\
            .execute()
        week_users = len(week_response.data)
        
        active_users = total_users
        blocked_users = 0
        
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
        date_filter = request.args.get('date_filter', 'all')
        
        offset = (page - 1) * per_page
        
        client = get_supabase_client()
        
        # Start building the query
        query = client.table('users').select('*')
        
        # Apply search filter
        if search:
            # Supabase OR filter for multiple columns
            query = query.or_(f"full_name.ilike.%{search}%,phone.ilike.%{search}%,email.ilike.%{search}%,location.ilike.%{search}%")
        
        # Apply location filter
        if location_filter == 'auto':
            query = query.like('location', '% | % | % | %')
        elif location_filter == 'manual':
            query = query.not_.like('location', '% | % | % | %')
        
        # Apply date filter
        if date_filter == 'today':
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time()).isoformat()
            today_end = datetime.combine(today, datetime.max.time()).isoformat()
            query = query.gte('created_at', today_start).lte('created_at', today_end)
        elif date_filter == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            query = query.gte('created_at', week_ago.isoformat())
        elif date_filter == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            query = query.gte('created_at', month_ago.isoformat())
        
        # Get total count - execute a count query first
        count_query = client.table('users').select('id', count='exact')
        
        # Apply same filters to count query
        if search:
            count_query = count_query.or_(f"full_name.ilike.%{search}%,phone.ilike.%{search}%,email.ilike.%{search}%,location.ilike.%{search}%")
        if location_filter == 'auto':
            count_query = count_query.like('location', '% | % | % | %')
        elif location_filter == 'manual':
            count_query = count_query.not_.like('location', '% | % | % | %')
        if date_filter == 'today':
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time()).isoformat()
            today_end = datetime.combine(today, datetime.max.time()).isoformat()
            count_query = count_query.gte('created_at', today_start).lte('created_at', today_end)
        elif date_filter == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            count_query = count_query.gte('created_at', week_ago.isoformat())
        elif date_filter == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            count_query = count_query.gte('created_at', month_ago.isoformat())
        
        count_response = count_query.execute()
        total = count_response.count if hasattr(count_response, 'count') else len(count_response.data)
        
        # Get paginated results
        response = query.range(offset, offset + per_page - 1)\
            .order('created_at', desc=True)\
            .execute()
        
        users = response.data
        
        # Format user data
        for user in users:
            parsed_loc = parse_location_data(user.get('location', ''))
            user['parsed_location'] = parsed_loc
            user['is_auto_detected'] = parsed_loc['is_auto_detected']
            
            created_at = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00')) if user.get('created_at') else datetime.now()
            user['formatted_created'] = created_at.strftime('%d %b %Y, %I:%M %p')
            user['formatted_updated'] = user['formatted_created']
            user['status'] = 'active'
            user['last_updated'] = user.get('created_at', user.get('updated_at', user.get('created_at')))
        
        return jsonify({
            'success': True,
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total or 0,
                'total_pages': ((total or 0) + per_page - 1) // per_page if total else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>', methods=['GET'])
@admin_login_required
def get_user_details(user_id):
    """Get single user details"""
    try:
        client = get_supabase_client()
        response = client.table('users').select('*').eq('id', user_id).execute()
        
        if not response.data:
            return jsonify({'success': False, 'error': 'User not found'})
        
        user = response.data[0]
        parsed_loc = parse_location_data(user.get('location', ''))
        user['parsed_location'] = parsed_loc
        
        created_at = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00')) if user.get('created_at') else datetime.now()
        user['formatted_created'] = created_at.strftime('%d %b %Y, %I:%M %p')
        user['status'] = 'active'
        
        return jsonify({'success': True, 'user': user})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>', methods=['PUT'])
@admin_login_required
def update_user(user_id):
    """Update user details"""
    try:
        data = request.get_json()
        client = get_supabase_client()
        
        # Check if user exists
        check_response = client.table('users').select('id').eq('id', user_id).execute()
        if not check_response.data:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Check email uniqueness
        if 'email' in data and data['email']:
            email_check = client.table('users').select('id')\
                .eq('email', data['email'])\
                .neq('id', user_id)\
                .execute()
            if email_check.data:
                return jsonify({'success': False, 'error': 'Email already registered to another user'})
        
        # Check phone uniqueness
        if 'phone' in data and data['phone']:
            phone_check = client.table('users').select('id')\
                .eq('phone', data['phone'])\
                .neq('id', user_id)\
                .execute()
            if phone_check.data:
                return jsonify({'success': False, 'error': 'Phone number already registered to another user'})
        
        # Prepare update data
        update_data = {}
        
        if 'full_name' in data:
            update_data['full_name'] = data['full_name']
        
        if 'email' in data:
            update_data['email'] = data['email']
        
        if 'phone' in data:
            update_data['phone'] = data['phone']
        
        if 'location' in data:
            update_data['location'] = data['location']
        
        if 'password' in data and data['password']:
            update_data['password'] = generate_password_hash(data['password'])
        
        if 'profile_pic' in data:
            update_data['profile_pic'] = data['profile_pic']
        
        if update_data:
            # Add updated_at timestamp
            update_data['updated_at'] = datetime.now().isoformat()
            
            response = client.table('users').update(update_data).eq('id', user_id).execute()
            
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
    """Update user status"""
    try:
        data = request.get_json()
        status = data.get('status', 'active')
        
        client = get_supabase_client()
        
        # Check if user exists
        check_response = client.table('users').select('id').eq('id', user_id).execute()
        if not check_response.data:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Check if status column exists by trying to select it
        try:
            test_response = client.table('users').select('status').eq('id', user_id).execute()
            # Update status
            response = client.table('users').update({
                'status': status,
                'updated_at': datetime.now().isoformat()
            }).eq('id', user_id).execute()
            
            return jsonify({
                'success': True,
                'message': f'User status updated to {status}'
            })
        except Exception as e:
            # If status column doesn't exist
            return jsonify({
                'success': False,
                'error': 'Status column does not exist in users table. Please add a status column to enable this feature.'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/<int:user_id>', methods=['DELETE'])
@admin_login_required
def delete_user(user_id):
    """Delete user"""
    try:
        client = get_supabase_client()
        
        # Get user info before deletion
        user_response = client.table('users').select('full_name, email').eq('id', user_id).execute()
        
        if not user_response.data:
            return jsonify({'success': False, 'error': 'User not found'})
        
        user = user_response.data[0]
        
        # Delete user
        response = client.table('users').delete().eq('id', user_id).execute()
        
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
        client = get_supabase_client()
        response = client.table('users').select('*').order('created_at', desc=True).execute()
        users = response.data
        
        csv_data = "ID,Full Name,Phone,Email,Address,Latitude,Longitude,Map Link,Registration Date\n"
        
        for user in users:
            parsed_loc = parse_location_data(user.get('location', ''))
            
            address = parsed_loc['address'].replace(',', ';') if parsed_loc['address'] else ''
            email = user.get('email', '').replace(',', ';')
            full_name = user.get('full_name', '').replace(',', ';')
            phone = user.get('phone', '')
            
            created_at = user.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            csv_data += f'{user.get("id", "")},"{full_name}","{phone}","{email}","{address}",'
            csv_data += f'"{parsed_loc.get("latitude", "")}","{parsed_loc.get("longitude", "")}","{parsed_loc.get("map_link", "")}",'
            csv_data += f'"{created_at}"\n'
        
        return jsonify({
            'success': True,
            'csv_data': csv_data,
            'filename': f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/health')
def admin_health():
    """Health check endpoint"""
    try:
        client = get_supabase_client()
        response = client.table('users').select('id').limit(1).execute()
        
        return jsonify({
            'status': 'healthy', 
            'service': 'Users Admin Panel (Supabase)',
            'users_count': len(response.data)
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
