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

def parse_location_details(location_details_json):
    """
    Parse location_details JSON field to extract latitude and longitude
    Returns: Dictionary with latitude, longitude, and other details
    """
    if not location_details_json:
        return {
            'latitude': None,
            'longitude': None,
            'city': '',
            'state': '',
            'pincode': '',
            'country': '',
            'full_address': '',
            'accuracy': None
        }
    
    try:
        if isinstance(location_details_json, str):
            location_data = json.loads(location_details_json)
        else:
            location_data = location_details_json
        
        return {
            'latitude': location_data.get('latitude'),
            'longitude': location_data.get('longitude'),
            'city': location_data.get('city', ''),
            'state': location_data.get('state', ''),
            'pincode': location_data.get('pincode', ''),
            'country': location_data.get('country', ''),
            'full_address': location_data.get('full_address', ''),
            'address_line': location_data.get('address_line', ''),
            'accuracy': location_data.get('accuracy'),
            'place_id': location_data.get('place_id', '')
        }
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error parsing location_details: {e}")
        return {
            'latitude': None,
            'longitude': None,
            'city': '',
            'state': '',
            'pincode': '',
            'country': '',
            'full_address': '',
            'accuracy': None
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
        
        # Get auto-detected location users (from location string format)
        auto_response = client.table('users').select('id').like('location', '% | % | % | %').execute()
        auto_users_string = len(auto_response.data)
        
        # Get users with coordinates in database columns
        coords_response = client.table('users').select('id')\
            .not_.is_('latitude', 'null')\
            .not_.is_('longitude', 'null')\
            .execute()
        auto_users_coords = len(coords_response.data)
        
        # Combined auto-detected users
        auto_users = max(auto_users_string, auto_users_coords)
        
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
        
        # Get users with location_details
        location_details_response = client.table('users').select('id')\
            .not_.is_('location_details', 'null')\
            .execute()
        users_with_details = len(location_details_response.data)
        
        active_users = total_users
        blocked_users = 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'auto_users': auto_users,
                'auto_users_string': auto_users_string,
                'auto_users_coords': auto_users_coords,
                'users_with_details': users_with_details,
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
            # Users with coordinates in database OR location string with coordinates
            query = query.or_(f"latitude.not.is.null,location.like.%|%|%|%")
        elif location_filter == 'manual':
            # Users without coordinates
            query = query.and_(f"latitude.is.null,location.not.like.%|%|%|%")
        elif location_filter == 'has_details':
            # Users with location_details JSON
            query = query.not_.is_('location_details', 'null')
        
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
            count_query = count_query.or_(f"latitude.not.is.null,location.like.%|%|%|%")
        elif location_filter == 'manual':
            count_query = count_query.and_(f"latitude.is.null,location.not.like.%|%|%|%")
        elif location_filter == 'has_details':
            count_query = count_query.not_.is_('location_details', 'null')
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
            # Parse location from string format
            parsed_loc = parse_location_data(user.get('location', ''))
            user['parsed_location'] = parsed_loc
            user['is_auto_detected'] = parsed_loc['is_auto_detected']
            
            # Check for coordinates in database columns (preferred)
            if user.get('latitude') and user.get('longitude'):
                user['latitude'] = float(user['latitude']) if user['latitude'] else None
                user['longitude'] = float(user['longitude']) if user['longitude'] else None
                user['has_coordinates'] = True
            else:
                user['has_coordinates'] = False
            
            # Parse location_details JSON if exists
            if user.get('location_details'):
                user['location_details_parsed'] = parse_location_details(user['location_details'])
            else:
                user['location_details_parsed'] = None
            
            # Format dates
            created_at = None
            if user.get('created_at'):
                try:
                    if isinstance(user['created_at'], str):
                        created_at = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
                    else:
                        created_at = user['created_at']
                except:
                    created_at = datetime.now()
            else:
                created_at = datetime.now()
            
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
        
        # Parse location from string format
        parsed_loc = parse_location_data(user.get('location', ''))
        user['parsed_location'] = parsed_loc
        
        # Check for coordinates in database columns
        if user.get('latitude') and user.get('longitude'):
            user['latitude'] = float(user['latitude']) if user['latitude'] else None
            user['longitude'] = float(user['longitude']) if user['longitude'] else None
            user['has_coordinates'] = True
        else:
            user['has_coordinates'] = False
        
        # Parse location_details JSON if exists
        if user.get('location_details'):
            user['location_details_parsed'] = parse_location_details(user['location_details'])
        else:
            user['location_details_parsed'] = None
        
        # Format dates
        created_at = None
        if user.get('created_at'):
            try:
                if isinstance(user['created_at'], str):
                    created_at = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
                else:
                    created_at = user['created_at']
            except:
                created_at = datetime.now()
        else:
            created_at = datetime.now()
        
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
        
        # ✅ Update latitude and longitude if provided
        if 'latitude' in data and data['latitude'] is not None:
            try:
                update_data['latitude'] = float(data['latitude'])
            except (ValueError, TypeError):
                update_data['latitude'] = None
        
        if 'longitude' in data and data['longitude'] is not None:
            try:
                update_data['longitude'] = float(data['longitude'])
            except (ValueError, TypeError):
                update_data['longitude'] = None
        
        # ✅ Update location_details if provided
        if 'location_details' in data and data['location_details']:
            if isinstance(data['location_details'], dict):
                update_data['location_details'] = json.dumps(data['location_details'])
            elif isinstance(data['location_details'], str):
                update_data['location_details'] = data['location_details']
        
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
                'message': 'User updated successfully',
                'updated_fields': list(update_data.keys())
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
    """Export users data to CSV including latitude and longitude"""
    try:
        client = get_supabase_client()
        response = client.table('users').select('*').order('created_at', desc=True).execute()
        users = response.data
        
        # CSV Header with additional columns
        csv_data = "ID,Full Name,Phone,Email,Address,Latitude,Longitude,Map Link,City,State,Pincode,Country,Location Details,Registration Date\n"
        
        for user in users:
            # Parse location from string format
            parsed_loc = parse_location_data(user.get('location', ''))
            
            # Get coordinates from database columns (preferred)
            latitude = user.get('latitude') or parsed_loc.get('latitude')
            longitude = user.get('longitude') or parsed_loc.get('longitude')
            
            # Parse location_details if exists
            location_details = None
            city = ''
            state = ''
            pincode = ''
            country = ''
            
            if user.get('location_details'):
                details_parsed = parse_location_details(user['location_details'])
                city = details_parsed.get('city', '')
                state = details_parsed.get('state', '')
                pincode = details_parsed.get('pincode', '')
                country = details_parsed.get('country', '')
                location_details = json.dumps(details_parsed)
            
            address = parsed_loc['address'].replace(',', ';') if parsed_loc['address'] else ''
            email = user.get('email', '').replace(',', ';')
            full_name = user.get('full_name', '').replace(',', ';')
            phone = user.get('phone', '')
            
            created_at = user.get('created_at', '')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        dt = created_at
                    created_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            csv_data += f'{user.get("id", "")},"{full_name}","{phone}","{email}","{address}",'
            csv_data += f'"{latitude if latitude else ""}","{longitude if longitude else ""}","{parsed_loc.get("map_link", "")}",'
            csv_data += f'"{city}","{state}","{pincode}","{country}","{location_details if location_details else ""}",'
            csv_data += f'"{created_at}"\n'
        
        return jsonify({
            'success': True,
            'csv_data': csv_data,
            'filename': f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/location-map')
@admin_login_required
def get_users_location_map():
    """Get users with coordinates for map visualization"""
    try:
        client = get_supabase_client()
        
        # Get users with coordinates (from database columns or location string)
        response = client.table('users').select('id, full_name, latitude, longitude, location, location_details').execute()
        users = response.data
        
        location_data = []
        
        for user in users:
            # Try to get coordinates from database columns first
            lat = user.get('latitude')
            lng = user.get('longitude')
            
            # If not in columns, try to parse from location string
            if not lat or not lng:
                parsed = parse_location_data(user.get('location', ''))
                lat = parsed.get('latitude')
                lng = parsed.get('longitude')
            
            # If still no coordinates, try location_details
            if (not lat or not lng) and user.get('location_details'):
                details_parsed = parse_location_details(user['location_details'])
                lat = details_parsed.get('latitude')
                lng = details_parsed.get('longitude')
            
            # Only include users with valid coordinates
            if lat and lng:
                # Get address for display
                address = user.get('location', '')
                if address and ' | ' in address:
                    address = address.split(' | ')[0]
                
                location_data.append({
                    'id': user['id'],
                    'name': user.get('full_name', 'Unknown'),
                    'latitude': float(lat),
                    'longitude': float(lng),
                    'address': address[:100] if address else 'Location detected'
                })
        
        return jsonify({
            'success': True,
            'locations': location_data,
            'total': len(location_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/api/users/bulk-update-location', methods=['POST'])
@admin_login_required
def bulk_update_location():
    """Bulk update location coordinates from location string to database columns"""
    try:
        data = request.get_json()
        action = data.get('action', 'sync_coordinates')
        
        client = get_supabase_client()
        
        # Get all users
        response = client.table('users').select('id, location').execute()
        users = response.data
        
        updated_count = 0
        skipped_count = 0
        
        for user in users:
            location_string = user.get('location', '')
            parsed = parse_location_data(location_string)
            
            update_data = {}
            
            if action == 'sync_coordinates':
                # Sync coordinates from location string to database columns
                if parsed.get('latitude') and parsed.get('longitude'):
                    update_data['latitude'] = parsed['latitude']
                    update_data['longitude'] = parsed['longitude']
                    update_data['updated_at'] = datetime.now().isoformat()
                    
                    client.table('users').update(update_data).eq('id', user['id']).execute()
                    updated_count += 1
                else:
                    skipped_count += 1
            
            elif action == 'fix_location_string':
                # Fix location string format if needed
                if location_string and ' | ' not in location_string:
                    # Try to create formatted string from existing data
                    if update_data:
                        client.table('users').update(update_data).eq('id', user['id']).execute()
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} users, skipped {skipped_count} users',
            'updated': updated_count,
            'skipped': skipped_count
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
