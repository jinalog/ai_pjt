import os
import sys

sys.path.insert(0, os.getcwd())

from app.database import init_db, login_user

init_db()
user = login_user('tester', 'mask')
print(user)
