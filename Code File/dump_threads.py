import threading
import sys
import traceback

def dump_threads():
    for th in threading.enumerate():
        print(th, th.is_alive())
    print('\n*** STACKTRACE - START ***\n')
    for threadId, stack in sys._current_frames().items():
        print(f"\n# ThreadID: {threadId}")
        for filename, lineno, name, line in traceback.extract_stack(stack):
            print(f'File: "{filename}", line {lineno}, in {name}')
            if line:
                print(f'  {line.strip()}')
    print('\n*** STACKTRACE - END ***\n')

import time
time.sleep(2) # Give the background task a moment
