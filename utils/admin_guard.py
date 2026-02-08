# utils/admin_guard.py
ADMINS = [6196298047, 7482679982]

def is_admin(user_id):
    return user_id in ADMINS
