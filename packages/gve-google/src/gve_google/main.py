from gve_google import config
import os
import sys

def main(*args):
    print("main")
    print("Arguments Passed:", args)
    print('config:', config)
    print ('environment:', os.environ.get('GOOGLE_CLOUD_PROJECT'))

# Check to see if this file is the "__main__" script being executed
if __name__ == "__main__":
    # We don't care about the first unpacked value.
    # Use _ to "throw it away".
    _, *script_args = sys.argv
    main(*script_args)
