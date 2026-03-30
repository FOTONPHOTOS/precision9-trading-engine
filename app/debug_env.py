import sys
import pprint

print("--- Python Environment Diagnostic ---")

print(f"\n[1] Python Executable:")
print(sys.executable)

print(f"\n[2] Python Version:")
print(sys.version)

print(f"\n[3] System Paths (sys.path):")
pprint.pprint(sys.path)

print("\n[4] Attempting to import 'marketprofile'...")
try:
    import marketprofile
    print("\n SUCCESS: 'marketprofile' was imported successfully.")
    print(f"   - Location: {marketprofile.__file__}")
except ModuleNotFoundError as e:
    print("\n FAILURE: Could not import 'marketprofile'.")
    print(f"   - Error: {e}")
except Exception as e:
    print(f"\n FAILURE: An unexpected error occurred during import.")
    print(f"   - Error: {e}")

print("\n--- End of Diagnostic ---")
