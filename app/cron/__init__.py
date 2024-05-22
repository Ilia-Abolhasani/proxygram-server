import threading
# global variables
# use lock for prevent simultaneously running
job_lock = threading.Lock()
