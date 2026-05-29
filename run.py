import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.argv.append('--prod')

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)
