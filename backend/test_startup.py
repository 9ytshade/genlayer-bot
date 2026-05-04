import sys
sys.path.insert(0, '.')
try:
    import main
    print("main.py imports OK")
except Exception as e:
    print(f"IMPORT ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
